/* GPL-3.0-or-later */
#include "native_map.h"
#include <stdlib.h>
#include <string.h>
#include "native_policy.h"

#define KEY_BYTES 2048
static unsigned long big32(const unsigned char *p) {
	return ((unsigned long)p[0] << 24) | ((unsigned long)p[1] << 16) | ((unsigned long)p[2] << 8) | p[3];
}
static unsigned int big16(const unsigned char *p) { return ((unsigned int)p[0] << 8) | p[1]; }

static unsigned long little32(const unsigned char *p) {
	return p[0] | ((unsigned long)p[1] << 8) | ((unsigned long)p[2] << 16) | ((unsigned long)p[3] << 24);
}

static unsigned long key_hash(const char *key) {
	unsigned long hash = 2166136261UL;
	while (*key) {
		hash ^= (unsigned char)*key++;
		/* FNV's prime, using shifts to avoid a software 32-bit multiply on 68000. */
		hash = (hash + (hash << 1) + (hash << 4) + (hash << 7) + (hash << 8) + (hash << 24)) & 0xffffffffUL;
	}
	return hash;
}

static int sort_entries(struct NativeMapEntry *entries, unsigned long count) {
	struct NativeMapEntry *temporary = malloc(count * sizeof(*temporary));
	struct NativeMapEntry *source = entries, *destination = temporary, *swap;
	unsigned long buckets[256], i, total, next;
	unsigned int shift, bucket;
	if (!temporary)
		return 0;
	for (shift = 0; shift < 32; shift += 8) {
		memset(buckets, 0, sizeof(buckets));
		for (i = 0; i < count; ++i)
			++buckets[(source[i].hash >> shift) & 255];
		total = 0;
		for (bucket = 0; bucket < 256; ++bucket) {
			next = buckets[bucket];
			buckets[bucket] = total;
			total += next;
		}
		for (i = 0; i < count; ++i)
			destination[buckets[(source[i].hash >> shift) & 255]++] = source[i];
		swap = source;
		source = destination;
		destination = swap;
	}
	free(temporary);
	return 1;
}

static int read_entry(FILE *file, char *key, unsigned long *offset, unsigned long *length) {
	unsigned char size[2], ref[8];
	unsigned int bytes;
	if (fread(size, 1, 2, file) != 2)
		return 0;
	bytes = size[0] | ((unsigned int)size[1] << 8);
	if (!bytes || bytes >= KEY_BYTES || fread(key, 1, bytes, file) != bytes || memchr(key, 0, bytes))
		return 0;
	key[bytes] = 0;
	if (fread(ref, 1, 8, file) != 8)
		return 0;
	*offset = little32(ref);
	*length = little32(ref + 4);
	return 1;
}

void native_map_close(struct NativeMap *map) {
	if (map->file)
		fclose(map->file);
	free(map->entries);
	free(map->scratch);
	memset(map, 0, sizeof(*map));
}

int native_map_open(struct NativeMap *map, const char *path, unsigned long archive_size) {
	return native_map_open_policy(map, path, archive_size, 0);
}

