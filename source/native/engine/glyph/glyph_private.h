#include "native_driver.h"
struct NvGlyphState {
 NvU8 *block; NvU32 bytes,owner,owner_bytes,source,source_bytes,index;
 NvU32 regions[8][2]; NvU16 count,entries,font;
 volatile NvU16 valid;
 NvU32 loads,hits,declines,loaded_globals;
 struct {NvU32 p,pbytes,m,mbytes,owner,owner_bytes,stack,globals,code,block,bytes,index,source,source_bytes,generation,art_arena,art_loads;NvU16 valid;} memo;
 NvU16 hash[512];
 struct {NvU32 stack,globals,code,block,loads,art_arena,art_loads,owner,owner_bytes,p,pbytes,m,mbytes;NvU16 active,ready;} scope;
};
extern struct NvGlyphState nv_glyph;
void nv_glyph_scope_cancel(void);
void nv_glyph_scope_arm(NvU32,NvU32,NvU32,NvU32,NvU32,NvU32,NvU32);
