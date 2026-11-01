/* Local native experiment, GPL-3.0-or-later. */
#include "native_clock.h"
#include <exec/execbase.h>
#include <exec/libraries.h>
#include <exec/interrupts.h>
#include <proto/exec.h>

static NvU16 owned;
/* Own a CIA timer through cia.resource on every supported OS version.
 * Shared ReadEClock readings rolled backwards during the game's raw interrupt
 * masking in the 68000/2.04 integration run; the exact OS race is unresolved.
 * The original game replaces the CIAB level-6 handler and acknowledges the
 * entire CIAB ICR. Use CIAA only: no CIAB timer can provide a reliable overflow
 * callback while that handler is installed. Never take the game's CIAB timer.
 * Counter snapshots and callback epochs are reconciled even when the audio
 * IRQ preempts CIA dispatch. No shared OS timer or CPU-specific correction. */
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
 cia_sample(count,1);
 return 0;
}
static NvU16 master_state(void) = "\tmove.w\t$dff01c,d0\n\tandi.w\t#$4000,d0";
static void restore_master_off(void) = "\tmove.w\t#$4000,$dff09a";

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
 if (owned) return 1;
 /* ex_EClockFrequency exists from V36. Keep the existing frequency range check. */
 if (SysBase->LibNode.lib_Version >= 36 &&
     (SysBase->ex_EClockFrequency < 700000UL || SysBase->ex_EClockFrequency > 720000UL)) return 0;
 return cia_start();
}
NvU32 nv_clock_now(void) {
 if (!owned) return 0;
 return cia_sample(&cia_count,0);
}
void nv_clock_stop(void) {
 NvU16 prior;
 if (!owned) return;
 prior = master_state();
 Disable();
 *cia_control &= 0xfe;
 cia_remove(cia_resource, cia_bit, &cia_interrupt);
 cia_set(cia_resource, 1UL << cia_bit);
 owned = 0; cia_resource = 0; nv_clock_hardware = 0;
 Enable(); if (!prior) restore_master_off();
}
