/* Prepared glyph replay with bounded source ownership. */
#include "native_driver.h"
#include "cache_manager.h"
#include "art_manager.h"
#include "art_runtime.h"
#include <stddef.h>
extern NvU32 nv_glyph_open(const char *name);
extern void nv_glyph_close(NvU32 file);
extern NvU32 nv_glyph_read(NvU32 file, NvU8 *data, NvU32 bytes);
#include "glyph_private.h"
struct NvGlyphState nv_glyph;
typedef char GlyphScopeLayout[(sizeof(nv_glyph.scope)==56)?1:-1];
const NvU16 nv_glyph_layout[]={sizeof(struct NvGlyphState),offsetof(struct NvGlyphState,scope),offsetof(struct NvGlyphState,scope)+52,offsetof(struct NvGlyphState,scope)+54};
static NvU16 word(const NvU8 *p){
#ifdef __VBCC__
 if(!((NvU32)p&1))return *(const NvU16 *)p;
#endif
 return ((NvU16)p[0]<<8)|p[1];}
static NvU32 number(const NvU8 *p){
#ifdef __VBCC__
 if(!((NvU32)p&1))return *(const NvU32 *)p;
#endif
 return ((NvU32)word(p)<<16)|word(p+2);}
static NvU16 aligned_word(const NvU8 *p){
#ifdef __VBCC__
 return *(const NvU16 *)p;
#else
 return word(p);
#endif
}
static NvU32 aligned_number(const NvU8 *p){
#ifdef __VBCC__
 return *(const NvU32 *)p;
#else
 return number(p);
#endif
}
static NvU32 little(const NvU8 *p){return p[0]|((NvU32)p[1]<<8)|((NvU32)p[2]<<16)|((NvU32)p[3]<<24);}
static int ram(NvU32 p,NvU32 n){NvU16 i;if(!n||n>0xffffffffUL-p)return 0;for(i=0;i<nv_glyph.count;i++)if(p>=nv_glyph.regions[i][0]&&p+n<=nv_glyph.regions[i][1])return 1;return 0;}
static int overlap(NvU32 p,NvU32 n,NvU32 q,NvU32 m){return p<q+m&&q<p+n;}
static int span(NvU32 p,NvU32 n,NvU32 b,NvU32 z){return p>=b&&p<=b+z&&n<=b+z-p;}
static int protected(NvU32 p,NvU32 n,NvU32 stack){return overlap(p,n,(NvU32)nv_control.game_globals,29312)||overlap(p,n,(NvU32)nv_control.game_code,98800)||overlap(p,n,(NvU32)&nv_glyph,sizeof(nv_glyph))||overlap(p,n,stack-4096,8192)||overlap(p,n,(NvU32)&nv_control,sizeof(nv_control))||overlap(p,n,(NvU32)nv_art.arena,NV_ART_CAPACITY)||nv_art_runtime_overlap(p,n)||nv_costume_cache_overlap(p,n);}
static int owned(NvU32 p,NvU16 id,NvU32 *n){const NvU8 *a=(const NvU8 *)p;if(!ram(p,6)||a[4]!=4||a[5]!=id)return 0;*n=little(a);return *n>=6&&ram(p,*n);}
static void regions(void){NvU8 *exec=*(NvU8 **)4,*p;NvU16 i=0;nv_glyph.count=0;p=(NvU8 *)number(exec+322);while(p&&number(p)&&i++<64){NvU32 a=number(p+20),b=number(p+24);if(a<b&&nv_glyph.count<8){nv_glyph.regions[nv_glyph.count][0]=a;nv_glyph.regions[nv_glyph.count++][1]=b;}p=(NvU8 *)number(p);}}
static int same(const NvU8 *a,const NvU8 *b,NvU32 n){
#ifdef __VBCC__
 if(!(((NvU32)a^(NvU32)b)&1)){
  if(n&&((NvU32)a&1)){if(*a++!=*b++)return 0;n--;}
  while(n>=4){if(*(const NvU32 *)a!=*(const NvU32 *)b)return 0;a+=4;b+=4;n-=4;}
 }
#endif
 while(n--)if(*a++!=*b++)return 0;return 1;
}
static int owned_prior(NvU32 p,NvU16 id,NvU32 *n,NvU32 prior,NvU32 size){const NvU8 *a=(const NvU8 *)p;if(prior&&p==prior&&size&&a[4]==4&&a[5]==id&&little(a)==size){*n=size;return 1;}return owned(p,id,n);}

