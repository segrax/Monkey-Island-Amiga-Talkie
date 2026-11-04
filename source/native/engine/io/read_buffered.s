; GPL-3.0-or-later. Preserve byte-order copying; refill through the original reader.
 section text,code
 xdef _fread_fast
 xdef _fread_original
_fread_fast:
 cmpi.w #1,8(sp)
 bne _fread_original
 tst.w 10(sp)
 ble _fread_original
 ; Stream control must not alias the destination span.
 move.l 4(sp),d0
 movea.l 12(sp),a0
 move.l a0,d1
 addi.l #24,d1
 cmp.l d1,d0
 bcc .safe
 moveq #0,d1
 move.w 10(sp),d1
 add.l d0,d1
 cmp.l a0,d1
 bhi _fread_original
.safe:
 movem.l d2-d4/a2-a3,-(sp)
 movea.l 24(sp),a3
 moveq #0,d3
 move.w 30(sp),d3
 movea.l 32(sp),a2
 moveq #0,d4
.next:
 moveq #0,d2
 move.w 8(a2),d2
 ble .refill
 cmp.w d3,d2
 bls .bounded
 move.w d3,d2
.bounded:
 movea.l 4(a2),a0
 ; Embedded/unusual stream buffers retain the original implementation.
 move.l a2,d0
 addi.l #24,d0
 cmpa.l d0,a0
 bcc .copy
 move.l a0,d1
 add.l d2,d1
 cmp.l a2,d1
 bhi .tail
.copy:
 sub.w d2,8(a2)
 sub.w d2,d3
 add.w d2,d4
 ; Keep forward-copy semantics for aliases and word alignment on 68000.
 cmpi.w #16,d2
 bcs .byte_span
 move.l a0,d0
 move.l a3,d1
 eor.l d0,d1
 btst #0,d1
 bne .byte_span
 move.l a3,d1
 sub.l d0,d1
 bls .aligned_span
 cmpi.l #4,d1
 bcs .byte_span
.aligned_span:
 btst #0,d0
 beq .words
 move.b (a0)+,(a3)+
 subq.w #1,d2
.words:
 move.w d2,d1
 lsr.w #2,d1
 andi.w #3,d2
 subq.w #1,d1
.longs:
 move.l (a0)+,(a3)+
 dbra d1,.longs
 tst.w d2
 beq .copied
.byte_span:
 subq.w #1,d2
.bytes:
 move.b (a0)+,(a3)+
 dbra d2,.bytes
.copied:
 move.l a0,4(a2)
 tst.w d3
 bne .next
 bra .done
.refill:
 move.l a2,-(sp)
 move.w #1,-(sp)
 move.w #1,-(sp)
 move.l a3,-(sp)
 jsr _fread_original
 lea 12(sp),sp
 tst.l d0
 beq .done
 addq.l #1,a3
 addq.w #1,d4
 subq.w #1,d3
 bne .next
.done:
 moveq #0,d0
 move.w d4,d0
 movem.l (sp)+,d2-d4/a2-a3
 rts
.tail:
 move.l a2,-(sp)
 move.w d3,-(sp)
 move.w #1,-(sp)
 move.l a3,-(sp)
 jsr _fread_original
 lea 12(sp),sp
 add.w d4,d0
 movem.l (sp)+,d2-d4/a2-a3
 rts
_fread_original:
