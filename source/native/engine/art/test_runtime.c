#include "art_runtime.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static NvU8 *contents;
static NvU32 size, allocations, frees, closes, reads;
static int allocation_failure, missing;
NvU8 *nv_art_alloc(NvU32 bytes) {
	++allocations;
	return allocation_failure ? 0 : malloc(bytes);
}
void nv_art_free(NvU8 *memory, NvU32 bytes) {
	(void)bytes;
	++frees;
	free(memory);
}
NvU32 nv_art_file_open(void) {
	return missing ? 0 : 1;
}
void nv_art_file_close(NvU32 file) {
	(void)file;
	++closes;
}
NvS32 nv_art_read_at(NvU32 file, NvU32 offset, void *buffer, NvU32 bytes) {
	++reads;
	if (file != 1 || offset > size || bytes > size - offset)
		return -1;
	memcpy(buffer, contents + offset, bytes);
	return (NvS32)bytes;
}
static NvU32 be32(const NvU8 *p) {
	return ((NvU32)p[0] << 24) | ((NvU32)p[1] << 16) | ((NvU32)p[2] << 8) | p[3];
}
#define REQUIRE(test) do { if (!(test)) { fprintf(stderr, "line %d\n", __LINE__); return 1; } } while (0)
int main(int argc, char **argv) {
	FILE *input;
	NvU8 *pixels, *original;
	NvU32 saved, before, offset;
	NvU16 prefix, rows;
	unsigned i;
	if (argc != 2 || !(input = fopen(argv[1], "rb")))
		return 2;
	fseek(input, 0, SEEK_END);
	size = (NvU32)ftell(input);
	fseek(input, 0, SEEK_SET);
	contents = malloc(size);
	REQUIRE(contents && fread(contents, 1, size, input) == size);
	fclose(input);
	missing = 1;
	nv_art_start();
	REQUIRE(!nv_art.enabled && !nv_art.arena && !allocations && !reads);
	missing = 0;
	allocation_failure = 1;
	nv_art_start();
	REQUIRE(!nv_art.enabled && !nv_art.arena && allocations == 1 && !frees);
	allocation_failure = 0;
	nv_art_start();
	REQUIRE(nv_art.enabled && nv_art.arena && allocations == 3);
	nv_art_start();
	REQUIRE(allocations == 3);
	REQUIRE(nv_art_object(10, 113, 1) && nv_art.loads == 1);
	REQUIRE(nv_art.image.width == 216 && nv_art.image.height == 120);
	before = reads;
	REQUIRE(nv_art_object(10, 113, 1) && reads == before);
	pixels = malloc(64000 + 24 * 320);
	original = malloc(nv_art.image.source_bytes);
	REQUIRE(pixels && original);
	pixels += 24 * 320;
	memcpy(original, nv_art.image.source, nv_art.image.source_bytes);
	offset = be32(nv_art.image.strips);
	REQUIRE(!nv_art_bind(40, pixels, original + offset, original, nv_art.image.source_bytes, 0));
	REQUIRE(!nv_art_bind(0, pixels, original + offset + 1, original, nv_art.image.source_bytes, 0));
	REQUIRE(nv_art_bind(0, pixels, original + offset, original, nv_art.image.source_bytes, 0));
	for (i = 0; i < 120; ++i)
		REQUIRE(nv_art_c2p_indices(0, pixels + i * 320, 120 - i) == nv_art.image.indices + i * 2);
	REQUIRE(!nv_art_c2p_indices(0, pixels + 1, 1));
	REQUIRE(!nv_art_c2p_indices(0, pixels, 121));
	REQUIRE(!nv_art_c2p_indices(0, pixels, 0));
	REQUIRE(nv_art_c2p_span(0, pixels - 24 * 320, 144, &prefix, &rows) == nv_art.image.indices);
	REQUIRE(prefix == 24 && rows == 120);
	REQUIRE(nv_art_c2p_span(0, pixels - 24 * 320, 200, &prefix, &rows) == nv_art.image.indices);
	REQUIRE(prefix == 24 && rows == 120);
	REQUIRE(nv_art_c2p_span(0, pixels + 119 * 320, 81, &prefix, &rows) == nv_art.image.indices + 238);
	REQUIRE(prefix == 0 && rows == 1);
	REQUIRE(!nv_art_c2p_span(0, pixels - 24 * 320, 24, &prefix, &rows));
	REQUIRE(!nv_art_c2p_span(0, pixels - 1, 144, &prefix, &rows));
	REQUIRE(!nv_art_object(10, 65534, 2));
	before = reads;
	REQUIRE(!nv_art_object(10, 65534, 2) && reads == before);
	/* A smaller overlay leaves the useful dictionary and its bindings live. */
	REQUIRE(!nv_art_object(10, 117, 3) && nv_art.object == 113);
	REQUIRE(nv_art_c2p_indices(0, pixels, 120) == nv_art.image.indices);
	REQUIRE(!nv_art_object(255, 65534, 2));
	REQUIRE(!nv_art_c2p_indices(0, pixels, 120));
	nv_art_stop();
	REQUIRE(!nv_art.enabled && !nv_art.arena && frees == 2);
	/* A source descriptor outside the owned payload is rejected. */
	for (i = 0; i < be32(contents + 12); ++i) {
		NvU8 *entry = contents + 32 + i * 24;
		if (be32(entry) == ((10UL << 16) | 113)) {
			offset = be32(entry + 4) + 64;
			contents[offset] ^= 1;
			break;
		}
	}
	REQUIRE(i < be32(contents + 12));
	nv_art_start();
	REQUIRE(nv_art.enabled && !nv_art_object(10, 113, 1) && !nv_art.enabled && nv_art.rejects == 1);
	nv_art_stop();
	contents[offset] ^= 1;
	/* The offline checksum is diagnostic; valid prepared data is trusted. */
	offset = 32 + i * 24 + 20;
	contents[offset] ^= 1;
	nv_art_start();
	REQUIRE(nv_art.enabled && nv_art_object(10, 113, 1));
	nv_art_stop();
	contents[offset] ^= 1;
	saved = size;
	size = 31;
	nv_art_start();
	REQUIRE(!nv_art.enabled && !nv_art.arena);
	size = saved;
	free(pixels - 24 * 320);
	free(original);
	free(contents);
	printf("PASS optional-file/allocation/bounds/trusted-checksum/lifetime/row-binding cases; reads=%u alloc=%u free=%u close=%u\n",
	       reads, allocations, frees, closes);
	return 0;
}
