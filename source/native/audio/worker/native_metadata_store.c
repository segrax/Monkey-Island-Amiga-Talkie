/* GPL-3.0-or-later */
#include "native_metadata_store.h"
#include "native_md5.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>

#define META_HEADER 64

static NvU16 get16(const NvU8 *p) { return ((NvU16)p[0] << 8) | p[1]; }
static NvU32 get32(const NvU8 *p) { return ((NvU32)get16(p) << 16) | get16(p + 2); }
static void put16(NvU8 *p, NvU16 value) { p[0] = value >> 8; p[1] = value; }
static void put32(NvU8 *p, NvU32 value) { put16(p, value >> 16); put16(p + 2, value); }

static int names(const char *save, char path[256], char temporary[256]) {
	unsigned int length;
	if (!save || !save[0] || (length = strlen(save)) > 240)
		return 0;
	memcpy(path, save, length);
	strcpy(path + length, ".talkie");
	strcpy(temporary, path);
	strcat(temporary, ".tmp");
	return 1;
}

int nv_metadata_presence(const char *save) {
 char path[256], temporary[256], backup[256];
 FILE *file;
 if (!names(save, path, temporary)) return NV_META_INVALID;
 file = fopen(path, "rb");
 if (file) return fclose(file) ? NV_META_IO : NV_META_OK;
 if (errno != ENOENT) return NV_META_IO;
 strcpy(backup, path); strcat(backup, ".bak");
 file = fopen(backup, "rb");
 if (file) return fclose(file) ? NV_META_IO : NV_META_OK;
 return errno == ENOENT ? NV_META_MISSING : NV_META_IO;
}

static void digest(const NvU8 *data, NvU32 length, NvU8 result[16]) {
	struct NvMd5 md5;
	nv_md5_init(&md5);
	nv_md5_update(&md5, data, length);
	nv_md5_finish(&md5, result);
}

int nv_metadata_save(const char *save, const NvU8 map_digest[16], const struct NvPolicy *policy,
                      const void *blob, NvU32 bytes, NvU16 blob_version) {
	char path[256], temporary[256], backup[256];
	NvU8 save_digest[16], *data;
	NvU32 payload, length;
	NvU16 i, j;
	FILE *file;
	int result, had_previous = 0;
	if (!names(save, path, temporary) || !map_digest || !policy || policy->magic != NV_POLICY_MAGIC ||
	    policy->version != NV_POLICY_VERSION || policy->size != sizeof(*policy) ||
	    policy->selector_count > NV_POLICY_LIMIT || !policy->random_seed || !blob_version ||
	    bytes > NV_METADATA_MAX_BLOB || (bytes && !blob))
		return NV_META_INVALID;
	for (i = 0; i < policy->selector_count; ++i) {
		if (!nv_policy_selector_valid(policy, &policy->selectors[i]))
			return NV_META_INVALID;
		for (j = 0; j < i; ++j)
			if (policy->selectors[i].id == policy->selectors[j].id)
				return NV_META_INVALID;
	}
	if (!nv_md5_file(save, save_digest))
		return NV_META_IO;
	payload = (NvU32)policy->selector_count * 8 + bytes;
	length = META_HEADER + payload + 16;
	data = malloc(length);
	if (!data)
		return NV_META_IO;
	memset(data, 0, META_HEADER);
	memcpy(data, "NMT1", 4);
	put16(data + 4, 1);
	put16(data + 6, META_HEADER);
	put32(data + 8, payload);
	put32(data + 12, bytes);
	put16(data + 16, blob_version);
	put16(data + 18, policy->selector_count);
	memcpy(data + 20, map_digest, 16);
	memcpy(data + 36, save_digest, 16);
	put32(data + 52, policy->random_seed);
	for (i = 0; i < policy->selector_count; ++i) {
		NvU8 *out = data + META_HEADER + i * 8;
		put16(out, policy->selectors[i].id);
		put16(out + 2, policy->selectors[i].room);
		put16(out + 4, policy->selectors[i].index);
		put16(out + 6, policy->selectors[i].count);
	}
	if (bytes)
		memcpy(data + META_HEADER + (NvU32)policy->selector_count * 8, blob, bytes);
	digest(data, length - 16, data + length - 16);
	file = fopen(temporary, "wb");
	if (!file) {
		free(data);
		return NV_META_IO;
	}
	result = fwrite(data, 1, length, file) == length;
	if (fclose(file))
		result = 0;
	free(data);
	if (!result) {
		remove(temporary);
		return NV_META_IO;
	}
	strcpy(backup, path); strcat(backup, ".bak");
	file = fopen(path, "rb");
	if (file) {
		fclose(file);
		remove(backup);
		if (rename(path, backup)) { remove(temporary); return NV_META_IO; }
		had_previous = 1;
	}
	if (rename(temporary, path)) {
		if (had_previous) rename(backup, path);
		remove(temporary);
		return NV_META_IO;
	}
	remove(backup);
	return NV_META_OK;
}

