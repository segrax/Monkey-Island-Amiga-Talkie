 section text,code
 xdef _nv_costume_exec
 xdef _nv_costume_alloc
 xdef _nv_costume_free
_nv_costume_exec:
 move.l 4.w,d0
 rts
_nv_costume_alloc:
 move.l a6,-(sp)
 move.l 8(sp),d0
 move.l #$10005,d1
 movea.l 4.w,a6
 jsr -198(a6)
 movea.l (sp)+,a6
 rts
_nv_costume_free:
 move.l a6,-(sp)
 movea.l 8(sp),a1
 move.l 12(sp),d0
 movea.l 4.w,a6
 jsr -210(a6)
 movea.l (sp)+,a6
 rts

 xdef _nv_costume_flush
_nv_costume_flush:
 move.l a6,-(sp)
 movea.l 4.w,a6
 jsr -636(a6)
 movea.l (sp)+,a6
 rts
