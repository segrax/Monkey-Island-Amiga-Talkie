#include "art_game.h"
#include "native_driver.h"
#include <stddef.h>
typedef char ArtDecodeLayout[(sizeof(struct NvArtDecode)==28 &&
 offsetof(struct NvArtDecode,height)==24 && sizeof(struct NvArtC2p)==12 &&
 offsetof(struct NvArtObjectGate,slots)==2)?1:-1];
#ifdef NV_ART_COSTUME_CACHE
#include "cache_manager.h"
#endif

#define GLOBAL_BYTES 29312UL
extern NvU8 *nv_art_exec(void);
extern NvU32 nv_art_dos;
struct NvArtDecode nv_art_decode;
NvU16 nv_art_decode_ready;
struct NvArtC2p nv_art_c2p;
struct NvArtObjectGate nv_art_object_gate;
static struct {
	NvU32 regions[8][2], source, source_bytes;
	NvU32 owner, owner_bytes;
	NvU16 count, active, room, object, slot;
 struct {NvU32 stack,globals,code;NvU16 active,warm;} batch;
	struct {
		NvU32 primary, primary_bytes, backup, backup_bytes, mask, mask_bytes;
		NvU32 source, source_bytes, owner, owner_bytes, lut, stack, generation;
		NvU16 valid;
	} surfaces;
	struct {
		NvU32 primary, primary_bytes, bitmap, lut, stack, generation;
		NvU16 valid;
	} display;
} game;

static NvU16 word(const NvU8 *p) {
#ifdef __VBCC__
	if (!((NvU32)p & 1))
		return *(const NvU16 *)p;
#endif
	return ((NvU16)p[0] << 8) | p[1];
}
static NvU32 number(const NvU8 *p) {
#ifdef __VBCC__
	if (!((NvU32)p & 1))
		return *(const NvU32 *)p;
#endif
	return ((NvU32)word(p) << 16) | word(p + 2);
}
static NvU32 little(const NvU8 *p) {
	return p[0] | ((NvU32)p[1] << 8) | ((NvU32)p[2] << 16) | ((NvU32)p[3] << 24);
}
static int ram(NvU32 p, NvU32 n) {
	NvU16 i;
	if (!n || n > 0xFFFFFFFFUL - p)
		return 0;
	for (i = 0; i < game.count; ++i)
		if (p >= game.regions[i][0] && p + n <= game.regions[i][1])
			return 1;
	return 0;
}
static int overlap(NvU32 p, NvU32 n, NvU32 q, NvU32 m) {
	return p < q + m && q < p + n;
}
static int protected(NvU32 p, NvU32 n, NvU32 stack) {
	NvU32 arena = (NvU32)nv_art.arena;
	if (!n || p + n < p)
		return 1;
#ifdef NV_ART_COSTUME_CACHE
	if (nv_costume_cache_overlap(p, n))
		return 1;
#endif
	return overlap(p, n, arena, NV_ART_CAPACITY) ||
	       overlap(p, n, (NvU32)nv_control.game_globals, GLOBAL_BYTES) ||
	       overlap(p, n, (NvU32)nv_control.game_code, 98800) ||
	       overlap(p, n, (NvU32)&nv_control, sizeof(nv_control)) ||
	       overlap(p, n, (NvU32)&game, sizeof(game)) ||
	       overlap(p, n, (NvU32)&nv_art_decode, sizeof(nv_art_decode)) ||
	       overlap(p, n, (NvU32)&nv_art_decode_ready, sizeof(nv_art_decode_ready)) ||
	       overlap(p, n, (NvU32)&nv_art_c2p, sizeof(nv_art_c2p)) ||
	       overlap(p, n, (NvU32)&nv_art_object_gate, sizeof(nv_art_object_gate)) ||
	       overlap(p, n, (NvU32)&nv_art_dos, sizeof(nv_art_dos)) ||
	       overlap(p, n, stack - 4096, 8192) || nv_art_runtime_overlap(p, n);
}
static int owned(NvU32 base, NvU16 type, NvU16 id, NvU32 *bytes) {
	const NvU8 *p = (const NvU8 *)base;
	NvU32 prior = 0;
	/* Reuse only an existing, fully validated span; never publish state here. */
	if (type == 3 && game.active && base == game.owner && id == game.room)
		prior = game.owner_bytes;
	else if (type == 4) {
		if (game.surfaces.valid) {
			if (id == 1 && base == game.surfaces.primary)
				prior = game.surfaces.primary_bytes;
			else if (id == 5 && base == game.surfaces.backup)
				prior = game.surfaces.backup_bytes;
			else if (id == 9 && base == game.surfaces.mask)
				prior = game.surfaces.mask_bytes;
		}
		if (!prior && id == 1 && game.display.valid && base == game.display.primary)
			prior = game.display.primary_bytes;
	}
	if (prior && p[4] == type && p[5] == id && little(p) == prior) {
		*bytes = prior;
		return 1;
	}
	if (!ram(base, 6) || p[4] != type || p[5] != id)
		return 0;
	*bytes = little(p);
	return *bytes >= 6 && ram(base, *bytes);
}