int native_map_open_policy(struct NativeMap *map, const char *path, unsigned long archive_size,
                           struct NvPolicy *policy) {
	unsigned char header[64], raw[16];
	unsigned long i, j, policies, policy_offset, data_offset, bytes, records, position;
	long actual;
	struct NvPolicy local;
	struct NvPolicy *destination = policy;
	struct NvTrigger *trigger;
	memset(map, 0, sizeof(*map));
	map->file = fopen(path, "rb");
	if (!map->file || fread(header, 1, 4, map->file) != 4) goto invalid;
	if (!memcmp(header, "MAT1", 4)) {
		fclose(map->file); map->file = 0;
		return native_map_open_scan(map, path, archive_size, policy ? nv_policy_collect : 0, policy);
	}
	if (memcmp(header, "MAT2", 4) || fread(header + 4, 1, 60, map->file) != 60 ||
	    big16(header + 4) != 1 || big16(header + 6) != 64 || big32(header + 8) != archive_size ||
	    archive_size > 0x7fffffffUL) goto invalid;
	for (i = 40; i < 64; ++i) if (header[i]) goto invalid;
	map->count = big32(header + 12);
	policy_offset = big32(header + 20); policies = big32(header + 24);
	data_offset = big32(header + 28); bytes = big32(header + 32); records = big32(header + 36);
	if (!map->count || map->count > 50000 || policies > NV_POLICY_LIMIT ||
	    big32(header + 16) != 64 || policy_offset != 64 + map->count * 8 ||
	    data_offset != policy_offset + policies * 16 || bytes > 0x7fffffffUL ||
	    bytes < data_offset || records != bytes - data_offset || records < map->count * 11 ||
	    records > map->count * (KEY_BYTES + 9)) goto invalid;
	if (fseek(map->file, 0, SEEK_END) || (actual = ftell(map->file)) < 0 ||
	    (unsigned long)actual != bytes || fseek(map->file, 64, SEEK_SET)) goto invalid;
	map->entries = malloc(map->count * sizeof(*map->entries));
	map->scratch = malloc(2 * KEY_BYTES);
	if (!map->entries || !map->scratch) goto invalid;
#ifdef __VBCC__
	/* m68k is big-endian, and both fields are exactly 32 bits. */
	{
		typedef char EntryMustBeEightBytes[sizeof(struct NativeMapEntry) == 8 ? 1 : -1];
		if (fread(map->entries, 8, map->count, map->file) != map->count) goto invalid;
	}
#else
	for (i = 0; i < map->count; ++i) {
		if (fread(raw, 1, 8, map->file) != 8) goto invalid;
		map->entries[i].hash = big32(raw);
		map->entries[i].position = (long)big32(raw + 4);
	}
#endif
	for (i = 0; i < map->count; ++i) {
		position = (unsigned long)map->entries[i].position;
		if (position < data_offset || position > bytes - 11 ||
		    (i && (map->entries[i].hash < map->entries[i-1].hash ||
		    (map->entries[i].hash == map->entries[i-1].hash &&
		     map->entries[i].position <= map->entries[i-1].position)))) goto invalid;
	}
	if (policy && (policy->magic != NV_POLICY_MAGIC || policy->version != NV_POLICY_VERSION ||
	    policy->size != sizeof(*policy) || !policy->random_seed || policy->trigger_count || policy->selector_count)
		) goto invalid;
	nv_policy_init(&local, policy ? policy->random_seed : 1);
	policy = &local;
	for (i = 0; i < policies; ++i) {
		if (fread(raw, 1, 16, map->file) != 16) goto invalid;
		trigger = &policy->triggers[i];
		trigger->kind = big16(raw); trigger->resource_room = big16(raw+2);
		trigger->script = big16(raw+4); trigger->room = big16(raw+6);
		trigger->selector = big16(raw+8); trigger->count = big16(raw+10);
		trigger->offset = big32(raw+12);
		if (trigger->kind < NATIVE_GLOBAL || trigger->kind > NATIVE_EXCD ||
		    !trigger->room || trigger->room > 255 || !trigger->count || trigger->count > 16 ||
		    trigger->offset > 0x7fffffffUL ||
		    ((trigger->kind == NATIVE_GLOBAL || trigger->kind == NATIVE_OBJECT) && trigger->resource_room) ||
		    ((trigger->kind == NATIVE_ENCD || trigger->kind == NATIVE_EXCD) && trigger->script)) goto invalid;
		for (j = 0; j < i; ++j) {
			struct NvTrigger *prior = &policy->triggers[j];
			if (prior->kind == trigger->kind && prior->resource_room == trigger->resource_room &&
			    prior->script == trigger->script && prior->offset == trigger->offset &&
			    prior->selector == trigger->selector) goto invalid;
		}
	}
	policy->trigger_count = (NvU16)policies;
	if (destination) {
		memcpy(destination->triggers, policy->triggers, sizeof(policy->triggers));
		destination->trigger_count = policy->trigger_count;
	}
	map->archive_size = archive_size; map->data_start = data_offset; map->file_bytes = bytes;
	map->preindexed = 1;
	return 1;
invalid:
	native_map_close(map);
	return 0;
}

