/* Local native experiment, GPL-3.0-or-later. */
#include "paula_mix.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static NvS8 pcm[NATIVE_VOICE_CAPACITY];
static NvS8 read_sample(void *context, NvU32 address) {
	(void)address;
	return *(NvS8 *)context;
}
int main(void) {
	struct NvMixer m;
	struct NativeVoice v;
	NvS8 native, output;
	int a,b,expected;
	for(a=-128;a<128;++a) for(b=-128;b<128;++b) {
		memset(&v,0,sizeof(v)); native=(NvS8)a;
		v.capacity=NATIVE_VOICE_CAPACITY;v.pcm=pcm;v.speech_gain=64;
		v.generation=1;v.state=NATIVE_VOICE_READY;v.write_cursor=1;v.eof=1;pcm[0]=(NvS8)b;
		nv_mixer_init(&m,&v,read_sample,&native,161);
		nv_paula_period(&m.native,65535);nv_paula_volume(&m.native,64);nv_paula_dma(&m.native,1);
		nv_mixer_render(&m,&output,1,0);
		expected=a+b;if(expected>127)expected=127;if(expected< -128)expected=-128;
		assert(output==expected && m.music_gain==64 && m.native.volume==64);
		nv_mixer_played(&m,0);
		nv_mixer_render(&m,&output,1,1);
		assert(output==a && m.music_gain==64);
	}
	puts("65536 full-native/full-voice mix pairs and exact idle native output passed");
	return 0;
}
