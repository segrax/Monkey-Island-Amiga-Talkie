/* Hybrid music and speech playback, GPL-3.0-or-later. */
#include "native_driver.h"
#include "native_client.h"
#include "native_clock.h"
#include "native_timeline.h"
#include <stddef.h>
#define W(a) (*(volatile NvU16 *)(a))
#define L(a) (*(volatile NvU32 *)(a))
#ifdef NV_QUIET_NATIVE
extern NvU32 nv_mmio_read_word(NvU32);
#define R(a) ((NvU16)nv_mmio_read_word(a))
#else
#define R(a) W(a)
#endif
#define AUD 0xdff0a0UL
#define DMA 0xdff096UL
#define ENA 0xdff09aUL
#define REQ 0xdff09cUL
#define CHUNK 256
#define VIRTUAL_CHANNELS 2
/* Exact tables generated at build time, stored with ordinary code rather
 * than DMA buffers. No per-sample divide or runtime table construction. */
extern const NvS8 nv_amplitude[65][256], nv_half_amplitude[65][256];
extern const NvU16 nv_speech_words[65][256];
#define amplitude nv_amplitude
#define half_amplitude nv_half_amplitude
extern void *nv_alloc_chip(NvU32);
extern void nv_free_chip(void *,NvU32);
extern void nv_signal_worker(void *,NvU32);
extern void nv_disable_interrupts(void);
extern void nv_enable_interrupts(void);
extern void nv_irq(void);
void *SysBase;
struct NvControl nv_control={NV_CONTROL_MAGIC,NV_CONTROL_VERSION,sizeof(struct NvControl),0,0,0,0,0};
struct StereoDriver {
 struct NvPaula native[4];
 NvS8 *buffers[2],*right[2];
 NvU16 serials[2],next_serial,active,first_irq,running,dma_bits;
 NvU32 irqs,original_handler;
 NvU16 clock_started;
 NvU32 last_tick,clipped,frames_produced,max_render_ticks,late_buffers;
 struct NvMixer tail;
 /* Only this driver writes these banks; bits 0/1 mark silent left/right. */
 NvU16 clean[2];
 /* Fixed transport deadlines in Paula clocks; live state keeps EClock time. */
 NvU32 render_target,render_resyncs;
};
struct StereoDriver nv_driver;
volatile NvU8 nv_stereo_bank[4][16];
#ifdef NV_QUIET_NATIVE
/* Native music, mixed speech and bounded DMA handover state. */
volatile NvU16 nv_music_owner;
volatile NvU16 nv_quiet_muted,nv_quiet_notify;
volatile NvU32 nv_quiet_prepare_refused;
volatile NvU32 nv_quiet_period_bound[2],nv_quiet_off_tick[2];
volatile NvU32 nv_quiet_wait_ticks,nv_quiet_max_wait_ticks,nv_quiet_attach_refused;
struct QuietDiagnostic {
 NvU32 native_entries,mix_entries,native_irqs,native_services,refused_returns;
 NvU32 last_prepare_ticks,max_prepare_ticks;
 NvU16 prime_mask,speech_banks,quiet_irqs,last_rounding[2],manual_pending;
};
struct QuietDiagnostic nv_quiet;
const NvU16 nv_quiet_layout[]={sizeof(struct QuietDiagnostic),
 offsetof(struct QuietDiagnostic,native_entries),offsetof(struct QuietDiagnostic,mix_entries),
 offsetof(struct QuietDiagnostic,native_irqs),offsetof(struct QuietDiagnostic,native_services),
 offsetof(struct QuietDiagnostic,refused_returns),offsetof(struct QuietDiagnostic,last_prepare_ticks),
 offsetof(struct QuietDiagnostic,max_prepare_ticks),offsetof(struct QuietDiagnostic,prime_mask),
 offsetof(struct QuietDiagnostic,speech_banks),offsetof(struct QuietDiagnostic,quiet_irqs),
 offsetof(struct QuietDiagnostic,last_rounding),offsetof(struct QuietDiagnostic,manual_pending)};
static NvU16 bank_word(unsigned c,unsigned o);
static void quiet_write(unsigned c,unsigned o) {
 NvU32 address=AUD+16*c,period;NvU16 value;
 if(nv_music_owner!=1)return;
 if(o==6){period=bank_word(c,6);if(!period)period=65536UL;if(period>nv_quiet_period_bound[c])nv_quiet_period_bound[c]=period;}
 if(((o==0 || o==4) && (nv_quiet.prime_mask&(0x80<<c))) || (o==8 && (nv_quiet_muted&(0x80<<c))))return;
 if(!o)L(address)=((NvU32)bank_word(c,0)<<16)|bank_word(c,2);
 else {value=bank_word(c,o);if(o==8)value=(value&64?64:value&63)>>1;W(address+o)=value;}
}
#endif

volatile NvU32 nv_skipped_pirate_checks;
const NvU16 nv_driver_layout[]={sizeof(struct StereoDriver),
 offsetof(struct StereoDriver,native),
 offsetof(struct StereoDriver,buffers),offsetof(struct StereoDriver,right),
 offsetof(struct StereoDriver,serials),offsetof(struct StereoDriver,next_serial),
 offsetof(struct StereoDriver,active),offsetof(struct StereoDriver,first_irq),
 offsetof(struct StereoDriver,running),offsetof(struct StereoDriver,dma_bits),
 offsetof(struct StereoDriver,irqs),offsetof(struct StereoDriver,original_handler),
 offsetof(struct StereoDriver,clock_started),offsetof(struct StereoDriver,last_tick),
 offsetof(struct StereoDriver,clipped),offsetof(struct StereoDriver,frames_produced),
 offsetof(struct StereoDriver,max_render_ticks),offsetof(struct StereoDriver,late_buffers)};
