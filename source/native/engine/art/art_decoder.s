; Exact admitted strip decode and masked primary copy.
; A4 points to the manager-validated NvArtDecode context. The manager proves
; artifact/current source/palette/history/output/control ranges do not alias.
 section text,code
 xdef _nv_art_decoder
_nv_art_decoder:
 movem.l d2-d7/a2-a5,-(sp)
 move.l d0,d7
 move.l a4,d0
 beq.w art_dec_miss
 btst #0,d0
 bne.w art_dec_miss
 tst.w 26(a4)
 bne.w art_dec_miss
 xdef _nv_art_global_000
_nv_art_global_000:
 tst.w $5d40.l
 bne.w art_dec_miss
 moveq #0,d6
 move.w 24(a4),d6
 beq.w art_dec_miss
 cmpi.w #200,d6
 bhi.w art_dec_miss
 moveq #0,d0
 xdef _nv_art_global_001
_nv_art_global_001:
 move.b $5c38.l,d0
 cmp.w d6,d0
 bne.w art_dec_miss
 lsl.w #6,d0
 move.w d0,d1
 lsl.w #2,d0
 add.w d1,d0
 subq.w #1,d0
 xdef _nv_art_global_002
_nv_art_global_002:
 cmp.w $5c36.l,d0
 bne.w art_dec_miss
 xdef _nv_art_global_003
_nv_art_global_003:
 move.l $5c1a.l,d0
 xdef _nv_art_global_004
_nv_art_global_004:
 move.l $5c1e.l,d1
 or.l d1,d0
 btst #0,d0
 bne.w art_dec_miss
 move.l 12(a4),d5
 sub.l 8(a4),d5
 bcs.w art_dec_miss
 beq.w art_dec_miss
 cmpi.l #65535,d5
 bhi.w art_dec_miss
 xdef _nv_art_global_005
_nv_art_global_005:
 move.l $5c2a.l,d4
 beq.w art_dec_miss
 subq.l #1,d4
 move.l d4,d0
 add.l d5,d0
 bcs.w art_dec_miss
 movea.l 20(a4),a0
 xdef _nv_art_global_006
_nv_art_global_006:
 lea $5c49.l,a1
 moveq #15,d2
art_dec_palette:
 cmpm.b (a0)+,(a1)+
 bne.w art_dec_miss
 dbra d2,art_dec_palette
 movea.l 8(a4),a0
 movea.l d4,a1
 move.l d5,d3
 move.l a0,d0
 eor.l d4,d0
 btst #0,d0
 bne.s art_dec_source_bytes
 btst #0,d4
 beq.s art_dec_source_aligned
 cmpm.b (a0)+,(a1)+
 bne.w art_dec_miss
 subq.w #1,d3
 beq.s art_dec_source_equal
art_dec_source_aligned:
 move.w d3,d2
 lsr.w #2,d2
 beq.s art_dec_source_suffix
 subq.w #1,d2
art_dec_source_longs:
 cmpm.l (a0)+,(a1)+
 bne.w art_dec_miss
 dbra d2,art_dec_source_longs
art_dec_source_suffix:
 andi.w #3,d3
 beq.s art_dec_source_equal
art_dec_source_bytes:
 move.w d3,d2
 subq.w #1,d2
art_dec_source_byte:
 cmpm.b (a0)+,(a1)+
 bne.w art_dec_miss
 dbra d2,art_dec_source_byte
art_dec_source_equal:
 movea.l (a4),a5
 movea.l 4(a4),a2
 movea.l 16(a4),a1
 xdef _nv_art_global_007
_nv_art_global_007:
 lea $6812.l,a3
 move.w d6,d2
art_dec_history_byte:
 moveq #0,d1
 move.b (a1)+,d1
 beq.s art_dec_history_skip
 moveq #7,d0
art_dec_history_row:
 btst d0,d1
 beq.s art_dec_history_next
 move.w (a2),d3
 move.b (a5,d3.w),d3
 cmp.b (a3),d3
 bne.w art_dec_miss
art_dec_history_next:
 addq.l #2,a2
 addq.l #1,a3
 subq.w #1,d2
 beq.s art_dec_verified
 subq.w #1,d0
 bpl.s art_dec_history_row
 bra.s art_dec_history_byte
art_dec_history_skip:
 subi.w #8,d2
 bls.s art_dec_verified
 lea 16(a2),a2
 lea 8(a3),a3
 bra.s art_dec_history_byte
art_dec_verified:
 movea.l (a4),a5
 movea.l 4(a4),a2
 xdef _nv_art_global_008
_nv_art_global_008:
 lea $6812.l,a3
 xdef _nv_art_global_009
_nv_art_global_009:
 movea.l $5c1a.l,a4
 xdef _nv_art_global_010
_nv_art_global_010:
 movea.l $5c1e.l,a1
 move.l a6,d7
 xdef _nv_art_global_011
_nv_art_global_011:
 movea.l $5c26.l,a6
 subq.w #1,d6
art_dec_fused_row:
 move.w (a2)+,d0
 lea (a5,d0.w),a0
 move.l (a0)+,d0
 move.l (a0)+,d1
 move.l d0,(a4)+
 move.l d1,(a4)+
 move.b d1,(a3)+
 move.b (a6),d2
 bne.s art_dec_fused_masked
 move.l d0,(a1)
 move.l d1,4(a1)
art_dec_fused_masked:
 adda.w #320,a1
 adda.w #312,a4
 adda.w #40,a6
 dbra d6,art_dec_fused_row
 move.l d1,d3
 movea.l a1,a0
 movea.l a6,a3
 movea.l d7,a6
 movea.l d4,a1
 adda.l d5,a1
 move.l #312,d0
 moveq #0,d1
 move.w #$ffff,d1
 tst.b d2
 bne.s art_dec_fused_done
 tst.l d3
art_dec_fused_done:
 movem.l (sp)+,d2-d7/a2-a5
 rts
art_dec_miss:
 move.l d7,d0
 jmp _nv_art_decoder_fallback

 xdef _nv_art_decoder_end
_nv_art_decoder_end:
