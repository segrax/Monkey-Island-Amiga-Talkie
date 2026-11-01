/* GPL-3.0-or-later: bounded-memory reader for the existing MAT1 speech map. */
#ifndef NATIVE_TALKIE_MAP_H
#define NATIVE_TALKIE_MAP_H
#include <stdio.h>

struct NativeMapEntry {
	unsigned long hash;
	long position;
};

struct NativeMap {
	FILE *file;
	struct NativeMapEntry *entries;
	char *scratch;
	unsigned long count;
	unsigned long archive_size;
	unsigned long data_start, file_bytes;
	int preindexed;
};

int native_map_open(struct NativeMap *map, const char *path, unsigned long archive_size);
typedef int (*NativeMapVisitor)(void *, const char *, unsigned long, unsigned long);
int native_map_open_scan(struct NativeMap *map, const char *path, unsigned long archive_size,
                         NativeMapVisitor visitor, void *context);
struct NvPolicy;
/* MAT2 loads static triggers; policy seed and mutable selectors remain fresh. */
int native_map_open_policy(struct NativeMap *map, const char *path, unsigned long archive_size,
                           struct NvPolicy *policy);
void native_map_close(struct NativeMap *map);
/* 1 = found, 0 = absent, -1 = invalid input/read failure. */
int native_map_find(struct NativeMap *map, const char *key,
                    unsigned long *offset, unsigned long *header_length);
#endif
