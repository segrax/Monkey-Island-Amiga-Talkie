 section text,code
 xdef _nv_mmio_read_word
 xdef _nv_mmio_read_byte
 xdef _nv_read_cia_counter
_nv_mmio_read_word:
 movea.l 4(sp),a0
 moveq #0,d0
 move.w (a0),d0
 rts
_nv_mmio_read_byte:
 movea.l 4(sp),a0
 moveq #0,d0
 move.b (a0),d0
 rts
_nv_read_cia_counter:
 movea.l 4(sp),a0
 movea.l 8(sp),a1
.retry:
 moveq #0,d0
 move.b (a1),d0
 moveq #0,d1
 move.b (a0),d1
 cmp.b (a1),d0
 bne.s .retry
 lsl.w #8,d0
 or.w d1,d0
 rts
