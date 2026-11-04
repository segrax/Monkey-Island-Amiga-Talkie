 section code,code
 xdef _engine_mask_rle
_engine_mask_rle:
 ; D1 is the original byte height: zero means 256 rows.
 ; D2-D4 use exactly the original twelve-byte save frame.
 movem.l d2-d4,-(sp)
 movea.l $5c22.l,a1
 move.w #40,d3
 move.w #127,d4
 moveq #0,d1
 move.b $5c38.l,d1
 movea.l $5c2e.l,a0
.decode:
 moveq #0,d2
 move.b (a0)+,d2
 bmi .repeat
 subq.b #1,d2
.literal:
 ; Literal reads stay immediately adjacent to their corresponding writes.
 move.b (a0)+,(a1)
 adda.w d3,a1
 subq.b #1,d1
 beq .finish
 dbra d2,.literal
 bra .decode
.repeat:
 ; Preserve zero-count packet semantics through the original byte decrement.
 and.b d4,d2
 subq.b #1,d2
 move.b (a0)+,d0
 cmpi.w #7,d2
 blo .repeat_small
 addq.w #1,d2
 moveq #0,d3
 move.b d1,d3
 bne .height
 move.w #256,d3
.height:
 cmp.w d3,d2
 bls .selected
 move.w d3,d2
.selected:
 ; Bound a complete run before unrolling. Keep individual BYTE bus accesses.
 sub.b d2,d1
 move.w d2,d4
 lsr.w #3,d4
 andi.w #7,d2
 tst.w d4
 beq .remainder
 subq.w #1,d4
.block:
 move.b d0,(a1)
 move.b d0,40(a1)
 move.b d0,80(a1)
 move.b d0,120(a1)
 move.b d0,160(a1)
 move.b d0,200(a1)
 move.b d0,240(a1)
 move.b d0,280(a1)
 adda.w #320,a1
 dbra d4,.block
.remainder:
 tst.w d2
 beq .next
 subq.w #1,d2
.tail:
 move.b d0,(a1)
 adda.w #40,a1
 dbra d2,.tail
.next:
 move.w #40,d3
 move.w #127,d4
 tst.b d1
 bne .decode
 ; Recreate the original final SUBQ.B 1 -> 0 flags, including cleared X.
 moveq #1,d1
 subq.b #1,d1
 bra .finish
.repeat_small:
 move.b d0,(a1)
 adda.w d3,a1
 subq.b #1,d1
 beq .finish
 dbra d2,.repeat_small
 bra .decode
.finish:
 movem.l (sp)+,d2-d4
 rts

 xdef _engine_mask_rle_end
_engine_mask_rle_end:
