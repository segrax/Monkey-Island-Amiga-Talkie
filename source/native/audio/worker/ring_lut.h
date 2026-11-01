/* Local native experiment, GPL-3.0-or-later. */
#ifndef NATIVE_RING_LUT_H
#define NATIVE_RING_LUT_H
void native_ring_lut_copy(signed char *ring, unsigned long index,
	const unsigned char *source, unsigned long count, const signed char *table);
#endif
