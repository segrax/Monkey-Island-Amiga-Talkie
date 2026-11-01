/* Local native experiment, GPL-3.0-or-later. */
#include "native_clock.h"
#include "native_driver.h"
#include <devices/timer.h>
#include <exec/execbase.h>
#include <exec/libraries.h>
#include <exec/interrupts.h>
#include <proto/exec.h>

static NvU16 owned;
static struct timerequest timer_request;
static struct Library *timer_base;
extern void nv_music_tick(NvU8 *);
/* V39 timer.device owns CIAB-B and reprograms it for one-shot requests.
 * The original TFMX player takes that timer without consulting cia.resource.
 * On V39+, give TFMX our reserved CIAA timer and leave CIAB to the OS;
 * ReadEClock is then usable without the player corrupting its hardware. */
struct MusicPatch { NvU16 offset, size; NvU8 saved[8]; };
static struct MusicPatch music_patches[] = {
 {0x922,4},{0x92a,4},
 {0x116e,4},{0x1176,4},{0x11a8,4},{0x11b0,4},
 {0x15d2,4},{0x15da,4},{0x15f6,4},{0x15fe,4},
 {0x161c,2},{0x161e,4},{0x1608,8},{0x1614,6},{0x1622,8},{0x162a,8}
};
static NvU8 *music_code;
static NvU32 read_clock(__reg("a6") struct Library *base,
 __reg("a0") struct EClockVal *value) = "\tjsr\t-60(a6)";
/* Older systems retain the owned CIA clock used by the working 1.3/2.x path.
 * The original player replaces the CIAB level-6 handler and acknowledges the
 * entire CIAB ICR. Use CIAA only: no CIAB timer can provide a reliable overflow
 * callback while that handler is installed. On 3.x, the reserved timer drives
 * music instead, and the player leaves the OS clock and level-6 vector alone.
 * The older backend reconciles counter snapshots and callback epochs even
 * when the audio IRQ preempts CIA dispatch. No CPU-specific correction. */
static struct Library *cia_resource;
static volatile NvU8 *cia_low, *cia_high, *cia_control;
struct CiaCount { NvU32 epoch, ticks; NvU16 previous; };
static struct CiaCount cia_count;
static NvU16 cia_bit;
static struct Interrupt cia_interrupt;
volatile NvU32 nv_clock_hardware;
static void *cia_add(__reg("a6") struct Library *base,
 __reg("d0") NvU32 bit, __reg("a1") struct Interrupt *interrupt) = "\tjsr\t-6(a6)";
static void cia_remove(__reg("a6") struct Library *base,
 __reg("d0") NvU32 bit, __reg("a1") struct Interrupt *interrupt) = "\tjsr\t-12(a6)";
static NvU32 cia_set(__reg("a6") struct Library *base,
 __reg("d0") NvU32 mask) = "\tjsr\t-24(a6)";
static NvU32 cia_sample(struct CiaCount *,NvU16);
static NvU32 cia_overflow(__reg("a1") struct CiaCount *count) {
 if (owned == 3) nv_music_tick(music_code);
 else cia_sample(count,1);
 return 0;
}
static NvU16 master_state(void) = "\tmove.w\t$dff01c,d0\n\tandi.w\t#$4000,d0";
static void restore_master_off(void) = "\tmove.w\t#$4000,$dff09a";

static NvU32 system_now(struct EClockVal *value) {
 NvU16 prior = master_state();
 NvU32 frequency = read_clock(timer_base,value);
 if (!prior) restore_master_off();
 return frequency;
}
static void music_restore(void) {
 unsigned i,j;
 if (!music_code) return;
 for(i=0;i<sizeof(music_patches)/sizeof(music_patches[0]);++i)
  for(j=0;j<music_patches[i].size;++j)
   music_code[music_patches[i].offset+j]=music_patches[i].saved[j];
 music_code=0;
 CacheClearU();
}
static int music_redirect(void) {
 unsigned i,j;
 NvU8 *code=nv_control.game_code;
 if (!code) return 0;
 /* Refuse an unexpected player layout before touching executable code. */
 for(i=0;i<10;++i)
  if (*(NvU32 *)(code+music_patches[i].offset)!=(i&1?0xbfd600UL:0xbfd700UL)) return 0;
 if (*(NvU32 *)(code+0x161e)!=0xbfdf00UL ||
     *(NvU32 *)(code+0x1608)!=0x2d790000UL ||
     *(NvU32 *)(code+0x1614)!=0x23ce0000UL ||
     *(NvU32 *)(code+0x1622)!=0x13fc0082UL ||
     *(NvU32 *)(code+0x162a)!=0x33fca000UL) return 0;
 music_code=code;
 for(i=0;i<sizeof(music_patches)/sizeof(music_patches[0]);++i)
  for(j=0;j<music_patches[i].size;++j)
   music_patches[i].saved[j]=code[music_patches[i].offset+j];
 for(i=0;i<10;++i)
  *(NvU32 *)(code+music_patches[i].offset)=(NvU32)(i&1?cia_low:cia_high);
 *(NvU16 *)(code+0x161c)=0x11|(*cia_control&(cia_bit?0x80:0xc0));
 *(NvU32 *)(code+0x161e)=(NvU32)cia_control;
 /* cia.resource already installed and enabled our callback. Do not replace
  * the OS level-6 vector, clear its pending flags, or change its mask. */
 for(i=12;i<sizeof(music_patches)/sizeof(music_patches[0]);++i)
  for(j=0;j<music_patches[i].size;j+=2)
   *(NvU16 *)(code+music_patches[i].offset+j)=0x4e71;
 CacheClearU();
 return 1;
}

