/* Local native experiment, GPL-3.0-or-later. */
#include "native_driver.h"
#include "native_provenance.h"
#include "native_lookup.h"

#define RESOURCE_LIMIT 183
#define FRAME_LIMIT 16
#define SPAN_LIMIT 32

struct NvOrigin { struct NvSite site, caller; };
struct NvPending { struct NvOrigin origin; NvU16 index; };
struct NvSpan { struct NvOrigin origin; NvU16 start, end; };
struct NvFrame { struct NvOrigin origin; NvU16 start, embedded; };
static struct NvOrigin origins[RESOURCE_LIMIT];
static struct NvSite callers[20];
static struct NvSite opcodes[20];
static struct NvPending pending[FRAME_LIMIT];
static struct NvSpan spans[SPAN_LIMIT];
static struct NvFrame frames[FRAME_LIMIT];
static NvU16 pending_depth, frame_depth, span_count, expansion_failed;

static void copy_site(struct NvSite *out, const struct NvSite *in) {
	out->kind = in->kind; out->resource_room = in->resource_room;
	out->script = in->script; out->valid = in->valid; out->offset = in->offset;
}
static void copy_origin(struct NvOrigin *out, const struct NvOrigin *in) {
	copy_site(&out->site, &in->site); copy_site(&out->caller, &in->caller);
}
static int same_site(const struct NvSite *a, const struct NvSite *b) {
	return a->valid == b->valid && (!a->valid || (a->kind == b->kind &&
		a->resource_room == b->resource_room && a->script == b->script && a->offset == b->offset));
}
static int same_origin(const struct NvOrigin *a, const struct NvOrigin *b) {
	return same_site(&a->site, &b->site) && same_site(&a->caller, &b->caller);
}
static NvU32 pointer(unsigned offset) {
	return *(volatile NvU32 *)(nv_control.game_globals + offset);
}
static int resource_from_source(NvU32 source) {
	unsigned i;
	if (!source) return -1;
	for (i = 0; i < RESOURCE_LIMIT; ++i) {
		NvU32 value = pointer(0x2780 + 4 * i);
		if (value && value + 6 == source) return (int)i;
	}
	return -1;
}

void nv_provenance_reset(void) {
	frame_depth = span_count = expansion_failed = 0;
}

void nv_provenance_program(NvU32 slot) {
	NvU8 *g = nv_control.game_globals;
	NvU16 caller;
	if (!(nv_control.flags & NV_CONTROL_RUNNING) || slot >= 20) return;
	callers[slot].valid = 0;
	caller = g[0x2024];
	if (caller < 20) nv_game_site(caller, pointer(0x5a50), &callers[slot]);
	opcodes[slot].valid = 0;
}

void nv_definition_begin(void) {
	NvU16 slot;
	NvU32 next, current, base;
	if (!(nv_control.flags & NV_CONTROL_RUNNING)) return;
	slot = nv_control.game_globals[0x2024];
	if (slot >= 20) return;
 opcodes[slot].valid = 0;
 next = pointer(0x66fa);
 current = pointer(0x5a50);
 base = pointer(0x5a56);
 if (base && next > base && current >= next)
  nv_game_site(slot, next - 1, &opcodes[slot]);
}

void nv_resource_begin(NvU32 index, NvU32 source) {
	struct NvPending *p;
	NvU16 slot;
	int old;
	if (!(nv_control.flags & NV_CONTROL_RUNNING)) return;
	if (pending_depth >= FRAME_LIMIT) { ++pending_depth; return; }
	p = &pending[pending_depth++];
	p->index = index < RESOURCE_LIMIT ? (NvU16)index : RESOURCE_LIMIT;
	p->origin.site.valid = p->origin.caller.valid = 0;
	if (p->index == RESOURCE_LIMIT) return;
	if (!source) {
		slot = nv_control.game_globals[0x2024];
		if (slot < 20) {
			/* CCC2 enters before clearing/allocating: PC points at literal text. */
			nv_game_site(slot, pointer(0x5a50), &p->origin.site);
			copy_site(&p->origin.caller, &callers[slot]);
		}
	} else {
		old = resource_from_source(source);
		if (old >= 0) copy_origin(&p->origin, &origins[old]);
	}
}

