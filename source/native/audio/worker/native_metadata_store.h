/* GPL-3.0-or-later. Optional sidecar; original saves are never rewritten. */
#ifndef NATIVE_SPEECH_METADATA_H
#define NATIVE_SPEECH_METADATA_H
#include "native_policy.h"

#define NV_METADATA_MAX_BLOB 65536UL
enum NvMetadataResult { NV_META_OK = 1, NV_META_MISSING = 0, NV_META_INVALID = -1, NV_META_IO = -2 };
int nv_metadata_presence(const char *save_path);
int nv_metadata_save(const char *save_path, const NvU8 map_digest[16], const struct NvPolicy *policy,
                      const void *blob, NvU32 bytes, NvU16 blob_version);
int nv_metadata_load(const char *save_path, const NvU8 map_digest[16], struct NvPolicy *policy,
                      void *blob, NvU32 capacity, NvU32 *bytes, NvU16 blob_version);
#endif
