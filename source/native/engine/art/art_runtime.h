#ifndef NV_ART_RUNTIME_H
#define NV_ART_RUNTIME_H
#include "art_manager.h"

struct NvArtState {
	NvU8 *arena;
	struct NvArtImage image;
	NvU32 starts, loads, rejects, lookups, bindings, c2p_hits, decode_hits;
	NvU16 room, object, enabled, reserved;
};
extern struct NvArtState nv_art;
struct NvArtWarm {
	NvU32 requests, searches, loads, uses, replaced;
	NvU16 room, object, done, reserved;
	NvU8 seen[32];
};
extern struct NvArtWarm nv_art_warm;
int nv_art_prewarm(NvU32 room);
extern NvU8 nv_art_columns[40];
void nv_art_start(void);
void nv_art_stop(void);
void nv_art_room(NvU32 room);
/* Called once per visible object, before its strip loop. */
int nv_art_object(NvU32 room, NvU32 object, NvU32 slot);
int nv_art_bind(NvU32 column, NvU8 *primary, const NvU8 *codec,
               const NvU8 *original_oi, NvU32 original_bytes, NvU32 strip);
const NvU8 *nv_art_c2p_span(NvU32 column, const NvU8 *primary, NvU32 height,
                            NvU16 *prefix, NvU16 *rows);
const NvU8 *nv_art_c2p_indices(NvU32 column, const NvU8 *primary, NvU32 height);
int nv_art_runtime_overlap(NvU32 address, NvU32 bytes);
#endif
