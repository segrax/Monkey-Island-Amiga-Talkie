#ifndef NV_COSTUME_CACHE_H
#define NV_COSTUME_CACHE_H
#include "native_voice.h"

/* Assembly offsets are asserted in cache_manager.c.  The arena is optional;
 * none of these pointers is placed in the original game's globals. */
struct NvCostumeCache {
 NvU8 *record, *record_end, *source_end, *source_begin;
 NvU8 *plan, *cursor;
 NvU16 published, kind;
 NvU8 *arena_base;
 NvU32 begins, hits, builds, cold, evictions, overflows, entries, used, high_water;
 NvU32 negative_skips, records_armed;
 /* Appended diagnostic; original76-byte assembly ABI is unchanged. */
 NvU32 capacity;
};
extern struct NvCostumeCache nv_costume_cache;
void nv_costume_cache_start(void);
void nv_costume_cache_stop(void);
NvU8 *nv_costume_cache_begin(NvU32 kind);
/* begin returns -1 for direct pristine fallback, NULL for a cold/record miss,
 * or a plan pointer for a hit.  Hard rejection need not write the context. */
void nv_costume_cache_finish(void);
#ifdef NV_ART_COSTUME_CACHE
int nv_costume_cache_overlap(NvU32 address, NvU32 bytes);
#endif
/* Main-task, static DATA valid-word holder only; no arena ownership transfer. */
NvU8 *nv_costume_cache_lease(NvU32 bytes,volatile NvU16 *valid);
NvU32 nv_costume_cache_lease_capacity(void);
int nv_costume_cache_lease_commit(volatile NvU16 *valid);
void nv_costume_cache_lease_cancel(volatile NvU16 *valid);
#endif
