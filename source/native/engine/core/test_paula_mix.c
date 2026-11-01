/* Local native experiment, GPL-3.0-or-later. */
#include "paula_mix.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static NvS8 memory[32] = {64,-64,32,-32,0,0,0,0,10,20};
static NvS8 pcm[NATIVE_VOICE_CAPACITY];

static NvS8 sample_read(void *unused, NvU32 address) {
	(void)unused;
	assert(address < sizeof(memory));
	return memory[address];
}

static void start(struct NvMixer *m, struct NativeVoice *v, NvU16 period) {
	memset(v, 0, sizeof(*v));
	v->magic = NATIVE_VOICE_MAGIC;
	v->version = NATIVE_VOICE_VERSION;
	v->capacity = NATIVE_VOICE_CAPACITY;
	v->pcm = pcm;
	v->speech_gain = 64;
	nv_mixer_init(m, v, sample_read, 0, 161);
	nv_paula_pointer(&m->native, 0);
	nv_paula_length(&m->native, 2);
	nv_paula_period(&m->native, period);
	nv_paula_volume(&m->native, 64);
	nv_paula_dma(&m->native, 1);
}

int main(void) {
	struct NvMixer m;
	struct NativeVoice v;
	NvS8 out[16];
	start(&m, &v, 161);
	assert(m.native.irq_pending && !nv_paula_take_irq(&m.native));
	nv_paula_irq_enable(&m.native, 1);
	assert(nv_paula_take_irq(&m.native));
	assert(!m.native.irq_enabled && !m.native.irq_pending);
	nv_mixer_render(&m, out, 2, 0);
	assert(out[0] == 64 && out[1] == -64);
	nv_paula_pointer(&m.native, 9);
	nv_paula_length(&m.native, 1);
	nv_mixer_render(&m, out, 4, 1);
	assert(out[0] == 32 && out[1] == -32 && out[2] == 10 && out[3] == 20);
	assert(m.native.latches == 3 && m.native.irq_pending);
	assert(!nv_paula_take_irq(&m.native));
	nv_paula_irq_ack(&m.native);
	nv_paula_irq_enable(&m.native, 1);
	assert(!nv_paula_take_irq(&m.native));
	nv_paula_dma(&m.native, 0);
	nv_mixer_render(&m, out, 1, 2);
	assert(out[0] == 0);
	start(&m, &v, 322);
	nv_mixer_render(&m, out, 3, 0);
	assert(out[0] == 64 && out[1] == 64 && out[2] == -64);
	nv_paula_dma(&m.native, 1);
	nv_mixer_render(&m, out, 1, 1);
	assert(out[0] == -64);
	start(&m, &v, 322);
	nv_mixer_render(&m, out, 1, 0);
	nv_paula_period(&m.native, 161);
	nv_mixer_render(&m, out, 2, 1);
	assert(out[0] == 64 && out[1] == -64);
	start(&m, &v, 161);
	nv_paula_volume(&m.native, 0);
	nv_mixer_render(&m, out, 2, 0);
	nv_paula_volume(&m.native, 127);
	nv_mixer_render(&m, out, 1, 1);
	assert(out[0] == 32 && m.native.volume == 64);
	nv_paula_period(&m.native, 0);
	nv_paula_length(&m.native, 0);
	assert(m.native.period == 65536UL && m.native.reload_bytes == 131072UL);
	start(&m, &v, 161);
	nv_paula_dma(&m.native, 0);
	v.generation = 1;
	v.state = NATIVE_VOICE_READY;
	v.read_cursor = 65534;
	v.write_cursor = 2;
	v.eof = 1;
	pcm[16382]=1; pcm[16383]=2; pcm[0]=3; pcm[1]=4;
	nv_mixer_render(&m, out, 4, 65535);
#ifdef NV_MUSIC_DUCK
	assert(out[0]==0 && out[1]==1 && out[2]==2 && out[3]==3);
#else
	assert(out[0]==1 && out[1]==2 && out[2]==3 && out[3]==4);
#endif
	assert(v.read_cursor==2 && v.state==NATIVE_VOICE_DRAINING);
	assert(v.rendered_generation==1 && !v.played_generation);
	nv_mixer_played(&m, 65534);
	assert(v.state==NATIVE_VOICE_DRAINING);
	nv_mixer_played(&m, 65535);
	assert(v.state==NATIVE_VOICE_DONE && v.played_generation==1);
	start(&m, &v, 161);
	v.generation=2; v.state=NATIVE_VOICE_READY;
	assert(nv_mixer_render(&m,out,2,0));
#ifdef NV_MUSIC_DUCK
	assert(out[0]==16 && out[1]==-16 && v.underruns==1);
#else
	assert(out[0]==64 && out[1]==-64 && v.underruns==1);
#endif
	assert(v.state==NATIVE_VOICE_READY && v.played_generation==0);
	pcm[0]=100;v.write_cursor=1;v.eof=1;
	nv_mixer_render(&m,out,1,1);
#ifdef NV_MUSIC_DUCK
	assert(out[0]==83 && m.clipped==0);
#else
	assert(out[0]==127 && m.clipped==1);
#endif
	nv_mixer_played(&m,1);
	assert(v.state==NATIVE_VOICE_DONE);
	v.generation=3;v.cancel_generation=3;v.state=NATIVE_VOICE_READY;
	v.read_cursor=0;v.write_cursor=1;
	nv_mixer_render(&m,out,1,2);
	assert(v.state==NATIVE_VOICE_CANCELLED && v.read_cursor==v.write_cursor);
	assert(m.music_gain==64);
	{
		int native, speech;
		for (native = -128; native < 128; ++native) {
			for (speech = -128; speech < 128; ++speech) {
				start(&m, &v, 65535);
				m.native.sample = (NvS8)native;
				v.generation = 1; v.state = NATIVE_VOICE_READY;
				v.write_cursor = 1; v.eof = 1; pcm[0] = (NvS8)speech;
				nv_mixer_render(&m, out, 1, 0);
#ifdef NV_MUSIC_DUCK
				assert(out[0] == (native * 16 + speech * 48) / 64);
				assert(!m.clipped && m.music_gain == 16 && m.native.volume == 64);
#else
				{ int expected=native+speech; if(expected>127)expected=127;if(expected< -128)expected=-128;
				assert(out[0]==expected && m.music_gain==64 && m.native.volume==64); }
#endif
				nv_mixer_render(&m, out, 1, 1);
#ifdef NV_MUSIC_DUCK
				assert(m.music_gain == 16);
#else
				assert(m.music_gain == 64);
#endif
				nv_mixer_played(&m, 0);
				nv_mixer_render(&m, out, 1, 2);
				assert(m.music_gain == 64);
			}
		}
	}
	puts("Paula phase/reload/IRQ and voice ring/drain fixtures passed");
	return 0;
}