void nv_resource_end(void) {
	struct NvPending *p;
	if (!(nv_control.flags & NV_CONTROL_RUNNING) || !pending_depth) return;
	if (--pending_depth >= FRAME_LIMIT) return;
	p = &pending[pending_depth];
	if (p->index < RESOURCE_LIMIT && pointer(0x2780 + 4 * p->index))
		copy_origin(&origins[p->index], &p->origin);
}

void nv_resource_clear(NvU32 index) {
	if (index < RESOURCE_LIMIT) origins[index].site.valid = 0;
}

void nv_resource_mutate(NvU32 string_id) {
	if (string_id < 50) nv_resource_clear(string_id + 133);
}

void nv_conversion_begin(NvU32 source) {
	struct NvFrame *f;
	NvU32 start, buffer;
	int resource;
	if (!(nv_control.flags & NV_CONTROL_RUNNING)) return;
	if (frame_depth >= FRAME_LIMIT) { ++frame_depth; expansion_failed = 1; return; }
	f = &frames[frame_depth++];
	f->origin.site.valid = 0;
	f->embedded = 0;
	buffer = (NvU32)(nv_control.game_globals + 0x5ed4);
	start = pointer(0x5ed0);
	if (start < buffer || start >= buffer + 256) return;
	f->start = (NvU16)(start - buffer);
	resource = resource_from_source(source);
	if (resource >= 0) { f->embedded = 1; copy_origin(&f->origin, &origins[resource]); }
}

void nv_conversion_end(void) {
	struct NvFrame *f;
	struct NvSpan *s;
	NvU32 end, buffer;
	if (!(nv_control.flags & NV_CONTROL_RUNNING) || !frame_depth) return;
	if (--frame_depth >= FRAME_LIMIT) return;
	f = &frames[frame_depth];
	if (!f->embedded) return;
	buffer = (NvU32)(nv_control.game_globals + 0x5ed4);
	end = pointer(0x5ed0);
	if (end < buffer + f->start || end > buffer + 256) { expansion_failed = 1; return; }
	if (span_count == SPAN_LIMIT) { expansion_failed = 1; return; }
	s = &spans[span_count++];
	copy_origin(&s->origin, &f->origin);
	s->start = f->start; s->end = (NvU16)(end - buffer);
}

static unsigned segment_at(const struct NvSpan *s, unsigned position, NvU16 *cursor, NvU16 *segment) {
	unsigned at;
	NvU8 *buffer = nv_control.game_globals + 0x5ed4;
	for (at = *cursor; at < position && at < s->end; ++at) {
		if (buffer[at] != 0xff && buffer[at] != 0xfe) continue;
		if (++at >= s->end) break;
		if (buffer[at] == 2 || buffer[at] == 3) ++*segment;
		else if (buffer[at] != 1 && buffer[at] != 8) at += 2;
	}
	*cursor = (NvU16)at;
	return *segment;
}

