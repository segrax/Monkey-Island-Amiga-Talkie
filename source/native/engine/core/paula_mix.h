/* Local native experiment, GPL-3.0-or-later. */
#ifndef NATIVE_PAULA_MIX_H
#define NATIVE_PAULA_MIX_H
#include "native_voice.h"

typedef NvS8 (*NvSampleRead)(void *context, NvU32 address);

struct NvPaula {
	NvU32 reload_address;
	NvU32 reload_bytes;
	NvU32 active_address;
	NvU32 active_bytes;
	NvU32 index;
	NvU32 elapsed;
	NvU32 period;
	NvU32 latched_period;
	NvU32 latches;
	NvU16 volume;
	NvU16 dma;
	NvU16 irq_enabled;
	NvU16 irq_pending;
	NvS8 sample;
	NvSampleRead read;
	void *context;
};

struct NvMixer {
	struct NvPaula native;
	struct NativeVoice *voice;
	NvU16 generation;
	NvU16 tail_serial;
	NvU16 tail_valid;
	NvU16 output_period;
	NvU32 clipped;
	NvU16 music_gain;
};

void nv_paula_init(struct NvPaula *p, NvSampleRead read, void *context);
void nv_paula_pointer(struct NvPaula *p, NvU32 address);
void nv_paula_length(struct NvPaula *p, NvU16 words);
void nv_paula_period(struct NvPaula *p, NvU16 period);
void nv_paula_volume(struct NvPaula *p, NvU16 volume);
void nv_paula_dma(struct NvPaula *p, NvU16 enabled);
void nv_paula_irq_enable(struct NvPaula *p, NvU16 enabled);
void nv_paula_irq_ack(struct NvPaula *p);
int nv_paula_take_irq(struct NvPaula *p);
void nv_mixer_init(struct NvMixer *m, struct NativeVoice *voice,
	NvSampleRead read, void *context, NvU16 output_period);
/* Returns nonzero when the producer should be signalled for more PCM. */
int nv_mixer_render(struct NvMixer *m, NvS8 *output, NvU16 samples, NvU16 serial);
/* Invoke only after this physical block finished, not when it was queued. */
void nv_mixer_played(struct NvMixer *m, NvU16 serial);

#endif
