#include "art_manager.h"
#ifdef NV_ART_NATIVE_CHECKSUM
extern int nv_art_indices(const NvU8 *indices, NvU32 rows, NvU32 maximum);
#endif

static NvU16 word(const NvU8 *p) {
	return ((NvU16)p[0] << 8) | p[1];
}

static NvU32 number(const NvU8 *p) {
	return ((NvU32)word(p) << 16) | word(p + 2);
}

static int span(NvU32 offset, NvU32 length, NvU32 bytes) {
	return !(offset & 1) && offset >= 64 && offset <= bytes && length <= bytes - offset;
}

static int equal(const NvU8 *a, const NvU8 *b, NvU32 bytes) {
	while (bytes--)
		if (*a++ != *b++)
			return 0;
	return 1;
}

#ifndef NV_ART_NATIVE_CHECKSUM
NvU32 nv_art_checksum(const NvU8 *data, NvU32 bytes) {
	NvU32 a = 65535, sum = 65535, count;
	if (bytes & 1)
		return 0;
	bytes /= 2;
	while (bytes) {
		count = bytes > 359 ? 359 : bytes;
		bytes -= count;
		while (count--) {
			a += word(data);
			sum += a;
			data += 2;
		}
		a = (a & 65535) + (a >> 16);
		sum = (sum & 65535) + (sum >> 16);
	}
	a = (a & 65535) + (a >> 16);
	sum = (sum & 65535) + (sum >> 16);
	return (sum << 16) | a;
}
#endif

int nv_art_validate(const NvU8 *data, NvU32 bytes, struct NvArtImage *image) {
	NvU32 dictionary, indices, source, strips, rows, count, i, j, end, masks;
	NvU16 width, height, columns, flags, version;
	struct NvArtImage result;
	if (!data || !image || bytes < 64 || bytes > NV_ART_CAPACITY || (bytes & 1) ||
	    !equal(data, (const NvU8 *)"NPD1", 4) || (word(data + 4) != 1 && word(data + 4) != 2) ||
	    word(data + 6) != 64 || number(data + 8) != bytes || word(data + 18) != 14)
		return 0;
	version = word(data + 4);
	width = word(data + 12);
	height = word(data + 14);
	count = word(data + 16);
	columns = word(data + 44);
	flags = word(data + 46);
	if (!width || width > 320 || (width & 7) || !height || height > 200 ||
	    !count || count > 2340 || columns != width / 8 || (flags & ~3))
		return 0;
	rows = (NvU32)columns * height;
	if (number(data + 20) != rows)
		return 0;
	dictionary = number(data + 24);
	indices = number(data + 28);
	source = number(data + 32);
	strips = number(data + 40);
	result.source_bytes = number(data + 36);
	/* Require the builder's single canonical packing: no overlapping regions. */
	if (strips != 64 || dictionary != strips + columns * 8UL ||
	    indices != dictionary + count * 14UL || source != indices + rows * 2 + version - 1 ||
	    !span(dictionary, count * 14UL, bytes) || !span(indices, rows * 2, bytes) ||
	    source > bytes || result.source_bytes > bytes - source ||
	    (version == 2 && data[source - 1]))
		return 0;
	end = source + result.source_bytes;
	masks = (end + 1) & ~1UL;
	j = (NvU32)columns * ((height + 7) / 8);
	if (flags != 3 || end > bytes || masks > bytes || j > bytes - masks ||
	    ((masks + j + 1) & ~1UL) != bytes ||
	    ((end & 1) && data[end]) || ((j & 1) && data[masks + j]))
		return 0;
#ifdef NV_ART_NATIVE_CHECKSUM
	if (!nv_art_indices(data + indices, rows, count * 14UL - 14))
		return 0;
#else
	for (i = 0; i < rows; ++i) {
		j = word(data + indices + i * 2);
		if ((j & 1) || j > count * 14UL - 14)
			return 0;
	}
#endif
	for (i = 0; i < columns; ++i) {
		const NvU8 *descriptor = data + strips + i * 8;
		NvU32 offset = number(descriptor);
		NvU32 length = word(descriptor + 4);
		if (!length || offset >= result.source_bytes || length > result.source_bytes - offset ||
		    (word(descriptor + 6) & ~128))
			return 0;
	}
#ifdef NV_ART_SEMANTIC_TEST
	for (i = 0; i < 16; ++i)
		if (data[48 + i] > 31)
			return 0;
	for (i = 0; i < rows; ++i) {
		j = word(data + indices + i * 2);
		if (j >= count * 14UL || j % 14)
			return 0;
	}
	for (i = 0; i < count; ++i) {
		const NvU8 *record = data + dictionary + i * 14;
		NvU8 planes[5];
		for (j = 0; j < 5; ++j)
			planes[j] = 0;
		for (j = 0; j < 8; ++j) {
			NvU8 pixel = record[j];
			if (pixel > 31)
				return 0;
			planes[0] = (planes[0] << 1) | (pixel & 1);
			planes[1] = (planes[1] << 1) | ((pixel >> 1) & 1);
			planes[2] = (planes[2] << 1) | ((pixel >> 3) & 1);
			planes[3] = (planes[3] << 1) | ((pixel >> 4) & 1);
			planes[4] = (planes[4] << 1) | ((pixel >> 2) & 1);
		}
		if (!equal(record + 8, planes, 5) || record[13])
			return 0;
	}
#endif
	result.dictionary = data + dictionary;
	result.indices = data + indices;
	result.source = data + source;
	result.strips = data + strips;
	result.dependencies = data + masks;
	result.palette = data + 48;
	result.bytes = bytes;
	result.dictionary_bytes = count * 14UL;
	result.width = width;
	result.height = height;
	result.columns = columns;
	result.flags = flags;
	/* Do not publish any pointer until the entire payload has passed. */
#ifdef NV_ART_SEMANTIC_TEST
	if (!nv_art_verify_decode(&result))
		return 0;
#endif
	*image = result;
	return 1;
}

