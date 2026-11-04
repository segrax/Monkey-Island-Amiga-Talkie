 section text,code
 xdef _nv_art_checksum
; Fletcher32 over BE16 words. End-around carry performs modulo65535
; after each addition; all-zero checksums retain the FFFF representation.
_nv_art_checksum:
 movem.l d2-d3,-(sp)
 movea.l 12(sp),a0
 move.l 16(sp),d3
 lsr.l #1,d3
 move.l d3,d0
 andi.w #3,d0
 movea.l d0,a1
 move.l #65535,d1
 move.l d1,d2
 moveq #0,d0
 lsr.w #2,d3
 beq.s .scalar
 subq.w #1,d3
.four:
 add.w (a0)+,d1
 addx.w d0,d1
 add.w d1,d2
 addx.w d0,d2
 add.w (a0)+,d1
 addx.w d0,d1
 add.w d1,d2
 addx.w d0,d2
 add.w (a0)+,d1
 addx.w d0,d1
 add.w d1,d2
 addx.w d0,d2
 add.w (a0)+,d1
 addx.w d0,d1
 add.w d1,d2
 addx.w d0,d2
 dbra d3,.four
.scalar:
 move.l a1,d3
 beq.s .done
 subq.w #1,d3
.one:
 add.w (a0)+,d1
 addx.w d0,d1
 add.w d1,d2
 addx.w d0,d2
 dbra d3,.one
.done:
 move.l d2,d0
 swap d0
 move.w d1,d0
 movem.l (sp)+,d2-d3
 rts
