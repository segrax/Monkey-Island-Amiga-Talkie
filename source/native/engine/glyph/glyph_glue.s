 section text,code
 xref _nv_glyph_load,_nv_glyph_lookup,_nv_glyph_scope_lookup,_nv_glyph
 xdef _nv_glyph_load_entry,_nv_glyph_entry,_nv_glyph_fallback
_nv_glyph_load_entry:

 movem.l d0-d7/a0-a6,-(sp)
 seq d0
 smi d1
 scs d2
 svs d3
 moveq #0,d4
 addx.b d4,d4
 andi.w #1,d0
 andi.w #1,d1
 andi.w #1,d2
 andi.w #1,d3
 lsl.w #4,d4
 lsl.w #2,d0
 lsl.w #3,d1
 lsl.w #1,d3
 or.w d0,d4
 or.w d1,d4
 or.w d2,d4
 or.w d3,d4
 move.w d4,-(sp)
 movem.l 2(sp),d0-d7/a0-a6
 move.l sp,d0
 addi.l #62,d0
 move.l d0,-(sp)
 moveq #0,d0
 move.w 8(a5),d0
 move.l d0,-(sp)
 jsr _nv_glyph_load
 addq.l #8,sp
 move.w (sp)+,ccr
 movem.l (sp)+,d0-d7/a0-a6
 movem.l -20(a5),d5-d7
 xdef _nv_continue_glyph_load
_nv_continue_glyph_load:
 jmp $250e.l
_nv_glyph_entry:
 tst.w _nv_glyph+98
 beq.w _nv_glyph_fallback
 subq.l #4,sp

 movem.l d0-d7/a0-a6,-(sp)
 seq d0
 smi d1
 scs d2
 svs d3
 moveq #0,d4
 addx.b d4,d4
 andi.w #1,d0
 andi.w #1,d1
 andi.w #1,d2
 andi.w #1,d3
 lsl.w #4,d4
 lsl.w #2,d0
 lsl.w #3,d1
 lsl.w #1,d3
 or.w d0,d4
 or.w d1,d4
 or.w d2,d4
 or.w d3,d4
 move.w d4,-(sp)
 movem.l 2(sp),d0-d7/a0-a6
 move.l sp,d0
 addi.l #66,d0
 move.l d0,-(sp)
 jsr _nv_glyph_scope_lookup
 tst.l d0
 bne.s .selected
 jsr _nv_glyph_lookup
.selected:
 addq.l #4,sp
 tst.l d0
 beq.w .miss
 move.l d0,62(sp)
 move.w (sp)+,ccr
 movem.l (sp)+,d0-d7/a0-a6
 bsr.w replay
 addq.l #4,sp
 rts
.miss:
 move.w (sp)+,ccr
 movem.l (sp)+,d0-d7/a0-a6
 addq.l #4,sp
_nv_glyph_fallback:
 jmp $0.l
replay:
 movem.l d2-d6/a2-a5,-(sp)
 movea.l 40(sp),a3
 xdef _nv_glyph_global_000
_nv_glyph_global_000:
 movea.l $5c1e.l,a0
 movea.l a0,a1
 xdef _nv_glyph_global_001
_nv_glyph_global_001:
 lea $5920.l,a2
 xdef _nv_glyph_global_002
_nv_glyph_global_002:
 movea.l $5c26.l,a4
 moveq #0,d3
 moveq #0,d6
 xdef _nv_glyph_global_003
_nv_glyph_global_003:
 move.b $6f5c.l,d6
glyph_phase:
 cmpi.b #$80,d6
 beq.s glyph_mode
 add.b d6,d6
 addq.w #1,d3
 bra.s glyph_phase
glyph_mode:
 xdef _nv_glyph_global_004
_nv_glyph_global_004:
 move.w $5d40.l,d4
 xdef _nv_glyph_global_005
_nv_glyph_global_005:
 or.b $66e9.l,d4
 lea glyph_done(pc),a5
 jmp (a3)
glyph_done:
 moveq #0,d0
 xdef _nv_glyph_global_006
_nv_glyph_global_006:
 move.b $6f5a.l,d0
 mulu.w #320,d0
 xdef _nv_glyph_global_007
_nv_glyph_global_007:
 add.l $5c1e.l,d0
 movea.l d0,a0
 movea.l d0,a1
 move.l #$ffff0000,d1
 xdef _nv_glyph_global_008
_nv_glyph_global_008:
 move.b $6f5a.l,d1
 movem.l (sp)+,d2-d6/a2-a5
 move.w #4,ccr
 rts

 xref _nv_glyph_scope_begin,_nv_glyph_scope_cancel
 xdef _nv_glyph_scope_entry,_nv_glyph_scope_exit
_nv_glyph_scope_entry:

 movem.l d0-d7/a0-a6,-(sp)
 seq d0
 smi d1
 scs d2
 svs d3
 moveq #0,d4
 addx.b d4,d4
 andi.w #1,d0
 andi.w #1,d1
 andi.w #1,d2
 andi.w #1,d3
 lsl.w #4,d4
 lsl.w #2,d0
 lsl.w #3,d1
 lsl.w #1,d3
 or.w d0,d4
 or.w d1,d4
 or.w d2,d4
 or.w d3,d4
 move.w d4,-(sp)
 movem.l 2(sp),d0-d7/a0-a6
 move.l sp,d0
 addi.l #62,d0
 move.l d0,-(sp)
 jsr _nv_glyph_scope_begin
 addq.l #4,sp
 move.w (sp)+,ccr
 movem.l (sp)+,d0-d7/a0-a6
 tst.b $672c(a4)
 beq.s glyph_scope_zero
 xdef _nv_continue_glyph_scope_nonzero
_nv_continue_glyph_scope_nonzero:
 jmp $dfd6.l
glyph_scope_zero:
 xdef _nv_continue_glyph_scope_zero
_nv_continue_glyph_scope_zero:
 jmp $dfe2.l
_nv_glyph_scope_exit:

 movem.l d0-d7/a0-a6,-(sp)
 seq d0
 smi d1
 scs d2
 svs d3
 moveq #0,d4
 addx.b d4,d4
 andi.w #1,d0
 andi.w #1,d1
 andi.w #1,d2
 andi.w #1,d3
 lsl.w #4,d4
 lsl.w #2,d0
 lsl.w #3,d1
 lsl.w #1,d3
 or.w d0,d4
 or.w d1,d4
 or.w d2,d4
 or.w d3,d4
 move.w d4,-(sp)
 movem.l 2(sp),d0-d7/a0-a6
 jsr _nv_glyph_scope_cancel
 move.w (sp)+,ccr
 movem.l (sp)+,d0-d7/a0-a6
 movem.l (sp)+,d2-d4/d7/a3
 unlk a5
 xdef _nv_continue_glyph_scope_exit
_nv_continue_glyph_scope_exit:
 jmp $e156.l
