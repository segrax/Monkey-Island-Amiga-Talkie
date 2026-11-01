/* Local stereo software-mixing trial, GPL-3.0-or-later. */
#include "native_driver.h"
#include "native_client.h"
#include "native_clock.h"
#include "native_timeline.h"
#include <stddef.h>
#define W(a) (*(volatile NvU16 *)(a))
#define L(a) (*(volatile NvU32 *)(a))
#define AUD 0xdff0a0UL
#define DMA 0xdff096UL
#define ENA 0xdff09aUL
#define REQ 0xdff09cUL
#define CHUNK 128
#ifdef __VBCC__
static int third(__reg("d0") int value) = "\text.l\td0\n\tdivs.w\t#3,d0";
#else
static int third(int value) { return value/3; }
#endif
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
 NvU32 last_tick,clipped,frames_produced;
 struct NvMixer tail;
};
struct StereoDriver nv_driver;
volatile NvU8 nv_stereo_bank[4][16];
volatile NvU32 nv_skipped_pirate_checks;
const NvU16 nv_driver_layout[]={sizeof(struct StereoDriver),
 offsetof(struct StereoDriver,native),
 offsetof(struct StereoDriver,buffers),offsetof(struct StereoDriver,right),
 offsetof(struct StereoDriver,serials),offsetof(struct StereoDriver,next_serial),
 offsetof(struct StereoDriver,active),offsetof(struct StereoDriver,first_irq),
 offsetof(struct StereoDriver,running),offsetof(struct StereoDriver,dma_bits),
 offsetof(struct StereoDriver,irqs),offsetof(struct StereoDriver,original_handler),
 offsetof(struct StereoDriver,clock_started),offsetof(struct StereoDriver,last_tick),
 offsetof(struct StereoDriver,clipped),offsetof(struct StereoDriver,frames_produced)};
NvU32 nv_game_skip_script(NvU32 script) {
 if ((nv_control.flags&(NV_CONTROL_ENABLE|NV_CONTROL_SKIP_PIRATE_CHECK))==
     (NV_CONTROL_ENABLE|NV_CONTROL_SKIP_PIRATE_CHECK) && script==152) {
  ++nv_skipped_pirate_checks;return 1;
 } return 0;
}
static NvU16 lock(void) { NvU16 prior=W(0xdff01cUL)&0x4000;nv_disable_interrupts();return prior; }
static void unlock(NvU16 prior) { nv_enable_interrupts();if(!prior)W(ENA)=0x4000; }
static NvU16 bank_word(unsigned c,unsigned o) { return (NvU16)((nv_stereo_bank[c][o]<<8)|nv_stereo_bank[c][o+1]); }
static NvS8 read_sample(void *unused,NvU32 address) { (void)unused;return *(volatile NvS8 *)address; }
static void advance(void) {
 NvU32 now=nv_clock_now(),clocks=(now-nv_driver.last_tick)*5;
 unsigned c;nv_driver.last_tick=now;
 for(c=0;c<4;++c)nv_paula_advance(&nv_driver.native[c],clocks);
}
static void events(void) {
 unsigned c;
 for(c=0;c<4;++c)if(nv_paula_take_irq(&nv_driver.native[c]))
  *(volatile NvU8 *)(nv_control.game_code+0x17e2+4*c)=0xff;
}
static int channel(NvU32 address) {
 unsigned c;
 for(c=0;c<4;++c)if(address==(NvU32)nv_stereo_bank[c] || address==AUD+16*c)return (int)c;
 return -1;
}
void nv_driver_write(NvU32 address,NvU32 offset) {
 int c=channel(address);NvU16 prior;struct NvPaula *p;
 if(!(nv_control.flags&NV_CONTROL_RUNNING)||c<0)return;
 prior=lock();advance();p=&nv_driver.native[c];
 switch(offset) {
 case 0:nv_paula_pointer(p,((NvU32)bank_word(c,0)<<16)|bank_word(c,2));break;
 case 4:nv_paula_length(p,bank_word(c,4));break;
 case 6:nv_paula_period(p,bank_word(c,6));break;
 case 8:nv_paula_volume(p,bank_word(c,8));break;
 }
 if(prior)events();unlock(prior);
}
void nv_driver_volume(NvU32 address,NvU32 value) {
 int c=channel(address);NvU16 prior;
 if(!(nv_control.flags&NV_CONTROL_RUNNING)||c<0){W(address+8)=(NvU16)value;return;}
 prior=lock();advance();nv_stereo_bank[c][8]=(NvU8)(value>>8);nv_stereo_bank[c][9]=(NvU8)value;
 nv_paula_volume(&nv_driver.native[c],(NvU16)value);if(prior)events();unlock(prior);
}
void nv_driver_clear_native_volume(NvU32 c) { if(c<4)nv_driver_volume(AUD+16*c,0); }
void nv_driver_clear_volume(void) { nv_driver_clear_native_volume(0); }

/* Render snapshots only. Live native clocks/events advance exclusively with
 * ReadEClock; rendering ahead must never advance the song a second time. */
