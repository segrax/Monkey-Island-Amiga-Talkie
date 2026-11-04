 section text,code
 xdef _nv_glyph_same
; Boolean equality for admitted 0..64548-byte RAM spans. C ABI, D2 preserved.
_nv_glyph_same:
 move.l d2,-(sp)
 movea.l 8(sp),a0
 movea.l 12(sp),a1
 move.l 16(sp),d0
 beq.s .equal
 move.l a0,d1
 move.l a1,d2
 eor.l d2,d1
 btst #0,d1
 bne.s .bytes
 btst #0,d2
 beq.s .aligned
 cmpm.b (a0)+,(a1)+
 bne.s .different
 subq.l #1,d0
.aligned:
 move.l d0,d1
 lsr.l #2,d1
 beq.s .bytes
 subq.w #1,d1
 andi.w #3,d0
.longs:
 cmpm.l (a0)+,(a1)+
 bne.s .different
 dbra d1,.longs
.bytes:
 tst.l d0
 beq.s .equal
 subq.w #1,d0
.byte_loop:
 cmpm.b (a0)+,(a1)+
 bne.s .different
 dbra d0,.byte_loop
.equal:
 moveq #1,d0
 move.l (sp)+,d2
 rts
.different:
 moveq #0,d0
 move.l (sp)+,d2
 rts
