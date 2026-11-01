/* Local native experiment, GPL-3.0-or-later. */
#include "native_driver.h"
#include "native_client.h"
#include <stddef.h>
#include "native_timeline.h"
extern int nv_clock_start(void);
extern NvU32 nv_clock_now(void);
extern void nv_clock_stop(void);
extern void nv_copy_output(NvS8 *to, const NvS8 *from, NvU16 bytes);
extern void nv_zero_output(NvS8 *to, NvU16 bytes);
extern void nv_disable_interrupts(void);
extern void nv_enable_interrupts(void);

#define HW_WORD(address) (*(volatile NvU16 *)(address))
#define HW_LONG(address) (*(volatile NvU32 *)(address))
#define INTENAR 0xdff01cUL
#define INTREQR 0xdff01eUL
#define DMACON 0xdff096UL
#define INTENA 0xdff09aUL
#define INTREQ 0xdff09cUL
#define AUD0 0xdff0a0UL

extern void *nv_alloc_chip(NvU32 size);
extern void nv_free_chip(void *memory, NvU32 size);
extern void nv_signal_worker(void *task, NvU32 mask);
extern void nv_irq(void);
void nv_driver_install(NvU32 original_handler);
static NvU16 interrupt_lock(void);
static void interrupt_restore(NvU16 prior);

struct NvControl nv_control = {NV_CONTROL_MAGIC, NV_CONTROL_VERSION, sizeof(struct NvControl), 0, 0, 0, 0, 0};
void *SysBase;

struct NvDriver {
	struct NvMixer mixer;
	volatile NvU8 bank[12];
	NvS8 *buffers[2];
	NvU16 serials[2];
	NvU16 next_serial;
	NvU16 active;
	NvU16 first_irq;
	NvU16 running;
	NvU16 dma_bits;
	NvU32 irqs;
	NvU32 original_handler;
	NvU16 gains[2];
	NvU16 physical_gain;
	NvU16 native_volumes[4];
	NvU16 speech_active, native_first_irq, clock_started;
	NvU32 last_tick, native_events;
};

struct NvDriver nv_driver;
volatile NvU32 nv_skipped_pirate_checks;

NvU32 nv_game_skip_script(NvU32 script) {
	if ((nv_control.flags & (NV_CONTROL_ENABLE | NV_CONTROL_SKIP_PIRATE_CHECK)) ==
		(NV_CONTROL_ENABLE | NV_CONTROL_SKIP_PIRATE_CHECK) && script == 152) {
		++nv_skipped_pirate_checks;
		return 1;
	}
	return 0;
}
const NvU16 nv_driver_layout[] = {
	sizeof(struct NvDriver), offsetof(struct NvDriver, mixer), offsetof(struct NvMixer, clipped),
	offsetof(struct NvMixer, music_gain), offsetof(struct NvDriver, bank), offsetof(struct NvDriver, buffers),
	offsetof(struct NvDriver, serials), offsetof(struct NvDriver, next_serial), offsetof(struct NvDriver, active),
	offsetof(struct NvDriver, first_irq), offsetof(struct NvDriver, running), offsetof(struct NvDriver, dma_bits),
	offsetof(struct NvDriver, irqs), offsetof(struct NvDriver, original_handler), offsetof(struct NvDriver, gains),
	offsetof(struct NvDriver, physical_gain), offsetof(struct NvDriver, native_volumes),
	offsetof(struct NvDriver, speech_active), offsetof(struct NvDriver, native_first_irq),
	offsetof(struct NvDriver, clock_started), offsetof(struct NvDriver, last_tick),
	offsetof(struct NvDriver, native_events)
};

static NvU16 bank_word(unsigned int offset) {
	return (NvU16)(((NvU16)nv_driver.bank[offset] << 8) | nv_driver.bank[offset + 1]);
}

static void synchronize(void) {
	struct NvPaula *p = &nv_driver.mixer.native;
	nv_paula_pointer(p, ((NvU32)bank_word(0) << 16) | bank_word(2));
	nv_paula_length(p, bank_word(4));
	nv_paula_period(p, bank_word(6));
	nv_paula_volume(p, bank_word(8));
}

