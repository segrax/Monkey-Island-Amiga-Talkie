/* GPL-3.0-or-later. The CPU reads the ring; Paula uses separate DMA buffers. */
static void *nv_alloc_voice_ring(void) {
 void *pcm = AllocMem(NATIVE_VOICE_CAPACITY, MEMF_PUBLIC | MEMF_FAST | MEMF_CLEAR);
 if (!pcm)
  pcm = AllocMem(NATIVE_VOICE_CAPACITY, MEMF_PUBLIC | MEMF_CLEAR);
 return pcm;
}
