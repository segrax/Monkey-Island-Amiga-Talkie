/* GPL-3.0-or-later */
#include "native_lookup.h"
#include "native_policy.h"
#include <stdio.h>
#include <string.h>

static int find_key(struct NativeMap *map, const char *prefix, const char *key,
                     unsigned long *offset, unsigned long *length) {
	char qualified[1600];
	if (!prefix[0])
		return native_map_find(map, key, offset, length);
	if (strlen(prefix) + strlen(key) >= sizeof(qualified))
		return -1;
	sprintf(qualified, "%s%s", prefix, key);
	return native_map_find(map, qualified, offset, length);
}

static int lookup(struct NativeMap *map, struct NativeSpeechSequence *sequence, const char *key, const char *prefix) {
	unsigned long offset, length;
	int result = find_key(map, prefix, key, &offset, &length);
	if (result == 1) {
		sequence->count = 1;
		sequence->offset[0] = offset;
		sequence->header_length[0] = length;
	}
	return result;
}

static int lookup_mode(struct NativeMap *map, const struct NativeSpeechContext *ctx,
                        struct NativeSpeechSequence *sequence, const char *prefix, int queue_only) {
	char text[NATIVE_TEXT_BYTES], key[1536], site[64], scope[64], queue_base[1024];
	const char *origins[3];
	NvU16 pos, used = 0, actor, alternative, i, count, found_count, origin_index;
	unsigned long offset, length, marker_offset = 0, marker_length = 0;
	int result;
	sequence->count = 0;
	if (ctx->text_length > NATIVE_TEXT_BYTES || !memchr(ctx->origin, 0, sizeof(ctx->origin)))
		return -1;
	for (pos = 0; pos < ctx->text_length; ++pos) {
		NvU8 c = ctx->text[pos];
		if (!c)
			break;
		if (c == 0xff || c == 0xfe) {
			if (++pos >= ctx->text_length)
				return -1;
			c = ctx->text[pos];
			if (c == 2 || c == 3)
				break;
			if (c == 1 || c == 8)
				continue;
			if ((c != 9 && c != 12 && c != 13 && c != 14) || ctx->text_length - pos <= 2)
				return -1;
			pos += 2;
			continue;
		}
		if (c >= 'A' && c <= 'Z')
			c += 'a' - 'A';
		if ((c >= 'a' && c <= 'z') || (c >= '0' && c <= '9')) {
			if ((unsigned int)used + 1 >= sizeof(text))
				return -1;
			text[used++] = c;
		}
	}
	text[used] = 0;
	if (!used)
		return 0;
	site[0] = scope[0] = 0;
	switch (ctx->kind) {
	case NATIVE_GLOBAL:
		sprintf(site, "g:%u", ctx->script);
		sprintf(scope, "g:%u", ctx->script);
		break;
	case NATIVE_LOCAL:
		sprintf(site, "l:%u:%u", ctx->resource_room, ctx->script);
		sprintf(scope, "s:%u:%u", ctx->resource_room, ctx->script);
		break;
	case NATIVE_OBJECT:
		sprintf(site, "o:%u", ctx->script);
		sprintf(scope, "o:%u", ctx->script);
		break;
	case NATIVE_ENCD:
	case NATIVE_EXCD:
		sprintf(site, "e:%u:%s", ctx->resource_room, ctx->kind == NATIVE_ENCD ? "ENCD" : "EXCD");
		break;
	}
	if (!queue_only) {
		if (ctx->origin[0]) {
			const char *origin = ctx->origin;
			for (;;) {
				for (alternative = 0; alternative < 2; ++alternative) {
					actor = alternative ? 0 : ctx->actor;
					sprintf(key, "%s:%u:%s", origin, actor, text);
					result = lookup(map, sequence, key, prefix);
					if (result)
						return result;
				}
				if (origin != ctx->origin || !(origin = strstr(origin, ":r:")))
					break;
				++origin;
			}
		}
		if (site[0] && ctx->message_offset != 0xffffffffUL) {
			for (alternative = 0; alternative < 2; ++alternative) {
				actor = alternative ? 0 : ctx->actor;
				sprintf(key, "p:%s:%lu:%u:%u:%s", site, (unsigned long)ctx->message_offset, ctx->segment, actor, text);
				result = lookup(map, sequence, key, prefix);
				if (result)
					return result;
			}
		}
		if (scope[0]) {
			for (alternative = 0; alternative < 2; ++alternative) {
				actor = alternative ? 0 : ctx->actor;
				sprintf(key, "%s:%u:%s", scope, actor, text);
				result = lookup(map, sequence, key, prefix);
				if (result)
					return result;
			}
		}
		for (i = 0; i < 4; ++i) {
			sprintf(key, "%u:%u:%s", (unsigned int)(i & 1 ? 0 : ctx->room),
			        (unsigned int)(i & 2 ? 0 : ctx->actor), text);
			result = lookup(map, sequence, key, prefix);
			if (result)
				return result;
		}
		return 0;
	}
	if (!site[0] || ctx->message_offset == 0xffffffffUL)
		return 0;
	origins[0] = ctx->origin[0] ? ctx->origin : 0;
	origins[1] = strstr(ctx->origin, ":r:");
	if (origins[1]) ++origins[1];
	origins[2] = "";
	for (origin_index = 0; origin_index < 3; ++origin_index) {
		if (!origins[origin_index])
			continue;
		if (strlen(origins[origin_index]) + strlen(text) + strlen(site) + 80 >= sizeof(queue_base))
			return -1;
		for (alternative = 0; alternative < 2; ++alternative) {
			actor = alternative ? 0 : ctx->actor;
			if (origins[origin_index][0])
				sprintf(queue_base, "q:%u:%s:%lu:%u:%u:%s:%s", ctx->room, site,
				        (unsigned long)ctx->message_offset, ctx->segment, actor, origins[origin_index], text);
			else
				sprintf(queue_base, "q:%u:%s:%lu:%u:%u:%s", ctx->room, site,
				        (unsigned long)ctx->message_offset, ctx->segment, actor, text);
			found_count = 0;
			for (count = 2; count <= NATIVE_SEQUENCE_CLIPS; ++count) {
				sprintf(key, "%s:count:%u", queue_base, count);
				result = find_key(map, prefix, key, &offset, &length);
				if (result < 0)
					return -1;
				if (result) {
					if (found_count)
						return -1;
					found_count = count;
					marker_offset = offset;
					marker_length = length;
				}
			}
			if (!found_count)
				continue;
			for (i = 0; i < found_count; ++i) {
				sprintf(key, "%s:%u", queue_base, i);
				if (find_key(map, prefix, key, &offset, &length) != 1)
					return -1;
				sequence->offset[i] = offset;
				sequence->header_length[i] = length;
			}
			if (offset != marker_offset || length != marker_length)
				return -1;
			sequence->count = found_count;
			return 1;
		}
	}
	return 0;
}

