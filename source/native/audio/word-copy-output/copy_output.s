; Local native experiment, GPL-3.0-or-later.
 section text,code
 xdef _nv_copy_output
_nv_copy_output:
 move.l 4(sp),a0
 move.l 8(sp),a1
 moveq #0,d0
 move.w 14(sp),d0
 beq .done
 move.l a0,d1
 btst #0,d1
 bne .bytes
 move.l a1,d1
 btst #0,d1
 bne .bytes
 move.w d0,d1
 lsr.w #2,d1
 beq .bytes
 subq.w #1,d1
.long:
 move.l (a1)+,(a0)+
 dbra d1,.long
 andi.w #3,d0
 beq .done
.bytes:
 subq.w #1,d0
.byte:
 move.b (a1)+,(a0)+
 dbra d0,.byte
.done:
 rts
