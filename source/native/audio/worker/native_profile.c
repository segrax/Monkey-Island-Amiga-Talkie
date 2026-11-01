/* Local native experiment, GPL-3.0-or-later. */
#include "native_profile.h"
#include "pcm_bindings.h"
#include "prepared_bindings.h"
#include <errno.h>
#include <string.h>
int native_profile_mode(void) {
 unsigned char marker[8];
 size_t bytes;
 int failed;
 FILE *file = fopen("PreparedOnly", "rb");
 if (!file) return errno == ENOENT ? 0 : -1;
 bytes = fread(marker, 1, sizeof(marker), file);
 failed = ferror(file);
 if (fclose(file)) failed = 1;
 if (failed) return -1;
 return (bytes == 5 && !memcmp(marker, "NPC1\n", 5)) ||
        (bytes == 6 && !memcmp(marker, "NPC1\r\n", 6)) ? 1 : -1;
}
int native_profile_gain(unsigned int *gain) {
 unsigned char value[8];
 size_t bytes;
 int failed;
 FILE *file = fopen("VoiceBoost", "rb");
 *gain = NPC_PREPARED_GAIN;
 if (!file) return errno == ENOENT;
 bytes = fread(value, 1, sizeof(value), file);
 failed = ferror(file);
 if (fclose(file)) failed = 1;
 return !failed && bytes >= 1 && value[0] == '0' + NPC_PREPARED_GAIN &&
        (bytes == 1 || (bytes == 2 && value[1] == '\n') ||
         (bytes == 3 && value[1] == '\r' && value[2] == '\n'));
}

int native_profile_archive(int prepared, const char *path, FILE **archive, long *bytes) {
 *archive = 0; *bytes = 0;
 if (prepared == 1) { *bytes = NPC_SOURCE_BYTES; return 1; }
 if (prepared) return 0;
 *archive = fopen(path, "rb");
 if (!*archive) return 0;
 if (fseek(*archive, 0, SEEK_END) || (*bytes = ftell(*archive)) < 0) {
  fclose(*archive); *archive = 0; *bytes = 0; return 0;
 }
 return 1;
}
int native_profile_ready(int prepared, int status, unsigned int gain, const struct NativePcm *pcm) {
 if (!prepared) return status >= 0;
 return prepared == 1 && status == 1 && gain == NPC_PREPARED_GAIN && pcm && pcm->file &&
        pcm->count == NPC_PREPARED_CLIPS && pcm->file_bytes == NPC_PREPARED_BYTES;
}