static void advance(void) {
	NvU32 now = nv_clock_now(), elapsed = now - nv_driver.last_tick;
	NvU16 pending = nv_driver.mixer.native.irq_pending;
	nv_driver.last_tick = now;
	nv_paula_advance(&nv_driver.mixer.native, elapsed * 5);
	/* Physical native reloads are authoritative while channel 0 is not stolen. */
	if (!nv_driver.speech_active) nv_driver.mixer.native.irq_pending = pending;
}

void nv_driver_write(NvU32 address, NvU32 offset) {
	NvU16 prior;
	struct NvPaula *p = &nv_driver.mixer.native;
	if (!(nv_control.flags & NV_CONTROL_RUNNING) || address != (NvU32)nv_driver.bank) return;
	prior = interrupt_lock();
	if (offset != 8) advance();
	switch (offset) {
	case 0: nv_paula_pointer(p, ((NvU32)bank_word(0) << 16) | bank_word(2)); break;
	case 4: nv_paula_length(p, bank_word(4)); break;
	case 6: nv_paula_period(p, bank_word(6)); break;
	case 8: nv_paula_volume(p, bank_word(8)); break;
	default: synchronize(); break;
	}
	if (!nv_driver.speech_active) {
		if (!offset) HW_LONG(AUD0) = nv_driver.mixer.native.reload_address;
		else HW_WORD(AUD0 + offset) = bank_word((unsigned int)offset);
	}
	interrupt_restore(prior);
}

static NvS8 read_sample(void *context, NvU32 address) {
	return *(volatile NvS8 *)(address + (NvU32)context);
}

static NvU16 interrupt_lock(void) {
	NvU16 prior = HW_WORD(INTENAR) & 0x4000;
	nv_disable_interrupts();
	return prior;
}

static void interrupt_restore(NvU16 prior) {
	nv_enable_interrupts();
	if (!prior) HW_WORD(INTENA) = 0x4000;
}

static void virtual_interrupt(void) {
	if (nv_paula_take_irq(&nv_driver.mixer.native)) {
		*(volatile NvU8 *)(nv_control.game_code + 0x17e2) = 0xff;
		if (!nv_driver.speech_active && !nv_driver.native_first_irq) HW_WORD(INTREQ) = 0x80;
	}
	if (!nv_driver.speech_active && !nv_driver.native_first_irq && !nv_driver.mixer.native.irq_enabled)
		HW_WORD(INTENA) = 0x80;
}

void nv_driver_volume(NvU32 address, NvU32 incoming) {
	NvU16 value = (NvU16)incoming, prior, channel;
	if (!(nv_control.flags & NV_CONTROL_RUNNING)) {
		HW_WORD(address + 8) = value;
		return;
	}
	prior = interrupt_lock();
	if (address == (NvU32)nv_driver.bank) {
		nv_driver.bank[8] = (NvU8)(value >> 8); nv_driver.bank[9] = (NvU8)value;
		nv_paula_volume(&nv_driver.mixer.native, value);
	} else if (address >= AUD0 + 16 && address <= AUD0 + 48 && !((address - AUD0) & 15)) {
		channel = (NvU16)((address - AUD0) >> 4);
		nv_driver.native_volumes[channel] = value & 64 ? 64 : value & 63;
		HW_WORD(address + 8) = nv_driver.native_volumes[channel] * nv_driver.physical_gain / 64;
	} else {
		HW_WORD(address + 8) = value;
	}
	interrupt_restore(prior);
}

void nv_driver_clear_native_volume(NvU32 channel) {
	if (channel >= 1 && channel < 4) nv_driver_volume(AUD0 + 16 * channel, 0);
}

