#include "native_server.h"
#include "native_profile.h"
#include <stdio.h>
static struct NativeVoice voice;
static struct NativePcm prebuilt;
static struct NativeSpeechSequence sequence;
static NvU16 sequence_index;
static int prepared_only;
static int next_clip(FILE *archive) {
	NvU16 rate;
	NvU32 remaining;
	if (sequence_index >= sequence.count)
		return 0;
	if (prebuilt.file) {
		if (!native_pcm_select(&prebuilt, sequence.offset[sequence_index],
		                       sequence.header_length[sequence_index], &remaining)) {
			if (prepared_only) puts("PreparedOnly: mapped clip unavailable; refusing speech.");
			return -1;
		}
		rate = 22050;
	} else if (prepared_only || !archive) {
		puts("PreparedOnly: native PCM unavailable; no SOU fallback.");
		return -1;
	} else if (!native_voc_open(archive, sequence.offset[sequence_index],
	                           sequence.header_length[sequence_index], &remaining, &rate) || rate != 22050)
		return -1;
	++sequence_index;
	voice.remaining = remaining;
	voice.clip_rate = rate;
	return 1;
}

struct NativePcm *probe_pcm(void) { return &prebuilt; }
int probe_next(int mode,int ready,FILE *archive) {
 prepared_only=mode; prebuilt.file=ready?(FILE *)0x200100:0;
 sequence.count=1;sequence_index=0;sequence.offset[0]=123;sequence.header_length[0]=10;
 return next_clip(archive);
}
