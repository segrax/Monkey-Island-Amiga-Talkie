/* Isolated guest E-clock benchmark; never patches a running game. */
#include <exec/types.h>
#include <exec/memory.h>
#include <proto/exec.h>
#include <stdio.h>
#include <string.h>
#include "native_clock.h"
#include "bench_bindings.h"

static unsigned char *globals, *pixels, *frame, *mask;

static void word(unsigned offset, unsigned value) {
    *(unsigned short *)(globals + offset) = value;
}
static void pointer(unsigned offset, void *value) {
    *(unsigned long *)(globals + offset) = (unsigned long)value;
}
static unsigned long read32(FILE *f) {
    unsigned char b[4];
    if (fread(b, 1, 4, f) != 4) return 0;
    return (unsigned long)b[0]<<24 | (unsigned long)b[1]<<16 | (unsigned)b[2]<<8 | b[3];
}
static void *load(const char *name, const unsigned short *relocs, unsigned count) {
    FILE *f = fopen(name, "rb");
    unsigned long bytes;
    unsigned char *code;
    unsigned i;
    if (!f) return 0;
    fseek(f, 0, SEEK_END); bytes = ftell(f); rewind(f);
    code = AllocMem(bytes, MEMF_PUBLIC | MEMF_FAST);
    if (!code || fread(code, 1, bytes, f) != bytes) { fclose(f); return 0; }
    fclose(f);
    for (i=0; i<count; ++i) *(unsigned long *)(code+relocs[i]) += (unsigned long)globals;
    return code;
}
static unsigned long checksum(void) {
    unsigned long sum=0, i, y;
    unsigned height=globals[0x5c38] ? globals[0x5c38] : 256;
    for (y=0; y<height; ++y) for (i=0; i<8; ++i)
        sum=sum*33+pixels[y*320+i]+frame[y*320+i];
    for (i=0; i<256; ++i) sum=sum*33+globals[0x6812+i];
    return sum;
}
static void prepare(unsigned char *tokens, unsigned height, unsigned mode) {
    unsigned i;
    memset(globals, 0, 0x7300);
    memset(pixels, 'Z', 0x20000); memset(frame, 'Q', 0x20000);
    memset(mask, 0, 0x3000); memset(globals+0x6812, 'W', 256);
    for (i=0; i<16; ++i) globals[0x5c49+i]=16+i;
    pointer(0x5c26, mask); pointer(0x5c2a, tokens);
    pointer(0x5c1e, frame); pointer(0x5c1a, pixels);
    word(0x5c36, height*320-1); globals[0x5c38]=height;
    word(0x5d40, mode);
}
int main(void) {
    void (*functions[2])(void);
    FILE *cases, *result;
    unsigned long count, n, length, height, memory, mode, order, variant, repeat;
    unsigned long ticks[2], sums[2], start;
    unsigned char *tokens;
    globals=AllocMem(0x7300, MEMF_PUBLIC|MEMF_FAST);
    pixels=AllocMem(0x20000, MEMF_PUBLIC|MEMF_FAST);
    mask=AllocMem(0x3000, MEMF_PUBLIC|MEMF_FAST);
    if (!globals || !pixels || !mask || !nv_clock_start()) return 10;
    functions[0]=load("baseline.bin", baseline_relocs, sizeof(baseline_relocs)/2);
    functions[1]=load("candidate.bin", candidate_relocs, sizeof(candidate_relocs)/2);
    if (!functions[0] || !functions[1]) return 11;
    result=fopen("results.csv", "w"); if (!result) return 12;
    fprintf(result,"memory,case,height,mask,order,baseline_ticks,candidate_ticks,checksum\n");
    fflush(result);
    for (memory=0; memory<2; ++memory) {
        frame=AllocMem(0x20000, MEMF_PUBLIC|(memory ? MEMF_CHIP : MEMF_FAST));
        if (!frame) return 13;
        cases=fopen("cases.dat", "rb"); if (!cases) return 14;
        count=read32(cases);
        for (n=0; n<count; ++n) {
            height=read32(cases); length=read32(cases);
            tokens=AllocMem(length+16, MEMF_PUBLIC|MEMF_FAST|MEMF_CLEAR);
            if (!tokens || fread(tokens,1,length,cases)!=length) return 15;
            for (mode=0; mode<2; ++mode) for (order=0; order<2; ++order) {
                for (repeat=0; repeat<2; ++repeat) {
                    variant=repeat^order;
                    prepare(tokens,height,mode);
                    /* No disk writes, host IPC or emulator polling inside this interval. */
                    start=nv_clock_now();
                    functions[variant](); functions[variant]();
                    functions[variant](); functions[variant]();
                    ticks[variant]=nv_clock_now()-start;
                    sums[variant]=checksum();
                }
                if (sums[0]!=sums[1]) { fprintf(result,"MISMATCH\n"); fclose(result); return 16; }
                fprintf(result,"%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu\n",memory,n,height,mode,order,ticks[0],ticks[1],sums[0]);
                fflush(result);
            }
            FreeMem(tokens,length+16);
        }
        fclose(cases); FreeMem(frame,0x20000);
    }
    fprintf(result,"DONE\n"); fclose(result); nv_clock_stop();
    return 0;
}