const NvU16 nv_phase_layout[]={offsetof(struct StereoDriver,render_target),offsetof(struct StereoDriver,render_resyncs)};
NvU32 nv_game_skip_script(NvU32 script) {
 if ((nv_control.flags&(NV_CONTROL_ENABLE|NV_CONTROL_SKIP_PIRATE_CHECK))==
     (NV_CONTROL_ENABLE|NV_CONTROL_SKIP_PIRATE_CHECK) && script==152) {
  ++nv_skipped_pirate_checks;return 1;
 } return 0;
}
static NvU16 lock(void) { NvU16 prior=R(0xdff01cUL)&0x4000;nv_disable_interrupts();return prior; }
static void unlock(NvU16 prior) { nv_enable_interrupts();if(!prior)W(ENA)=0x4000; }
static NvU16 bank_word(unsigned c,unsigned o) { return (NvU16)((nv_stereo_bank[c][o]<<8)|nv_stereo_bank[c][o+1]); }
static NvS8 read_sample(void *unused,NvU32 address) { (void)unused;return *(volatile NvS8 *)address; }
static void advance(void) {
 NvU32 now=nv_clock_now_locked(),elapsed=now-nv_driver.last_tick,clocks;
 nv_driver.last_tick=now;
 /* Keep unsigned wraparound without the 68000 compiler's long multiply. */
 clocks=(elapsed<<2)+elapsed;
 /* The hybrid has exactly two virtual channels. Fixed addresses avoid
  * generating a long multiply for every sizeof(NvPaula) array index. */
 nv_paula_advance(&nv_driver.native[0],clocks);
 nv_paula_advance(&nv_driver.native[1],clocks);
}
static void events(void) {
#ifdef NV_QUIET_NATIVE
 if(nv_music_owner)return;
#endif
 if(nv_driver.native[0].irq_enabled && nv_driver.native[0].irq_pending) {
  nv_driver.native[0].irq_enabled=nv_driver.native[0].irq_pending=0;
  *(volatile NvU8 *)(nv_control.game_code+0x17e2)=0xff;
 }
 if(nv_driver.native[1].irq_enabled && nv_driver.native[1].irq_pending) {
  nv_driver.native[1].irq_enabled=nv_driver.native[1].irq_pending=0;
  *(volatile NvU8 *)(nv_control.game_code+0x17e6)=0xff;
 }
}

static int channel(NvU32 address) {
 unsigned c;
 for(c=0;c<4;++c)if(address==(NvU32)nv_stereo_bank[c] || address==AUD+16*c)return (int)c;
 return -1;
}
typedef char HybridControlFlagsLayout[(offsetof(struct NvControl,flags)==20 && NV_CONTROL_RUNNING==2)?1:-1];
typedef char HybridVolumeFastLayout[(sizeof(struct NvPaula)==54 && offsetof(struct NvPaula,volume)==36 && offsetof(struct NvPaula,irq_enabled)==40 && offsetof(struct StereoDriver,native)==0)?1:-1];
/* The assembly entry validates the running state and passes only channel 0/1. */
void nv_driver_write_virtual(__reg("d0") unsigned c,__reg("d1") NvU32 offset) {
 NvU16 prior;struct NvPaula *p;NvU32 period=0;
 /* The guards leave only channels 0/1; avoid a long struct-index multiply. */
 prior=lock();p=c?&nv_driver.native[1]:&nv_driver.native[0];
 if(offset==6) {
  period=bank_word(c,6);if(!period)period=65536UL;
  /* An identical period has no clock effect while neither virtual IRQ is
   * enabled. Keep the check under the existing interrupt lock. */
  if(!nv_driver.native[0].irq_enabled && !nv_driver.native[1].irq_enabled && period==p->period) {
   unlock(prior);return;
  }
 }
 /* Volume changes neither DMA position nor reload timing. With no enabled
  * virtual IRQ, advancing can wait until the next timed operation/service.
  * Enabling an IRQ always advances first in nv_driver_control(). */
 if(offset!=8 || nv_driver.native[0].irq_enabled || nv_driver.native[1].irq_enabled)advance();
 switch(offset) {
 case 0:nv_paula_pointer(p,((NvU32)bank_word(c,0)<<16)|bank_word(c,2));break;
 case 4:nv_paula_length(p,bank_word(c,4));break;
 case 6:p->period=period;break;
 case 8:nv_paula_volume(p,bank_word(c,8));break;
 }
 #ifdef NV_QUIET_NATIVE
 if(nv_music_owner)quiet_write(c,offset);
#endif
 if(prior)events();unlock(prior);
}
void nv_driver_volume(NvU32 address,NvU32 value) {
 int c=channel(address);NvU16 prior;struct NvPaula *p;
 if(!(nv_control.flags&NV_CONTROL_RUNNING)||c<0){W(address+8)=(NvU16)value;return;}
 if(c>=VIRTUAL_CHANNELS){W(AUD+16*c+8)=(value&64?64:value&63)>>1;return;}
 prior=lock();p=c?&nv_driver.native[1]:&nv_driver.native[0];
 if(nv_driver.native[0].irq_enabled || nv_driver.native[1].irq_enabled)advance();
 nv_stereo_bank[c][8]=(NvU8)(value>>8);nv_stereo_bank[c][9]=(NvU8)value;
 nv_paula_volume(p,(NvU16)value);
#ifdef NV_QUIET_NATIVE
 if(nv_music_owner)quiet_write(c,8);
#endif
 if(prior)events();unlock(prior);
}
void nv_driver_clear_native_volume(NvU32 c) { if(c<4)nv_driver_volume(AUD+16*c,0); }
void nv_driver_clear_volume(void) { nv_driver_clear_native_volume(0); }

