/* Optional, bounded compiled costume draws.  No resource hooks
 * or persistent assumptions about an allocation's previous owner are used. */
#include <stddef.h>
#include "cache_manager.h"
#include "native_driver.h"

#define ARENA_MAX_BYTES 65536UL
#define ARENA_MIN_BYTES 16384UL
#define ARENA_STEP_BYTES 4096UL
#define SLOTS 16
#define RAM_REGIONS 8
#define GLOBAL_BYTES 29312UL

struct Key {
 NvU32 source, base, limit;
 NvU16 dimensions, sx, sy, phases;
 NvU8 reset_phase, bit;
 NvU16 reserved;
};
struct Entry {
 struct Key key;
 NvU32 offset, bytes, age;
};
struct Arena {
 struct Entry entries[SLOTS];
 struct Key history[SLOTS];
 NvU8 failures[SLOTS];
 NvU32 clock, history_next, high_water;
 NvU8 payload[1];
};
struct NvCostumeCache nv_costume_cache;
static struct State {
 struct Arena *storage;
 NvU32 capacity;
 NvU32 ram_regions[RAM_REGIONS][2];
 NvU16 ram_count, flush_code;
 volatile NvU16 *lease_valid;
 struct Key recording_key;
 NvU16 recording_slot;
 NvU32 recording_offset, recording_capacity;
} state;
#define arena state.storage
#define regions state.ram_regions
#define region_count state.ram_count
#define pending state.recording_key
#define pending_slot state.recording_slot
#define pending_offset state.recording_offset
#define pending_capacity state.recording_capacity

extern void *nv_costume_alloc(NvU32 bytes);
extern void nv_costume_free(void *block, NvU32 bytes);
extern void *nv_costume_exec(void);
extern void nv_costume_flush(void);

typedef char CacheLayout[(offsetof(struct NvCostumeCache,record)==0 &&
 offsetof(struct NvCostumeCache,record_end)==4 &&
 offsetof(struct NvCostumeCache,source_end)==8 &&
 offsetof(struct NvCostumeCache,source_begin)==12 &&
 offsetof(struct NvCostumeCache,plan)==16 &&
 offsetof(struct NvCostumeCache,cursor)==20 &&
 offsetof(struct NvCostumeCache,published)==24 &&
 offsetof(struct NvCostumeCache,kind)==26 &&
 offsetof(struct NvCostumeCache,arena_base)==28 &&
 offsetof(struct NvCostumeCache,begins)==32 &&
 offsetof(struct NvCostumeCache,capacity)==76 && sizeof(struct Key)==24)?1:-1];

static NvU16 word(const NvU8 *p) { return ((NvU16)p[0]<<8)|p[1]; }
static NvU32 longword(const NvU8 *p) {
 return ((NvU32)word(p)<<16)|word(p+2);
}
static NvU32 little(const NvU8 *p) {
 return ((NvU32)p[3]<<24)|((NvU32)p[2]<<16)|((NvU32)p[1]<<8)|p[0];
}
static int ram(NvU32 p,NvU32 n) {
 unsigned i;NvU32 end=p+n;
 if(!n||end<p)return 0;
 for(i=0;i<region_count;++i)
  if(p>=regions[i][0]&&end<=regions[i][1])return 1;
 return 0;
}
static int overlap(NvU32 a,NvU32 an,NvU32 b,NvU32 bn) {
 return a<b+bn&&b<a+an;
}
#ifdef NV_ART_COSTUME_CACHE
int nv_costume_cache_overlap(NvU32 p,NvU32 n) {
 if(!n||p+n<p)return 1;
 return overlap(p,n,(NvU32)&state,sizeof(state))||
  overlap(p,n,(NvU32)&nv_costume_cache,sizeof(nv_costume_cache))||
  (arena&&overlap(p,n,(NvU32)arena,state.capacity));
}
#endif
/* Main-task only. The holder is a static module-lifetime DATA word,
 * outside this arena. No IRQ may execute or publish borrowed code. */