static void render(unsigned int buffer) {
	struct NativeVoice *v = nv_control.voice;
	struct NvMixer *m = &nv_driver.mixer;
	NvU16 count = 0, first, available, serial = nv_driver.next_serial++;
	NvS8 *output = nv_driver.buffers[buffer];
	nv_driver.serials[buffer] = serial;
	if (m->generation != v->generation) {
		m->generation = v->generation;
		m->tail_valid = 0;
	}
	if (v->generation && v->cancel_generation == v->generation) {
		v->read_cursor = v->write_cursor;
		v->state = NATIVE_VOICE_CANCELLED;
	}
	if (v->state == NATIVE_VOICE_READY || v->state == NATIVE_VOICE_PLAYING) {
		available = (NvU16)(v->write_cursor - v->read_cursor);
		count = available < NATIVE_MIX_SAMPLES ? available : NATIVE_MIX_SAMPLES;
		first = (NvU16)(v->capacity - (v->read_cursor & (v->capacity - 1)));
		if (first > count) first = count;
		if (first) nv_copy_output(output, v->pcm + (v->read_cursor & (v->capacity - 1)), first);
		if (count > first) nv_copy_output(output + first, v->pcm, (NvU16)(count - first));
		v->read_cursor = (NvU16)(v->read_cursor + count);
		if (count) {
			v->state = NATIVE_VOICE_PLAYING;
			m->tail_serial = serial;
			m->tail_valid = 1;
		}
		if (!v->eof && count < NATIVE_MIX_SAMPLES) ++v->underruns;
		if (v->eof && v->read_cursor == v->write_cursor) {
			v->rendered_generation = v->generation;
			v->state = NATIVE_VOICE_DRAINING;
			if (!m->tail_valid) { m->tail_valid = 1; m->tail_serial = (NvU16)(serial - 1); }
		}
	}
	if (count < NATIVE_MIX_SAMPLES) nv_zero_output(output + count, (NvU16)(NATIVE_MIX_SAMPLES - count));
	if ((v->state == NATIVE_VOICE_READY || v->state == NATIVE_VOICE_PLAYING) && !v->eof &&
		(NvU16)(v->write_cursor - v->read_cursor) <= v->capacity / 2 && v->worker_task && v->signal_mask)
		nv_signal_worker(v->worker_task, v->signal_mask);
}

static void program(unsigned int buffer) {
	HW_LONG(AUD0) = (NvU32)nv_driver.buffers[buffer];
	HW_WORD(AUD0 + 4) = NATIVE_MIX_SAMPLES / 2;
	HW_WORD(AUD0 + 6) = nv_driver.mixer.output_period;
	/* Keep the previous Paula data word inaudible until the initial speech
	 * DMA latch has fired. Subsequent program calls run after first_irq clears. */
	HW_WORD(AUD0 + 8) = nv_driver.first_irq ? 0 : 64;
}

static void restore_native(void) {
	struct NvPaula *p = &nv_driver.mixer.native;
	NvU32 index, address, bytes;
	HW_WORD(DMACON) = 1;
	HW_WORD(INTENA) = 0x80;
	HW_WORD(INTREQ) = 0x80;
	advance();
	nv_driver.speech_active = 0;
	index = (p->index + 1) & 0xfffffffeUL;
	address = p->active_address + index;
	bytes = p->active_bytes - index;
	if (!bytes) { address = p->reload_address; bytes = p->reload_bytes; }
	HW_LONG(AUD0) = address;
	HW_WORD(AUD0 + 4) = (NvU16)(bytes / 2);
	HW_WORD(AUD0 + 6) = (NvU16)p->period;
	HW_WORD(AUD0 + 8) = p->volume;
	if (p->dma) {
		/* The artificial initial latch must not become a native macro event. */
		nv_driver.native_first_irq = 1;
		HW_WORD(INTENA) = 0x8080;
		HW_WORD(DMACON) = 0x8201;
	}
	virtual_interrupt();
}

