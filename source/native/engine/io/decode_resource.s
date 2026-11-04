; Replace only the post-read XOR loop. Keep fread calls and chunking unchanged.
 xdef _decode_fast
_decode_fast:
 cmpi.l #$4000,d6
 bhi .original
 tst.l d6
 ble .original
 movem.l d1-d2,-(sp)
 move.l a3,d1
 add.l d6,d1
 bcs .fallback
 lea $671c(a4),a0
 cmpa.l a3,a0
 blo .separate
 cmpa.l d1,a0
 blo .fallback
.separate:
 moveq #0,d0
 move.b $671c(a4),d0
 move.w d0,d1
 lsl.w #8,d0
 or.w d1,d0
 move.w d0,d1
 swap d0
 move.w d1,d0
 move.l a3,d1
 btst #0,d1
 beq .aligned
 eor.b d0,(a3)+
 subq.l #1,d6
.aligned:
 move.w d6,d1
 lsr.w #2,d1
 beq .tail
 subq.w #1,d1
.longs:
 eor.l d0,(a3)+
 dbra d1,.longs
.tail:
 andi.w #3,d6
 beq .done
 subq.w #1,d6
.bytes:
 eor.b d0,(a3)+
 dbra d6,.bytes
.done:
 lea -1(a3),a0
 movem.l (sp)+,d1-d2
 moveq #0,d0
 moveq #0,d6
 subq.l #1,d6
 tst.l d0
 rts
.fallback:
 movem.l (sp)+,d1-d2
.original:
 bra .test
.byte:
 movea.l a3,a0
 addq.l #1,a3
 move.b $671c(a4),d0
 eor.b d0,(a0)
.test:
 move.l d6,d0
 subq.l #1,d6
 tst.l d0
 bne .byte
 rts