void nv_glyph_load(NvU32 font,NvU32 stack){
 NvU8 header[36],*b,*g=nv_control.game_globals;NvU32 file=0,total,owner,owner_bytes,source,source_bytes,index,code,check;NvU16 entries,i,previous=0;char name[]="native-font-1.dat";
 nv_glyph_scope_cancel();
 if(font<1||font>4||stack<4096||stack>0xffffdfffUL)return;
 nv_glyph.memo.valid=0;regions();if(!ram((NvU32)g,29312))return;
 owner=number(g+0x27a8+font*4);if(!owned(owner,(NvU16)(10+font),&owner_bytes)||protected(owner,owner_bytes,stack))return;
 name[12]=(char)('0'+font);file=nv_glyph_open(name);if(!file)return;
 if(nv_glyph_read(file,header,36)!=36||number(header)!=0x4e475032UL||word(header+4)!=2||word(header+6)!=36||word(header+12)!=font)goto done;
 total=number(header+8);if(total<36||(total&1)||total>nv_costume_cache_lease_capacity())goto done;
 /* Keep the larger useful resident block; selecting a resident font does not reload it. */
 if(nv_glyph.valid&&(NvU32)g==nv_glyph.loaded_globals&&total<=nv_glyph.bytes){
  NvU32 live=number(g+0x27a8+nv_glyph.font*4),live_bytes;
  if(live==nv_glyph.owner&&owned(live,(NvU16)(10+nv_glyph.font),&live_bytes)&&live_bytes==nv_glyph.owner_bytes&&nv_glyph.source_bytes<=live_bytes-6&&same(nv_glyph.block+nv_glyph.source,(const NvU8 *)(live+6),nv_glyph.source_bytes))goto done;
 }
 b=nv_costume_cache_lease(total,&nv_glyph.valid);if(!b)goto done;
 /* The first read only inspected the header; fill it directly in the lease. */
 for(i=0;i<36;i++)b[i]=header[i];
 if(nv_glyph_read(file,b+36,total-36)!=total-36||nv_glyph_read(file,header,1)!=0)goto cancel;
 check=number(b+32);b[32]=b[33]=b[34]=b[35]=0;if(nv_art_checksum(b,total)!=check)goto cancel;
 b[32]=(NvU8)(check>>24);b[33]=(NvU8)(check>>16);b[34]=(NvU8)(check>>8);b[35]=(NvU8)check;
 entries=word(b+14);index=number(b+16);source=number(b+20);source_bytes=number(b+24);code=number(b+28);
 if(!entries||entries>256||index!=36||(NvU32)entries*12>total-index||source!=index+entries*12UL||source_bytes<1028||source_bytes>total-source||code!=(source+source_bytes+1UL)/2*2||code>=total||source_bytes>owner_bytes-6||b[source]!=2||!same(b+source,(const NvU8 *)(owner+6),source_bytes))goto cancel;
 for(i=0;i<entries;i++){const NvU8 *d=b+index+i*12UL;NvU16 off=word(d),n=word(d+2),len=word(d+8),w,h;NvU32 at=number(d+4);if((i&&off<=previous)||off<1028||off>source_bytes||source_bytes-off<5||word(d+10)||at<code||(at&1)||(len&1)||len<2||at>total||len>total-at)goto cancel;w=b[source+off];h=b[source+off+1];if(w<2||w>9||!h||h>127||(NvU32)(h-1)*320+w-1>32767||n!=5+(NvU32)w*h/4||n>source_bytes-off||word(b+at+len-2)!=0x4ed5)goto cancel;previous=off;}
 for(i=0;i<512;i++)nv_glyph.hash[i]=0;
 for(i=0;i<entries;i++){NvU16 slot=(word(b+index+i*12UL)>>3)&511;while(nv_glyph.hash[slot])slot=(slot+1)&511;nv_glyph.hash[slot]=(NvU16)(i*12+1);}
 nv_glyph.block=b;nv_glyph.bytes=total;nv_glyph.owner=owner;nv_glyph.owner_bytes=owner_bytes;nv_glyph.source=source;nv_glyph.source_bytes=source_bytes;nv_glyph.index=index;nv_glyph.entries=entries;nv_glyph.font=(NvU16)font;nv_glyph.loaded_globals=(NvU32)g;
 if(nv_costume_cache_lease_commit(&nv_glyph.valid))nv_glyph.loads++;
 goto done;
cancel:nv_costume_cache_lease_cancel(&nv_glyph.valid);
done:nv_glyph_close(file);
}
NvU8 *nv_glyph_lookup(NvU32 stack){
 NvU8 *g=nv_control.game_globals,*b;NvU32 owner,owner_bytes,p,pn,m,mn,dst,dirty,source,n,off,at;NvU16 w,h,phase,slot,probe;const NvU8 *d;NvU32 pbytes,mbytes,row,row320;NvU16 pixels;
 if(!nv_glyph.valid||(NvU32)g!=nv_glyph.loaded_globals||!ram((NvU32)g,29312)||stack<4096||stack>0xffffdfffUL)return 0;
 b=nv_glyph.block;owner=number(g+0x27a8+nv_glyph.font*4);
 if(owner!=nv_glyph.owner||!owned_prior(owner,(NvU16)(10+nv_glyph.font),&owner_bytes,nv_glyph.owner,nv_glyph.owner_bytes)||owner_bytes!=nv_glyph.owner_bytes)return 0;
 if(g[0x6f5f]!=2||g[0x6f60]!=6||g[0x6f61]!=192||word(g+0x6f3a)!=8)return 0;
 source=number(g+0x6f48);if(source<5)return 0;source-=5;if(!span(source,5,owner+6,nv_glyph.source_bytes))return 0;
 w=word(g+0x6f58);h=g[0x6f5a];phase=g[0x6f5c];if(w<2||w>9||!h||h>127)return 0;row=(NvU32)h-1;row320=(row<<8)+(row<<6);if(row320+w-1>32767||!phase||(phase&(phase-1))||word(g+0x6f54)>32767||word(g+0x6f50)>32767||word(g+0x6f54)+(NvU32)h>word(g+0x6f50))return 0;
 pixels=(NvU16)(w*h);n=5+(pixels>>2);off=source-owner-6;if(!span(source,n,owner+6,nv_glyph.source_bytes)||((const NvU8 *)source)[0]!=w||((const NvU8 *)source)[1]!=h||(NvU8)word(g+0x6f40)!=((const NvU8 *)source)[4])return 0;
 slot=(NvU16)((off>>3)&511);for(probe=0;probe<512;probe++){NvU16 entry=nv_glyph.hash[slot];if(!entry)return 0;d=b+nv_glyph.index+entry-1;if(off==aligned_word(d))goto found;slot=(slot+1)&511;}return 0;
found:if(aligned_word(d+2)!=n||!same((const NvU8 *)source,b+nv_glyph.source+off,n))return 0;
 p=number(g+0x2784);m=number(g+0x27a4);if(!owned_prior(p,1,&pbytes,nv_glyph.memo.valid?nv_glyph.memo.p:0,nv_glyph.memo.pbytes)||!owned_prior(m,9,&mbytes,nv_glyph.memo.valid?nv_glyph.memo.m:0,nv_glyph.memo.mbytes))return 0;
 dst=number(g+0x5c1e);dirty=number(g+0x5c26);pn=row320+w;mn=(row<<5)+(row<<3)+2;
 if(!span(dst,pn,p+6,pbytes-6)||!span(dirty,mn,m+6,mbytes-6))return 0;
 if(!nv_glyph.memo.valid||nv_glyph.memo.p!=p||nv_glyph.memo.pbytes!=pbytes||nv_glyph.memo.m!=m||nv_glyph.memo.mbytes!=mbytes||nv_glyph.memo.owner!=owner||nv_glyph.memo.owner_bytes!=owner_bytes||nv_glyph.memo.stack!=stack||nv_glyph.memo.globals!=(NvU32)g||nv_glyph.memo.code!=(NvU32)nv_control.game_code||nv_glyph.memo.block!=(NvU32)b||nv_glyph.memo.bytes!=nv_glyph.bytes||nv_glyph.memo.index!=nv_glyph.index||nv_glyph.memo.source!=nv_glyph.source||nv_glyph.memo.source_bytes!=nv_glyph.source_bytes||nv_glyph.memo.generation!=nv_glyph.loads||nv_glyph.memo.art_arena!=(NvU32)nv_art.arena||nv_glyph.memo.art_loads!=nv_art.loads){
  nv_glyph.memo.valid=0;
  if(protected(p,pbytes,stack)||protected(m,mbytes,stack)||protected(owner,owner_bytes,stack)||overlap(p,pbytes,m,mbytes)||overlap(p,pbytes,owner,owner_bytes)||overlap(m,mbytes,owner,owner_bytes))return 0;
  nv_glyph.memo.p=p;nv_glyph.memo.pbytes=pbytes;nv_glyph.memo.m=m;nv_glyph.memo.mbytes=mbytes;nv_glyph.memo.owner=owner;nv_glyph.memo.owner_bytes=owner_bytes;nv_glyph.memo.stack=stack;nv_glyph.memo.globals=(NvU32)g;nv_glyph.memo.code=(NvU32)nv_control.game_code;nv_glyph.memo.block=(NvU32)b;nv_glyph.memo.bytes=nv_glyph.bytes;nv_glyph.memo.index=nv_glyph.index;nv_glyph.memo.source=nv_glyph.source;nv_glyph.memo.source_bytes=nv_glyph.source_bytes;nv_glyph.memo.generation=nv_glyph.loads;nv_glyph.memo.art_arena=(NvU32)nv_art.arena;nv_glyph.memo.art_loads=nv_art.loads;nv_glyph.memo.valid=1;
 }
 nv_glyph_scope_arm(stack,owner,owner_bytes,p,pbytes,m,mbytes);
 at=aligned_number(d+4);nv_glyph.hits++;return b+at;
}
