/* Local native experiment, GPL-3.0-or-later. */
#include "native_clock.h"
#include <devices/timer.h>
#include <exec/execbase.h>
#include <exec/libraries.h>
#include <proto/exec.h>

static struct timerequest request;
static struct Library *timer_base;
static NvU16 owned;
static NvU32 frequency;
static NvU32 read_clock(__reg("a6") struct Library *base,
 __reg("a0") struct EClockVal *value) = "\tjsr\t-60(a6)";
static NvU16 master_state(void) = "\tmove.w\t$dff01c,d0\n\tandi.w\t#$4000,d0";
static void restore_master_off(void) = "\tmove.w\t#$4000,$dff09a";

static NvU32 read_preserving_master(struct EClockVal *value) {
 NvU16 prior = master_state();
 NvU32 result = read_clock(timer_base, value);
 if (!prior) restore_master_off();
 return result;
}

int nv_clock_start(void) {
 struct EClockVal value;
 if (owned) return 1;
 if (SysBase->LibNode.lib_Version < 36) return 0;
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
 read_preserving_master(&value);
 return value.ev_lo;
}
void nv_clock_stop(void) {
 if (!owned) return;
 owned = 0;
 CloseDevice((struct IORequest *)&request);
 timer_base = 0;
 frequency = 0;
}
