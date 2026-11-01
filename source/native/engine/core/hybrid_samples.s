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
 ; Count down to the next source sample. Reload periods apply after the
 ; currently latched sample, including the first one in this snapshot.
 sub.l d2,d3
 move.l d3,d2
 move.w #255,d6
 moveq #0,d0
 move.b (a3),d0
 move.b (0,a1,d0.w),d1
.sample:
 move.b d1,(a2)+
 sub.l d5,d2
 bgt.s .next
.phase:
 addq.l #1,a3
 cmpa.l a4,a3
 bne.s .period
 movea.l (a0),a3
 movea.l a3,a4
 adda.l 4(a0),a4
.period:
 add.l d4,d2
 ble.s .phase
 ; Repeated output samples reuse the scaled byte; skipped source samples
 ; need no memory read. Live music phase is still advanced elsewhere.
 move.b (a3),d0
 move.b (0,a1,d0.w),d1
.next:
 dbra d6,.sample
 movem.l (sp)+,d2-d6/a2-a4
 rts

 xdef _nv_hybrid_speech
; (left, right, contiguous PCM, scaled-speech word row, sample count as long)
_nv_hybrid_speech:
 movem.l d2-d3/a2-a4,-(sp)
 movea.l 24(sp),a0
 movea.l 28(sp),a1
 movea.l 32(sp),a2
 movea.l 36(sp),a3
 move.l 40(sp),d3
 beq.s .done
 xref _nv_average
 lea _nv_average+32768,a4
 subq.w #1,d3
.mix:
 moveq #0,d2
 move.b (a2)+,d2
 add.w d2,d2
 ; Word table places scaled speech in the high byte. Each music byte
 ; completes a signed 16-bit index into the exact signed-average table.
 move.w (0,a3,d2.w),d0
 move.b (a0),d0
 move.b (0,a4,d0.w),(a0)+
 move.b (a1),d0
 move.b (0,a4,d0.w),(a1)+
 dbra d3,.mix
.done:
 movem.l (sp)+,d2-d3/a2-a4
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