#ifdef NV_ART_SEMANTIC_TEST
int nv_art_verify_decode(const struct NvArtImage *image) {
	NvU8 history[200];
	NvU16 strip, x, y, count, mode, a, b, token, dependent;
	NvU32 start, length, p, i, offset;
	NvU16 mask_bytes = (image->height + 7) / 8;
	const NvU8 *source = image->source;
	for (y = 0; y < image->height; ++y)
		history[y] = image->palette[0];
	if (image->source_bytes < 12UL + image->columns * 4UL)
		return 0;
	for (strip = 0; strip < image->columns; ++strip) {
		const NvU8 *descriptor = image->strips + strip * 8;
		const NvU8 *mask = image->dependencies + strip * mask_bytes;
		start = number(descriptor);
		length = word(descriptor + 4);
		if (!length || start >= image->source_bytes || length > image->source_bytes - start ||
		    source[start] != 10 || (word(descriptor + 6) & ~128))
			return 0;
		/* The little-endian OI strip table must select this exact prefix. */
		i = 12UL + strip * 4UL;
		offset = source[i] | ((NvU32)source[i + 1] << 8) |
		         ((NvU32)source[i + 2] << 16) | ((NvU32)source[i + 3] << 24);
		if (start < 8 || offset != start - 8)
			return 0;
		p = start + 1;
		count = mode = a = b = dependent = 0;
		for (x = 0; x < 8; ++x) {
			for (y = 0; y < image->height; ++y) {
				NvU8 color, expected;
				const NvU8 *record;
				if (!count) {
					if (p >= start + length)
						return 0;
					token = source[p++];
					if (token < 128) {
						mode = 0; a = token & 15; count = token >> 4;
					} else if (token < 192) {
						mode = 1; count = token & 63;
					} else {
						if (p >= start + length)
							return 0;
						mode = 2; count = token & 63;
						a = source[p] >> 4; b = source[p++] & 15;
					}
					if (!count) {
						if (p >= start + length)
							return 0;
						count = source[p++];
						if (!count)
						count = 256;
					}
				}
				color = mode == 1 ? history[y] : image->palette[a];
				if (!x) {
					expected = (mask[y / 8] >> (7 - (y & 7))) & 1;
					if (expected != (mode == 1))
						return 0;
					dependent |= expected;
				}
				if (mode == 2) {
					token = a; a = b; b = token;
				}
				history[y] = color;
				i = ((NvU32)strip * image->height + y) * 2;
				record = image->dictionary + word(image->indices + i);
				if (record[x] != color)
					return 0;
				--count;
			}
		}
		if (count || p != start + length || !!(word(descriptor + 6) & 128) != !!dependent)
			return 0;
		if ((image->height & 7) && (mask[mask_bytes - 1] & ((1 << (8 - (image->height & 7))) - 1)))
			return 0;
	}
	return 1;
}
#endif
