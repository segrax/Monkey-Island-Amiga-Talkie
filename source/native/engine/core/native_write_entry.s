; GPL-3.0-or-later. Resolve channel addresses once; direct Paula writes need no virtual clock.
 section text,code
 xdef _nv_driver_write
 xref _nv_driver_write_virtual
 xref _nv_control
 xref _nv_stereo_bank
 xref _nv_driver
 ifd NV_QUIET_NATIVE
 xref _nv_music_owner
 endc
_nv_driver_write:
 btst.b #1,_nv_control+23
 beq .done
 move.l 4(sp),d0
 subi.l #_nv_stereo_bank,d0
 cmpi.l #48,d0
 bls.s .bank
 move.l 4(sp),d0
 subi.l #$dff0a0,d0
 cmpi.l #48,d0
 bhi .done
.bank:
 move.w d0,d1
 andi.w #15,d1
 bne .done
 move.l 8(sp),d1
 cmpi.w #32,d0
 bcc .hardware
 ifd NV_QUIET_NATIVE
 tst.w _nv_music_owner
 bne .virtual
 endc
 cmpi.l #8,d1
 bne .virtual
 ; Prior-off calls retain the C unlock transient Enable behavior.
 move.w $dff01c,d1
 andi.w #$4000,d1
 beq.s .volume_unmasked
 ; Keep nested Exec Disable and enabled virtual events on the C path.
 move.w #$4000,$dff09a
 movea.l 4.w,a0
 tst.b $126(a0)
 bpl.s .volume_slow
 tst.w _nv_driver+40
 bne.s .volume_slow
 tst.w _nv_driver+94
 bne.s .volume_slow
 lea _nv_driver,a0
 lea _nv_stereo_bank,a1
 adda.w d0,a1
 tst.w d0
 beq.s .volume_pointer
 lea 54(a0),a0
.volume_pointer:
 move.w 8(a1),d1
 btst #6,d1
 beq.s .volume_six
 moveq #64,d1
 bra.s .volume_store
.volume_six:
 andi.w #63,d1
.volume_store:
 move.w d1,36(a0)
 move.w #$c000,$dff09a
 rts
.volume_slow:
 move.w #$c000,$dff09a
.volume_unmasked:
 moveq #8,d1
.virtual:
 lsr.w #4,d0
 jmp _nv_driver_write_virtual
.hardware:
 lea _nv_stereo_bank,a1
 adda.w d0,a1
 addi.l #$dff0a0,d0
 movea.l d0,a0
 tst.l d1
 beq.s .pointer
 cmpi.l #8,d1
 beq.s .volume
 adda.l d1,a0
 moveq #0,d0
 move.w d1,d0
 move.w (a1,d0.l),d0
 move.w d0,(a0)
.done:
 rts
.pointer:
 move.l (a1),(a0)
 rts
.volume:
 move.w 8(a1),d0
 btst #6,d0
 bne.s .max_volume
 andi.w #63,d0
 lsr.w #1,d0
 move.w d0,8(a0)
 rts
.max_volume:
 move.w #32,8(a0)
 rts
