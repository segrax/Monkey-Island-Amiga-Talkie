#include "glyph_private.h"
/* Scope contract: original DFD0..E150 has no resource or allocation mutator.
 * DDDC and font loading cancel before preprocessing; costume use revokes valid. */
extern int nv_glyph_same(const NvU8 *,const NvU8 *,NvU32);
static NvU16 word(const NvU8 *p){return *(const NvU16 *)p;}
static NvU32 number(const NvU8 *p){return *(const NvU32 *)p;}
void nv_glyph_scope_cancel(void){nv_glyph.scope.active=nv_glyph.scope.ready=0;}
void nv_glyph_scope_begin(NvU32 stack){nv_glyph_scope_cancel();if(nv_glyph.valid&&stack>=4096&&stack<=0xffffdfffUL){nv_glyph.scope.stack=stack;nv_glyph.scope.active=1;}}
static int gate(NvU32 stack){return nv_glyph.scope.active&&nv_glyph.scope.stack>=42&&stack==nv_glyph.scope.stack-42&&!(stack&1)&&number((const NvU8 *)stack)==(NvU32)nv_control.game_code+0x12b9e&&number((const NvU8 *)stack+36)==(NvU32)nv_control.game_code+0xe132;}
void nv_glyph_scope_arm(NvU32 stack,NvU32 owner,NvU32 owner_bytes,NvU32 p,NvU32 pbytes,NvU32 m,NvU32 mbytes){
 NvU16 i;NvU32 n;const NvU8 *a,*b;NvU8 *g=nv_control.game_globals;
 if(!nv_glyph.valid||nv_glyph.scope.ready||!nv_glyph.scope.active||((NvU32)g&1)||g[0x60d5]!=nv_glyph.font)return;
 for(i=0;i<nv_glyph.count;i++)if(stack>=nv_glyph.regions[i][0]&&stack<=nv_glyph.regions[i][1]&&40<=nv_glyph.regions[i][1]-stack)break;
 if(i==nv_glyph.count||!gate(stack))return;
 a=(const NvU8 *)(owner+6);b=nv_glyph.block+nv_glyph.source;n=nv_glyph.source_bytes;
 if(!nv_glyph_same(a,b,n)){nv_glyph_scope_cancel();return;}
 nv_glyph.scope.globals=(NvU32)g;nv_glyph.scope.code=(NvU32)nv_control.game_code;
 nv_glyph.scope.owner=owner;nv_glyph.scope.owner_bytes=owner_bytes;
 nv_glyph.scope.p=p;nv_glyph.scope.pbytes=pbytes;nv_glyph.scope.m=m;nv_glyph.scope.mbytes=mbytes;
 nv_glyph.scope.ready=1;
}
NvU8 *nv_glyph_scope_lookup(NvU32 stack){
 NvU8 *g,*b;const NvU8 *d,*ref;NvU32 off,src,dst,dirty,row,pn,mn;NvU16 slot,probe,entry,w,h,y,limit,phase;
 if(!nv_glyph.valid||!nv_glyph.scope.ready||!nv_glyph.scope.active)return 0;
 g=nv_control.game_globals;if((NvU32)g!=nv_glyph.scope.globals||g[0x60d5]!=nv_glyph.font||!gate(stack))return 0;
 if(word(g+0x6f3a)!=8||g[0x6f5f]!=2||g[0x6f60]!=6||g[0x6f61]!=192)return 0;
 src=number(g+0x6f48);if(src<nv_glyph.scope.owner+11)return 0;
 off=src-nv_glyph.scope.owner-11;if(off>nv_glyph.source_bytes-5)return 0;
 b=nv_glyph.block;slot=(NvU16)((off>>3)&511);
 for(probe=0;probe<512;probe++){entry=nv_glyph.hash[slot];if(!entry)return 0;d=b+nv_glyph.index+entry-1;if(off==word(d))goto found;slot=(slot+1)&511;}return 0;
found:
 ref=b+nv_glyph.source+off;w=ref[0];h=ref[1];
 if(word(g+0x6f58)!=w||g[0x6f5a]!=h||(NvU8)word(g+0x6f40)!=ref[4])return 0;
 phase=g[0x6f5c];y=word(g+0x6f54);limit=word(g+0x6f50);
 if(!phase||(phase&(phase-1))||y>32767||limit>32767||(NvU32)y+h>limit)return 0;
 row=(NvU32)h-1;pn=(row<<8)+(row<<6)+w;mn=(row<<5)+(row<<3)+2;
 dst=number(g+0x5c1e);dirty=number(g+0x5c26);
 if(dst<nv_glyph.scope.p+6||dst>nv_glyph.scope.p+nv_glyph.scope.pbytes||pn>nv_glyph.scope.p+nv_glyph.scope.pbytes-dst||dirty<nv_glyph.scope.m+6||dirty>nv_glyph.scope.m+nv_glyph.scope.mbytes||mn>nv_glyph.scope.m+nv_glyph.scope.mbytes-dirty)return 0;
 nv_glyph.hits++;return b+number(d+4);
}
