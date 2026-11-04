 section text,code
 xdef _nv_art_indices
; (even-aligned uint16 indices, rows <= 8000, even maximum offset <= 32754).
_nv_art_indices:
 move.l d2,-(sp)
 movea.l 8(sp),a0
 move.l 12(sp),d2
 move.l 16(sp),d1
 lsr.w #1,d1
 tst.l d2
 beq.s .valid
 subq.w #1,d2
.loop:
 move.w (a0)+,d0
 ; Odd offsets rotate into the high half, beyond every permitted limit.
 ror.w #1,d0
 cmp.w d1,d0
 bhi.s .invalid
 dbra d2,.loop
.valid:
 moveq #1,d0
 bra.s .done
.invalid:
 moveq #0,d0
.done:
 move.l (sp)+,d2
 rts