int nv_metadata_load(const char *save, const NvU8 map_digest[16], struct NvPolicy *policy,
                      void *blob, NvU32 capacity, NvU32 *bytes, NvU16 blob_version) {
	char path[256], temporary[256], backup[256];
	NvU8 save_digest[16], checksum[16], *data;
	NvU32 blob_bytes, payload, seed;
	NvU16 count, i, j;
	struct NvSelector selectors[NV_POLICY_LIMIT];
	long length;
	FILE *file;
	int result = NV_META_INVALID;
	if (!bytes) return NV_META_INVALID;
	*bytes = 0;
	if (!map_digest || !policy || policy->magic != NV_POLICY_MAGIC || policy->version != NV_POLICY_VERSION ||
	    policy->size != sizeof(*policy))
		return NV_META_INVALID;
	policy->selector_count = 0;
	if (!names(save, path, temporary) || !blob_version || capacity > NV_METADATA_MAX_BLOB || (capacity && !blob))
		return NV_META_INVALID;
	file = fopen(path, "rb");
	if (!file) {
		if (errno != ENOENT) return NV_META_IO;
		strcpy(backup, path); strcat(backup, ".bak");
		file = fopen(backup, "rb");
		if (!file) return errno == ENOENT ? NV_META_MISSING : NV_META_IO;
	}
	if (fseek(file, 0, SEEK_END) || (length = ftell(file)) < META_HEADER + 16 ||
	    (NvU32)length > META_HEADER + 16 + NV_POLICY_LIMIT * 8 + NV_METADATA_MAX_BLOB || fseek(file, 0, SEEK_SET)) {
		fclose(file);
		return NV_META_INVALID;
	}
	data = malloc(length);
	if (!data) {
		fclose(file);
		return NV_META_IO;
	}
	if (fread(data, 1, length, file) != (NvU32)length || ferror(file)) {
		fclose(file);
		free(data);
		return NV_META_IO;
	}
	fclose(file);
	payload = get32(data + 8);
	blob_bytes = get32(data + 12);
	count = get16(data + 18);
	seed = get32(data + 52);
	if (memcmp(data, "NMT1", 4) || get16(data + 4) != 1 || get16(data + 6) != META_HEADER ||
	    get16(data + 16) != blob_version || count > NV_POLICY_LIMIT || !seed ||
	    blob_bytes > capacity || blob_bytes > NV_METADATA_MAX_BLOB ||
	    payload != (NvU32)count * 8 + blob_bytes || (NvU32)length != META_HEADER + payload + 16 ||
	    get32(data + 56) || get32(data + 60) || memcmp(data + 20, map_digest, 16))
		goto done;
	digest(data, length - 16, checksum);
	if (memcmp(checksum, data + length - 16, 16))
		goto done;
	if (!nv_md5_file(save, save_digest)) {
		result = NV_META_IO;
		goto done;
	}
	if (memcmp(save_digest, data + 36, 16))
		goto done;
	for (i = 0; i < count; ++i) {
		const NvU8 *in = data + META_HEADER + i * 8;
		selectors[i].id = get16(in);
		selectors[i].room = get16(in + 2);
		selectors[i].index = get16(in + 4);
		selectors[i].count = get16(in + 6);
		if (!nv_policy_selector_valid(policy, &selectors[i]))
			goto done;
		for (j = 0; j < i; ++j)
			if (selectors[i].id == selectors[j].id)
				goto done;
	}
	if (blob_bytes)
		memcpy(blob, data + META_HEADER + (NvU32)count * 8, blob_bytes);
	memcpy(policy->selectors, selectors, count * sizeof(*selectors));
	policy->selector_count = count;
	policy->random_seed = seed;
	*bytes = blob_bytes;
	result = NV_META_OK;
done:
	free(data);
	return result;
}
