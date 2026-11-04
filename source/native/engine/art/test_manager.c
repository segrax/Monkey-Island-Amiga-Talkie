#include "art_manager.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static NvU32 be32(const NvU8 *p) {
	return ((NvU32)p[0] << 24) | ((NvU32)p[1] << 16) | ((NvU32)p[2] << 8) | p[3];
}

static NvU32 reference(const NvU8 *p, NvU32 bytes) {
	unsigned long long a = 65535, b = 65535;
	while (bytes) {
		a += (p[0] << 8) | p[1];
		b += a;
		p += 2;
		bytes -= 2;
	}
	a %= 65535;
	b %= 65535;
	return ((NvU32)(b ? b : 65535) << 16) | (NvU32)(a ? a : 65535);
}

int main(int argc, char **argv) {
	FILE *file;
	NvU8 *data, *copy;
	long bytes;
	NvU32 i, n, count, mutations = 0;
	struct NvArtImage image, pristine;
	if (argc != 2 || !(file = fopen(argv[1], "rb")))
		return 2;
	fseek(file, 0, SEEK_END);
	bytes = ftell(file);
	fseek(file, 0, SEEK_SET);
	data = malloc(bytes);
	copy = malloc(NV_ART_CAPACITY);
	if (!data || !copy || fread(data, 1, bytes, file) != (size_t)bytes)
		return 3;
	fclose(file);
	if (bytes < 32 || memcmp(data, "NVPART01", 8) || be32(data + 24) != (NvU32)bytes)
		return 4;
	count = be32(data + 12);
	for (i = 0; i < count; ++i) {
		const NvU8 *entry = data + 32 + i * 24;
		NvU32 offset = be32(entry + 4), length = be32(entry + 8);
		NvU32 checksum = be32(entry + 20);
		if (offset > (NvU32)bytes || length > (NvU32)bytes - offset || length > NV_ART_CAPACITY ||
		    !nv_art_validate(data + offset, length, &image) ||
		    nv_art_checksum(data + offset, length) != reference(data + offset, length) ||
		    (checksum && checksum != nv_art_checksum(data + offset, length))) {
			fprintf(stderr, "entry %u failed\n", i);
			return 5;
		}
		/* Every single-byte mutation changes the integrity check. */
		memcpy(copy, data + offset, length);
		for (n = 0; n < length; ++n) {
			copy[n] ^= 1;
			if (nv_art_checksum(copy, length) == nv_art_checksum(data + offset, length))
				return 6;
			copy[n] ^= 1;
			++mutations;
		}
		/* Structural failures cannot partially publish pointer fields. */
		memset(&pristine, 0xA5, sizeof(pristine));
		image = pristine;
		copy[24] = 0xFF;
		if (nv_art_validate(copy, length, &image) || memcmp(&image, &pristine, sizeof(image)))
			return 7;
	}
	memset(copy, 0, NV_ART_CAPACITY);
	if (nv_art_checksum(copy, 720) != 0xFFFFFFFFUL)
		return 8;
	for (i = 0; i < NV_ART_CAPACITY; ++i)
		copy[i] = (NvU8)((i * 37 + (i >> 5)) ^ 0xA7);
	{
		static const NvU32 words[] = {1, 358, 359, 360, 1024, 16384};
		for (i = 0; i < sizeof(words) / sizeof(words[0]); ++i)
			if (nv_art_checksum(copy, words[i] * 2) != reference(copy, words[i] * 2))
				return 9;
	}
	printf("PASS entries=%u byte_mutations=%u checksum_boundary_cases=7\n", count, mutations);
	free(copy);
	free(data);
	return 0;
}
