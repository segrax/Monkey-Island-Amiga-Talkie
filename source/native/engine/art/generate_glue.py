"""Optional immutable-art adapters; original stripe fallback stays installed."""
from pathlib import Path

HERE = Path(__file__).resolve().parent


def append(lines, patches, code, save, restore):
    imports = ('nv_art_game_scope_cancel','nv_art_game_scope_begin','nv_art_game_object', 'nv_art_game_bind', 'nv_art_game_c2p', 'nv_art_game_room',
               'nv_art_game_prewarm', 'nv_art_warm',
               'nv_art', 'nv_art_columns', 'nv_art_object_gate', 'nv_art_c2p',
               'nv_art_decode', 'nv_art_decode_ready')
    lines += [' xref _' + name for name in imports]
    lines += [' xdef _nv_art_prewarm_entry', '_nv_art_prewarm_entry:',
              ' tst.w _nv_art+80', ' beq art_prewarm_original',
              ' tst.w _nv_art_warm+24', ' bne art_prewarm_original', save,
              ' pea 62(sp)', ' moveq #0,d0', ' move.b 9(a5),d0',
              ' move.l d0,-(sp)', ' jsr _nv_art_game_prewarm', ' addq.l #8,sp', restore,
              'art_prewarm_original:', ' moveq #0,d0', ' move.b 9(a5),d0',
              ' xdef _nv_continue_art_prewarm', '_nv_continue_art_prewarm:', ' jmp $3b80.l']
    lines += [' xdef _nv_art_object_entry', '_nv_art_object_entry:',
              ' tst.w _nv_art+80', ' beq art_object_original',
              ' move.l d0,-(sp)', ' move.l a0,-(sp)', ' moveq #0,d0',
              ' move.b $19f9(a4),d0', ' cmp.w _nv_art_object_gate,d0',
              ' bne art_object_unknown', ' moveq #0,d0', ' move.b $68e8(a4),d0',
              ' cmpi.w #69,d0', ' bhi art_object_known',
              ' lea _nv_art_object_gate+2,a0', ' tst.b (a0,d0.w)',
              ' bne art_object_known', 'art_object_unknown:',
              ' movea.l (sp)+,a0', ' move.l (sp)+,d0', save,
              ' pea 62(sp)', ' jsr _nv_art_game_object', ' addq.l #4,sp', restore,
              ' bra art_object_original', 'art_object_known:',
              ' movea.l (sp)+,a0', ' move.l (sp)+,d0', 'art_object_original:',
              ' tst.w _nv_art+80',' beq art_scope_object_original',save,' pea 62(sp)',
              ' jsr _nv_art_game_scope_begin',' addq.l #4,sp',restore,
              'art_scope_object_original:',' move.w d0,-10(a5)', ' xdef _nv_continue_art_object',
              '_nv_continue_art_object:', ' jmp $51fe.l']
    lines += [' xdef _nv_art_bind_entry', '_nv_art_bind_entry:',
              ' tst.w _nv_art+80', ' beq art_bind_original', save,
              ' pea 62(sp)', ' move.l d7,-(sp)', ' jsr _nv_art_game_bind',
              ' addq.l #8,sp', restore, 'art_bind_original:',
              ' moveq #0,d0', ' move.b $5c38(a4),d0',
              ' xdef _nv_continue_art_bind', '_nv_continue_art_bind:', ' jmp $4aca.l']
    lines += [' xdef _nv_art_dispatch', '_nv_art_dispatch:',
              ' bne.s art_dispatch_other', ' movem.l d2-d7/a2-a5,-(sp)',
              ' tst.w _nv_art_decode_ready', ' beq.s _nv_art_decoder_fallback',
              ' clr.w _nv_art_decode_ready', ' lea _nv_art_decode,a4',
              ' bra.w _nv_art_decoder+4', '_nv_art_decoder_fallback:',
              ' movem.l (sp)+,d2-d7/a2-a5', ' xdef _nv_continue_art_stripe',
              '_nv_continue_art_stripe:', ' jmp $4ddc.l', 'art_dispatch_other:', ' rts']
    lines += (HERE / 'art_decoder.s').read_text().splitlines()
    lines += [' xdef _nv_art_c2p_call', '_nv_art_c2p_call:',
              ' pea art_c2p_cleanup(pc)', ' move.l d0,-(sp)', ' moveq #0,d0',
              ' move.b $19f9(a4),d0', ' cmp.w _nv_art+76,d0',
              ' bne art_c2p_room_changed', ' move.w $5ebe(a4),d0', ' cmpi.w #39,d0',
              ' bhi art_c2p_unbound', ' lea _nv_art_columns,a0',
              ' tst.b (a0,d0.w)', ' beq art_c2p_unbound', ' move.l (sp)+,d0', save,
              ' lea 62(sp),a0', ' move.l a0,-(sp)', ' moveq #0,d0',
              ' move.w 16(a0),d0', ' move.l d0,-(sp)', ' move.l 4(a0),-(sp)',
              ' move.l 8(a0),-(sp)', ' jsr _nv_art_game_c2p', ' lea 16(sp),sp',
              ' tst.l d0', ' beq art_c2p_rejected', restore,
              ' move.w _nv_art_c2p+10,-(sp)', ' move.w _nv_art_c2p+8,-(sp)',
              ' move.l _nv_art_c2p+4,-(sp)', ' move.l _nv_art_c2p,-(sp)',
              ' clr.w -(sp)', ' move.w 30(sp),-(sp)', ' move.l 28(sp),-(sp)',
              ' move.l 28(sp),-(sp)', ' move.l 28(sp),-(sp)',
              ' bsr.w _nv_art_c2p_kernel', ' lea 28(sp),sp', ' rts',
              'art_c2p_room_changed:', ' move.l (sp)+,d0', save,
              ' jsr _nv_art_game_room', restore, ' bra art_c2p_original',
              'art_c2p_unbound:', ' move.l (sp)+,d0', ' bra art_c2p_original',
              'art_c2p_rejected:', restore, 'art_c2p_original:',
              ' xdef _nv_continue_art_c2p_original', '_nv_continue_art_c2p_original:',
              ' jmp $15390.l', 'art_c2p_cleanup:', ' lea 14(sp),sp',
              ' xdef _nv_continue_art_c2p_cleanup', '_nv_continue_art_c2p_cleanup:',
              ' jmp $14e7a.l']
    row = 'dc.w ' + ','.join('$' + code[i:i+2].hex() for i in range(0x153b6, 0x1540e, 2))
    lines += (HERE / 'c2p.s.in').read_text().format(original_row=row).splitlines()
    lines += [' xdef _nv_art_scope_cancel_entry','_nv_art_scope_cancel_entry:',save,
              ' jsr _nv_art_game_scope_cancel',restore,' link a5,#-12',
              ' movem.l d2-d7/a2,-(sp)',' xdef _nv_continue_art_scope_cancel',
              '_nv_continue_art_scope_cancel:',' jmp $510c.l',
              ' xdef _nv_art_scope_end_entry','_nv_art_scope_end_entry:',save,
              ' jsr _nv_art_game_scope_cancel',restore,' movem.l (sp)+,d2-d7/a2',
              ' unlk a5',' xdef _nv_continue_art_scope_end',
              '_nv_continue_art_scope_end:',' jmp $520e.l']
    for address, size, symbol, target, expected in (
            (0x5104,8,'_nv_art_scope_cancel_entry',0x510c,'4e55fff448e73f20'),
            (0x5208,6,'_nv_art_scope_end_entry',0x520e,'4cdf04fc4e5d'),
            (0x3b7a, 6, '_nv_art_prewarm_entry', 0x3b80, '7000102d0009'),
            (0x516a, 8, '_nv_art_object_entry', 0x51fe, '3b40fff66000008e'),
            (0x4ac4, 6, '_nv_art_bind_entry', 0x4aca, '7000102c5c38'),
            (0x4bb2, 6, '_nv_art_dispatch', None, '66044eba0226'),
            (0x14e72, 8, '_nv_art_c2p_call', 0x14e7a, '4eba051c4fef000e')):
        assert code[address:address+size].hex() == expected
        patches.append(dict(address=address, size=size, symbol=symbol, jump=True,
                            continuation=target, expected=expected))