static void revoke_lease(void) {
 if(state.lease_valid) {
  *state.lease_valid=0;
  state.lease_valid=0;
 }
}
static int lease_empty(void) {
 unsigned i;
 if(!arena||nv_costume_cache.entries||nv_costume_cache.used||
    nv_costume_cache.record||nv_costume_cache.record_end||
    nv_costume_cache.source_begin||nv_costume_cache.source_end||
    nv_costume_cache.plan||nv_costume_cache.cursor||nv_costume_cache.published)
  return 0;
 for(i=0;i<SLOTS;++i)if(arena->entries[i].bytes)return 0;
 return 1;
}
NvU8 *nv_costume_cache_lease(NvU32 bytes,volatile NvU16 *valid) {
 NvU32 p=(NvU32)valid,offset=(offsetof(struct Arena,payload)+3)&~3UL;
 revoke_lease();
 if(!valid||(p&1)||!ram(p,2)||
    overlap(p,2,(NvU32)&state,sizeof(state))||
    overlap(p,2,(NvU32)&nv_costume_cache,sizeof(nv_costume_cache))||
    (arena&&overlap(p,2,(NvU32)arena,state.capacity)))return 0;
 *valid=0;
 if(!bytes||bytes>state.capacity-offset||!lease_empty())return 0;
 state.lease_valid=valid;
 return (NvU8 *)arena+offset;
}
NvU32 nv_costume_cache_lease_capacity(void) {
 return arena?state.capacity-((offsetof(struct Arena,payload)+3)&~3UL):0;
}
int nv_costume_cache_lease_commit(volatile NvU16 *valid) {
 if(!valid||state.lease_valid!=valid||*valid||!lease_empty())return 0;
 if(state.flush_code)nv_costume_flush();
 *valid=1;
 return 1;
}
void nv_costume_cache_lease_cancel(volatile NvU16 *valid) {
 if(state.lease_valid==valid)revoke_lease();
}

static int equal(const struct Key *a,const struct Key *b) {
 return a->source==b->source&&a->base==b->base&&a->limit==b->limit&&
  a->dimensions==b->dimensions&&a->sx==b->sx&&a->sy==b->sy&&
  a->phases==b->phases&&a->reset_phase==b->reset_phase&&a->bit==b->bit&&a->reserved==b->reserved;
}
static void record_failed(void) {
 unsigned i;
 ++nv_costume_cache.overflows;
 for(i=0;i<SLOTS;++i)if(equal(&pending,&arena->history[i])) {
  if(arena->failures[i]<2)++arena->failures[i];
  break;
 }
 if(arena->high_water<state.capacity/2)arena->high_water*=2;
 nv_costume_cache.high_water=arena->high_water;
}
static void clear_context(void) {
 nv_costume_cache.record=0;nv_costume_cache.record_end=0;
 nv_costume_cache.source_end=0;nv_costume_cache.source_begin=0;
 nv_costume_cache.plan=0;nv_costume_cache.cursor=0;
 nv_costume_cache.published=0;
}
void nv_costume_cache_start(void) {
 NvU8 *exec,*node;unsigned count=0;
 revoke_lease();
 if(arena)return;
 clear_context();region_count=0;
 exec=nv_costume_exec();
 /* Older Exec cannot reliably identify every later CPU or flush its caches.
  * On those combinations keep the ordinary renderer. */
 state.flush_code=(word(exec+296)&2)!=0;
 if(state.flush_code&&word(exec+20)<37)return;
 /* Exec MemList is a list of MemHeader nodes.  mh_Lower/mh_Upper describe
  * actual RAM, including occupied allocations, rather than free fragments. */
 node=(NvU8 *)longword(exec+322);
 while(node&&longword(node)&&count++<64) {
  NvU32 lower=longword(node+20),upper=longword(node+24);
  if(lower<upper&&region_count<RAM_REGIONS) {
   regions[region_count][0]=lower;regions[region_count++][1]=upper;
  }
  node=(NvU8 *)longword(node);
 }
 if(!region_count)return;
 /* Keep the original64KB preference. Smaller optional banks preserve the
  * exact renderer when module growth leaves less contiguous Slow RAM. */
 state.capacity=0;nv_costume_cache.capacity=0;
 {
  NvU32 bytes;
  for(bytes=ARENA_MAX_BYTES;bytes>=ARENA_MIN_BYTES;bytes-=ARENA_STEP_BYTES) {
   arena=nv_costume_alloc(bytes);
   if(arena) {state.capacity=bytes;nv_costume_cache.capacity=bytes;break;}
  }
 }
 if(arena) {
  arena->high_water=4096;
  nv_costume_cache.arena_base=(NvU8 *)arena;
  nv_costume_cache.high_water=4096;
 }
}
void nv_costume_cache_stop(void) {
 struct Arena *old;NvU32 bytes;
 revoke_lease();
 old=arena;bytes=state.capacity;arena=0;state.capacity=0;
 nv_costume_cache.capacity=0;clear_context();region_count=0;
 nv_costume_cache.arena_base=0;
 if(old)nv_costume_free(old,bytes);
}

/* This runs before source comparison or any framebuffer writes.  Pointer
 * ownership and the CURRENT allocation size are validated every time.  Thus
 * freed/reallocated resources cannot cause a stale-length comparison. */
static int key(struct Key *k) {
 NvU8 *g=nv_control.game_globals,*base;
 NvU32 gp=(NvU32)g,table,count,size,dst,mask,dn,mn,ap=(NvU32)arena;
 NvU16 width,height,direction;NvU8 id;
 if(!ram(gp,GLOBAL_BYTES))return 0;
 direction=word(g+0x6dfc);
 if(g[0x6dfa]||(direction!=1&&direction!=65535))return 0;
 width=g[0x6dec]?g[0x6dec]:256;
 height=g[0x6ded]?g[0x6ded]:256;
 if(height>200||word(g+0x6df4)!=word(g+0x6df6))return 0;
 if(word(g+0x6df2)>319)return 0;
 if(direction==1) {if(width>320-word(g+0x6df2))return 0;}
 else if(width>word(g+0x6df2)+1)return 0;
 if(word(g+0x6df4)>200-height||word(g+0x6df8)>200||word(g+0x6df8)<word(g+0x6df4)||
    height>word(g+0x6df8)-word(g+0x6df4))return 0;
 k->base=longword(g+0x59b4);k->source=longword(g+0x59b8);
 if(!ram(k->base,6))return 0;
 base=(NvU8 *)k->base;id=base[5];
 if(base[4]!=2)return 0;
 table=longword(g+0x2778);count=word(g+0x235c);
 if(!count||count>256||id>=count||!ram(table,count*4))return 0;
 if(longword((NvU8 *)table+4*id)!=k->base)return 0;
 size=little(base);
 if(size<6||!ram(k->base,size))return 0;
 k->limit=k->base+size;
 if(k->source<k->base+6||k->source>=k->limit)return 0;
 dst=longword(g+0x5c16);mask=longword(g+0x5c22);
 dn=(NvU32)(height-1)*320+width;
 mn=(NvU32)(height-1)*40+(width+14)/8;
 if(direction==65535) {
  NvU32 left=(width-1+7-(g[0x6df3]&7))/8;
  if(dst<width-1||mask<left)return 0;
  dst-=width-1;mask-=left;mn=(NvU32)(height-1)*40+left+1;
 }
 if(!ram(dst,dn)||!ram(mask,mn))return 0;
 if(overlap(dst,dn,gp,GLOBAL_BYTES)||overlap(dst,dn,mask,mn)||
    overlap(dst,dn,k->base,size)||overlap(dst,dn,ap,state.capacity)||
    overlap(mask,mn,ap,state.capacity)||overlap(gp,GLOBAL_BYTES,ap,state.capacity)||
    overlap(k->base,size,ap,state.capacity))return 0;
 /* These guards precede every manager/context write, including counters.
  * A forged mask/source pointing at our control storage must also fall back
  * without changing the bytes the original renderer would read. */
 if(overlap(dst,dn,(NvU32)&state,sizeof(state))||
    overlap(dst,dn,(NvU32)&nv_costume_cache,sizeof(nv_costume_cache))||
    overlap(mask,mn,(NvU32)&state,sizeof(state))||
    overlap(mask,mn,(NvU32)&nv_costume_cache,sizeof(nv_costume_cache))||
    overlap(k->base,size,(NvU32)&state,sizeof(state))||
    overlap(k->base,size,(NvU32)&nv_costume_cache,sizeof(nv_costume_cache))||
    overlap(gp,GLOBAL_BYTES,(NvU32)&state,sizeof(state))||
    overlap(gp,GLOBAL_BYTES,(NvU32)&nv_costume_cache,sizeof(nv_costume_cache))||
    overlap(dst,dn,(NvU32)&nv_control,sizeof(nv_control))||
    overlap(mask,mn,(NvU32)&nv_control,sizeof(nv_control))||
    overlap(k->base,size,(NvU32)&nv_control,sizeof(nv_control)))return 0;
 k->dimensions=word(g+0x6dec);k->sx=word(g+0x59ac);k->sy=word(g+0x59ae);
 k->phases=((NvU16)g[0x6e00]<<8)|g[0x6e01];
 k->reset_phase=g[0x6e02];k->bit=g[0x6df3]&7;k->reserved=direction;
 return 1;
}
static int source_equal(const struct Entry *entry) {
 NvU8 *plan=(NvU8 *)arena+entry->offset;
 NvU32 copy=longword(plan),bytes=longword(plan+4);
 const NvU8 *a=(const NvU8 *)entry->key.source,*b=(const NvU8 *)copy;
 NvU32 begin=(NvU32)plan,end=begin+entry->bytes;
 if(!bytes||bytes>entry->key.limit-entry->key.source||
    copy<begin+10||copy>end||bytes>end-copy)return 0;
 /* The source and its copy have matching parity.  Longword reads on 68000
  * require only word alignment.  Do not round a source read past its end. */
 if((NvU32)a&1) { if(*a++!=*b++)return 0;--bytes; }
 while(bytes>=4) {
  if(*(const NvU32 *)a!=*(const NvU32 *)b)return 0;
  a+=4;b+=4;bytes-=4;
 }
 while(bytes--)if(*a++!=*b++)return 0;
 return 1;
}
/* Select the largest physically contiguous hole; no data moves and no second
 * drawing pass.  Bounded LRU eviction grows the hole for the recorder. */
