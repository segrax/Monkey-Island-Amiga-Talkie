#include "art_runtime.h"
#ifdef __VBCC__
#include <stddef.h>
typedef char ArtStateLayout[(offsetof(struct NvArtState,enabled)==80 && offsetof(struct NvArtWarm,done)==24)?1:-1];
#endif

extern NvU8 *nv_art_alloc(NvU32 bytes);
#ifdef NV_ART_ALLOW_CHIP
extern NvU8 *nv_art_alloc_any(NvU32 bytes);
#endif
extern void nv_art_free(NvU8 *memory, NvU32 bytes);
extern NvU32 nv_art_file_open(void);
extern void nv_art_file_close(NvU32 file);
extern NvS32 nv_art_read_at(NvU32 file, NvU32 offset, void *buffer, NvU32 bytes);
#ifdef __VBCC__
extern NvU16 nv_art_row(NvU32 offset);
#else
static NvU16 nv_art_row(NvU32 offset) { return (NvU16)(offset / 320); }
#endif

struct NvArtState nv_art;
struct NvArtWarm nv_art_warm;
static NvU16 payload_room, payload_object, prefilled;
NvU8 nv_art_columns[40];
static NvU32 file, entries, file_bytes, data_offset, score;
static NvU8 *index_cache;
struct Lookup {
	NvU16 room, object;
	NvU32 offset, bytes, checksum;
	NvU16 width, height;
};
struct Binding {
	const NvU8 *primary, *indices;
	NvU16 height, reserved;
};
static struct Lookup recent[16];
static struct Binding bindings[40];
static NvU16 next_recent;
static NvU16 slot_ids[70];
static NvU16 object_active;

static int storage_overlap(NvU32 p, NvU32 n, const void *storage, NvU32 bytes) {
#ifdef __VBCC__
	NvU32 base = (NvU32)storage;
#else
	NvU32 base = (NvU32)(uintptr_t)storage;
#endif
	return p < base + bytes && base < p + n;
}

int nv_art_runtime_overlap(NvU32 p, NvU32 n) {
	return storage_overlap(p, n, &nv_art_warm, sizeof(nv_art_warm)) ||
	       storage_overlap(p, n, &payload_room, sizeof(payload_room)) ||
	       storage_overlap(p, n, &payload_object, sizeof(payload_object)) ||
	       storage_overlap(p, n, &prefilled, sizeof(prefilled)) ||
	       storage_overlap(p, n, &nv_art, sizeof(nv_art)) ||
	       storage_overlap(p, n, nv_art_columns, sizeof(nv_art_columns)) ||
	       storage_overlap(p, n, &index_cache, sizeof(index_cache)) ||
	       (index_cache && storage_overlap(p, n, index_cache, entries * 24)) ||
	       storage_overlap(p, n, &file, sizeof(file)) ||
	       storage_overlap(p, n, &entries, sizeof(entries)) ||
	       storage_overlap(p, n, &file_bytes, sizeof(file_bytes)) ||
	       storage_overlap(p, n, &data_offset, sizeof(data_offset)) ||
	       storage_overlap(p, n, &score, sizeof(score)) ||
	       storage_overlap(p, n, recent, sizeof(recent)) ||
	       storage_overlap(p, n, bindings, sizeof(bindings)) ||
	       storage_overlap(p, n, slot_ids, sizeof(slot_ids)) ||
	       storage_overlap(p, n, &next_recent, sizeof(next_recent)) ||
	       storage_overlap(p, n, &object_active, sizeof(object_active));
}

static NvU16 word(const NvU8 *p) {
	return ((NvU16)p[0] << 8) | p[1];
}
static NvU32 number(const NvU8 *p) {
	return ((NvU32)word(p) << 16) | word(p + 2);
}
static void clear_bindings(void) {
	NvU16 i;
	for (i = 0; i < 40; ++i)
		bindings[i].height = nv_art_columns[i] = 0;
}

void nv_art_stop(void) {
	clear_bindings();
	nv_art.enabled = 0;
	object_active = 0;
	payload_room = payload_object = 65535;
	prefilled = 0;
	if (index_cache) {
		nv_art_free(index_cache, entries * 24);
		index_cache = 0;
	}
	if (nv_art.arena) {
		nv_art_free(nv_art.arena, NV_ART_CAPACITY);
		nv_art.arena = 0;
	}
	nv_art_file_close(file);
	file = 0;
}

