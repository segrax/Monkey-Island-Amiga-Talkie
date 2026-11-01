/* GPL-3.0-or-later. C adapter for the algorithm in common/md5.cpp. */
#ifndef NATIVE_SPEECH_MD5_H
#define NATIVE_SPEECH_MD5_H
#include "native_voice.h"
#include <stdio.h>

struct NvMd5 {
	NvU32 total[2], state[4];
	NvU8 buffer[64];
};

void nv_md5_init(struct NvMd5 *context);
void nv_md5_update(struct NvMd5 *context, const NvU8 *input, NvU32 bytes);
void nv_md5_finish(struct NvMd5 *context, NvU8 digest[16]);
int nv_md5_stream(FILE *stream, NvU8 digest[16]);
int nv_md5_file(const char *path, NvU8 digest[16]);
#endif