/* Render snapshots only. Live native clocks/events advance exclusively with
 * the native clock; rendering ahead must never advance the song twice. */
extern void nv_zero_output(NvS8 *,NvU16);
extern void nv_hybrid_channel(const struct NvPaula *,const NvS8 *,NvU32,NvS8 *);
extern void nv_hybrid_channel_runs(const struct NvPaula *,const NvS8 *,NvU32,NvS8 *);
extern void nv_hybrid_speech(NvS8 *,NvS8 *,const NvS8 *,const NvU16 *,NvU32);
extern void nv_hybrid_speech_only(NvS8 *,NvS8 *,const NvS8 *,const NvS8 *,NvU32);
extern const NvS8 nv_average[65536];
extern void nv_hybrid_fused_unity(const struct NvPaula *,const NvU16 *,NvU32,NvS8 *,const NvS8 *,const NvS8 *);
extern void nv_hybrid_half(NvS8 *,NvS8 *,NvU32);
typedef char HybridPaulaLayout[(offsetof(struct NvPaula,reload_address)==0 &&
 offsetof(struct NvPaula,reload_bytes)==4 && offsetof(struct NvPaula,active_address)==8 &&
 offsetof(struct NvPaula,active_bytes)==12 && offsetof(struct NvPaula,index)==16 &&
 offsetof(struct NvPaula,elapsed)==20 && offsetof(struct NvPaula,period)==24 &&
 offsetof(struct NvPaula,latched_period)==28)?1:-1];
/* Write voice alone when neither virtual music channel is audible. Keep this
 * separate from the usual resampler path to avoid extra per-sample work there. */