static NvU16 cia_counter(void) {
 NvU16 first, low, last;
 do {
  first = *cia_high;
  low = *cia_low;
  last = *cia_high;
 } while (first != last);
 return (NvU16)((last << 8) | low);
}
static int cia_start(void) {
 unsigned timer;
 struct Library *resource;
 NvU16 prior = master_state();
 cia_interrupt.is_Node.ln_Type = NT_INTERRUPT;
 cia_interrupt.is_Node.ln_Name = "Monkey Talkie clock";
 cia_interrupt.is_Data = (void *)&cia_count;
 cia_interrupt.is_Code = (void (*)())cia_overflow;
 resource = OpenResource("ciaa.resource");
 if (resource) {
  /* Prefer timer B, but never assume any particular timer is available. */
  for (timer = 0; timer < 2; ++timer) {
   NvU16 bit = timer ? 0 : 1;
   NvU32 address = 0xbfe001UL;
   Disable();
   if (!cia_add(resource, bit, &cia_interrupt)) {
    cia_resource = resource; cia_bit = bit;
    cia_count.epoch = cia_count.ticks = 0; cia_count.previous = 65535;
    cia_low = (volatile NvU8 *)(address + (bit ? 0x600 : 0x400));
    nv_clock_hardware = (NvU32)cia_low;
    cia_high = cia_low + 0x100;
    cia_control = (volatile NvU8 *)(address + (bit ? 0xf00 : 0xe00));
    /* Preserve unrelated serial/TOD control bits; disable PB output,
     * select continuous E-clock counting, load $ffff, then start. */
    *cia_control &= bit ? 0x80 : 0xc0;
    *cia_low = 0xff; *cia_high = 0xff;
    cia_set(resource, 1UL << bit);
    *cia_control |= 0x11;
    owned = 2;
    Enable(); if (!prior) restore_master_off();
    return 1;
   }
   Enable(); if (!prior) restore_master_off();
  }
 }
 return 0;
}
static NvU32 cia_sample(struct CiaCount *count,NvU16 overflow) {
 NvU16 counter, prior = master_state();
 NvU32 result, dispatched;
 Disable();
 if (overflow) count->epoch += 65536UL;
 counter = cia_counter();
 /* The audio IRQ can preempt CIA resource dispatch after its pending flag
  * was consumed but before our callback runs. Counter deltas still observe
  * that wrap. Callback epochs also retain whole periods during idle polling
  * gaps. Reconcile both observations without clearing resource pending bits
  * or counting a deferred callback's already-observed wrap twice.
  * The modular comparison is between adjacent observations, not absolute
  * uptime, so it also works across the 32-bit clock rollover. */
 result = count->ticks + (NvU16)(count->previous - counter);
 dispatched = count->epoch + (65535UL - counter);
 if ((NvS32)(dispatched - result) > 0) result = dispatched;
 count->ticks = result; count->previous = counter;
 Enable(); if (!prior) restore_master_off();
 return result;
}

int nv_clock_start(void) {
 struct EClockVal value;
 if (owned) return 1;
 /* ex_EClockFrequency exists from V36. Keep the existing frequency range check. */
 if (SysBase->LibNode.lib_Version >= 36 &&
     (SysBase->ex_EClockFrequency < 700000UL || SysBase->ex_EClockFrequency > 720000UL)) return 0;
 if (SysBase->LibNode.lib_Version < 39) return cia_start();
 timer_request.tr_node.io_Message.mn_Length=sizeof(timer_request);
 if (OpenDevice(TIMERNAME,UNIT_ECLOCK,(struct IORequest *)&timer_request,0)) return 0;
 timer_base=(struct Library *)timer_request.tr_node.io_Device;
 if (!timer_base || timer_base->lib_Version<36 ||
     system_now(&value)!=SysBase->ex_EClockFrequency) goto timer_fail;
 if (!cia_start()) goto timer_fail;
 if (!music_redirect()) { nv_clock_stop(); goto timer_fail; }
 owned=3;
 return 1;
timer_fail:
 CloseDevice((struct IORequest *)&timer_request);timer_base=0;
 return 0;
}
NvU32 nv_clock_now(void) {
 struct EClockVal value;
 if (!owned) return 0;
 if (owned==3) { system_now(&value);return value.ev_lo; }
 return cia_sample(&cia_count,0);
}
void nv_clock_stop(void) {
 NvU16 prior,system_clock;
 if (!owned) return;
 prior = master_state();
 Disable();
 system_clock=owned==3;
 *cia_control &= 0xfe;
 cia_remove(cia_resource, cia_bit, &cia_interrupt);
 cia_set(cia_resource, 1UL << cia_bit);
 owned = 0; cia_resource = 0; nv_clock_hardware = 0;
 if (system_clock) music_restore();
 Enable(); if (!prior) restore_master_off();
 if (system_clock) { CloseDevice((struct IORequest *)&timer_request);timer_base=0; }
}