int native_speech_lookup_selected(struct NativeMap *map, const struct NativeSpeechContext *ctx,
                                  struct NativeSpeechSequence *sequence,
                                  const struct NvSelector *selectors, NvU16 count) {
	struct NativeSpeechSequence candidate;
	char prefix[32];
	NvU16 i, clip, phase;
	int result, found = 0;
	sequence->count = 0;
	if (count > NV_POLICY_LIMIT || (count && !selectors))
		return -1;
	for (i = 0; i < count; ++i)
		if (!selectors[i].count || selectors[i].count > 16 || selectors[i].index >= selectors[i].count)
			return -1;
	for (phase = 0; phase < 2; ++phase) {
		found = 0;
		for (i = 0; i < count; ++i) {
			if (selectors[i].room != ctx->room)
				continue;
			sprintf(prefix, "v:%u:%u:", selectors[i].id, selectors[i].index);
			result = lookup_mode(map, ctx, &candidate, prefix, phase);
			if (result < 0)
				return -1;
			if (!result)
				continue;
			if (found) {
				if (sequence->count != candidate.count)
					return -1;
				for (clip = 0; clip < sequence->count; ++clip)
					if (sequence->offset[clip] != candidate.offset[clip] ||
					    sequence->header_length[clip] != candidate.header_length[clip])
						return -1;
			} else {
				*sequence = candidate;
				found = 1;
			}
		}
		if (found)
			return 1;
		result = lookup_mode(map, ctx, sequence, "", phase);
		if (result)
			return result;
	}
	return 0;
}

int native_speech_lookup(struct NativeMap *map, const struct NativeSpeechContext *ctx,
                         struct NativeSpeechSequence *sequence) {
	return native_speech_lookup_selected(map, ctx, sequence, 0, 0);
}

int native_voc_open(FILE *archive, NvU32 offset, NvU32 header_length, NvU32 *bytes, NvU16 *rate) {
	unsigned char header[26], block[6], vctl[8];
	unsigned long length, version, checksum, data_offset;
	long start;
	if (offset > 0x7fff0000UL || header_length < 8 || header_length > 132 || (header_length & 1))
		return 0;
	if (fseek(archive, offset, SEEK_SET) || fread(vctl, 1, 8, archive) != 8 || memcmp(vctl, "VCTL", 4))
		return 0;
	length = ((unsigned long)vctl[4] << 24) | ((unsigned long)vctl[5] << 16) | ((unsigned long)vctl[6] << 8) | vctl[7];
	if (length != header_length || fseek(archive, offset + header_length, SEEK_SET) ||
	    fread(header, 1, 26, archive) != 26 || memcmp(header, "Creative Voice File\032", 20))
		return 0;
	data_offset = header[20] | ((unsigned long)header[21] << 8);
	version = header[22] | ((unsigned long)header[23] << 8);
	checksum = header[24] | ((unsigned long)header[25] << 8);
	if (data_offset < 26 || checksum != ((~version + 0x1234UL) & 0xffff))
		return 0;
	if (fseek(archive, offset + header_length + data_offset, SEEK_SET) || fread(block, 1, 6, archive) != 6)
		return 0;
	length = block[1] | ((unsigned long)block[2] << 8) | ((unsigned long)block[3] << 16);
	if (block[0] != 1 || length < 3 || block[5] != 0)
		return 0;
	*rate = block[4] == 0xd3 ? 22050 : 1000000UL / (256 - block[4]);
	*bytes = length - 2;
	start = ftell(archive);
	if (start < 0 || fseek(archive, start + *bytes, SEEK_SET) || fgetc(archive) != 0)
		return 0;
	return fseek(archive, start, SEEK_SET) == 0;
}

#include <stddef.h>
typedef char NativeMapMustBe32Bytes[sizeof(struct NativeMap) == 32 ? 1 : -1];
typedef char NativeEntryMustBe8Bytes[sizeof(struct NativeMapEntry) == 8 ? 1 : -1];
typedef char NativeMapTailMustMatch[
    offsetof(struct NativeMap, data_start) == 20 &&
    offsetof(struct NativeMap, file_bytes) == 24 &&
    offsetof(struct NativeMap, preindexed) == 28 ? 1 : -1];