void nv_driver_service(void) {
	struct NativeVoice *v = nv_control.voice;
	NvU16 prior;
	if (!(nv_control.flags & NV_CONTROL_RUNNING)) return;
	prior = interrupt_lock();
	advance();
	if (nv_driver.speech_active) {
		if (v->generation != nv_driver.mixer.generation ||
			v->cancel_generation == v->generation || v->state == NATIVE_VOICE_CANCELLED ||
			v->state == NATIVE_VOICE_FAILED || v->state == NATIVE_VOICE_DONE) restore_native();
	} else if (v->state == NATIVE_VOICE_READY || v->state == NATIVE_VOICE_PLAYING) {
		if ((HW_WORD(INTREQR) & 0x80) && nv_driver.mixer.native.dma)
			nv_driver.mixer.native.irq_pending = 1;
		HW_WORD(AUD0 + 8) = 0;
		HW_WORD(DMACON) = 1;
		HW_WORD(INTENA) = 0x80;
		HW_WORD(INTREQ) = 0x80;
		nv_driver.speech_active = 1;
		nv_driver.next_serial = 0;
		render(0); render(1);
		nv_driver.active = 0;
		nv_driver.first_irq = 1;
		program(0);
		HW_WORD(INTENA) = 0x8080;
		HW_WORD(DMACON) = 0x8201;
	}
	virtual_interrupt();
	interrupt_restore(prior);
}

void nv_driver_start(void) {
	struct NativeVoice *v = nv_control.voice;
	SysBase = *(void **)4;
	nv_game_set_policy(nv_control.policy);
	if (!(nv_control.flags & NV_CONTROL_ENABLE) || (nv_control.flags & NV_CONTROL_RUNNING))
		return;
	if (!v || !nv_control.game_code || !nv_control.game_globals || v->magic != NATIVE_VOICE_MAGIC ||
		v->version != NATIVE_VOICE_VERSION || v->capacity != NATIVE_VOICE_CAPACITY ||
		!v->pcm || v->output_period < 124) {
		nv_control.flags |= NV_CONTROL_FAILED;
		return;
	}
	nv_driver.buffers[0] = nv_alloc_chip(NATIVE_MIX_SAMPLES);
	nv_driver.buffers[1] = nv_alloc_chip(NATIVE_MIX_SAMPLES);
	if (!nv_driver.buffers[0] || !nv_driver.buffers[1]) {
		if (nv_driver.buffers[0]) nv_free_chip(nv_driver.buffers[0], NATIVE_MIX_SAMPLES);
		if (nv_driver.buffers[1]) nv_free_chip(nv_driver.buffers[1], NATIVE_MIX_SAMPLES);
		nv_control.flags |= NV_CONTROL_FAILED;
		return;
	}
	nv_mixer_init(&nv_driver.mixer, v, read_sample, 0, v->output_period);
	synchronize();
	if (!nv_clock_start()) {
		nv_free_chip(nv_driver.buffers[0], NATIVE_MIX_SAMPLES);
		nv_free_chip(nv_driver.buffers[1], NATIVE_MIX_SAMPLES);
		nv_control.flags |= NV_CONTROL_FAILED;
		return;
	}
	nv_driver.clock_started = 1;
	nv_driver.last_tick = nv_clock_now();
	nv_driver.dma_bits = 0x200;
	nv_driver.physical_gain = 64;
	nv_driver.original_handler = HW_LONG(0x70);
	*(volatile NvU32 *)(nv_control.game_code + 0x1942) = (NvU32)nv_driver.bank;
	nv_control.flags |= NV_CONTROL_RUNNING;
	nv_driver_install(nv_driver.original_handler);
}

void nv_driver_install(NvU32 original_handler) {
	NvU16 prior;
	if (!(nv_control.flags & NV_CONTROL_RUNNING)) {
		HW_LONG(0x70) = original_handler;
		return;
	}
	prior = interrupt_lock();
	HW_LONG(0x70) = (NvU32)nv_irq;
	if (!nv_driver.running) {
		nv_driver.running = 1;
	}
	interrupt_restore(prior);
}

