/* GPL-3.0-or-later */
#ifndef NATIVE_SPEECH_LOOKUP_H
#define NATIVE_SPEECH_LOOKUP_H
#include "native_map.h"
#include "native_voice.h"

#define NATIVE_TEXT_BYTES 512
#define NATIVE_ORIGIN_BYTES 256
#define NATIVE_SEQUENCE_CLIPS 16

enum NativeProgramKind { NATIVE_GLOBAL = 1, NATIVE_LOCAL, NATIVE_OBJECT, NATIVE_ENCD, NATIVE_EXCD };

struct NativeSpeechContext {
	NvU16 room, resource_room, actor, kind, script, segment;
	NvU32 message_offset;
	char origin[NATIVE_ORIGIN_BYTES];
	NvU16 text_length;
	NvU8 text[NATIVE_TEXT_BYTES];
};

struct NativeSpeechSequence {
	NvU16 count;
	NvU32 offset[NATIVE_SEQUENCE_CLIPS];
	NvU32 header_length[NATIVE_SEQUENCE_CLIPS];
};

int native_speech_lookup(struct NativeMap *map, const struct NativeSpeechContext *context,
                         struct NativeSpeechSequence *sequence);
struct NvSelector;
int native_speech_lookup_selected(struct NativeMap *map, const struct NativeSpeechContext *context,
                                  struct NativeSpeechSequence *sequence,
                                  const struct NvSelector *selectors, NvU16 count);
int native_voc_open(FILE *archive, NvU32 offset, NvU32 header_length, NvU32 *bytes, NvU16 *rate);
#endif
