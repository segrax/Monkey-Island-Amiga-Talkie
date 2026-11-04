 section text,code
 xdef _engine_find_slot
_engine_find_slot:
 movem.l d2-d3/d7/a1-a2,-(sp)
 move.w 24(sp),d2
 move.w 26(sp),d3
 lea $5539(a4),a2
 lea $57f4(a4),a1
 moveq #1,d7
.block:
 moveq #0,d1
 move.b (a2)+,d1
 cmp.w d2,d1
 beq .secondary0
.after0:
 moveq #0,d1
 move.b (a2)+,d1
 cmp.w d2,d1
 beq .secondary1
.after1:
 moveq #0,d1
 move.b (a2)+,d1
 cmp.w d2,d1
 beq .secondary2
.after2:
 moveq #0,d1
 move.b (a2)+,d1
 cmp.w d2,d1
 beq .secondary3
.after3:
 addq.w #4,d7
 cmpi.w #97,d7
 bcs .block
.tail:
 moveq #0,d1
 move.b (a2)+,d1
 cmp.w d2,d1
 beq .tail_secondary
.tail_next:
 addq.w #1,d7
 cmpi.w #100,d7
 bcs .tail
 lea $5538(a4),a0
 moveq #0,d0
.return:
 movem.l (sp)+,d2-d3/d7/a1-a2
 tst.l d7
 rts
.found:
 movea.l a1,a0
 move.l d0,d0
 bra .return
.tail_secondary:
 move.l d7,d0
 move.b (a1,d0.w),d1
 cmp.w d3,d1
 beq .found
 addq.w #1,d7
 cmpi.w #100,d7
 bcs .tail
 movea.l a1,a0
 moveq #0,d0
 bra .return
.secondary0:
 move.l d7,d0
 move.b (a1,d0.w),d1
 cmp.w d3,d1
 beq .found
 bra .after0
.secondary1:
 move.l d7,d0
 addq.w #1,d0
 move.b (a1,d0.w),d1
 cmp.w d3,d1
 beq .found
 bra .after1
.secondary2:
 move.l d7,d0
 addq.w #2,d0
 move.b (a1,d0.w),d1
 cmp.w d3,d1
 beq .found
 bra .after2
.secondary3:
 move.l d7,d0
 addq.w #3,d0
 move.b (a1,d0.w),d1
 cmp.w d3,d1
 beq .found
 bra .after3
