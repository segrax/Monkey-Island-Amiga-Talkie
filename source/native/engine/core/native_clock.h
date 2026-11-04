/* Local native experiment, GPL-3.0-or-later. */
#ifndef NATIVE_DEDICATED_CLOCK_H
#define NATIVE_DEDICATED_CLOCK_H
#include "native_voice.h"
int nv_clock_start(void);
NvU32 nv_clock_now(void);
/* Caller holds Exec Disable() or masks CPU interrupts at IPL7. */
NvU32 nv_clock_now_locked(void);
void nv_clock_stop(void);
#endif

