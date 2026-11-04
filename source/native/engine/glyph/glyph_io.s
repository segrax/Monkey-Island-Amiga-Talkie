 section text,code
 xdef _nv_glyph_open,_nv_glyph_close,_nv_glyph_read
_nv_glyph_open:
 movem.l d2/a6,-(sp)
 movea.l 4.w,a6
 lea _dos_name(pc),a1
 moveq #0,d0
 jsr -552(a6)
 move.l d0,_nv_glyph_dos
 beq.s _open_done
 movea.l d0,a6
 move.l 12(sp),d1
 move.l #1005,d2
 jsr -30(a6)
 tst.l d0
 bne.s _open_done
 movea.l a6,a1
 movea.l 4.w,a6
 jsr -414(a6)
 clr.l _nv_glyph_dos
 moveq #0,d0
_open_done:
 movem.l (sp)+,d2/a6
 rts
_nv_glyph_close:
 move.l a6,-(sp)
 move.l _nv_glyph_dos,d0
 beq.s _close_done
 movea.l d0,a6
 move.l 8(sp),d1
 beq.s _close_library
 jsr -36(a6)
_close_library:
 movea.l a6,a1
 movea.l 4.w,a6
 jsr -414(a6)
 clr.l _nv_glyph_dos
_close_done:
 movea.l (sp)+,a6
 rts
_nv_glyph_read:
 movem.l d2-d3/a6,-(sp)
 movea.l _nv_glyph_dos,a6
 move.l 16(sp),d1
 move.l 20(sp),d2
 move.l 24(sp),d3
 jsr -42(a6)
 movem.l (sp)+,d2-d3/a6
 rts
_dos_name:
 dc.b 'dos.library',0
 even
 section bss,bss
_nv_glyph_dos: ds.l 1
