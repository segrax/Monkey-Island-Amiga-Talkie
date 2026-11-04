#ifndef NV_ART_GAME_H
#define NV_ART_GAME_H
#include "art_runtime.h"
extern struct NvArtDecode nv_art_decode;
extern NvU16 nv_art_decode_ready;
struct NvArtC2p { const NvU8 *dictionary, *indices; NvU16 prefix, rows; };
extern struct NvArtC2p nv_art_c2p;
struct NvArtObjectGate { NvU16 room; NvU8 slots[70]; };
extern struct NvArtObjectGate nv_art_object_gate;
void nv_art_game_start(void);
void nv_art_game_stop(void);
void nv_art_game_room(void);
void nv_art_game_prewarm(NvU32 room, NvU32 stack);
void nv_art_game_object(NvU32 stack);
void nv_art_game_bind(NvU32 strip, NvU32 stack);
int nv_art_game_c2p(const NvU8 *source, NvU8 *destination, NvU32 height, NvU32 stack);
void nv_art_game_scope_cancel(void);
void nv_art_game_scope_begin(NvU32 stack);
#endif
