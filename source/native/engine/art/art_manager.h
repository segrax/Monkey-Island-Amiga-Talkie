#ifndef NV_ART_MANAGER_H
#define NV_ART_MANAGER_H
#include "native_voice.h"

#define NV_ART_CAPACITY 32768UL

struct NvArtImage {
	const NvU8 *dictionary, *indices, *source, *strips, *dependencies, *palette;
	NvU32 bytes, source_bytes, dictionary_bytes;
	NvU16 width, height, columns, flags;
};

/* Assembly ABI: six pointers followed by two words (28 bytes on Amiga). */
struct NvArtDecode {
	const NvU8 *dictionary, *indices, *codec, *end, *dependencies, *palette;
	NvU16 height, reserved;
};

int nv_art_validate(const NvU8 *data, NvU32 bytes, struct NvArtImage *image);
int nv_art_verify_decode(const struct NvArtImage *image);
NvU32 nv_art_checksum(const NvU8 *data, NvU32 bytes);
#endif
