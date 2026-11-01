; GPL-3.0-or-later. Exact signed8 hybrid sample loops for a plain 68000.
 section text,code
 xdef _nv_hybrid_channel
; (snapshot, amplitude row, output period as long, output)
; NvPaula offsets are checked by the compiled driver's layout assertions.
_nv_hybrid_channel:
 movem.l d2-d6/a2-a4,-(sp)
 movea.l 36(sp),a0
 movea.l 40(sp),a1
 move.l 44(sp),d5
 movea.l 48(sp),a2
 movea.l 8(a0),a3
 adda.l 16(a0),a3
 movea.l 8(a0),a4
 adda.l 12(a0),a4
 move.l 20(a0),d2
 move.l 28(a0),d3
 move.l 24(a0),d4
 move.w #255,d6
 moveq #0,d0
.sample:
 move.b (a3),d0
 move.b (0,a1,d0.w),(a2)+
 add.l d5,d2
.phase:
 cmp.l d3,d2
 blo.s .next
 sub.l d3,d2
 move.l d4,d3
 addq.l #1,a3
 cmpa.l a4,a3
 bne.s .phase
 movea.l (a0),a3
 movea.l a3,a4
 adda.l 4(a0),a4
 bra.s .phase
.next:
 dbra d6,.sample
 movem.l (sp)+,d2-d6/a2-a4
 rts

 xdef _nv_hybrid_speech
; (left, right, contiguous PCM, amplitude row, sample count as long)
_nv_hybrid_speech:
 movem.l d2-d3/a2-a3,-(sp)
 movea.l 20(sp),a0
 movea.l 24(sp),a1
 movea.l 28(sp),a2
 movea.l 32(sp),a3
 move.l 36(sp),d3
 beq.s .done
 subq.w #1,d3
 moveq #0,d2
.mix:
 move.b (a2)+,d2
 move.b (0,a3,d2.w),d0
 ext.w d0
 move.b (a0),d1
 ext.w d1
 add.w d0,d1
 asr.w #1,d1
 move.b d1,(a0)+
 move.b (a1),d1
 ext.w d1
 add.w d0,d1
 asr.w #1,d1
 move.b d1,(a1)+
 dbra d3,.mix
.done:
 movem.l (sp)+,d2-d3/a2-a3
 rts

 xdef _nv_hybrid_half
; (left, right, sample count as long); arithmetic shift preserves odd negatives.
_nv_hybrid_half:
 movea.l 4(sp),a0
 movea.l 8(sp),a1
 move.l 12(sp),d0
 beq.s .done
 subq.w #1,d0
.half:
 move.b (a0),d1
 asr.b #1,d1
 move.b d1,(a0)+
 move.b (a1),d1
 asr.b #1,d1
 move.b d1,(a1)+
 dbra d0,.half
.done:
 rts