static NvU32 hole(NvU32 *offset) {
 NvU32 start=(sizeof(struct Arena)+3)&~3UL,best=0,best_at=start;
 unsigned step,i;
 for(step=0;step<=SLOTS;++step) {
  NvU32 next=state.capacity,end=state.capacity;
  for(i=0;i<SLOTS;++i)if(arena->entries[i].bytes&&arena->entries[i].offset>=start&&
   arena->entries[i].offset<next) {
   next=arena->entries[i].offset;end=next+arena->entries[i].bytes;
  }
  if(next-start>best) {best=next-start;best_at=start;}
  if(next==state.capacity)break;
  start=end;
 }
 *offset=best_at;return best;
}
NvU8 *nv_costume_cache_begin(NvU32 kind) {
 struct Key current;
 unsigned i,slot=SLOTS,history_slot=0;
 NvU32 capacity,offset,oldest,width,height,demand;int warm=0;
 /* Revoke before even rejected costume requests inspect or reuse storage. */
 revoke_lease();
 if(!arena||!key(&current))return (NvU8 *)0xffffffffUL;
 ++nv_costume_cache.begins;
 /* A mid-column overflow continues the untouched renderer and bypasses finish.
  * Account for it at the next safe entry, without per-pixel bookkeeping. */
 if(nv_costume_cache.record&&!nv_costume_cache.published) {
  record_failed();
 }
 clear_context();nv_costume_cache.kind=(NvU16)kind;
 nv_costume_cache.high_water=arena->high_water;
 if(++arena->clock==0) {
  /* A wrap cannot turn a newly used entry into the oldest one. */
  for(i=0;i<SLOTS;++i)arena->entries[i].age=0;
  arena->clock=1;
 }
 for(i=0;i<SLOTS;++i)if(arena->entries[i].bytes&&equal(&current,&arena->entries[i].key)) {
  if(source_equal(&arena->entries[i])) {
   arena->entries[i].age=arena->clock;
   ++nv_costume_cache.hits;
   nv_costume_cache.plan=(NvU8 *)arena+arena->entries[i].offset;
   return nv_costume_cache.plan;
  }
  nv_costume_cache.used-=arena->entries[i].bytes;--nv_costume_cache.entries;
  arena->entries[i].bytes=0;
 }
 for(i=0;i<SLOTS;++i)if(equal(&current,&arena->history[i])) {warm=1;history_slot=i;break;}
 if(!warm) {
  ++nv_costume_cache.cold;
  i=arena->history_next++&15;arena->history[i]=current;arena->failures[i]=0;return 0;
 }
 if(arena->failures[history_slot]>=2) {
  ++nv_costume_cache.negative_skips;return (NvU8 *)0xffffffffUL;
 }
 /* Two failed attempts bound miss work for an oversized pose.  A changed
  * source with the same key may remain uncached, which only forgoes a gain. */
 pending=current;
 width=pending.dimensions>>8;if(!width)width=256;
 height=pending.dimensions&255;if(!height)height=256;
 demand=(12+2*width+14*width*height+1+3)&~3UL;
 if(demand>arena->high_water)demand=arena->high_water;
 for(i=0;i<SLOTS;++i)if(!arena->entries[i].bytes) {slot=i;break;}
 capacity=hole(&offset);
 for(i=0;i<SLOTS&&(slot==SLOTS||capacity<demand);++i) {
  unsigned j,victim=SLOTS;oldest=0xffffffffUL;
  for(j=0;j<SLOTS;++j)if(arena->entries[j].bytes&&arena->entries[j].age<=oldest) {
   victim=j;oldest=arena->entries[j].age;
  }
  if(victim==SLOTS)break;
  nv_costume_cache.used-=arena->entries[victim].bytes;--nv_costume_cache.entries;
  ++nv_costume_cache.evictions;
  arena->entries[victim].bytes=0;slot=victim;capacity=hole(&offset);
 }
 if(slot==SLOTS||capacity<16)return 0;
 pending_slot=(NvU16)slot;pending_offset=offset;pending_capacity=capacity;
 nv_costume_cache.record=(NvU8 *)arena+offset;
 nv_costume_cache.record_end=nv_costume_cache.record+capacity;
 nv_costume_cache.source_begin=(NvU8 *)pending.source;
 nv_costume_cache.source_end=(NvU8 *)pending.limit;
 ++nv_costume_cache.records_armed;
 return 0;
}
void nv_costume_cache_finish(void) {
 struct Key current;struct Entry *entry;NvU32 bytes;
 if(!arena||!nv_costume_cache.record)return;
 if(!nv_costume_cache.published||!key(&current)||!equal(&pending,&current)) {
  /* Overflow is harmless: the original draw has already completed.  A later
   * attempt can reserve a larger contiguous hole, with a fixed total budget. */
  if(!nv_costume_cache.published) {
   record_failed();
  }
  clear_context();return;
 }
 bytes=(NvU32)nv_costume_cache.cursor-(NvU32)nv_costume_cache.record;
 bytes=(bytes+3)&~3UL;
 if(!bytes||bytes>pending_capacity) {clear_context();return;}
 /* All instructions, the return and the source copy are complete before
  * making this entry visible, including reuse of an evicted code address. */
 if(state.flush_code)nv_costume_flush();
 entry=&arena->entries[pending_slot];entry->key=pending;
 {
  unsigned i;
  for(i=0;i<SLOTS;++i)if(equal(&pending,&arena->history[i]))arena->failures[i]=0;
 }
 entry->offset=pending_offset;entry->bytes=bytes;entry->age=arena->clock;
 ++nv_costume_cache.builds;++nv_costume_cache.entries;nv_costume_cache.used+=bytes;
 if(bytes>arena->high_water)arena->high_water=bytes;
 nv_costume_cache.high_water=arena->high_water;
 clear_context();
}
