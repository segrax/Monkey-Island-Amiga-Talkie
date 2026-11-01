/* Local native experiment, GPL-3.0-or-later. */
#ifndef NATIVE_PROVENANCE_H
#define NATIVE_PROVENANCE_H
#include "native_voice.h"

struct NvSite {
	NvU16 kind, resource_room, script, valid;
	NvU32 offset;
};

int nv_game_site(NvU32 slot, NvU32 pointer, struct NvSite *site);
void nv_provenance_reset(void);
void nv_provenance_program(NvU32 slot);
void nv_definition_begin(void);
void nv_resource_begin(NvU32 index, NvU32 source);
void nv_resource_end(void);
void nv_resource_clear(NvU32 index);
void nv_resource_mutate(NvU32 string_id);
void nv_conversion_begin(NvU32 source);
void nv_conversion_end(void);
void nv_provenance_origin(NvU32 start, char *output, NvU32 capacity);
NvU32 nv_provenance_export(NvU8 *output, NvU32 capacity);
int nv_provenance_import(const NvU8 *input, NvU32 bytes, int apply);
void nv_provenance_clear(void);
#endif