void nv_art_start(void) {
	NvU8 header[32];
	NvU16 i;
	/* This hook runs once before the original game reserves its heap. */
	++nv_art.starts;
	if (nv_art.arena || file)
		return;
	nv_art.reserved = 1;
	file = nv_art_file_open();
	if (!file)
		goto failed;
	nv_art.reserved = 2;
	if (nv_art_read_at(file, 0, header, 32) != 32)
		goto failed;
	nv_art.reserved = 3;
	for (i = 0; i < 8; ++i)
		if (header[i] != (NvU8)"NVPART01"[i])
			goto failed;
	entries = number(header + 12);
	data_offset = number(header + 20);
	file_bytes = number(header + 24);
	if (word(header + 8) != 1 || word(header + 10) != 24 ||
	    number(header + 16) != 32 || number(header + 28) || !entries ||
	    entries > 65535 || data_offset != 32 + entries * 24 ||
	    file_bytes < data_offset || file_bytes > 0x7FFFFFFFUL)
		goto failed;
	nv_art.reserved = 4;
	nv_art.arena = nv_art_alloc(NV_ART_CAPACITY);
#ifdef NV_ART_ALLOW_CHIP
	if (!nv_art.arena)
		nv_art.arena = nv_art_alloc_any(NV_ART_CAPACITY);
#endif
	if (!nv_art.arena)
		goto failed;
	/* Optional early metadata prefetch removes object-time DOS searches. */
	if (entries <= 16384UL / 24) {
		index_cache = nv_art_alloc(entries * 24);
		nv_art.reserved = 5;
		if (index_cache && nv_art_read_at(file, 32, index_cache, entries * 24) != (NvS32)(entries * 24))
			goto failed;
	}
	for (i = 0; i < 16; ++i)
		recent[i].room = 65535;
	next_recent = 0;
	nv_art.room = 65535;
	nv_art.object = 65535;
	nv_art.enabled = 1;
#ifdef __VBCC__
	nv_art.reserved = (NvU32)nv_art.arena < 0x200000UL ? 256 : 0;
#else
	nv_art.reserved = 0;
#endif
	score = 0;
	payload_room = payload_object = 65535;
	prefilled = 0;
	for (i = 0; i < sizeof(nv_art_warm); ++i)
		((NvU8 *)&nv_art_warm)[i] = 0;
	nv_art_warm.room = nv_art_warm.object = 65535;
	return;
failed:
	nv_art_stop();
}

static int find(NvU16 room, NvU16 object, struct Lookup *result) {
	NvU8 buffer[24];
	const NvU8 *entry;
	NvU32 first = 0, end = entries, mid, key = ((NvU32)room << 16) | object;
	NvU16 i;
	for (i = 0; i < 16; ++i)
		if (recent[i].room == room && recent[i].object == object) {
			*result = recent[i];
			return result->bytes != 0;
		}
	++nv_art.lookups;
	result->room = room;
	result->object = object;
	result->bytes = 0;
	while (first < end) {
		mid = first + (end - first) / 2;
		if (index_cache)
			entry = index_cache + mid * 24;
		else {
			if (nv_art_read_at(file, 32 + mid * 24, buffer, 24) != 24)
				return 0;
			entry = buffer;
		}
		if (number(entry) < key)
			first = mid + 1;
		else if (number(entry) > key)
			end = mid;
		else {
			result->offset = number(entry + 4);
			result->bytes = number(entry + 8);
			result->checksum = number(entry + 20);
			result->width = word(entry + 16);
			result->height = word(entry + 18);
			if (!result->bytes || result->bytes > NV_ART_CAPACITY || (result->bytes & 1) ||
			    (result->offset & 1) || result->offset < data_offset ||
			    result->offset > file_bytes || result->bytes > file_bytes - result->offset)
				return 0;
			break;
		}
	}
	recent[next_recent] = *result;
	next_recent = (next_recent + 1) & 15;
	return result->bytes != 0;
}

void nv_art_room(NvU32 room) {
	NvU16 i;
	if (nv_art.room != room) {
		clear_bindings();
		nv_art.room = (NvU16)room;
		nv_art.object = 65535;
		score = 0;
		object_active = 0;
		for (i = 0; i < 70; ++i)
			slot_ids[i] = 65535;
	}
}

static int load_image(const struct Lookup *found) {
	struct NvArtImage image;
	clear_bindings();
	nv_art.object = 65535;
	payload_room = payload_object = 65535;
	prefilled = 0;
	if (nv_art_read_at(file, found->offset, nv_art.arena, found->bytes) != (NvS32)found->bytes ||
	    !nv_art_validate(nv_art.arena, found->bytes, &image) ||
	    image.width != found->width || image.height != found->height) {
		++nv_art.rejects;
		nv_art_stop();
		return 0;
	}
	nv_art.image = image;
	payload_room = found->room;
	payload_object = found->object;
	++nv_art.loads;
	return 1;
}

static const NvU8 *entry_at(NvU32 index, NvU8 *buffer) {
	if (index_cache)
		return index_cache + index * 24;
	return nv_art_read_at(file, 32 + index * 24, buffer, 24) == 24 ? buffer : 0;
}

