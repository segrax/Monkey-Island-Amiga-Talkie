/* Local native experiment, GPL-3.0-or-later. */
#include "native_timeline.h"

#ifdef __VBCC__
extern NvU32 nv_divmod16(NvU32 numerator, NvU32 denominator, NvU32 *remainder);
#endif

static NvU32 divide(NvU32 numerator, NvU32 denominator, NvU32 *remainder) {
	NvU32 bit = 1, quotient = 0, rest;
	if (numerator < denominator) {
		*remainder = numerator;
		return 0;
	}
	rest = numerator - denominator;
	if (rest < denominator) {
		*remainder = rest;
		return 1;
	}
	if (denominator == 65536UL) {
		*remainder = numerator & 65535UL;
		return numerator >> 16;
	}
	if (denominator == 131072UL) {
		*remainder = numerator & 131071UL;
		return numerator >> 17;
	}
	if (denominator <= 65535UL && (numerator >> 16) < denominator) {
#ifdef __VBCC__
		return nv_divmod16(numerator, denominator, remainder);
#else
		*remainder = numerator % denominator;
		return numerator / denominator;
#endif
	}
	while (denominator <= (numerator >> 1)) { denominator <<= 1; bit <<= 1; }
	while (bit) {
		if (numerator >= denominator) { numerator -= denominator; quotient |= bit; }
		denominator >>= 1; bit >>= 1;
	}
	*remainder = numerator;
	return quotient;
}

void nv_paula_advance(struct NvPaula *p, NvU32 clocks) {
	NvU32 first, steps, left;
	if (!p->dma) return;
	first = p->latched_period - p->elapsed;
	if (clocks < first) { p->elapsed += clocks; return; }
	clocks -= first;
	p->latched_period = p->period;
	steps = divide(clocks, p->period, &p->elapsed);
	/* Consume the first old-period sample separately to avoid steps+1 overflow. */
	if (++p->index == p->active_bytes) {
		p->active_address = p->reload_address;
		p->active_bytes = p->reload_bytes;
		p->index = 0;
		p->irq_pending = 1;
		++p->latches;
	}
	left = p->active_bytes - p->index;
	if (steps < left) { p->index += steps; return; }
	steps -= left;
	p->active_address = p->reload_address;
	p->active_bytes = p->reload_bytes;
	p->irq_pending = 1;
	p->latches += 1 + divide(steps, p->active_bytes, &p->index);
}