void nv_art_game_scope_cancel(void) {
 game.batch.active = game.batch.warm = 0;
}
void nv_art_game_scope_begin(NvU32 stack) {
 nv_art_game_scope_cancel();
 if (!nv_art.enabled || !game.active || stack < 4096 || stack > 0xFFFFDFFFUL ||
     !ram(stack - 4096, 8192) || !ram((NvU32)nv_control.game_globals, GLOBAL_BYTES))
  return;
 game.batch.stack = stack;
 game.batch.globals = (NvU32)nv_control.game_globals;
 game.batch.code = (NvU32)nv_control.game_code;
 game.batch.active = 1;
}
static int batch_match(NvU32 stack) {
 return game.batch.active && stack == game.batch.stack - 58 &&
  game.batch.globals == (NvU32)nv_control.game_globals &&
  game.batch.code == (NvU32)nv_control.game_code &&
  number((const NvU8 *)(stack + 48)) == game.batch.code + 0x51F8;
}

void nv_art_game_start(void) {
	NvU8 *exec = nv_art_exec(), *node;
	NvU16 i = 0;
 nv_art_game_scope_cancel();
	if (game.count)
		return;
	nv_art_object_gate.room = 65535;
	node = (NvU8 *)number(exec + 322);
	while (node && number(node) && i++ < 64) {
		NvU32 low = number(node + 20), high = number(node + 24);
		if (low < high && game.count < 8) {
			game.regions[game.count][0] = low;
			game.regions[game.count++][1] = high;
		}
		node = (NvU8 *)number(node);
	}
	if (game.count)
		nv_art_start();
}
void nv_art_game_stop(void) {
 nv_art_game_scope_cancel();
	nv_art_decode_ready = 0;
	game.active = 0;
	game.surfaces.valid = game.display.valid = 0;
	nv_art_stop();
	game.count = 0;
	nv_art_object_gate.room = 65535;
}

void nv_art_game_room(void) {
 nv_art_game_scope_cancel();
	nv_art_decode_ready = 0;
	game.active = 0;
	game.surfaces.valid = game.display.valid = 0;
	nv_art_room(nv_control.game_globals[0x19F9]);
}

void nv_art_game_prewarm(NvU32 room, NvU32 stack) {
	NvU8 *g = nv_control.game_globals;
	NvU32 table, owner, bytes;
	NvU16 count;
 nv_art_game_scope_cancel();
	if (!nv_art.enabled || nv_art_warm.done || nv_art_decode_ready || game.active ||
	    room > 255 || stack < 4096 || stack > 0xFFFFDFFFUL ||
	    !ram((NvU32)g, GLOBAL_BYTES))
		return;
	count = word(g + 0x235A);
	table = number(g + 0x2368);
	if (room >= count || !ram(table, (NvU32)count * 4))
		return;
	owner = number((const NvU8 *)table + room * 4);
	if (!owned(owner, 3, (NvU16)room, &bytes) || protected(owner, bytes, stack))
		return;
	nv_art_prewarm(room);
}