int native_map_open_scan(struct NativeMap *map, const char *path, unsigned long archive_size,
                         NativeMapVisitor visitor, void *context) {
	unsigned char header[12];
	char *key, *previous;
	unsigned long i, j, offset, length;
	long position = 12;
	memset(map, 0, sizeof(*map));
	map->file = fopen(path, "rb");
	if (!map->file || fread(header, 1, 12, map->file) != 12 || memcmp(header, "MAT1", 4) ||
	    little32(header + 4) != archive_size)
		goto invalid;
	map->count = little32(header + 8);
	map->archive_size = archive_size;
	if (!map->count || map->count > 50000 || archive_size > 0x7fffffffUL)
		goto invalid;
	map->entries = malloc(map->count * sizeof(*map->entries));
	map->scratch = malloc(2 * KEY_BYTES);
	if (!map->entries || !map->scratch)
		goto invalid;
	key = map->scratch;
	previous = map->scratch + KEY_BYTES;
	for (i = 0; i < map->count; ++i) {
#ifdef NATIVE_DIAGNOSTIC
		if (!(i & 4095)) { FILE *trace = fopen("voice-index.log", i ? "a" : "w"); if (trace) { fprintf(trace, "entry %lu\n", i); fclose(trace); } }
#endif
		map->entries[i].position = position;
		if (!read_entry(map->file, key, &offset, &length) ||
		    length < 8 || length > 132 || (length & 1) || archive_size < length + 26 ||
		    offset > archive_size - length - 26)
			goto invalid;
		if (visitor && !visitor(context, key, offset, length))
			goto invalid;
		map->entries[i].hash = key_hash(key);
		position += 10 + strlen(key);
	}
	if (fgetc(map->file) != EOF || ferror(map->file))
		goto invalid;
	clearerr(map->file);

#ifdef NATIVE_DIAGNOSTIC
	{ FILE *trace = fopen("voice-index.log", "a"); if (trace) { fputs("sorting\n", trace); fclose(trace); } }
#endif
	if (!sort_entries(map->entries, map->count))
		goto invalid;
	/* A hash collision is valid; duplicate full keys are not. */
	for (i = 1; i < map->count; ++i) {
		if (map->entries[i].hash != map->entries[i - 1].hash)
			continue;
		if (fseek(map->file, map->entries[i].position, SEEK_SET) || !read_entry(map->file, key, &offset, &length))
			goto invalid;
		for (j = i; j > 0 && map->entries[j - 1].hash == map->entries[i].hash; --j) {
			if (fseek(map->file, map->entries[j - 1].position, SEEK_SET) ||
			    !read_entry(map->file, previous, &offset, &length) || !strcmp(key, previous))
				goto invalid;
		}
	}
	return 1;
invalid:
	native_map_close(map);
	return 0;
}

int native_map_find(struct NativeMap *map, const char *key,
                    unsigned long *offset, unsigned long *header_length) {
	unsigned long low = 0, high = map->count, middle, hash;
	unsigned long found_offset = 0, found_length = 0;
	int found = 0;
	char *stored = map->scratch;
	if (!map->file || !key || !*key || strlen(key) >= KEY_BYTES)
		return -1;
	hash = key_hash(key);
	while (low < high) {
		middle = low + (high - low) / 2;
		if (map->entries[middle].hash < hash)
			low = middle + 1;
		else
			high = middle;
	}
	while (low < map->count && map->entries[low].hash == hash) {
		if (fseek(map->file, map->entries[low].position, SEEK_SET) ||
		    !read_entry(map->file, stored, offset, header_length))
			return -1;
		if (map->preindexed && (key_hash(stored) != hash || *header_length < 8 ||
		    *header_length > 132 || (*header_length & 1) || map->archive_size < *header_length + 26 ||
		    *offset > map->archive_size - *header_length - 26 ||
		    (unsigned long)map->entries[low].position + 10 + strlen(stored) > map->file_bytes)) return -1;
		if (!strcmp(stored, key)) {
			if (!map->preindexed) return 1;
			if (found) return -1;
			found = 1; found_offset = *offset; found_length = *header_length;
		}
		++low;
	}
	if (found) { *offset = found_offset; *header_length = found_length; }
	return found;
}

#include <stddef.h>
typedef char NativeMapMustBe32Bytes[sizeof(struct NativeMap) == 32 ? 1 : -1];
typedef char NativeEntryMustBe8Bytes[sizeof(struct NativeMapEntry) == 8 ? 1 : -1];
typedef char NativeMapTailMustMatch[
    offsetof(struct NativeMap, data_start) == 20 &&
    offsetof(struct NativeMap, file_bytes) == 24 &&
    offsetof(struct NativeMap, preindexed) == 28 ? 1 : -1];
