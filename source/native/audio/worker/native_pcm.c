/* Local native experiment, GPL-3.0-or-later. */
#include "native_pcm.h"
#include "pcm_bindings.h"
#include <stdlib.h>
#include <string.h>

static unsigned long big32(const unsigned char *p) {
 return ((unsigned long)p[0] << 24) | ((unsigned long)p[1] << 16) |
        ((unsigned long)p[2] << 8) | p[3];
}
static unsigned int big16(const unsigned char *p) {
 return ((unsigned int)p[0] << 8) | p[1];
}
void native_pcm_close(struct NativePcm *pcm) {
 if (pcm->file) fclose(pcm->file);
 free(pcm->toc);
 memset(pcm, 0, sizeof(*pcm));
}
int native_pcm_open(struct NativePcm *pcm, const char *path, unsigned int gain,
                    unsigned long archive_bytes, unsigned long map_bytes) {
 unsigned char header[128], *row;
 unsigned long count, data, file_bytes, position, offset, length, previous_offset = 0,
               previous_length = 0, bytes, i;
 long actual;
 memset(pcm, 0, sizeof(*pcm));
 pcm->file = fopen(path, "rb");
 if (!pcm->file) return 0;
 if (fread(header, 1, 128, pcm->file) != 128 || memcmp(header, "NPC1", 4) ||
     big16(header + 4) != 1 || big16(header + 6) != 128 ||
     big32(header + 8) != 22050 || big32(header + 12) < 1 || big32(header + 12) > 8 ||
     archive_bytes != NPC_SOURCE_BYTES || map_bytes != NPC_MAP_BYTES ||
     big32(header + 16) != archive_bytes || big32(header + 20) != map_bytes ||
     memcmp(header + 40, npc_source_sha, 32) || memcmp(header + 72, npc_map_sha, 32)) goto invalid;
 for (i = 104; i < 128; ++i) if (header[i]) goto invalid;
 count = big32(header + 24); data = big32(header + 32); file_bytes = big32(header + 36);
 if (!count || count > 50000 || big32(header + 28) != 128 ||
     data != 128 + count * 16 || file_bytes > 0x7fffffffUL || file_bytes <= data ||
     fseek(pcm->file, 0, SEEK_END) || (actual = ftell(pcm->file)) < 0 ||
     (unsigned long)actual != file_bytes || fseek(pcm->file, 128, SEEK_SET)) goto invalid;
 pcm->toc = malloc(count * 16);
 if (!pcm->toc || fread(pcm->toc, 16, count, pcm->file) != count) goto invalid;
 position = data;
 for (i = 0; i < count; ++i) {
  row = pcm->toc + i * 16;
  offset = big32(row); length = big32(row + 4); bytes = big32(row + 12);
  if (length < 8 || length > 132 || (length & 1) ||
      archive_bytes < length + 32 || offset > archive_bytes - length - 32 ||
      (i && (offset < previous_offset || (offset == previous_offset && length <= previous_length))) ||
      big32(row + 8) != position || !bytes || bytes > file_bytes - position) goto invalid;
  position += bytes; previous_offset = offset; previous_length = length;
 }
 if (position != file_bytes) goto invalid;
 if (big32(header + 12) != gain) { native_pcm_close(pcm); return 2; }
 pcm->count = count; pcm->file_bytes = file_bytes; pcm->data_offset = data;
 return 1;
invalid:
 native_pcm_close(pcm);
 return -1;
}
int native_pcm_select(struct NativePcm *pcm, unsigned long offset,
                      unsigned long header_length, unsigned long *bytes) {
 unsigned long left = 0, right = pcm->count, middle, source, length;
 unsigned char *row;
 if (!pcm->file || !pcm->toc) return 0;
 while (left < right) {
  middle = left + (right - left) / 2;
  row = pcm->toc + middle * 16; source = big32(row); length = big32(row + 4);
  if (source < offset || (source == offset && length < header_length)) left = middle + 1;
  else right = middle;
 }
 if (left == pcm->count) return 0;
 row = pcm->toc + left * 16;
 if (big32(row) != offset || big32(row + 4) != header_length ||
     fseek(pcm->file, big32(row + 8), SEEK_SET)) return 0;
 *bytes = big32(row + 12);
 return 1;
}
