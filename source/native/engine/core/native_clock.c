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
 * Our snapshot consumes only our owned timer's pending wrap, even while the
 * game masks interrupts. No shared OS timer or CPU-specific correction. */
static struct Library *cia_resource;
static volatile NvU8 *cia_low, *cia_high, *cia_control;
static volatile NvU32 cia_epoch;
static NvU16 cia_bit;
static struct Interrupt cia_interrupt;
volatile NvU32 nv_clock_hardware;
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
 cia_interrupt.is_Data = (void *)&cia_epoch;
 cia_interrupt.is_Code = (void (*)())cia_overflow;
 resource = OpenResource("ciaa.resource");
 if (resource) {
  /* Prefer timer B, but never assume any particular timer is available. */
  for (timer = 0; timer < 2; ++timer) {
   NvU16 bit = timer ? 0 : 1;
   NvU32 address = 0xbfe001UL;
   Disable();
   if (!cia_add(resource, bit, &cia_interrupt)) {
    cia_resource = resource; cia_bit = bit; cia_epoch = 0;
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

int nv_clock_start(void) {
 if (owned) return 1;
 /* ex_EClockFrequency exists from V36. Keep the existing frequency range check. */
 if (SysBase->LibNode.lib_Version >= 36 &&
     (SysBase->ex_EClockFrequency < 700000UL || SysBase->ex_EClockFrequency > 720000UL)) return 0;
 return cia_start();
}
NvU32 nv_clock_now(void) {
 if (!owned) return 0;
 return cia_now();
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
