/* Local native experiment, GPL-3.0-or-later. */
#ifndef NATIVE_PREBUILT_PCM_H
#define NATIVE_PREBUILT_PCM_H
#include <stdio.h>
#include <stddef.h>
struct NativePcm {
 FILE *file;
 unsigned char *toc;
 unsigned long count, file_bytes, data_offset;
};
#ifdef __VBCC__
typedef char NativePcmSizeMustBe20[sizeof(struct NativePcm) == 20 ? 1 : -1];
typedef char NativePcmOffsetsMustMatch[
 offsetof(struct NativePcm, file) == 0 &&
 offsetof(struct NativePcm, toc) == 4 &&
 offsetof(struct NativePcm, count) == 8 &&
 offsetof(struct NativePcm, file_bytes) == 12 &&
 offsetof(struct NativePcm, data_offset) == 16 ? 1 : -1];
#endif
/* 1=ready,0=unavailable,2=gain mismatch,-1=invalid present file. */
int native_pcm_open(struct NativePcm *, const char *, unsigned int,
                    unsigned long, unsigned long);
void native_pcm_close(struct NativePcm *);
int native_pcm_select(struct NativePcm *, unsigned long, unsigned long,
                      unsigned long *);
#endif