static NvU16 speech_only(NvS8 *left,NvS8 *right,struct NativeVoice *v,NvU16 read,NvU16 available) {
 NvU16 i=0,mask=v->capacity-1;
 const NvS8 *table=half_amplitude[v->speech_gain>64?64:v->speech_gain];
 while(i<available) {
  NvU16 count=available-i,position=read&mask;
  if(count>v->capacity-position)count=v->capacity-position;
  nv_hybrid_speech_only(left+i,right+i,v->pcm+position,table,count);
  read+=count;i+=count;
 }
 nv_zero_output(left+i,CHUNK-i);nv_zero_output(right+i,CHUNK-i);
 return read;
}
/* q>=3 needs 96 bytes; q2 pairs conservatively require 129 on both sides. */
static int fused_span(const struct NvPaula *p,NvU32 maximum,NvU16 bytes) {
 return p->latched_period>p->elapsed && p->latched_period-p->elapsed<=maximum &&
  p->index<p->active_bytes && p->active_bytes-p->index>=bytes;
}
extern void nv_hybrid_channel_ahead(const struct NvPaula *,const NvS8 *,NvU32,NvS8 *,NvU32);
/* Exceptional periods retain the original snapshot projection and kernels. */
void nv_hybrid_channel_ahead_fallback(const struct NvPaula *live,const NvS8 *table,NvU32 period,NvS8 *output,NvU32 ahead) {
 struct NvPaula p;
 /* Projection/render use these fields; callback and latch output are unused. */
 p.reload_address=live->reload_address;p.reload_bytes=live->reload_bytes;
 p.active_address=live->active_address;p.active_bytes=live->active_bytes;
 p.index=live->index;p.elapsed=live->elapsed;
 p.period=live->period;p.latched_period=live->latched_period;
 p.latches=0;p.dma=live->dma;
 nv_paula_advance(&p,ahead);
 if(p.period>=period*2 && p.period<period*8)
  nv_hybrid_channel_runs(&p,table,period,output);
 else nv_hybrid_channel(&p,table,period,output);
}
static void render(unsigned buffer,NvU32 ahead) {
 struct NvPaula p0,p1;struct NativeVoice *v=nv_control.voice;
 struct NvMixer *tail=&nv_driver.tail;
 NvU16 i,serial=nv_driver.next_serial++,available=0,read=v->read_cursor;
 NvU16 period=v->output_period,mask=v->capacity-1;
#ifdef NV_RENDER_STATS
 NvU32 started=nv_clock_now(),elapsed;
#endif
 NvS8 *left=nv_driver.buffers[buffer],*right=nv_driver.right[buffer];
 const NvS8 *table0,*table1;
 const NvU16 *speech_table;
 NvU32 min_run_period,max_run_period;
 NvU16 fused_bytes;
 int active0,active1,voice_active;
 nv_driver.serials[buffer]=serial;
 if(tail->generation!=v->generation){tail->generation=v->generation;tail->tail_valid=0;}
 if(v->generation && v->cancel_generation==v->generation){v->read_cursor=v->write_cursor;v->state=NATIVE_VOICE_CANCELLED;}
 voice_active=v->generation && (v->state==NATIVE_VOICE_READY||v->state==NATIVE_VOICE_PLAYING);
 if(voice_active){available=(NvU16)(v->write_cursor-read);if(available>CHUNK)available=CHUNK;}
 active0=nv_driver.native[0].dma && nv_driver.native[0].volume;
 active1=nv_driver.native[1].dma && nv_driver.native[1].volume;
 if(!active0 && !active1) {
  if(available){nv_driver.clean[buffer]=0;read=speech_only(left,right,v,read,available);}
  else {
   /* Zero-volume DMA still advances and generates events in advance(). */
   if(!(nv_driver.clean[buffer]&1))nv_zero_output(left,CHUNK);
   if(!(nv_driver.clean[buffer]&2))nv_zero_output(right,CHUNK);
   nv_driver.clean[buffer]=3;
  }
 } else {
  if(!available) {
   if(active0){nv_driver.clean[buffer]&=2;nv_hybrid_channel_ahead(&nv_driver.native[0],half_amplitude[nv_driver.native[0].volume],period,left,ahead);}
   else if(!(nv_driver.clean[buffer]&1)){nv_zero_output(left,CHUNK);nv_driver.clean[buffer]|=1;}
   if(active1){nv_driver.clean[buffer]&=1;nv_hybrid_channel_ahead(&nv_driver.native[1],half_amplitude[nv_driver.native[1].volume],period,right,ahead);}
   else if(!(nv_driver.clean[buffer]&2)){nv_zero_output(right,CHUNK);nv_driver.clean[buffer]|=2;}
  } else {
  nv_driver.clean[buffer]=0;
  /* With no speech bytes, fold the final arithmetic half into the
   * amplitude lookup. Partial speech buffers still use the exact full mix. */
  if(active0) {
   p0=nv_driver.native[0];nv_paula_advance(&p0,ahead);
   table0=available?amplitude[p0.volume]:half_amplitude[p0.volume];
  }
  if(active1) {
   p1=nv_driver.native[1];nv_paula_advance(&p1,ahead);
   table1=available?amplitude[p1.volume]:half_amplitude[p1.volume];
  }
  /* Render only local snapshots. The assembly loops keep sample cursors and
   * phase in registers; no change to live music timing or signed rounding. */
  min_run_period=(NvU32)period*2;max_run_period=(NvU32)period*8;
  fused_bytes=96;
  if(active0 && active1 && (p0.period<min_run_period+period || p1.period<min_run_period+period))fused_bytes=129;
  if(available==CHUNK && active0 && active1 && v->speech_gain>=64 &&
     p1.period>=min_run_period && p1.period<max_run_period &&
     p0.period>=min_run_period && p0.period<max_run_period && period<=8191 &&
     v->capacity-(read&mask)>=CHUNK &&
     !(((NvU32)left|(NvU32)right|(NvU32)(v->pcm+(read&mask)))&1) &&
     fused_span(&p0,max_run_period,fused_bytes) &&
     fused_span(&p1,max_run_period,fused_bytes)) {
   nv_hybrid_fused_unity(&p0,nv_speech_words[p0.volume],period,left,v->pcm+(read&mask),nv_average+32768);
   nv_hybrid_fused_unity(&p1,nv_speech_words[p1.volume],period,right,v->pcm+(read&mask),nv_average+32768);
   read+=CHUNK;
  } else {
   if(active0) {
    if(p0.period>=min_run_period && p0.period<max_run_period)
     nv_hybrid_channel_runs(&p0,table0,period,left);
    else nv_hybrid_channel(&p0,table0,period,left);
   } else nv_zero_output(left,CHUNK);
   if(active1) {
    if(p1.period>=min_run_period && p1.period<max_run_period)
     nv_hybrid_channel_runs(&p1,table1,period,right);
    else nv_hybrid_channel(&p1,table1,period,right);
   } else nv_zero_output(right,CHUNK);
   if(available)speech_table=nv_speech_words[v->speech_gain>64?64:v->speech_gain];
   i=0;
   while(i<available) {
    NvU16 count=available-i,position=read&mask;
    if(count>v->capacity-position)count=v->capacity-position;
    nv_hybrid_speech(left+i,right+i,v->pcm+position,speech_table,count);
    read+=count;i+=count;
   }
   if(available)nv_hybrid_half(left+i,right+i,CHUNK-i);
  }
  }
 }
 #ifdef NV_QUIET_NATIVE
 if(available)nv_quiet.speech_banks|=(NvU16)(1<<buffer);
 else nv_quiet.speech_banks&=(NvU16)~(1<<buffer);
#endif
 nv_driver.frames_produced+=CHUNK;
 if(available){v->read_cursor=read;v->state=NATIVE_VOICE_PLAYING;tail->tail_serial=serial;tail->tail_valid=1;}
 if(voice_active && available<CHUNK && !v->eof)++v->underruns;
 if(v->generation && (v->state==NATIVE_VOICE_READY||v->state==NATIVE_VOICE_PLAYING) && v->eof && v->read_cursor==v->write_cursor) {
  v->rendered_generation=v->generation;v->state=NATIVE_VOICE_DRAINING;
  if(!tail->tail_valid){tail->tail_valid=1;tail->tail_serial=(NvU16)(serial-1);}
 }
 if((v->state==NATIVE_VOICE_READY||v->state==NATIVE_VOICE_PLAYING)&&!v->eof &&
    (NvU16)(v->write_cursor-v->read_cursor)<=v->capacity/2 && v->worker_task && v->signal_mask)
  nv_signal_worker(v->worker_task,v->signal_mask);
#ifdef NV_RENDER_STATS
 elapsed=nv_clock_now()-started;
 if(elapsed>nv_driver.max_render_ticks)nv_driver.max_render_ticks=elapsed;
 if(elapsed*5 >= (NvU32)CHUNK*v->output_period)++nv_driver.late_buffers;
#endif
}