void nv_art_game_object(NvU32 stack) {
	NvU8 *g = nv_control.game_globals;
	NvU32 table, base, bytes, offset, source, length;
	NvU16 room, slot, count, object;
 nv_art_game_scope_cancel();
	/* All these hooks execute in the original game task, outside IRQs. */
	if (!nv_art.enabled || !ram((NvU32)g, GLOBAL_BYTES) || stack < 4096 || stack > 0xFFFFDFFFUL)
		return;
	room = g[0x19F9];
	slot = g[0x68E8];
	count = word(g + 0x235A);
	table = number(g + 0x2368);
	if (!slot || slot >= 70 || room >= count || !ram(table, (NvU32)count * 4))
		return;
	base = number((const NvU8 *)table + room * 4UL);
	if (!owned(base, 3, room, &bytes) || protected(base, bytes, stack))
		return;
	offset = number(g + 0x1DAE + slot * 4UL);
	if (offset < 14 || offset > bytes)
		return;
	source = base + offset - 8;
	length = little((const NvU8 *)source);
	if (length < 16 || length > bytes - offset + 8 ||
	    ((const NvU8 *)source)[4] != 'O' || ((const NvU8 *)source)[5] != 'I')
		return;
	object = ((const NvU8 *)source)[6] | ((NvU16)((const NvU8 *)source)[7] << 8);
	/* Clear old decode eligibility before any allocation, I/O or payload reuse. */
	nv_art_decode_ready = 0;
	game.active = 0;
	game.surfaces.valid = game.display.valid = 0;
	if (nv_art_object_gate.room != room) {
		NvU16 i;
		for (i = 0; i < 70; ++i)
			nv_art_object_gate.slots[i] = 0;
		nv_art_object_gate.room = room;
	}
	nv_art_object_gate.slots[slot] = 1;
	if (!nv_art_object(room, object, slot) || length != nv_art.image.source_bytes)
		return;
	game.source = source;
	game.source_bytes = length;
	game.owner = base;
	game.owner_bytes = bytes;
	game.room = room;
	game.object = object;
	game.slot = slot;
	game.active = 1;
}

