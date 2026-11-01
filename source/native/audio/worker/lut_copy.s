; Local native experiment, GPL-3.0-or-later.
 section text,code
 xdef _native_lut_copy
_native_lut_copy:
 move.l a2,-(sp)
 movea.l 8(sp),a0
 movea.l 12(sp),a1
 move.l 16(sp),d1
 movea.l 20(sp),a2
 tst.l d1
 beq .done
 cmpi.l #16384,d1
 bhi .done
 subq.w #1,d1
 moveq #0,d0
.copy:
 move.b (a1)+,d0
 move.b (a2,d0.w),(a0)+
 dbra d1,.copy
.done:
 movea.l (sp)+,a2
 rts