struct NvFormat { char *output; NvU32 capacity, used; };
static void character(struct NvFormat *f, char value) {
	if (f->used + 1 < f->capacity) f->output[f->used++] = value;
	else f->used = f->capacity;
}
static void number(struct NvFormat *f, NvU32 value) {
	static const NvU32 powers[] = {1000000000UL,100000000UL,10000000UL,1000000UL,100000UL,10000UL,1000UL,100UL,10UL,1UL};
	unsigned i, digit, started = 0;
	for (i = 0; i < 10; ++i) {
		digit = 0;
		while (value >= powers[i]) { value -= powers[i]; ++digit; }
		if (digit || started || i == 9) { character(f, (char)('0' + digit)); started = 1; }
	}
}
static void site(struct NvFormat *f, const struct NvSite *s) {
	character(f, s->kind == NATIVE_GLOBAL ? 'g' : s->kind == NATIVE_LOCAL ? 'l' : s->kind == NATIVE_OBJECT ? 'o' : 'e');
	character(f, ':');
	if (s->kind == NATIVE_LOCAL || s->kind == NATIVE_ENCD || s->kind == NATIVE_EXCD) {
		number(f, s->resource_room); character(f, ':');
	}
	if (s->kind == NATIVE_ENCD || s->kind == NATIVE_EXCD) {
		character(f, 'E'); character(f, s->kind == NATIVE_ENCD ? 'N' : 'X'); character(f, 'C'); character(f, 'D');
	} else number(f, s->script);
	character(f, ':'); number(f, s->offset);
}

void nv_provenance_origin(NvU32 start, char *output, NvU32 capacity) {
	NvU8 *buffer = nv_control.game_globals + 0x5ed4;
	unsigned i, at, chosen = SPAN_LIMIT, segment = 0, current;
	struct NvFormat f;
	NvU16 scan_at[SPAN_LIMIT], scan_segment[SPAN_LIMIT];
	if (!capacity) return;
	output[0] = 0;
	if (expansion_failed || start >= 256 || !span_count) return;
	for (i = 0; i < span_count; ++i) {
		scan_at[i] = spans[i].start; scan_segment[i] = 0;
	}
	for (at = (unsigned)start; at < 256; ++at) {
		NvU8 c = buffer[at];
		if (!c) break;
		if (c == 0xff || c == 0xfe) {
			if (++at >= 256) return;
			c = buffer[at];
			if (c == 2 || c == 3) break;
			if (c == 1 || c == 8) continue;
			if (c != 9 && c != 12 && c != 13 && c != 14) return;
			at += 2; continue;
		}
		if (c <= ' ' || c == '@') continue;
		for (i = 0; i < span_count; ++i) {
			if (at < spans[i].start || at >= spans[i].end) continue;
			if (!spans[i].origin.site.valid) return;
			current = segment_at(&spans[i], at, &scan_at[i], &scan_segment[i]);
			if (chosen == SPAN_LIMIT) { chosen = i; segment = current; }
			else if (!same_origin(&spans[i].origin, &spans[chosen].origin) || current != segment) return;
		}
	}
	if (chosen == SPAN_LIMIT) return;
	f.output = output; f.capacity = capacity; f.used = 0;
	if (spans[chosen].origin.caller.valid) {
		character(&f, 'c'); character(&f, ':'); site(&f, &spans[chosen].origin.caller); character(&f, ':');
	}
	character(&f, 'r'); character(&f, ':'); site(&f, &spans[chosen].origin.site);
	character(&f, ':'); number(&f, segment);
	if (f.used >= capacity) output[0] = 0;
	else output[f.used] = 0;
}

#define PROVENANCE_BYTES 5784UL
static void put_word(NvU8 **p, NvU16 value) {
	*(*p)++ = (NvU8)(value >> 8); *(*p)++ = (NvU8)value;
}
static NvU16 get_word(const NvU8 **p) {
	NvU16 value = (NvU16)((*p)[0] << 8) | (*p)[1]; *p += 2; return value;
}
static void write_site(NvU8 **p, const struct NvSite *s) {
	put_word(p, s->valid ? s->kind : 0);
	put_word(p, s->valid ? s->resource_room : 0);
	put_word(p, s->valid ? s->script : 0);
	put_word(p, s->valid ? 1 : 0);
	put_word(p, s->valid ? (NvU16)(s->offset >> 16) : 0);
	put_word(p, s->valid ? (NvU16)s->offset : 0);
}
static int read_site(const NvU8 **p, struct NvSite *s) {
	s->kind = get_word(p); s->resource_room = get_word(p);
	s->script = get_word(p); s->valid = get_word(p);
	s->offset = (NvU32)get_word(p) << 16; s->offset |= get_word(p);
	if (!s->valid) return !(s->kind || s->resource_room || s->script || s->offset);
	return s->valid == 1 && s->kind >= NATIVE_GLOBAL && s->kind <= NATIVE_EXCD &&
		s->resource_room < 256 && s->offset <= 0x7fffffffUL;
}
static void write_origin(NvU8 **p, const struct NvOrigin *o) {
	write_site(p, &o->site); write_site(p, &o->caller);
}
static int read_origin(const NvU8 **p, struct NvOrigin *o) {
	int ok = read_site(p, &o->site);
	return read_site(p, &o->caller) && ok;
}

void nv_provenance_clear(void) {
	unsigned i;
	for (i = 0; i < RESOURCE_LIMIT; ++i)
		origins[i].site.valid = origins[i].caller.valid = 0;
	for (i = 0; i < 20; ++i) callers[i].valid = opcodes[i].valid = 0;
	pending_depth = 0;
	nv_provenance_reset();
}

NvU32 nv_provenance_export(NvU8 *output, NvU32 capacity) {
	NvU8 *p = output;
	struct NvOrigin empty;
	unsigned i;
	if (!output || capacity < PROVENANCE_BYTES || pending_depth || frame_depth) return 0;
	empty.site.valid = empty.caller.valid = 0;
	put_word(&p, 0x4e56); put_word(&p, 0x4f31); put_word(&p, 1);
	put_word(&p, RESOURCE_LIMIT); put_word(&p, 20); put_word(&p, span_count);
	put_word(&p, expansion_failed ? 1 : 0); put_word(&p, 0);
	for (i = 0; i < RESOURCE_LIMIT; ++i) write_origin(&p, &origins[i]);
	for (i = 0; i < 20; ++i) write_site(&p, &callers[i]);
	for (i = 0; i < 20; ++i) write_site(&p, &opcodes[i]);
	for (i = 0; i < SPAN_LIMIT; ++i) {
		write_origin(&p, i < span_count ? &spans[i].origin : &empty);
		put_word(&p, i < span_count ? spans[i].start : 0);
		put_word(&p, i < span_count ? spans[i].end : 0);
	}
	return (NvU32)(p - output);
}

int nv_provenance_import(const NvU8 *input, NvU32 bytes, int apply) {
	const NvU8 *p = input;
	struct NvOrigin origin;
	struct NvSite value;
	NvU16 count, failed, start, end;
	unsigned i;
	if (!input || bytes != PROVENANCE_BYTES) return 0;
	if (get_word(&p) != 0x4e56 || get_word(&p) != 0x4f31 || get_word(&p) != 1 ||
		get_word(&p) != RESOURCE_LIMIT || get_word(&p) != 20) return 0;
	count = get_word(&p); failed = get_word(&p);
	if (count > SPAN_LIMIT || failed > 1 || get_word(&p)) return 0;
	for (i = 0; i < RESOURCE_LIMIT; ++i) {
		if (!read_origin(&p, &origin)) return 0;
		if (apply) {
			copy_origin(&origins[i], &origin);
			if (!pointer(0x2780 + 4 * i)) origins[i].site.valid = origins[i].caller.valid = 0;
		}
	}
	for (i = 0; i < 40; ++i) {
		if (!read_site(&p, &value)) return 0;
		if (apply) copy_site(i < 20 ? &callers[i] : &opcodes[i - 20], &value);
	}
	for (i = 0; i < SPAN_LIMIT; ++i) {
		if (!read_origin(&p, &origin)) return 0;
		start = get_word(&p); end = get_word(&p);
		if (start > end || end > 256 || (i >= count && (start || end || origin.site.valid || origin.caller.valid))) return 0;
		if (apply) { copy_origin(&spans[i].origin, &origin); spans[i].start = start; spans[i].end = end; }
	}
	if (apply) { span_count = count; expansion_failed = failed; pending_depth = frame_depth = 0; }
	return 1;
}
