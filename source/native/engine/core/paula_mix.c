/* Local native experiment, GPL-3.0-or-later. */
#include "paula_mix.h"
#ifdef __VBCC__
extern void nv_zero_output(NvS8 *output, NvU16 samples);
#else
#include <string.h>
#endif

static void latch(struct NvPaula *p) {
	p->active_address = p->reload_address;
	p->active_bytes = p->reload_bytes;
	p->index = 0;
	p->sample = p->read(p->context, p->active_address);
	p->irq_pending = 1;
	++p->latches;
}

void nv_paula_init(struct NvPaula *p, NvSampleRead read, void *context) {
	p->reload_address = p->active_address = p->index = p->elapsed = p->latches = 0;
	p->reload_bytes = p->active_bytes = 131072UL;
	p->period = p->latched_period = 65536UL;
	p->volume = p->dma = p->irq_enabled = p->irq_pending = 0;
	p->sample = 0;
	p->read = read;
	p->context = context;
}

void nv_paula_pointer(struct NvPaula *p, NvU32 address) {
	p->reload_address = address & 0xfffffffeUL;
}

void nv_paula_length(struct NvPaula *p, NvU16 words) {
	p->reload_bytes = words ? (NvU32)words * 2 : 131072UL;
}

void nv_paula_period(struct NvPaula *p, NvU16 period) {
	p->period = period ? period : 65536UL;
}

void nv_paula_volume(struct NvPaula *p, NvU16 volume) {
	p->volume = volume & 64 ? 64 : volume & 63;
}

void nv_paula_dma(struct NvPaula *p, NvU16 enabled) {
	if (enabled && !p->dma) {
		p->elapsed = 0;
		p->latched_period = p->period;
		latch(p);
	}
	p->dma = enabled != 0;
}

void nv_paula_irq_enable(struct NvPaula *p, NvU16 enabled) {
	p->irq_enabled = enabled != 0;
}

void nv_paula_irq_ack(struct NvPaula *p) {
	p->irq_pending = 0;
}

int nv_paula_take_irq(struct NvPaula *p) {
	if (!p->irq_enabled || !p->irq_pending)
		return 0;
	p->irq_enabled = p->irq_pending = 0;
	return 1;
}

static int native_sample(struct NvPaula *p, NvU16 clocks) {
	int value;
	if (!p->dma)
		return 0;
	value = (int)p->sample * p->volume;
	p->elapsed += clocks;
	while (p->elapsed >= p->latched_period) {
		p->elapsed -= p->latched_period;
		p->latched_period = p->period;
		if (++p->index == p->active_bytes)
			latch(p);
		else
			p->sample = p->read(p->context, p->active_address + p->index);
	}
	return value;
}

void nv_mixer_init(struct NvMixer *m, struct NativeVoice *voice,
	NvSampleRead read, void *context, NvU16 output_period) {
	nv_paula_init(&m->native, read, context);
	m->voice = voice;
	m->generation = m->tail_serial = m->tail_valid = 0;
	m->output_period = output_period;
	m->clipped = 0;
	m->music_gain = 64;
}

int nv_mixer_render(struct NvMixer *m, NvS8 *output, NvU16 samples, NvU16 serial) {
	struct NativeVoice *v = m->voice;
	NvU16 i, generation = v->generation, consumed = 0, starved = 0;
	int value, speech, gain;
	if (generation != m->generation) {
		m->generation = generation;
		m->tail_valid = 0;
	}
	if (generation && v->cancel_generation == generation) {
		v->read_cursor = v->write_cursor;
		v->state = NATIVE_VOICE_CANCELLED;
	}
#ifdef NV_MUSIC_DUCK
	m->music_gain = generation && v->cancel_generation != generation &&
		(v->state == NATIVE_VOICE_READY || v->state == NATIVE_VOICE_PLAYING ||
		v->state == NATIVE_VOICE_DRAINING) ? 16 : 64;
	gain = v->speech_gain > 48 ? 48 : v->speech_gain;
#else
	m->music_gain = 64;
	gain = v->speech_gain > 64 ? 64 : v->speech_gain;
#endif
	if (!generation || (v->state != NATIVE_VOICE_READY && v->state != NATIVE_VOICE_PLAYING)) {
		if (!m->native.dma) {
#ifdef __VBCC__
			nv_zero_output(output, samples);
#else
			memset(output, 0, samples);
#endif
		} else {
			for (i = 0; i < samples; ++i) {
#ifdef NV_MUSIC_DUCK
				output[i] = native_sample(&m->native, m->output_period) * m->music_gain / 4096;
#else
				output[i] = native_sample(&m->native, m->output_period) / 64;
#endif
			}
		}
		return 0;
	}
	for (i = 0; i < samples; ++i) {
		speech = 0;
		if (generation && (v->state == NATIVE_VOICE_READY || v->state == NATIVE_VOICE_PLAYING)) {
			if (v->read_cursor != v->write_cursor) {
				speech = v->pcm[v->read_cursor & (v->capacity - 1)];
				v->read_cursor = (NvU16)(v->read_cursor + 1);
				v->state = NATIVE_VOICE_PLAYING;
				consumed = 1;
			} else if (!v->eof) {
				starved = 1;
			}
		}
#ifdef NV_MUSIC_DUCK
		value = (native_sample(&m->native, m->output_period) * m->music_gain / 64 + speech * gain) / 64;
#else
		value = (native_sample(&m->native, m->output_period) + speech * gain) / 64;
#endif
		if (value > 127) {
			value = 127;
			++m->clipped;
		} else if (value < -128) {
			value = -128;
			++m->clipped;
		}
		output[i] = value;
	}
	if (consumed) {
		m->tail_serial = serial;
		m->tail_valid = 1;
	}
	if (starved)
		++v->underruns;
	if (generation && (v->state == NATIVE_VOICE_READY || v->state == NATIVE_VOICE_PLAYING) &&
		v->eof && v->read_cursor == v->write_cursor) {
		v->rendered_generation = generation;
		v->state = NATIVE_VOICE_DRAINING;
		if (!m->tail_valid) {
			m->tail_serial = (NvU16)(serial - 1);
			m->tail_valid = 1;
		}
	}
	return (v->state == NATIVE_VOICE_READY || v->state == NATIVE_VOICE_PLAYING) && !v->eof &&
		(NvU16)(v->write_cursor - v->read_cursor) <= v->capacity / 2;
}

void nv_mixer_played(struct NvMixer *m, NvU16 serial) {
	struct NativeVoice *v = m->voice;
	if (m->tail_valid && v->generation == m->generation &&
		v->rendered_generation == m->generation && v->state == NATIVE_VOICE_DRAINING &&
		(NvU16)(serial - m->tail_serial) < 32768) {
		v->played_generation = m->generation;
		v->state = NATIVE_VOICE_DONE;
	}
}
