/* Local native experiment, GPL-3.0-or-later. */
#ifndef NATIVE_VOICE_H
#define NATIVE_VOICE_H

#ifdef __VBCC__
typedef signed char NvS8;
typedef unsigned char NvU8;
typedef unsigned short NvU16;
typedef unsigned long NvU32;
typedef signed long NvS32;
#else
#include <stdint.h>
typedef int8_t NvS8;
typedef uint8_t NvU8;
typedef uint16_t NvU16;
typedef uint32_t NvU32;
typedef int32_t NvS32;
#endif

#define NATIVE_VOICE_MAGIC 0x4d563031UL
#define NATIVE_VOICE_VERSION 1
#define NATIVE_VOICE_CAPACITY 16384
#define NATIVE_MIX_SAMPLES 256

enum NativeVoiceState {
	NATIVE_VOICE_IDLE,
	NATIVE_VOICE_PENDING,
	NATIVE_VOICE_PREFILL,
	NATIVE_VOICE_READY,
	NATIVE_VOICE_PLAYING,
	NATIVE_VOICE_DRAINING,
	NATIVE_VOICE_DONE,
	NATIVE_VOICE_FAILED,
	NATIVE_VOICE_CANCELLED
};

struct NativeVoice {
	NvU32 magic;
	NvU16 version;
	volatile NvU16 state;
	volatile NvU16 generation;
	volatile NvU16 cancel_generation;
	volatile NvU16 read_cursor;
	volatile NvU16 write_cursor;
	volatile NvU16 eof;
	volatile NvU16 rendered_generation;
	volatile NvU16 played_generation;
	volatile NvU16 underruns;
	NvU16 capacity;
	NvU16 speech_gain;
	NvU16 clip_rate;
	NvU16 output_period;
	NvU32 remaining;
	NvS8 *pcm;
	void *worker_task;
	NvU32 signal_mask;
};

/* Cursors are monotonic modulo65536; pcm indexes use cursor&(capacity-1).
 * The producer publishes write_cursor after PCM, then eof after its last data.
 * PENDING/flush/new generation changes happen together under Exec Disable.
 * Only the consumer changes read_cursor. Empty before eof means starvation.
 * rendered_generation means queued in CHIP; played_generation means DMA done.
 * IRQ code does no allocation or DOS I/O. It may Signal(worker_task,signal_mask).
 */

#endif