/* Step one fixed transport deadline. Live state represents last_tick exactly. */
static NvU32 render_ahead(void) {
 NvU32 block=(NvU32)CHUNK*nv_control.voice->output_period;
 NvU32 now=(nv_driver.last_tick<<2)+nv_driver.last_tick;
 NvU32 ahead=nv_driver.render_target-now;
 /* A missed deadline cannot be reconstructed backwards from live state.
  * Rebase one block ahead rather than projecting an unsigned huge gap.
  * Normal servicing, including the old-last-word IRQ, is below3blocks. */
 if(ahead>block*3) {
  ahead=block;nv_driver.render_target=now+ahead;++nv_driver.render_resyncs;
 }
 nv_driver.render_target+=block;
 return ahead;
}
static void program(unsigned buffer) {
 L(AUD)=(NvU32)nv_driver.buffers[buffer];L(AUD+16)=(NvU32)nv_driver.right[buffer];
 /* Never chain volatile register assignments: VBCC may read back the right
  * lvalue to supply the left store. Paula audio registers are write-only. */
 W(AUD+4)=CHUNK/2;W(AUD+20)=CHUNK/2;
}
#ifdef NV_QUIET_NATIVE
static void quiet_manual(void) {
 unsigned c;NvU16 bit;
 for(c=0;c<2;++c) {
  bit=(NvU16)(0x80<<c);
  if((nv_quiet.manual_pending&bit) && nv_driver.native[c].irq_enabled) {
   nv_quiet.manual_pending&=(NvU16)~bit;
   nv_driver.native[c].irq_enabled=0;nv_driver.native[c].irq_pending=0;
   if(!(nv_quiet.prime_mask&bit))W(ENA)=bit;
   *(volatile NvU8 *)(nv_control.game_code+0x17e2+4*c)=0xff;
  }
 }
}
static void quiet_pending(NvU16 pending) {
 unsigned c;NvU16 bit;
 for(c=0;c<4;++c) {
  bit=(NvU16)(0x80<<c);if(!(pending&bit))continue;
  W(REQ)=bit;
  if(c<2 && (nv_quiet.prime_mask&bit)) {
   struct NvPaula *p=c?&nv_driver.native[1]:&nv_driver.native[0];
   L(AUD+16*c)=p->reload_address;W(AUD+16*c+4)=(NvU16)(p->reload_bytes>>1);
   nv_quiet.prime_mask&=(NvU16)~bit;p->irq_pending=0;
   W(AUD+16*c+8)=p->volume>>1;nv_quiet_muted&=(NvU16)~bit;
   if((nv_quiet_notify&bit) && p->irq_enabled) {
    p->irq_enabled=0;*(volatile NvU8 *)(nv_control.game_code+0x17e2+4*c)=0xff;
   }
   nv_quiet_notify&=(NvU16)~bit;
   if(!p->irq_enabled)W(ENA)=bit;
  } else {
   W(ENA)=bit;
   if(c<2){nv_driver.native[c].irq_enabled=0;nv_driver.native[c].irq_pending=0;}
   *(volatile NvU8 *)(nv_control.game_code+0x17e2+4*c)=0xff;
  }
 }
}
/* The old physical counter may retain its prior period after PER is shortened.
 * No DAT/ACK is issued until that counter plus four minimum periods drain. */
