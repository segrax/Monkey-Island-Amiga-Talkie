/* Local native experiment, GPL-3.0-or-later. */
#include "native_driver.h"
#include "native_provenance.h"
#include "native_client.h"

struct NativeSpeechContext nv_dialogue_context;
#define context nv_dialogue_context
NvU16 nv_dialogue_valid, nv_dialogue_next_segment;
#define next_segment nv_dialogue_next_segment
volatile NvU32 nv_dialogue_captures, nv_dialogue_segments, nv_dialogue_holds, nv_dialogue_cancels;

static NvU16 word(unsigned offset) {
	return *(volatile NvU16 *)(nv_control.game_globals + offset);
}

static NvU32 pointer(unsigned offset) {
	return *(volatile NvU32 *)(nv_control.game_globals + offset);
}

static int program(unsigned slot, NvU16 *kind, NvU16 *script, NvU32 *base_offset) {
	NvU8 *g = nv_control.game_globals;
	NvU16 where, i;
	if (slot >= 20)
		return 0;
	*script = word(0x20ee + slot * 2);
	where = g[0x20da + slot];
	*base_offset = 0;
	if (where == 2) {
		*kind = *script < g[0x5980] ? NATIVE_GLOBAL : NATIVE_LOCAL;
	} else if (where == 1 && (*script == 998 || *script == 999)) {
		*kind = *script == 998 ? NATIVE_ENCD : NATIVE_EXCD;
		*base_offset = pointer(*script == 998 ? 0x19fe : 0x19fa);
	} else if (where == 0 || where == 1) {
		*kind = NATIVE_OBJECT;
		if (where == 1) {
			for (i = g[0x1a1e]; i; --i) {
				if (word(0x1c96 + 2 * i) == *script) {
					*base_offset = pointer(0x1ec6 + 4 * i);
					return 1;
				}
			}
			return 0;
		}
	} else {
		return 0;
	}
	return 1;
}

int nv_game_site(NvU32 slot, NvU32 position, struct NvSite *site) {
	NvU32 base, program_base;
	site->valid = 0;
	if (!program((unsigned)slot, &site->kind, &site->script, &program_base)) return 0;
	base = pointer(0x5a56);
	if (!base || position < base || position - base < program_base) return 0;
	site->resource_room = nv_control.game_globals[0x19f9];
	site->offset = position - base - program_base;
	site->valid = 1;
	return 1;
}

void nv_dialogue_program(NvU32 slot) {
	NvU16 kind, script;
	NvU32 base, offset;
	if (!(nv_control.flags & NV_CONTROL_RUNNING) || slot >= 20)
		return;
	nv_provenance_program(slot);
	if (!program((unsigned)slot, &kind, &script, &base)) return;
	offset = pointer(0x2026 + 4 * (unsigned)slot);
	if (offset < base)
		return;
	nv_game_program(kind, nv_control.game_globals[0x19f9], script, offset - base);
}

void nv_dialogue_capture(void) {
	NvU8 *g = nv_control.game_globals;
	NvU16 slot;
	NvU32 source, base, program_base;
	nv_dialogue_valid = 0;
	nv_provenance_reset();
	if (!(nv_control.flags & NV_CONTROL_RUNNING))
		return;
	slot = g[0x2024];
	if (slot >= 20)
		return;
	source = pointer(0x59f2);
	base = pointer(0x5a56);
	if (!source || !base || source < base)
		return;
	context.room = g[0x19f8];
	context.resource_room = g[0x19f9];
	if (!program(slot, &context.kind, &context.script, &program_base) || source - base < program_base)
		return;
	context.message_offset = source - base - program_base;
	context.origin[0] = 0;
	next_segment = 0;
	nv_dialogue_valid = 1;
	++nv_dialogue_captures;
}

void nv_dialogue_segment(void) {
	NvU8 *g = nv_control.game_globals;
	unsigned cursor, length = 0;
	NvU8 value;
	if (!nv_dialogue_valid || !(nv_control.flags & NV_CONTROL_RUNNING))
		return;
	context.actor = word(0x3a8e);
	context.segment = next_segment++;
	cursor = g[0x59f6];
	nv_provenance_origin(cursor, context.origin, NATIVE_ORIGIN_BYTES);
	while (cursor < 256 && length < NATIVE_TEXT_BYTES) {
		value = g[0x5ed4 + cursor++];
		if (!value)
			break;
		if (value == 0xff || value == 0xfe) {
			if (cursor >= 256)
				break;
			value = g[0x5ed4 + cursor++];
			if (value == 2 || value == 3)
				break;
			context.text[length++] = 0xff;
			context.text[length++] = value;
			if (value == 9 || value == 12 || value == 13 || value == 14) {
				if (cursor + 2 > 256 || length + 2 > NATIVE_TEXT_BYTES)
					return;
				context.text[length++] = g[0x5ed4 + cursor++];
				context.text[length++] = g[0x5ed4 + cursor++];
			}
			continue;
		}
		context.text[length++] = value;
	}
	context.text_length = length;
	if (length) {
		nv_game_play(&context);
		++nv_dialogue_segments;
	}
}

NvU32 nv_dialogue_display(void) {
	if (!(nv_control.flags & NV_CONTROL_RUNNING))
		return 0;
	nv_game_poll();
	if (nv_dialogue_valid && nv_control.game_globals[0x19f8] != context.room) {
		nv_game_cancel();
		nv_dialogue_valid = 0;
	}
	nv_driver_service();
	if (nv_game_active()) {
		++nv_dialogue_holds;
		return 1;
	}
	return 0;
}

void nv_dialogue_stop(void) {
	if (nv_control.flags & NV_CONTROL_RUNNING) {
		nv_game_cancel();
		++nv_dialogue_cancels;
	}
}
