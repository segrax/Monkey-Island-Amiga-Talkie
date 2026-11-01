/* Local native experiment, GPL-3.0-or-later. */
#ifndef NATIVE_TIMELINE_H
#define NATIVE_TIMELINE_H
#include "paula_mix.h"
/* Advance muted native DMA without reading or rendering any sample bytes. */
void nv_paula_advance(struct NvPaula *p, NvU32 clocks);
#endif