int nv_art_prewarm(NvU32 room) {
	struct Lookup best;
	NvU8 buffer[24];
	const NvU8 *entry;
	NvU32 first = 0, end = entries, mid, best_rows = 0;
	NvU16 width, height;
	if (!nv_art.enabled || room > 255 || nv_art_warm.done)
		return 0;
	++nv_art_warm.requests;
	if (nv_art_warm.seen[room >> 3] & (1 << (room & 7)))
		return 0;
	nv_art_warm.seen[room >> 3] |= (NvU8)(1 << (room & 7));
	++nv_art_warm.searches;
	while (first < end) {
		mid = first + (end - first) / 2;
		entry = entry_at(mid, buffer);
		if (!entry)
			return 0;
		if (word(entry) < room)
			first = mid + 1;
		else
			end = mid;
	}
	for (; first < entries; ++first) {
		NvU32 offset, bytes, rows;
		entry = entry_at(first, buffer);
		if (!entry || word(entry) != room)
			break;
		width = word(entry + 16);
		height = word(entry + 18);
		offset = number(entry + 4);
		bytes = number(entry + 8);
		if (!width || width > 320 || (width & 7) || !height || height > 200 ||
		    !bytes || bytes > NV_ART_CAPACITY || (bytes & 1) || (offset & 1) ||
		    offset < data_offset || offset > file_bytes || bytes > file_bytes - offset)
			continue;
		rows = (NvU32)(width / 8) * height;
		if (rows <= best_rows)
			continue;
		best.room = (NvU16)room;
		best.object = word(entry + 2);
		best.offset = offset;
		best.bytes = bytes;
		best.checksum = number(entry + 20);
		best.width = width;
		best.height = height;
		best_rows = rows;
	}
	if (!best_rows || !load_image(&best))
		return 0;
	nv_art_warm.room = (NvU16)room;
	nv_art_warm.object = best.object;
	nv_art_warm.done = 1;
	++nv_art_warm.loads;
	prefilled = 1;
	/* Prefill never claims the current room, draw score, or decoder admission. */
	return 1;
}

int nv_art_object(NvU32 room, NvU32 object, NvU32 slot) {
	struct Lookup found;
	NvU32 rows;
	object_active = 0;
	if (!nv_art.enabled || room > 255 || object >= 65535 || slot >= 70)
		return 0;
	nv_art_room(room);
	if (nv_art.object == object) {
		object_active = 1;
		return 1;
	}
	if (payload_room == room && payload_object == object) {
		nv_art.object = (NvU16)object;
		score = (NvU32)nv_art.image.columns * nv_art.image.height;
		object_active = 1;
		if (prefilled) {
			++nv_art_warm.uses;
			prefilled = 0;
		}
		return 1;
	}
	if (slot_ids[slot] == object)
		return 0;
	slot_ids[slot] = (NvU16)object;
	if (!find((NvU16)room, (NvU16)object, &found))
		return 0;
	rows = (NvU32)(found.width / 8) * found.height;
	if (rows <= score)
		return 0;
	if (prefilled)
		++nv_art_warm.replaced;
	if (!load_image(&found))
		return 0;
	nv_art.object = (NvU16)object;
	score = rows;
	nv_art_warm.done = 1;
	object_active = 1;
	return 1;
}

int nv_art_bind(NvU32 column, NvU8 *primary, const NvU8 *codec,
               const NvU8 *original_oi, NvU32 original_bytes, NvU32 strip) {
	NvU32 offset;
	const NvU8 *descriptor;
	if (!nv_art.enabled || !object_active || nv_art.object == 65535 || column >= 40 ||
	    strip >= nv_art.image.columns || original_bytes != nv_art.image.source_bytes)
		return 0;
	descriptor = nv_art.image.strips + strip * 8;
	offset = number(descriptor);
	if (codec != original_oi + offset)
		return 0;
	bindings[column].primary = primary;
	bindings[column].indices = nv_art.image.indices + strip * nv_art.image.height * 2;
	bindings[column].height = nv_art.image.height;
	nv_art_columns[column] = 1;
	++nv_art.bindings;
	return 1;
}

const NvU8 *nv_art_c2p_span(NvU32 column, const NvU8 *primary, NvU32 height,
                            NvU16 *prefix, NvU16 *rows) {
	const struct Binding *binding;
	NvU32 offset;
	NvU16 row, available;
	if (!nv_art.enabled || column >= 40 || !height || height > 200)
		return 0;
	binding = bindings + column;
	if (!binding->height)
		return 0;
	if (primary < binding->primary) {
		offset = (NvU32)(binding->primary - primary);
		if (offset > 64000)
			return 0;
		row = nv_art_row(offset);
		if (offset != (NvU32)row * 320 || row >= height)
			return 0;
		*prefix = row;
		available = (NvU16)height - row;
		*rows = available < binding->height ? available : binding->height;
		return binding->indices;
	}
	offset = (NvU32)(primary - binding->primary);
	if (offset >= (NvU32)binding->height * 320)
		return 0;
	row = nv_art_row(offset);
	if (offset != (NvU32)row * 320)
		return 0;
	*prefix = 0;
	available = binding->height - row;
	*rows = height < available ? (NvU16)height : available;
	return binding->indices + row * 2;
}

const NvU8 *nv_art_c2p_indices(NvU32 column, const NvU8 *primary, NvU32 height) {
	NvU16 prefix, rows;
	const NvU8 *indices = nv_art_c2p_span(column, primary, height, &prefix, &rows);
	return indices && !prefix && rows == height ? indices : 0;
}
