 section text,code
 xdef _engine_copy
_engine_copy:
 movem.l d6-d7/a2-a3,-(sp)
 movea.l 20(sp),a3
 movea.l 24(sp),a2
 move.w 28(sp),d7
 tst.w d7
 beq.s .return
 cmpi.w #16,d7
 bcs.s .bytes
 move.l a2,d0
 move.l a3,d6
 eor.l d0,d6
 btst #0,d6
 bne.s .bytes
 ; Close forward overlap must retain the original byte ordering.
 cmpa.l a2,a3
 bls.s .separate
 move.l a3,d6
 sub.l d0,d6
 cmpi.l #4,d6
 bcs.s .bytes
.separate:
 btst #0,d0
 beq.s .aligned
 move.b (a2)+,(a3)+
 subq.w #1,d7
.aligned:
 move.w d7,d0
 lsr.w #4,d0
 beq.s .remainder
 subq.w #1,d0
.longs:
 move.l (a2)+,(a3)+
 move.l (a2)+,(a3)+
 move.l (a2)+,(a3)+
 move.l (a2)+,(a3)+
 dbra d0,.longs
.remainder:
 andi.w #15,d7
 beq.s .finish
.bytes:
 move.b (a2)+,(a3)+
 subq.w #1,d7
 bne.s .bytes
.finish:
 ; Preserve the original counter test and D0 upper word.
 move.l d7,d0
 subq.w #1,d7
 tst.w d0
.return:
 movem.l (sp)+,d6-d7/a2-a3
 rts
