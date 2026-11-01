/* Local native experiment, GPL-3.0-or-later. */
#include "ring_lut.h"

extern void native_lut_copy(signed char *to, const unsigned char *from,
	unsigned long count, const signed char *table);

void native_ring_lut_copy(signed char *ring, unsigned long index,
	const unsigned char *source, unsigned long count, const signed char *table) {
	unsigned long first;
	if (!count || count > 16384)
		return;
	index &= 16383;
	first = 16384 - index;
	if (first > count)
		first = count;
	native_lut_copy(ring + index, source, first, table);
	if (count > first)
		native_lut_copy(ring, source + first, count - first, table);
}
