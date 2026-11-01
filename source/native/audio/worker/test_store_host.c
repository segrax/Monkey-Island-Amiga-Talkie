/* Host filesystem/fault-injection tests. The portable production codec is linked unchanged. */
#include "native_metadata_store.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
int __real_rename(const char *,const char *);
size_t __real_fwrite(const void *,size_t,size_t,FILE *);
int __real_fclose(FILE *);
static int rename_at,rename_n,write_fail,close_fail,restore_fail,close_n;
int __wrap_rename(const char*a,const char*b){
 ++rename_n;
 if(rename_n==rename_at || (restore_fail && strstr(a,".bak"))){errno=EIO;return -1;}
 return __real_rename(a,b);
}
size_t __wrap_fwrite(const void*p,size_t a,size_t n,FILE*f){if(write_fail){write_fail=0;return 0;}return __real_fwrite(p,a,n,f);}
int __wrap_fclose(FILE*f){int r=__real_fclose(f);if(++close_n==close_fail){return EOF;}return r;}
static unsigned char original[6574],loaded[6574],map[16];
static struct NvPolicy p;
static const char*save="savegame._a_";
static void reset(void){rename_at=rename_n=write_fail=close_fail=restore_fail=close_n=0;}
static int load(void){NvU32 n=123;int r=nv_metadata_load(save,map,&p,loaded,sizeof(loaded),&n,1);if(r==1)assert(n==sizeof(loaded)&&!memcmp(loaded,original,n));else assert(n==0);return r;}
static int store(void){return nv_metadata_save(save,map,&p,original,sizeof(original),1);}
static void copy(const char*a,const char*b){char buf[8192];size_t n;FILE*i=fopen(a,"rb"),*o=fopen(b,"wb");assert(i&&o);while((n=fread(buf,1,sizeof(buf),i)))assert(fwrite(buf,1,n,o)==n);assert(!fclose(i)&&!fclose(o));}
static void init(void){nv_policy_init(&p,0x12345678);p.trigger_count=1;p.triggers[0].selector=3;p.triggers[0].room=49;p.triggers[0].count=3;p.selector_count=1;p.selectors[0]=(struct NvSelector){3,49,2,3};}
int main(void){
 FILE*f;unsigned i;NvU32 n;
 remove("savegame._a_.talkie");remove("savegame._a_.talkie.tmp");remove("savegame._a_.talkie.bak");
 for(i=0;i<sizeof(original);++i)original[i]=(unsigned char)(i*37);
 memset(map,0x42,16);init();f=fopen(save,"wb");assert(f);assert(fwrite("ORIGINAL SAVE BYTES",1,19,f)==19);assert(!fclose(f));
 assert(load()==0);init();assert(store()==1);copy("savegame._a_.talkie","good");
 p.random_seed=77;p.selector_count=0;assert(load()==1&&p.random_seed==0x12345678&&p.selector_count==1&&p.selectors[0].index==2);
 /* Every header field, payload, selector and digest corruption must fail closed. */
 for(i=0;i<64+8+sizeof(original)+16;i+=17){copy("good","savegame._a_.talkie");f=fopen("savegame._a_.talkie","r+b");assert(f);assert(!fseek(f,i,SEEK_SET));{int c=fgetc(f);assert(c!=EOF);assert(!fseek(f,i,SEEK_SET));assert(fputc(c^0x80,f)!=EOF);}assert(!fclose(f));memset(loaded,0xaa,sizeof(loaded));assert(load()==-1&&loaded[0]==0xaa&&p.selector_count==0);}
 copy("good","savegame._a_.talkie");map[0]^=1;assert(load()==-1);map[0]^=1;
 f=fopen(save,"ab");assert(f);assert(fputc('x',f)!=EOF);assert(!fclose(f));assert(load()==-1);f=fopen(save,"wb");assert(f);assert(fwrite("ORIGINAL SAVE BYTES",1,19,f)==19);assert(!fclose(f));
 /* Existing sidecar survives write, close, first rename and commit failures. */
 for(i=0;i<4;++i){copy("good","savegame._a_.talkie");init();reset();if(i==0)write_fail=1;if(i==1)close_fail=2;if(i==2)rename_at=1;if(i==3)rename_at=2;assert(store()==-2);reset();assert(load()==1);}
 /* Failed rollback keeps a valid backup; only a missing main may use it. */
 copy("good","savegame._a_.talkie");init();reset();rename_at=2;restore_fail=1;assert(store()==-2);reset();assert(load()==1);assert(!rename("savegame._a_.talkie.bak","savegame._a_.talkie"));
 copy("good","savegame._a_.talkie.bak");f=fopen("savegame._a_.talkie","wb");assert(f);assert(!fclose(f));assert(load()==-1);assert(!remove("savegame._a_.talkie"));assert(load()==1);
 init();p.selectors[0].index=3;assert(store()==-1);init();p.selector_count=2;p.selectors[1]=p.selectors[0];assert(store()==-1);
 assert(nv_metadata_load(save,map,&p,loaded,sizeof(loaded),&n,2)==-1);
 f=fopen(save,"rb");assert(f);{char b[20]={0};assert(fread(b,1,19,f)==19&&!strcmp(b,"ORIGINAL SAVE BYTES"));assert(fgetc(f)==EOF);}assert(!fclose(f));
 puts("PASS: exact roundtrip/RNG/selectors, 392 corruption cases, binding, missing/backup, write/close/rename/rollback faults, original-save unchanged");return 0;
}
