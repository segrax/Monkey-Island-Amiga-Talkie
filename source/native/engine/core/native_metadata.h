/* Local native experiment, GPL-3.0-or-later. */
#ifndef NATIVE_METADATA_H
#define NATIVE_METADATA_H
#include "native_voice.h"
#define NV_METADATA_VERSION 1
#define NV_METADATA_BYTES 6574UL
NvU32 nv_metadata_export(NvU8 *output, NvU32 capacity);
int nv_metadata_import(const NvU8 *input, NvU32 bytes);
void nv_metadata_clear(void);
void nv_metadata_save(NvU32 slot);
void nv_metadata_load_begin(void);
void nv_metadata_load(NvU32 slot);
#endif
