; GPL-3.0-or-later. Avoid callee saves for DMA-off and no-boundary returns.
; The crossing helper receives a0=state,d0=clocks after the first transition.
 section text,code
 xdef _nv_paula_advance
 xref _nv_paula_advance_cross
_nv_paula_advance:
 movea.l 4(sp),a0
 tst.w 38(a0)
 beq.s .done
 move.l 28(a0),d1
 sub.l 20(a0),d1
 move.l 8(sp),d0
 cmp.l d1,d0
 bcc.s .full
 add.l d0,20(a0)
.done:
 rts
.full:
 sub.l d1,d0
 ; A complete 32/16 quotient is valid only when high(numerator)<period.
 ; Keep larger quotients on the complete analytical fallback.
 move.l 24(a0),d1
 cmpi.l #65535,d1
 bhi.s .fallback
 movea.l d0,a1
 swap d0
 cmp.w d1,d0
 bcc.s .restore
 swap d0
 divu.w d1,d0
 moveq #0,d1
 move.w d0,d1
 add.l 16(a0),d1
 addq.l #1,d1
 cmp.l 12(a0),d1
 bcc.s .reload
 move.l d1,16(a0)
 clr.w d0
 swap d0
 move.l d0,20(a0)
 move.l 24(a0),28(a0)
 rts
.restore:
 move.l a1,d0
.fallback:
 jmp _nv_paula_advance_cross
.reload:
 ; A valid cursor starts before active_bytes. With a fitting clock quotient,
 ; at most 65535 bytes remain after the first source reload.
 move.l d2,-(sp)
 move.l d1,d2
 sub.l 12(a0),d2
 cmp.l 4(a0),d2
 bcs.s .single_reload
 ; remaining >= reload_bytes proves both the divisor and quotient fit.
 divu.w 6(a0),d2
 moveq #0,d1
 move.w d2,d1
 addq.l #1,d1
 clr.w d2
 swap d2
 bra.s .publish_reload
.single_reload:
 moveq #1,d1
.publish_reload:
 add.l d1,32(a0)
 move.l d2,16(a0)
 clr.w d0
 swap d0
 move.l d0,20(a0)
 move.l 24(a0),28(a0)
 move.l (a0),8(a0)
 move.l 4(a0),12(a0)
 move.w #1,42(a0)
 move.l (sp)+,d2
 rts
