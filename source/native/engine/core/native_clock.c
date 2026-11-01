/* Local native experiment, GPL-3.0-or-later. */
#include "native_clock.h"
#include <devices/timer.h>
#include <exec/execbase.h>
#include <exec/libraries.h>
#include <exec/interrupts.h>
#include <proto/exec.h>

static struct timerequest request;
static struct Library *timer_base;
static NvU16 owned;
static NvU32 frequency;
/* ReadEClock/UNIT_ECLOCK were introduced in V36. On 1.3, own a
 * CIA timer through cia.resource instead of touching an OS-owned timer.
 * The overflow interrupt extends the 16-bit hardware counter. */
static struct Library *cia_resource;
static volatile NvU8 *cia_low, *cia_high, *cia_control;
static volatile NvU32 cia_epoch;
static NvU16 cia_bit;
static struct Interrupt cia_interrupt;
static void *cia_add(__reg("a6") struct Library *base,
 __reg("d0") NvU32 bit, __reg("a1") struct Interrupt *interrupt) = "\tjsr\t-6(a6)";
static void cia_remove(__reg("a6") struct Library *base,
 __reg("d0") NvU32 bit, __reg("a1") struct Interrupt *interrupt) = "\tjsr\t-12(a6)";
static NvU32 cia_set(__reg("a6") struct Library *base,
 __reg("d0") NvU32 mask) = "\tjsr\t-24(a6)";
static NvU32 cia_overflow(__reg("a1") volatile NvU32 *epoch) {
 *epoch += 65536UL;
 return 0;
}
static NvU32 read_clock(__reg("a6") struct Library *base,
 __reg("a0") struct EClockVal *value) = "\tjsr\t-60(a6)";
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
 unsigned chip, timer;
 NvU16 prior = master_state();
 cia_interrupt.is_Node.ln_Type = NT_INTERRUPT;
 cia_interrupt.is_Node.ln_Name = "Monkey Talkie clock";
 cia_interrupt.is_Data = (void *)&cia_epoch;
 cia_interrupt.is_Code = (void (*)())cia_overflow;
 for (chip = 0; chip < 2; ++chip) {
  struct Library *resource = OpenResource(chip ? "ciab.resource" : "ciaa.resource");
  if (!resource) continue;
  /* Prefer timer B, but never assume any particular timer is available. */
  for (timer = 0; timer < 2; ++timer) {
   NvU16 bit = timer ? 0 : 1;
   NvU32 address = chip ? 0xbfd000UL : 0xbfe001UL;
   Disable();
   if (!cia_add(resource, bit, &cia_interrupt)) {
    cia_resource = resource; cia_bit = bit; cia_epoch = 0;
    cia_low = (volatile NvU8 *)(address + (bit ? 0x600 : 0x400));
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
static NvU32 cia_now(void) {
 NvU16 before, after, pending, prior = master_state();
 NvU32 result;
 Disable();
 do {
  before = cia_counter();
  pending = (NvU16)cia_set(cia_resource, 1UL << cia_bit);
  if (pending & (1U << cia_bit)) cia_epoch += 65536UL;
  after = cia_counter();
  /* An underflow after SetICR must be consumed before publishing time. */
 } while (after > before);
 result = cia_epoch + (65535UL - after);
 Enable(); if (!prior) restore_master_off();
 return result;
}

static NvU32 read_preserving_master(struct EClockVal *value) {
 NvU16 prior = master_state();
 NvU32 result = read_clock(timer_base, value);
 if (!prior) restore_master_off();
 return result;
}

int nv_clock_start(void) {
 struct EClockVal value;
 if (owned) return 1;
 if (SysBase->LibNode.lib_Version < 36) return cia_start();
 request.tr_node.io_Message.mn_Length = sizeof(request);
 if (OpenDevice(TIMERNAME, UNIT_ECLOCK, (struct IORequest *)&request, 0)) return 0;
 timer_base = (struct Library *)request.tr_node.io_Device;
 if (!timer_base || timer_base->lib_Version < 36) {
  CloseDevice((struct IORequest *)&request);
  timer_base = 0;
  return 0;
 }
 frequency = read_preserving_master(&value);
 if (frequency < 700000UL || frequency > 720000UL ||
     frequency != SysBase->ex_EClockFrequency) {
  CloseDevice((struct IORequest *)&request);
  timer_base = 0;
  frequency = 0;
  return 0;
 }
 owned = 1;
 return 1;
}
NvU32 nv_clock_now(void) {
 struct EClockVal value;
 if (!owned) return 0;
 if (owned == 2) return cia_now();
 read_preserving_master(&value);
 return value.ev_lo;
}
void nv_clock_stop(void) {
 if (!owned) return;
 if (owned == 2) {
  NvU16 prior = master_state();
  Disable();
  *cia_control &= 0xfe;
  cia_remove(cia_resource, cia_bit, &cia_interrupt);
  cia_set(cia_resource, 1UL << cia_bit);
  owned = 0; cia_resource = 0;
  Enable(); if (!prior) restore_master_off();
  return;
 }
 owned = 0;
 CloseDevice((struct IORequest *)&request);
 timer_base = 0;
 frequency = 0;
}
