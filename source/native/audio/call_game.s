 ; GPL-3.0-or-later
 section text,code
 xdef _call_game
_call_game:
 movem.l d2-d7/a2-a6,-(sp)
 jsr (a1)
 movem.l (sp)+,d2-d7/a2-a6
 rts