void nv_art_game_bind(NvU32 strip, NvU32 stack) {
	NvU8 *g = nv_control.game_globals;
	NvU32 primary, backup, mask, pn, bn, mn, primary_bytes, backup_bytes, mask_bytes;
	NvU32 primary_base, backup_base, mask_base, codec, offset, table, lut;
	NvU16 height, y, x, camera, column;
	const NvU8 *descriptor;
	struct NvArtDecode context;
 int scoped = batch_match(stack);
 int warm = scoped && game.batch.warm;
 if (game.batch.active && !scoped) nv_art_game_scope_cancel();
	if (!nv_art.enabled || !game.active || strip >= nv_art.image.columns ||
	    (!warm && (stack < 4096 || stack > 0xFFFFDFFFUL || !ram((NvU32)g, GLOBAL_BYTES))))
		goto rejected;
	if (!warm) {
	/* Ownership is rechecked even when an earlier object hook declined. */
	table = number(g + 0x2368);
	if (g[0x19F9] != game.room || g[0x68E8] != game.slot || game.room >= word(g + 0x235A) ||
	    !ram(table, (NvU32)word(g + 0x235A) * 4) ||
	    number((const NvU8 *)table + game.room * 4UL) != game.owner ||
	    !owned(game.owner, 3, game.room, &primary_bytes) || primary_bytes != game.owner_bytes ||
	    game.source - game.owner != number(g + 0x1DAE + game.slot * 4UL) - 8 ||
	    little((const NvU8 *)game.source) != game.source_bytes ||
	    (((const NvU8 *)game.source)[6] | ((NvU16)((const NvU8 *)game.source)[7] << 8)) != game.object)
		goto rejected;
	}
	height = g[0x5C38];
	y = word(g + 0x5C34);
	x = word(g + 0x5C32);
	camera = word(g + 0x5992);
	if (word(g + 0x5D40) || height != nv_art.image.height || y > 200 - height ||
	    x < camera || x - camera >= 40)
		goto rejected;
	column = x - camera;
 if (warm) {
  primary_base = game.surfaces.primary; primary_bytes = game.surfaces.primary_bytes;
  backup_base = game.surfaces.backup; backup_bytes = game.surfaces.backup_bytes;
  mask_base = game.surfaces.mask; mask_bytes = game.surfaces.mask_bytes;
 } else {
	primary_base = number(g + 0x2784);
	backup_base = number(g + 0x2794);
	mask_base = number(g + 0x27A4);
	if (!owned(primary_base, 4, 1, &primary_bytes) || !owned(backup_base, 4, 5, &backup_bytes) ||
	    !owned(mask_base, 4, 9, &mask_bytes))
		goto rejected;
 }
	pn = primary_base + 6 + (NvU32)y * 320 + x * 8UL;
	bn = backup_base + 6 + (NvU32)y * 320 + x * 8UL;
	mn = mask_base + 6 + (NvU32)y * 40 + x;
	primary = number(g + 0x5C1E);
	backup = number(g + 0x5C1A);
	/* Mask pointer is assigned later in the original strip setup. */
	mask = mn;
	if (primary != pn || backup != bn)
		goto rejected;
	pn = (NvU32)(height - 1) * 320 + 8;
	bn = pn;
	mn = (NvU32)(height - 1) * 40 + 1;
	lut = warm ? game.surfaces.lut : number(g + 0x16F8);
	if (!warm && (!game.surfaces.valid || game.surfaces.primary != primary_base ||
	    game.surfaces.primary_bytes != primary_bytes || game.surfaces.backup != backup_base ||
	    game.surfaces.backup_bytes != backup_bytes || game.surfaces.mask != mask_base ||
	    game.surfaces.mask_bytes != mask_bytes || game.surfaces.lut != lut ||
	    game.surfaces.stack != stack || game.surfaces.source != game.source ||
	    game.surfaces.source_bytes != game.source_bytes || game.surfaces.owner != game.owner ||
	    game.surfaces.owner_bytes != game.owner_bytes || game.surfaces.generation != nv_art.loads)) {
		game.surfaces.valid = 0;
		if (protected(primary_base, primary_bytes, stack) ||
		    protected(backup_base, backup_bytes, stack) || protected(mask_base, mask_bytes, stack) ||
		    overlap(primary_base, primary_bytes, backup_base, backup_bytes) ||
		    overlap(primary_base, primary_bytes, mask_base, mask_bytes) ||
		    overlap(backup_base, backup_bytes, mask_base, mask_bytes) ||
		    overlap(primary_base, primary_bytes, game.source, game.source_bytes) ||
		    overlap(backup_base, backup_bytes, game.source, game.source_bytes) ||
		    overlap(mask_base, mask_bytes, game.source, game.source_bytes) ||
		    !ram(lut, 24576) || overlap(primary_base, primary_bytes, lut, 24576) ||
		    overlap(backup_base, backup_bytes, lut, 24576) || overlap(mask_base, mask_bytes, lut, 24576))
			goto rejected;
		game.surfaces.primary = primary_base;
		game.surfaces.primary_bytes = primary_bytes;
		game.surfaces.backup = backup_base;
		game.surfaces.backup_bytes = backup_bytes;
		game.surfaces.mask = mask_base;
		game.surfaces.mask_bytes = mask_bytes;
		game.surfaces.source = game.source;
		game.surfaces.source_bytes = game.source_bytes;
		game.surfaces.owner = game.owner;
		game.surfaces.owner_bytes = game.owner_bytes;
		game.surfaces.lut = lut;
		game.surfaces.stack = stack;
		game.surfaces.generation = nv_art.loads;
		game.surfaces.valid = 1;
	}
	if (primary < primary_base || primary > primary_base + primary_bytes || pn > primary_base + primary_bytes - primary ||
	    backup < backup_base || backup > backup_base + backup_bytes || bn > backup_base + backup_bytes - backup ||
	    mask < mask_base || mask > mask_base + mask_bytes || mn > mask_base + mask_bytes - mask)
		goto rejected;
	descriptor = nv_art.image.strips + strip * 8;
	offset = number(descriptor);
	codec = number(g + 0x5C2A);
	if (codec != game.source + offset || ((const NvU8 *)codec)[0] != 10 ||
	    !nv_art_bind(column, (NvU8 *)primary, (const NvU8 *)codec,
	    (const NvU8 *)game.source, game.source_bytes, strip))
		goto rejected;
	context.dictionary = nv_art.image.dictionary;
	context.indices = nv_art.image.indices + strip * height * 2;
	context.codec = nv_art.image.source + offset;
	context.end = context.codec + word(descriptor + 4);
	context.dependencies = nv_art.image.dependencies + strip * ((height + 7) / 8);
	context.palette = nv_art.image.palette;
	context.height = height;
	context.reserved = 0;
	nv_art_decode = context;
	nv_art_decode_ready = 1;
 if (scoped && !warm) {
  NvU32 table_bytes = (NvU32)word(g + 0x235A) * 4;
  if (protected(table, table_bytes, stack) ||
      overlap(table, table_bytes, primary_base, primary_bytes) ||
      overlap(table, table_bytes, backup_base, backup_bytes) ||
      overlap(table, table_bytes, mask_base, mask_bytes))
   nv_art_game_scope_cancel();
  else game.batch.warm = 1;
 }
	return;
rejected:
 nv_art_game_scope_cancel();
	nv_art_decode_ready = 0;
	game.surfaces.valid = 0;
}

