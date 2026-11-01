/* Local native experiment, GPL-3.0-or-later. */
#ifndef NATIVE_PREPARED_PROFILE_H
#define NATIVE_PREPARED_PROFILE_H
#include <stdio.h>
#include "native_pcm.h"
int native_profile_mode(void);
int native_profile_gain(unsigned int *gain);
int native_profile_archive(int prepared, const char *path, FILE **archive, long *bytes);
int native_profile_ready(int prepared, int status, unsigned int gain, const struct NativePcm *pcm);
#endif
