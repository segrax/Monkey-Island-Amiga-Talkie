; Local native experiment, GPL-3.0-or-later.
 section text,code
 xdef _nv_divmod16
_nv_divmod16:
 move.l 4(sp),d0
 move.w 10(sp),d1
 divu.w d1,d0
 move.l 12(sp),a0
 move.l d0,d1
 swap d1
 andi.l #$ffff,d1
 move.l d1,(a0)
 andi.l #$ffff,d0
 rts