int nv_art_game_c2p(const NvU8 *source, NvU8 *destination, NvU32 height, NvU32 stack) {
	NvU8 *g = nv_control.game_globals;
	NvU32 src = (NvU32)source, dst = (NvU32)destination, bytes, base, span, lut, bitmap, delta;
	NvU16 flip, prefix, rows;
	const NvU8 *indices;
	if (!nv_art.enabled || !height || height > 200 || (src & 1) ||
	    stack < 4096 || stack > 0xFFFFDFFFUL || !ram((NvU32)g, GLOBAL_BYTES))
		goto rejected;
	if (g[0x19F9] != nv_art.room) {
		nv_art_game_room();
		goto rejected;
	}
	indices = nv_art_c2p_span(word(g + 0x5EBE), source, height,
	                          &prefix, &rows);
	if (!indices)
		goto rejected;
	base = number(g + 0x2784);
	span = (height - 1) * 320 + 8;
	flip = g[0x16F5];
	if (flip > 1)
		goto rejected;
	bitmap = number(g + 0x706E + flip * 4UL);
	if (bitmap != number(g + (flip ? 0x7016 : 0x6FEE)) || !ram(bitmap, 40000) || dst < bitmap)
		goto rejected;
	delta = dst - bitmap;
	if (delta >= 8000 || (height - 1) * 40 + 1 > 8000 - delta)
		goto rejected;
	if (!owned(base, 4, 1, &bytes) || src < base + 6 || src > base + bytes ||
	    span > base + bytes - src)
		goto rejected;
	lut = number(nv_control.game_code + 0x154B8);
	if (lut != number(g + 0x16F8))
		goto rejected;
	if (!game.display.valid || game.display.primary != base || game.display.primary_bytes != bytes ||
	    game.display.bitmap != bitmap || game.display.lut != lut || game.display.stack != stack ||
	    game.display.generation != nv_art.loads) {
		game.display.valid = 0;
		if (protected(base, bytes, stack) || protected(bitmap, 40000, stack) ||
		    overlap(bitmap, 40000, base, bytes) || !ram(lut, 24576) ||
		    overlap(bitmap, 40000, lut, 24576))
			goto rejected;
		game.display.primary = base;
		game.display.primary_bytes = bytes;
		game.display.bitmap = bitmap;
		game.display.lut = lut;
		game.display.stack = stack;
		game.display.generation = nv_art.loads;
		game.display.valid = 1;
	}
	++nv_art.c2p_hits;
	nv_art_c2p.dictionary = nv_art.image.dictionary;
	nv_art_c2p.indices = indices;
	nv_art_c2p.prefix = prefix;
	nv_art_c2p.rows = rows;
	return 1;
rejected:
	game.display.valid = 0;
	return 0;
}