/* kind0=DMACON,1=INTENA,2=INTREQ. Original writes keep their set/clear semantics. */
void nv_driver_control(NvU32 kind, NvU32 incoming) {
	NvU16 prior, old_channels, new_channels, was_dma, value = (NvU16)incoming, set = value & 0x8000;
	NvU32 address = kind == 0 ? DMACON : kind == 1 ? INTENA : INTREQ;
	struct NvPaula *p = &nv_driver.mixer.native;
	if (!(nv_control.flags & NV_CONTROL_RUNNING)) {
		HW_WORD(address) = value;
		return;
	}
	if (!nv_driver.speech_active && !(p->irq_pending && p->irq_enabled)) {
		if ((kind == 1 && !(value & 0x4080)) || (kind == 2 && !(value & 0x80))) {
			HW_WORD(address) = value;
			return;
		}
		if (kind == 0 && !(value & 0x201)) {
			prior = interrupt_lock();
			old_channels = nv_driver.dma_bits & 0x200 ? nv_driver.dma_bits & 14 : 0;
			if (set) nv_driver.dma_bits |= value & 14;
			else nv_driver.dma_bits &= (NvU16)~(value & 14);
			new_channels = nv_driver.dma_bits & 0x200 ? nv_driver.dma_bits & 14 : 0;
			HW_WORD(address) = value & (NvU16)~0x20f;
			if (old_channels & (NvU16)~new_channels)
				HW_WORD(address) = old_channels & (NvU16)~new_channels;
			if (new_channels & (NvU16)~old_channels)
				HW_WORD(address) = 0x8000 | (new_channels & (NvU16)~old_channels);
			if (p->dma) HW_WORD(DMACON) = 0x8201;
			else HW_WORD(DMACON) = 1;
			if (!(nv_driver.dma_bits & 0x200)) HW_WORD(DMACON) = 0x200;
			interrupt_restore(prior);
			return;
		}
	}
	prior = interrupt_lock();
	if (kind == 0 || nv_driver.speech_active) advance();
	if (kind == 0) {
		was_dma = p->dma;
		old_channels = nv_driver.dma_bits & 0x200 ? nv_driver.dma_bits & 14 : 0;
		if (set) nv_driver.dma_bits |= value & 0x20f;
		else nv_driver.dma_bits &= (NvU16)~(value & 0x20f);
		nv_paula_dma(p, (nv_driver.dma_bits & 0x201) == 0x201);
		new_channels = nv_driver.dma_bits & 0x200 ? nv_driver.dma_bits & 14 : 0;
		HW_WORD(address) = value & (NvU16)~0x20f;
		if (old_channels & (NvU16)~new_channels)
			HW_WORD(address) = old_channels & (NvU16)~new_channels;
		if (new_channels & (NvU16)~old_channels)
			HW_WORD(address) = 0x8000 | (new_channels & (NvU16)~old_channels);
		if (!nv_driver.speech_active) {
			/* A native DMA start latches its original region directly in Paula. */
			if (p->dma) {
				HW_WORD(DMACON) = 0x8201;
			} else HW_WORD(DMACON) = 1;
			if (p->dma && !was_dma) {
				p->irq_pending = 0;
				nv_driver.native_first_irq = 0;
			}
			if (!(nv_driver.dma_bits & 0x200)) HW_WORD(DMACON) = 0x200;
		}
	} else if (kind == 1) {
		if (value & 0x80) nv_paula_irq_enable(p, set != 0);
		if (value & 0x4000) prior = set ? 0x4000 : 0;
		HW_WORD(address) = value & (NvU16)~0x4080;
		if (!nv_driver.speech_active && !nv_driver.native_first_irq && (value & 0x80))
			HW_WORD(address) = value & 0x8080;
	} else {
		if (value & 0x80) {
			if (set) p->irq_pending = 1;
			else nv_paula_irq_ack(p);
		}
		HW_WORD(address) = value & (NvU16)~0x80;
		if (!nv_driver.speech_active && (value & 0x80) && !set) HW_WORD(address) = 0x80;
	}
	if (prior) virtual_interrupt();
	interrupt_restore(prior);
}

NvU32 nv_driver_intena(void) {
	NvU16 value = HW_WORD(INTENAR);
	if (nv_control.flags & NV_CONTROL_RUNNING)
		value = (value & (NvU16)~0x80) | (nv_driver.mixer.native.irq_enabled ? 0x80 : 0);
	return value;
}