static NvU32 quiet_required(void) {
 NvU32 bound=0,required,limit;unsigned c;
 if(R(0xdff010UL)&0x33){++nv_quiet_attach_refused;return 0;}
 if(nv_music_owner==1) {
  for(c=0;c<2;++c)if(nv_driver.native[c].dma || nv_driver.last_tick-nv_quiet_off_tick[c]<71000UL)
   if(nv_quiet_period_bound[c]>bound)bound=nv_quiet_period_bound[c];
 } else bound=nv_control.voice->output_period;
 required=bound+4*124UL+456+4;
 limit=((NvU32)CHUNK*nv_control.voice->output_period)>>3;
 if(limit>4096UL)limit=4096UL;
 if(required>limit){++nv_quiet.refused_returns;return 0;}
 return required;
}
static void quiet_quiesce(NvU32 required) {
 NvU32 start,now,elapsed;
 nv_music_owner=2;nv_quiet.prime_mask=0;nv_quiet_notify=0;nv_quiet_muted=0x180;
 W(ENA)=0x180;W(AUD+8)=0;W(AUD+24)=0;W(DMA)=3;
 W(AUD+6)=124;W(AUD+22)=124;
 start=nv_clock_now_locked();
 do {
  now=nv_clock_now_locked();elapsed=now-start;
 } while(elapsed<=0x33333333UL && (elapsed<<2)+elapsed<required);
 nv_quiet_wait_ticks=elapsed;if(elapsed>nv_quiet_max_wait_ticks)nv_quiet_max_wait_ticks=elapsed;
 W(REQ)=0x180;advance();
}
static void quiet_to_mix(NvU16 *prior) {
 NvU32 now,prepared,required,frames=nv_driver.frames_produced;
 struct NativeVoice *v=nv_control.voice;
 NvU16 read=v->read_cursor,state=v->state,rendered=v->rendered_generation,underruns=v->underruns;
 NvU16 generation=nv_driver.tail.generation,tail_serial=nv_driver.tail.tail_serial,tail_valid=nv_driver.tail.tail_valid;
 NvU16 serial=nv_driver.next_serial,serial0=nv_driver.serials[0],serial1=nv_driver.serials[1];
 NvU16 speech_banks=nv_quiet.speech_banks;
 (void)prior;
 quiet_pending(R(0xdff01eUL)&R(0xdff01cUL)&0x180);
 required=quiet_required();if(!required)return;
 prepared=nv_driver.last_tick;
 render(0,0);
 now=nv_clock_now_locked();nv_quiet.last_prepare_ticks=now-prepared;
 if(nv_quiet.last_prepare_ticks>nv_quiet.max_prepare_ticks)nv_quiet.max_prepare_ticks=nv_quiet.last_prepare_ticks;
 /* Reserve the full drain and 2048 clocks for polling/programming overhead.
  * Reject before stopping native DMA; every consumed voice byte is restored. */
 if(nv_quiet.last_prepare_ticks>0x33333333UL ||
    (nv_quiet.last_prepare_ticks<<2)+nv_quiet.last_prepare_ticks+required+2048UL>=(NvU32)CHUNK*v->output_period) {
  v->read_cursor=read;v->state=state;v->rendered_generation=rendered;v->underruns=underruns;
  nv_driver.tail.generation=generation;nv_driver.tail.tail_serial=tail_serial;nv_driver.tail.tail_valid=tail_valid;
  nv_driver.next_serial=serial;nv_driver.serials[0]=serial0;nv_driver.serials[1]=serial1;
  nv_driver.frames_produced=frames;nv_driver.clean[0]=0;
  nv_quiet.speech_banks=speech_banks;++nv_quiet_prepare_refused;return;
 }
 quiet_quiesce(required);
 nv_driver.active=0;nv_driver.first_irq=1;
 nv_music_owner=0;nv_quiet.prime_mask=0;nv_quiet.quiet_irqs=0;nv_quiet_muted=nv_quiet_notify=0;
 if(nv_quiet.manual_pending&0x80)nv_driver.native[0].irq_pending=1;
 if(nv_quiet.manual_pending&0x100)nv_driver.native[1].irq_pending=1;
 nv_quiet.manual_pending=0;
 W(AUD+6)=v->output_period;W(AUD+22)=v->output_period;program(0);
 /* Bank0 and the first-IRQ bank1 use the same PREP sample epoch. */
 nv_driver.render_target=(prepared<<2)+prepared+(NvU32)CHUNK*v->output_period;
 nv_quiet_period_bound[0]=nv_quiet_period_bound[1]=v->output_period;
 ++nv_quiet.mix_entries;W(ENA)=0x8080;W(DMA)=0x8203;
}
static void quiet_to_native(NvU16 *prior) {
 unsigned c;NvU16 bits=0;NvU32 required;struct NvPaula *p;
 (void)prior;
 for(c=0;c<2;++c) {
  p=c?&nv_driver.native[1]:&nv_driver.native[0];
  if(p->dma && (!p->active_address || p->index>=p->active_bytes || p->latched_period!=p->period || p->active_bytes>131072UL || (p->active_address&1) || !p->reload_address || !p->reload_bytes || p->reload_bytes>131072UL || (p->reload_address&1))) {
   ++nv_quiet.refused_returns;return;
  }
 }
 required=quiet_required();if(!required)return;
 quiet_quiesce(required);
 /* Dispatch live logical events accumulated while only the old hardware was draining. */
 nv_music_owner=0;events();
 nv_music_owner=1;nv_quiet.prime_mask=0;nv_quiet_muted=0x180;nv_quiet_notify=0;
 for(c=0;c<2;++c) {
  NvU32 index;p=c?&nv_driver.native[1]:&nv_driver.native[0];
  index=p->index&~1UL;nv_quiet.last_rounding[c]=(NvU16)(p->index-index);
  if(p->dma) {
   L(AUD+16*c)=p->active_address+index;
   W(AUD+16*c+4)=(NvU16)((p->active_bytes-index)>>1);
   bits|=(NvU16)(1<<c);nv_quiet.prime_mask|=(NvU16)(0x80<<c);
  } else {L(AUD+16*c)=p->reload_address;W(AUD+16*c+4)=(NvU16)(p->reload_bytes>>1);}
  W(AUD+16*c+6)=(NvU16)p->period;W(AUD+16*c+8)=0;
  nv_quiet_period_bound[c]=p->period;nv_quiet_off_tick[c]=nv_driver.last_tick;
 }
 ++nv_quiet.native_entries;
 if(nv_quiet.prime_mask)W(ENA)=0x8000|nv_quiet.prime_mask;
 if(bits)W(DMA)=0x8200|bits;
}
#endif
void nv_driver_service(void) {
 NvU16 prior;if(!(nv_control.flags&NV_CONTROL_RUNNING))return;
 prior=lock();advance();
#ifdef NV_QUIET_NATIVE
 if(nv_music_owner) {
  struct NativeVoice *v=nv_control.voice;++nv_quiet.native_services;
  if(prior)quiet_manual();
  if(v->generation && (v->state==NATIVE_VOICE_READY || v->state==NATIVE_VOICE_PLAYING))quiet_to_mix(&prior);
 } else {
  struct NativeVoice *v=nv_control.voice;
  if(!nv_quiet.speech_banks && nv_quiet.quiet_irqs>=2 && v->state!=NATIVE_VOICE_READY && v->state!=NATIVE_VOICE_PLAYING && v->state!=NATIVE_VOICE_DRAINING)quiet_to_native(&prior);
 }
#endif
 if(prior)events();unlock(prior);
}
void nv_driver_install(NvU32 original_handler) {
 if(!(nv_control.flags&NV_CONTROL_RUNNING)){L(0x70)=original_handler;return;}
 L(0x70)=(NvU32)nv_irq;
}
void nv_driver_start(void) {
 unsigned c,b;NvU16 prior;struct NativeVoice *v=nv_control.voice;
 SysBase=*(void **)4;nv_game_set_policy(nv_control.policy);
 if(!(nv_control.flags&NV_CONTROL_ENABLE)||(nv_control.flags&NV_CONTROL_RUNNING))return;
 if(nv_control.flags&NV_CONTROL_DEBUG_BOOT){NvU8 *g=(NvU8 *)nv_control.game_globals;g[0x5d2a]=1;}
 if(!v||v->magic!=NATIVE_VOICE_MAGIC||v->version!=NATIVE_VOICE_VERSION||v->capacity!=NATIVE_VOICE_CAPACITY||!v->pcm||v->output_period<124)goto fail;
 for(b=0;b<2;++b){nv_driver.buffers[b]=nv_driver.right[b]=0;nv_driver.clean[b]=0;}
 for(b=0;b<2;++b){nv_driver.buffers[b]=nv_alloc_chip(CHUNK);nv_driver.right[b]=nv_alloc_chip(CHUNK);
  if(!nv_driver.buffers[b]||!nv_driver.right[b])goto free_fail;}
 if(!nv_clock_start())goto free_fail;
 nv_driver.clock_started=1;nv_driver.last_tick=nv_clock_now();nv_driver.dma_bits=0x200;
 for(c=0;c<4;++c)nv_paula_init(&nv_driver.native[c],read_sample,0);
 nv_mixer_init(&nv_driver.tail,v,0,0,v->output_period);
 prior=lock();nv_driver.original_handler=L(0x70);
 /* Paula retains its output latch when DMA stops. Silence every channel,
  * including the two direct music channels, before handing them to the game.
  * Do not write AUDxDAT: that would start manual playback and raise an IRQ. */
 for(c=0;c<4;++c)W(AUD+16*c+8)=0;
 W(DMA)=15;W(ENA)=0x780;W(REQ)=0x780;
 for(c=0;c<4;++c)*(volatile NvU32 *)(nv_control.game_code+0x1942+4*c)=(NvU32)nv_stereo_bank[c];
 nv_driver.active=0;nv_driver.next_serial=0;nv_driver.first_irq=1;nv_driver.render_resyncs=0;
#ifdef NV_QUIET_NATIVE
 nv_music_owner=1;nv_quiet.prime_mask=0;nv_quiet.manual_pending=0;nv_quiet_muted=nv_quiet_notify=0;nv_quiet.speech_banks=0;nv_quiet.quiet_irqs=0;
 nv_quiet_period_bound[0]=nv_quiet_period_bound[1]=65536UL;
 nv_quiet_off_tick[0]=nv_quiet_off_tick[1]=nv_driver.last_tick;
 ++nv_quiet.native_entries;nv_driver.running=1;nv_control.flags|=NV_CONTROL_RUNNING;
 L(0x70)=(NvU32)nv_irq;unlock(prior);return;
#endif
 render(0,0);render(1,(NvU32)CHUNK*v->output_period);
 /* Music writes/clears target mirrored banks. Physical 0/1 period and volume
  * belong to this fixed-rate transport until shutdown; DMA clears retain them. */
 W(AUD+6)=v->output_period;W(AUD+22)=v->output_period;program(0);
 nv_driver.running=1;nv_control.flags|=NV_CONTROL_RUNNING;
 /* Anchor once before DMA starts. Initial banks are positions0/256; the
  * first subsequent render belongs to512. Startup virtual DMA is OFF, so
  * initial music banks are silent. Physical startup adds a constant offset. */
 {NvU32 now=nv_clock_now_locked();nv_driver.render_target=(now<<2)+now+(NvU32)(2*CHUNK)*v->output_period;}
 L(0x70)=(NvU32)nv_irq;W(ENA)=0x8080;W(DMA)=0x8203;unlock(prior);return;
free_fail:
 for(b=0;b<2;++b){if(nv_driver.buffers[b])nv_free_chip(nv_driver.buffers[b],CHUNK);
  if(nv_driver.right[b])nv_free_chip(nv_driver.right[b],CHUNK);
  nv_driver.buffers[b]=nv_driver.right[b]=0;}
fail:nv_control.flags|=NV_CONTROL_FAILED;
}
void nv_driver_control(NvU32 kind,NvU32 incoming) {
 NvU16 value=(NvU16)incoming,set=value&0x8000,prior,bit,actual,wanted;unsigned c;
 NvU32 address=kind==0?DMA:kind==1?ENA:REQ;
 if(!(nv_control.flags&NV_CONTROL_RUNNING)){W(address)=value;return;}
 prior=lock();advance();
#ifdef NV_QUIET_NATIVE
 if(nv_music_owner) {
  if(kind==0) {
   if(set)nv_driver.dma_bits|=value&0x20f;else nv_driver.dma_bits&=(NvU16)~(value&0x20f);
   for(c=0;c<2;++c) {
    NvU16 wanted=(nv_driver.dma_bits&(0x200|(1<<c)))==(0x200|(1<<c));
    bit=(NvU16)(0x80<<c);
    if(nv_music_owner==1 && wanted && !nv_driver.native[c].dma) {
     if(nv_driver.last_tick-nv_quiet_off_tick[c]>=71000UL)nv_quiet_period_bound[c]=nv_driver.native[c].period;
     else if(nv_driver.native[c].period>nv_quiet_period_bound[c])nv_quiet_period_bound[c]=nv_driver.native[c].period;
    }
    if(nv_music_owner==1 && !wanted && nv_driver.native[c].dma)nv_quiet_off_tick[c]=nv_driver.last_tick;
    if(nv_music_owner==1 && wanted && !nv_driver.native[c].dma && (nv_quiet_muted&bit)) {
     nv_quiet.prime_mask|=bit;nv_quiet_notify|=bit;
    }
    nv_paula_dma(&nv_driver.native[c],wanted);
   }
  } else if(kind==1) {
   for(c=0;c<2;++c)if(value&(0x80<<c))nv_paula_irq_enable(&nv_driver.native[c],set!=0);
   if(value&0x4000)prior=set?0x4000:0;
  } else for(c=0;c<2;++c)if(value&(0x80<<c)) {
   bit=(NvU16)(0x80<<c);
   if(set) {
    nv_driver.native[c].irq_pending=1;
    if(nv_music_owner==2 || (nv_quiet.prime_mask&bit))nv_quiet.manual_pending|=bit;
   } else {nv_paula_irq_ack(&nv_driver.native[c]);nv_quiet.manual_pending&=(NvU16)~bit;}
  }
  if(nv_music_owner==2)W(address)=value&(NvU16)~(kind==0?3:0x180);
  else W(address)=kind==2 ? value&(NvU16)~nv_quiet.prime_mask : value;
  if(nv_music_owner==1 && kind==0)for(c=0;c<2;++c) {
   bit=(NvU16)(0x80<<c);
   if((nv_quiet.prime_mask&bit) && !nv_driver.native[c].dma) {
    nv_quiet.prime_mask&=(NvU16)~bit;nv_quiet_notify&=(NvU16)~bit;W(ENA)=bit;W(REQ)=bit;
    quiet_write(c,0);quiet_write(c,4);
    if(nv_driver.native[c].irq_enabled)W(ENA)=0x8000|bit;
   }
  }
  if(nv_music_owner==1 && (kind==0 || kind==1) && nv_quiet.prime_mask)W(ENA)=0x8000|nv_quiet.prime_mask;
  if(prior)quiet_manual();
  unlock(prior);return;
 }
#endif
 if(kind==0) {
  if(set)nv_driver.dma_bits|=value&0x20f;else nv_driver.dma_bits&=(NvU16)~(value&0x20f);
  for(c=0;c<VIRTUAL_CHANNELS;++c)nv_paula_dma(&nv_driver.native[c],(nv_driver.dma_bits&(0x200|(1<<c)))==(0x200|(1<<c)));
  W(DMA)=value&(NvU16)~0x20f;
  actual=R(0xdff002UL)&12;
  wanted=nv_driver.dma_bits&0x200 ? nv_driver.dma_bits&12 : 0;
  /* Touch physical2/3 DMA only on real state changes, never restart them
   * just because a different logical channel changed. */
  if(actual&~wanted)W(DMA)=actual&~wanted;
  if(wanted&~actual)W(DMA)=0x8000|(wanted&~actual);
  /* Video/song initialization may have cleared physical DMA. Native DMA
   * bits are virtual; the stereo output transport must remain running. */
  W(DMA)=0x8203;
 } else if(kind==1) {
  for(c=0;c<VIRTUAL_CHANNELS;++c)if(value&(0x80<<c))nv_paula_irq_enable(&nv_driver.native[c],set!=0);
  if(value&0x4000)prior=set?0x4000:0;
  W(ENA)=value&(NvU16)~0x4180;
  W(ENA)=0x8080;
 } else {
  for(c=0;c<VIRTUAL_CHANNELS;++c){bit=(NvU16)(0x80<<c);if(value&bit){
   if(set)nv_driver.native[c].irq_pending=1;else nv_paula_irq_ack(&nv_driver.native[c]);}}
  W(REQ)=value&(NvU16)~0x180;
 }
 if(prior)events();unlock(prior);
}
NvU32 nv_driver_intena(void) {
 NvU16 value=R(0xdff01cUL);unsigned c;
 if(nv_control.flags&NV_CONTROL_RUNNING){value&=(NvU16)~0x180;
  for(c=0;c<VIRTUAL_CHANNELS;++c)if(nv_driver.native[c].irq_enabled)value|=(NvU16)(0x80<<c);}
 return value;
}
void nv_driver_restore(NvU32 original_handler) { nv_driver_install(original_handler); }
void nv_driver_irq(void) {
 NvU16 pending=R(0xdff01eUL)&R(0xdff01cUL);unsigned free_buffer;
 ++nv_driver.irqs;advance();
#ifdef NV_QUIET_NATIVE
 if(nv_music_owner){++nv_quiet.native_irqs;quiet_pending(pending);quiet_manual();return;}
#endif
 if(pending&0x80){W(REQ)=0x80;
  if(nv_driver.first_irq){nv_driver.first_irq=0;W(AUD+8)=64;W(AUD+24)=64;
#ifdef NV_QUIET_NATIVE
   render(1,render_ahead());
#endif
   program(1);}
  else {free_buffer=nv_driver.active;nv_mixer_played(&nv_driver.tail,nv_driver.serials[free_buffer]);
   nv_driver.active^=1;render(free_buffer,render_ahead());program(free_buffer);
#ifdef NV_QUIET_NATIVE
     if(nv_quiet.speech_banks)nv_quiet.quiet_irqs=0;
     else if(nv_quiet.quiet_irqs<2)++nv_quiet.quiet_irqs;
#endif
   }
 }
 /* Preserve the original native reload-event handshake for hardware2/3. */
 for(free_buffer=2;free_buffer<4;++free_buffer)if(pending&(0x80<<free_buffer)) {
  W(ENA)=(NvU16)(0x80<<free_buffer);W(REQ)=(NvU16)(0x80<<free_buffer);
  *(volatile NvU8 *)(nv_control.game_code+0x17e2+4*free_buffer)=0xff;
 }
 events();
}
void nv_driver_end(void) {
 NvU16 prior;unsigned c,b;if(!(nv_control.flags&NV_CONTROL_RUNNING))return;
 prior=lock();W(ENA)=0x780;W(REQ)=0x780;W(DMA)=15;
 for(c=0;c<4;++c)W(AUD+16*c+8)=0;
 for(c=0;c<4;++c)*(volatile NvU32 *)(nv_control.game_code+0x1942+4*c)=AUD+16*c;
 L(0x70)=nv_driver.original_handler;nv_driver.running=0;
#ifdef NV_QUIET_NATIVE
 nv_music_owner=0;nv_quiet.prime_mask=0;nv_quiet_muted=nv_quiet_notify=0;
#endif
 nv_control.flags&=(NvU32)~NV_CONTROL_RUNNING;unlock(prior);
 for(b=0;b<2;++b){nv_free_chip(nv_driver.buffers[b],CHUNK);nv_free_chip(nv_driver.right[b],CHUNK);}
 if(nv_driver.clock_started){nv_clock_stop();nv_driver.clock_started=0;}
}
