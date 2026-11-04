 section text,code
 xdef _nv_art_alloc
 xdef _nv_art_alloc_any
 xdef _nv_art_free
 xdef _nv_art_file_open
 xdef _nv_art_file_close
 xdef _nv_art_read_at
 xdef _nv_art_row
 xdef _nv_art_exec
 xdef _nv_art_dos
_nv_art_exec:
 move.l 4.w,d0
 rts
_nv_art_row:
 move.l 4(sp),d0
 divu.w #320,d0
 andi.l #$ffff,d0
 rts
_nv_art_alloc:
 move.l a6,-(sp)
 move.l 8(sp),d0
 move.l #$10005,d1
 movea.l 4.w,a6
 jsr -198(a6)
 movea.l (sp)+,a6
 rts
_nv_art_alloc_any:
 move.l a6,-(sp)
 move.l 8(sp),d0
 move.l #$10001,d1
 movea.l 4.w,a6
 jsr -198(a6)
 movea.l (sp)+,a6
 rts
_nv_art_free:
 move.l a6,-(sp)
 movea.l 8(sp),a1
 move.l 12(sp),d0
 movea.l 4.w,a6
 jsr -210(a6)
 movea.l (sp)+,a6
 rts
_nv_art_file_open:
 movem.l d2/a6,-(sp)
 movea.l 4.w,a6
 lea _dos_name(pc),a1
 moveq #0,d0
 jsr -552(a6)
 move.l d0,_nv_art_dos
 beq.s _open_done
 movea.l d0,a6
 lea _file_name(pc),a0
 move.l a0,d1
 move.l #1005,d2
 jsr -30(a6)
_open_done:
 movem.l (sp)+,d2/a6
 rts
_nv_art_file_close:
 move.l a6,-(sp)
 move.l _nv_art_dos,d0
 beq.s _close_done
 movea.l d0,a6
 move.l 8(sp),d1
 beq.s _close_library
 jsr -36(a6)
_close_library:
 movea.l a6,a1
 movea.l 4.w,a6
 jsr -414(a6)
 clr.l _nv_art_dos
_close_done:
 movea.l (sp)+,a6
 rts
_nv_art_read_at:
 movem.l d2-d3/a6,-(sp)
 movea.l _nv_art_dos,a6
 move.l 16(sp),d1
 move.l 20(sp),d2
 moveq #-1,d3
 jsr -66(a6)
 cmpi.l #-1,d0
 beq.s _read_done
 move.l 16(sp),d1
 move.l 24(sp),d2
 move.l 28(sp),d3
 jsr -42(a6)
_read_done:
 movem.l (sp)+,d2-d3/a6
 rts
_dos_name:
 dc.b 'dos.library',0
_file_name:
 dc.b 'native-planar.dat',0
 even
 section BSS,bss
_nv_art_dos:
 ds.l 1