void nv_driver_restore(NvU32 original_handler) {
	NvU16 prior;
	if (!(nv_control.flags & NV_CONTROL_RUNNING)) {
		HW_LONG(0x70) = original_handler;
		return;
	}
	prior = interrupt_lock();
	/* Native song shutdown stops its virtual DMA, not the speech output clock. */
	HW_LONG(0x70) = (NvU32)nv_irq;
	interrupt_restore(prior);
}

void nv_driver_end(void) {
	NvU16 prior;
	if (!(nv_control.flags & NV_CONTROL_RUNNING))
		return;
	prior = interrupt_lock();
	HW_WORD(INTENA) = 0x80;
	HW_WORD(INTREQ) = 0x80;
	HW_WORD(DMACON) = 1;
	nv_driver.running = 0;
	HW_LONG(0x70) = nv_driver.original_handler;
	*(volatile NvU32 *)(nv_control.game_code + 0x1942) = AUD0;
	nv_control.flags &= (NvU32)~NV_CONTROL_RUNNING;
	interrupt_restore(prior);
	nv_free_chip(nv_driver.buffers[0], NATIVE_MIX_SAMPLES);
	nv_free_chip(nv_driver.buffers[1], NATIVE_MIX_SAMPLES);
	if (nv_driver.clock_started) { nv_clock_stop(); nv_driver.clock_started = 0; }
}

void nv_driver_clear_volume(void) {
	if (nv_control.flags & NV_CONTROL_RUNNING) {
		NvU16 prior = interrupt_lock();
		advance();
		nv_driver.bank[8] = nv_driver.bank[9] = 0;
		nv_paula_volume(&nv_driver.mixer.native, 0);
		if (!nv_driver.speech_active) HW_WORD(AUD0 + 8) = 0;
		interrupt_restore(prior);
	} else {
		HW_WORD(AUD0 + 8) = 0;
	}
}

/* Assembly enters with all registers saved and IPL7; the hardware frame restores SR. */
void nv_driver_irq(void) {
	NvU16 pending = HW_WORD(INTREQR) & HW_WORD(INTENAR), bit;
	unsigned int channel, free_buffer;
	++nv_driver.irqs;
	advance();
	if (pending & 0x80) {
		HW_WORD(INTREQ) = 0x80;
		if (!nv_driver.speech_active) {
			if (nv_driver.native_first_irq) {
				nv_driver.native_first_irq = 0;
				HW_LONG(AUD0) = nv_driver.mixer.native.reload_address;
				HW_WORD(AUD0 + 4) = (NvU16)(nv_driver.mixer.native.reload_bytes / 2);
				if (nv_driver.mixer.native.irq_enabled) HW_WORD(INTENA) = 0x8080;
			} else {
				nv_driver.mixer.native.irq_pending = 1;
				++nv_driver.native_events;
			}
		} else if (nv_control.voice->generation != nv_driver.mixer.generation) {
			restore_native();
		} else if (nv_control.voice->cancel_generation == nv_control.voice->generation) {
			nv_control.voice->state = NATIVE_VOICE_CANCELLED;
			restore_native();
		} else if (nv_driver.first_irq) {
			nv_driver.first_irq = 0;
			program(1);
		} else {
			free_buffer = nv_driver.active;
			nv_mixer_played(&nv_driver.mixer, nv_driver.serials[free_buffer]);
			if (nv_control.voice->state == NATIVE_VOICE_DONE) restore_native();
			else {
				nv_driver.active ^= 1;
				render(free_buffer);
				program(free_buffer);
			}
		}
	}
	virtual_interrupt();
	for (channel = 1; channel < 4; ++channel) {
		bit = (NvU16)(0x80 << channel);
		if (pending & bit) {
			HW_WORD(INTENA) = bit;
			HW_WORD(INTREQ) = bit;
			*(volatile NvU8 *)(nv_control.game_code + 0x17e2 + 4 * channel) = 0xff;
		}
	}
}
