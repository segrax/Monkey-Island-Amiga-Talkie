 section text,code
 xdef _engine_fill
_engine_fill:
 movem.l d6-d7/a3,-(sp)
 movea.l 16(sp),a3
 move.b 21(sp),d7
 move.w 22(sp),d6
 tst.w d6
 beq.s .return
 cmpi.w #16,d6
 bcs.s .bytes
 andi.l #255,d7
 move.w d7,d0
 lsl.w #8,d7
 or.w d0,d7
 move.w d7,d0
 swap d7
 move.w d0,d7
 move.l a3,d0
 btst #0,d0
 beq.s .aligned
 move.b d7,(a3)+
 subq.w #1,d6
.aligned:
 move.w d6,d0
 lsr.w #4,d0
 beq.s .remainder
 subq.w #1,d0
.longs:
 move.l d7,(a3)+
 move.l d7,(a3)+
 move.l d7,(a3)+
 move.l d7,(a3)+
 dbra d0,.longs
.remainder:
 andi.w #15,d6
 beq.s .finish
.bytes:
 move.b d7,(a3)+
 subq.w #1,d6
 bne.s .bytes
.finish:
 ; The original's final loop test returns D6's upper word in D0,
 ; zero in its low word, Z set and X set by the final decrement.
 move.l d6,d0
 subq.w #1,d6
 tst.w d0
.return:
 movem.l (sp)+,d6-d7/a3
 rts