static void render(unsigned buffer,NvU32 ahead) {
 struct NvPaula p[4];struct NativeVoice *v=nv_control.voice;
 struct NvMixer *tail=&nv_driver.tail;
 NvU16 i,c,serial=nv_driver.next_serial++,consumed=0,starved=0;
 int sound[4],speech,left,right,gain=v->speech_gain>64?64:v->speech_gain;
 nv_driver.serials[buffer]=serial;
 for(c=0;c<4;++c){p[c]=nv_driver.native[c];nv_paula_advance(&p[c],ahead);}
 if(tail->generation!=v->generation){tail->generation=v->generation;tail->tail_valid=0;}
 if(v->generation && v->cancel_generation==v->generation){v->read_cursor=v->write_cursor;v->state=NATIVE_VOICE_CANCELLED;}
 for(i=0;i<CHUNK;++i) {
  for(c=0;c<4;++c) {
   sound[c]=p[c].dma ? (int)*(volatile NvS8 *)(p[c].active_address+p[c].index)*p[c].volume/64:0;
   if(p[c].dma) {
    p[c].elapsed+=v->output_period;
    while(p[c].elapsed>=p[c].latched_period) {
     p[c].elapsed-=p[c].latched_period;p[c].latched_period=p[c].period;
     if(++p[c].index==p[c].active_bytes){p[c].active_address=p[c].reload_address;
      p[c].active_bytes=p[c].reload_bytes;p[c].index=0;}
    }
   }
  }
  speech=0;
  if(v->generation && (v->state==NATIVE_VOICE_READY||v->state==NATIVE_VOICE_PLAYING)) {
   if(v->read_cursor!=v->write_cursor){speech=(int)v->pcm[v->read_cursor&(v->capacity-1)]*gain/64;
    ++v->read_cursor;v->state=NATIVE_VOICE_PLAYING;consumed=1;
   } else if(!v->eof)starved=1;
  }
  /* Paula 0+3 are left; 1+2 are right. Constant 1/3 headroom prevents
   * overflow without speech-dependent music ducking or gain pumping. */
  left=third(sound[0]+sound[3]+speech);right=third(sound[1]+sound[2]+speech);
  nv_driver.buffers[buffer][i]=(NvS8)left;nv_driver.right[buffer][i]=(NvS8)right;
 }
 nv_driver.frames_produced+=CHUNK;
 if(consumed){tail->tail_serial=serial;tail->tail_valid=1;}
 if(starved)++v->underruns;
 if(v->generation && (v->state==NATIVE_VOICE_READY||v->state==NATIVE_VOICE_PLAYING) && v->eof && v->read_cursor==v->write_cursor) {
  v->rendered_generation=v->generation;v->state=NATIVE_VOICE_DRAINING;
  if(!tail->tail_valid){tail->tail_valid=1;tail->tail_serial=(NvU16)(serial-1);}
 }
 if((v->state==NATIVE_VOICE_READY||v->state==NATIVE_VOICE_PLAYING)&&!v->eof &&
    (NvU16)(v->write_cursor-v->read_cursor)<=v->capacity/2 && v->worker_task && v->signal_mask)
  nv_signal_worker(v->worker_task,v->signal_mask);
}
static void program(unsigned buffer) {
 NvU16 volume=nv_driver.first_irq?0:64;
 L(AUD)=(NvU32)nv_driver.buffers[buffer];L(AUD+16)=(NvU32)nv_driver.right[buffer];
 /* Never chain volatile register assignments: VBCC may read back the right
  * lvalue to supply the left store. Paula audio registers are write-only. */
 W(AUD+4)=CHUNK/2;W(AUD+20)=CHUNK/2;
 W(AUD+6)=nv_control.voice->output_period;W(AUD+22)=nv_control.voice->output_period;
 W(AUD+8)=volume;W(AUD+24)=volume;
}
void nv_driver_service(void) {
 NvU16 prior;if(!(nv_control.flags&NV_CONTROL_RUNNING))return;
 prior=lock();advance();if(prior)events();unlock(prior);
}
void nv_driver_install(NvU32 original_handler) {
 if(!(nv_control.flags&NV_CONTROL_RUNNING)){L(0x70)=original_handler;return;}
 L(0x70)=(NvU32)nv_irq;
}
void nv_driver_start(void) {
 unsigned c,b;NvU16 prior;struct NativeVoice *v=nv_control.voice;
 SysBase=*(void **)4;nv_game_set_policy(nv_control.policy);
 if(!(nv_control.flags&NV_CONTROL_ENABLE)||(nv_control.flags&NV_CONTROL_RUNNING))return;
 if(!v||v->magic!=NATIVE_VOICE_MAGIC||v->version!=NATIVE_VOICE_VERSION||v->capacity!=NATIVE_VOICE_CAPACITY||!v->pcm||v->output_period<124)goto fail;
 for(b=0;b<2;++b)nv_driver.buffers[b]=nv_driver.right[b]=0;
 for(b=0;b<2;++b){nv_driver.buffers[b]=nv_alloc_chip(CHUNK);nv_driver.right[b]=nv_alloc_chip(CHUNK);
  if(!nv_driver.buffers[b]||!nv_driver.right[b])goto free_fail;}
 if(!nv_clock_start())goto free_fail;
 nv_driver.clock_started=1;nv_driver.last_tick=nv_clock_now();nv_driver.dma_bits=0x200;
 for(c=0;c<4;++c)nv_paula_init(&nv_driver.native[c],read_sample,0);
 nv_mixer_init(&nv_driver.tail,v,0,0,v->output_period);
 prior=lock();nv_driver.original_handler=L(0x70);
 W(AUD+8)=0;W(AUD+24)=0;W(DMA)=15;W(ENA)=0x780;W(REQ)=0x780;
 for(c=0;c<4;++c)*(volatile NvU32 *)(nv_control.game_code+0x1942+4*c)=(NvU32)nv_stereo_bank[c];
 nv_driver.active=0;nv_driver.next_serial=0;nv_driver.first_irq=1;
 render(0,0);render(1,(NvU32)CHUNK*v->output_period);program(0);
 nv_driver.running=1;nv_control.flags|=NV_CONTROL_RUNNING;
 L(0x70)=(NvU32)nv_irq;W(ENA)=0x8080;W(DMA)=0x8203;unlock(prior);return;
free_fail:
 for(b=0;b<2;++b){if(nv_driver.buffers[b])nv_free_chip(nv_driver.buffers[b],CHUNK);
  if(nv_driver.right[b])nv_free_chip(nv_driver.right[b],CHUNK);
  nv_driver.buffers[b]=nv_driver.right[b]=0;}
fail:nv_control.flags|=NV_CONTROL_FAILED;
}
void nv_driver_control(NvU32 kind,NvU32 incoming) {
 NvU16 value=(NvU16)incoming,set=value&0x8000,prior,bit;unsigned c;
 NvU32 address=kind==0?DMA:kind==1?ENA:REQ;
 if(!(nv_control.flags&NV_CONTROL_RUNNING)){W(address)=value;return;}
 prior=lock();advance();
 if(kind==0) {
  if(set)nv_driver.dma_bits|=value&0x20f;else nv_driver.dma_bits&=(NvU16)~(value&0x20f);
  for(c=0;c<4;++c)nv_paula_dma(&nv_driver.native[c],(nv_driver.dma_bits&(0x200|(1<<c)))==(0x200|(1<<c)));
  W(DMA)=value&(NvU16)~0x20f;
  /* Video/song initialization may have cleared physical DMA. Native DMA
   * bits are virtual; the stereo output transport must remain running. */
  W(DMA)=0x8203;
 } else if(kind==1) {
  for(c=0;c<4;++c)if(value&(0x80<<c))nv_paula_irq_enable(&nv_driver.native[c],set!=0);
  if(value&0x4000)prior=set?0x4000:0;
  W(ENA)=value&(NvU16)~0x4780;
  W(ENA)=0x8080;
 } else {
  for(c=0;c<4;++c){bit=(NvU16)(0x80<<c);if(value&bit){
   if(set)nv_driver.native[c].irq_pending=1;else nv_paula_irq_ack(&nv_driver.native[c]);}}
  W(REQ)=value&(NvU16)~0x780;
 }
 if(prior)events();unlock(prior);
}
NvU32 nv_driver_intena(void) {
 NvU16 value=W(0xdff01cUL);unsigned c;
 if(nv_control.flags&NV_CONTROL_RUNNING){value&=(NvU16)~0x780;
  for(c=0;c<4;++c)if(nv_driver.native[c].irq_enabled)value|=(NvU16)(0x80<<c);}
 return value;
}
void nv_driver_restore(NvU32 original_handler) { nv_driver_install(original_handler); }
void nv_driver_irq(void) {
 NvU16 pending=W(0xdff01eUL)&W(0xdff01cUL);unsigned free_buffer;
 ++nv_driver.irqs;advance();
 if(pending&0x80){W(REQ)=0x80;
  if(nv_driver.first_irq){nv_driver.first_irq=0;program(1);}
  else {free_buffer=nv_driver.active;nv_mixer_played(&nv_driver.tail,nv_driver.serials[free_buffer]);
   nv_driver.active^=1;render(free_buffer,(NvU32)CHUNK*nv_control.voice->output_period);program(free_buffer);}
 }
 events();
}
void nv_driver_end(void) {
 NvU16 prior;unsigned c,b;if(!(nv_control.flags&NV_CONTROL_RUNNING))return;
 prior=lock();W(ENA)=0x780;W(REQ)=0x780;W(DMA)=15;W(AUD+8)=0;W(AUD+24)=0;
 for(c=0;c<4;++c)*(volatile NvU32 *)(nv_control.game_code+0x1942+4*c)=AUD+16*c;
 L(0x70)=nv_driver.original_handler;nv_driver.running=0;nv_control.flags&=(NvU32)~NV_CONTROL_RUNNING;unlock(prior);
 for(b=0;b<2;++b){nv_free_chip(nv_driver.buffers[b],CHUNK);nv_free_chip(nv_driver.right[b],CHUNK);}
 if(nv_driver.clock_started){nv_clock_stop();nv_driver.clock_started=0;}
}
