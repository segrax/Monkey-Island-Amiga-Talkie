/* Local native experiment, GPL-3.0-or-later. */
#include <assert.h>
#include <stdio.h>
#include "paula_mix.c"
#include "native_timeline.h"
static NvU32 seed = 42;
static NvU32 draw(void) { seed ^= seed << 13; seed ^= seed >> 17; seed ^= seed << 5; return seed; }
static NvS8 sample(void *context, NvU32 address) { (void)context; return (NvS8)address; }
static void equal(const struct NvPaula *a, const struct NvPaula *b) {
	assert(a->active_address == b->active_address);
	assert(a->active_bytes == b->active_bytes && a->index == b->index);
	assert(a->elapsed == b->elapsed && a->latched_period == b->latched_period);
	assert(a->irq_pending == b->irq_pending && a->latches == b->latches);
}
int main(void) {
	struct NvPaula a, b;
	unsigned i, j;
	for (i = 0; i < 10000; ++i) {
		nv_paula_init(&a, sample, 0);
		nv_paula_pointer(&a, 0x1000);
		nv_paula_length(&a, (NvU16)(1 + draw() % 100));
		nv_paula_period(&a, (NvU16)(1 + draw() % 600));
		nv_paula_dma(&a, 1);
		b = a;
		for (j = 0; j < 20; ++j) {
			NvU16 clocks = (NvU16)(draw() % 2000);
			NvU16 period = (NvU16)(1 + draw() % 600);
			NvU16 length = (NvU16)(1 + draw() % 100);
			nv_paula_period(&a, period); nv_paula_period(&b, period);
			nv_paula_length(&a, length); nv_paula_length(&b, length);
			a.reload_address = b.reload_address = draw() & 0xfffffe;
			a.irq_pending = b.irq_pending = 0;
			(void)native_sample(&a, clocks);
			nv_paula_advance(&b, clocks);
			equal(&a, &b);
		}
	}
	puts("Analytical native timeline: 200,000 transitions match sample-stepped reference");
	return 0;
}
