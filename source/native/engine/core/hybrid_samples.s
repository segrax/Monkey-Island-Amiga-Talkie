; GPL-3.0-or-later. Exact signed8 hybrid sample loops for a plain 68000.
 section text,code
 xdef _nv_hybrid_channel
; (snapshot, amplitude row, output period as long, output)
; NvPaula offsets are checked by the compiled driver's layout assertions.
_nv_hybrid_channel:
 movem.l d2-d7/a2-a4,-(sp)
 movea.l 40(sp),a0
 movea.l 44(sp),a1
 move.l 48(sp),d5
 movea.l 52(sp),a2
 movea.l 8(a0),a3
 adda.l 16(a0),a3
 movea.l 8(a0),a4
 adda.l 12(a0),a4
 move.l 20(a0),d2
 move.l 28(a0),d3
 move.l 24(a0),d4
 ; Count down to the next source sample. Reload periods apply after the
 ; currently latched sample, including the first one in this snapshot.
_nv_project_generic_ready equ *
 sub.l d2,d3
 move.l d3,d2
 ; Bias remaining ticks by one so carry/borrow tests can use word ALU
 ; operations on the 68000. A hardware period of zero represents 65536;
 ; retain the long loop for that case (and oversized output periods).
 cmpi.l #65536,d4
 beq.w .long_entry
 cmpi.l #65535,d5
 bhi.w .long_entry
 ; DBRA also tracks source bytes until reload. Its biased word counter
 ; covers 1..65536 bytes; larger spans use the existing long fallback.
 cmpi.l #65536,4(a0)
 bhi.w .long_entry
 move.l a4,d3
 sub.l a3,d3
 cmpi.l #65536,d3
 bhi.w .long_entry
 cmpi.l #16383,d5
 bhi.w .long_entry
 subq.w #1,d3
 subq.w #1,d2
 ; Short-period music uses an eight-sample loop. For slower
 ; sources, write four identical samples whenever their phase span permits.
 ; Both paths advance at most once per output: period >= output step.
 ; A long contiguous source span needs no per-sample reload counter.
 ; Bounds include the final look-ahead read. Do not change live DMA state.
 cmp.w d5,d4
 blo.s .span_fast_source
 cmpi.w #256,d3
 bhs.w .span_begin
 bra.s .span_regular
.span_fast_source:
 cmpi.w #512,d3
 blo.s .span_regular
 move.w d4,d7
 add.w d7,d7
 cmp.w d5,d7
 bhs.w .span_begin
.span_regular:
 move.l d5,d7
 add.w d7,d7
 add.w d5,d7
 cmp.w d7,d4
 blo.w .short_entry
 movea.w d7,a4
 add.w d5,d7
 move.w #63,d6
 moveq #0,d0
 move.b (a3),d0
 move.b (0,a1,d0.w),d1
.batch:
 cmp.w a4,d2
 bcs.s .separate
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 sub.w d7,d2
 bcs.w .batch_phase3
 bra.w .batch_next3
.separate:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .batch_next0
.batch_phase0:
 addq.l #1,a3
 dbra d3,.batch_period0
 movea.l (a0),a3
 move.l 4(a0),d3
 subq.w #1,d3
.batch_period0:
 add.w d4,d2
 move.b (a3),d0
 move.b (0,a1,d0.w),d1
.batch_next0:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .batch_next1
.batch_phase1:
 addq.l #1,a3
 dbra d3,.batch_period1
 movea.l (a0),a3
 move.l 4(a0),d3
 subq.w #1,d3
.batch_period1:
 add.w d4,d2
 move.b (a3),d0
 move.b (0,a1,d0.w),d1
.batch_next1:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .batch_next2
.batch_phase2:
 addq.l #1,a3
 dbra d3,.batch_period2
 movea.l (a0),a3
 move.l 4(a0),d3
 subq.w #1,d3
.batch_period2:
 add.w d4,d2
 move.b (a3),d0
 move.b (0,a1,d0.w),d1
.batch_next2:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .batch_next3
.batch_phase3:
 addq.l #1,a3
 dbra d3,.batch_period3
 movea.l (a0),a3
 move.l 4(a0),d3
 subq.w #1,d3
.batch_period3:
 add.w d4,d2
 move.b (a3),d0
 move.b (0,a1,d0.w),d1
.batch_next3:
 dbra d6,.batch
 movem.l (sp)+,d2-d7/a2-a4
 rts

.short_entry:
 ; With period >= output step, an underflow crosses exactly one source
 ; boundary. Keep the general transition loop for faster source rates.
 cmp.w d5,d4
 blo.w .multi_entry
 ; Eight outputs per loop for short-period notes
 ; amortize DBRA without extra phase tests or changes to source reloads.
 move.w #31,d6
 moveq #0,d0
 move.b (a3),d0
 move.b (0,a1,d0.w),d1
.sample:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .next0
.phase0:
 addq.l #1,a3
 dbra d3,.period0
 movea.l (a0),a3
 move.l 4(a0),d3
 subq.w #1,d3
.period0:
 add.w d4,d2
 move.b (a3),d0
 move.b (0,a1,d0.w),d1
.next0:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .next1
.phase1:
 addq.l #1,a3
 dbra d3,.period1
 movea.l (a0),a3
 move.l 4(a0),d3
 subq.w #1,d3
.period1:
 add.w d4,d2
 move.b (a3),d0
 move.b (0,a1,d0.w),d1
.next1:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .next2
.phase2:
 addq.l #1,a3
 dbra d3,.period2
 movea.l (a0),a3
 move.l 4(a0),d3
 subq.w #1,d3
.period2:
 add.w d4,d2
 move.b (a3),d0
 move.b (0,a1,d0.w),d1
.next2:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .next3
.phase3:
 addq.l #1,a3
 dbra d3,.period3
 movea.l (a0),a3
 move.l 4(a0),d3
 subq.w #1,d3
.period3:
 add.w d4,d2
 move.b (a3),d0
 move.b (0,a1,d0.w),d1
.next3:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .next4
.phase4:
 addq.l #1,a3
 dbra d3,.period4
 movea.l (a0),a3
 move.l 4(a0),d3
 subq.w #1,d3
.period4:
 add.w d4,d2
 move.b (a3),d0
 move.b (0,a1,d0.w),d1
.next4:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .next5
.phase5:
 addq.l #1,a3
 dbra d3,.period5
 movea.l (a0),a3
 move.l 4(a0),d3
 subq.w #1,d3
.period5:
 add.w d4,d2
 move.b (a3),d0
 move.b (0,a1,d0.w),d1
.next5:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .next6
.phase6:
 addq.l #1,a3
 dbra d3,.period6
 movea.l (a0),a3
 move.l 4(a0),d3
 subq.w #1,d3
.period6:
 add.w d4,d2
 move.b (a3),d0
 move.b (0,a1,d0.w),d1
.next6:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .next7
.phase7:
 addq.l #1,a3
 dbra d3,.period7
 movea.l (a0),a3
 move.l 4(a0),d3
 subq.w #1,d3
.period7:
 add.w d4,d2
 move.b (a3),d0
 move.b (0,a1,d0.w),d1
.next7:
 dbra d6,.sample
 movem.l (sp)+,d2-d7/a2-a4
 rts

.multi_entry:
 ; When output spans at most two source periods, the second transition
 ; is bounded: avoid jumping back through the general transition loop.
 move.w d4,d7
 add.w d7,d7
 cmp.w d5,d7
 blo.w .multi_generic_entry
 move.w #31,d6
 moveq #0,d0
 move.b (a3),d0
 move.b (0,a1,d0.w),d1
.pair_sample:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .pair_next0
 add.w d4,d2
 bcs.s .pair_last0
 addq.l #1,a3
 dbra d3,.pair_second0
 movea.l (a0),a3
 move.l 4(a0),d3
 subq.w #1,d3
.pair_second0:
 add.w d4,d2
.pair_last0:
 addq.l #1,a3
 dbra d3,.pair_loaded0
 movea.l (a0),a3
 move.l 4(a0),d3
 subq.w #1,d3
.pair_loaded0:
 move.b (a3),d0
 move.b (0,a1,d0.w),d1
.pair_next0:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .pair_next1
 add.w d4,d2
 bcs.s .pair_last1
 addq.l #1,a3
 dbra d3,.pair_second1
 movea.l (a0),a3
 move.l 4(a0),d3
 subq.w #1,d3
.pair_second1:
 add.w d4,d2
.pair_last1:
 addq.l #1,a3
 dbra d3,.pair_loaded1
 movea.l (a0),a3
 move.l 4(a0),d3
 subq.w #1,d3
.pair_loaded1:
 move.b (a3),d0
 move.b (0,a1,d0.w),d1
.pair_next1:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .pair_next2
 add.w d4,d2
 bcs.s .pair_last2
 addq.l #1,a3
 dbra d3,.pair_second2
 movea.l (a0),a3
 move.l 4(a0),d3
 subq.w #1,d3
.pair_second2:
 add.w d4,d2
.pair_last2:
 addq.l #1,a3
 dbra d3,.pair_loaded2
 movea.l (a0),a3
 move.l 4(a0),d3
 subq.w #1,d3
.pair_loaded2:
 move.b (a3),d0
 move.b (0,a1,d0.w),d1
.pair_next2:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .pair_next3
 add.w d4,d2
 bcs.s .pair_last3
 addq.l #1,a3
 dbra d3,.pair_second3
 movea.l (a0),a3
 move.l 4(a0),d3
 subq.w #1,d3
.pair_second3:
 add.w d4,d2
.pair_last3:
 addq.l #1,a3
 dbra d3,.pair_loaded3
 movea.l (a0),a3
 move.l 4(a0),d3
 subq.w #1,d3
.pair_loaded3:
 move.b (a3),d0
 move.b (0,a1,d0.w),d1
.pair_next3:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .pair_next4
 add.w d4,d2
 bcs.s .pair_last4
 addq.l #1,a3
 dbra d3,.pair_second4
 movea.l (a0),a3
 move.l 4(a0),d3
 subq.w #1,d3
.pair_second4:
 add.w d4,d2
.pair_last4:
 addq.l #1,a3
 dbra d3,.pair_loaded4
 movea.l (a0),a3
 move.l 4(a0),d3
 subq.w #1,d3
.pair_loaded4:
 move.b (a3),d0
 move.b (0,a1,d0.w),d1
.pair_next4:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .pair_next5
 add.w d4,d2
 bcs.s .pair_last5
 addq.l #1,a3
 dbra d3,.pair_second5
 movea.l (a0),a3
 move.l 4(a0),d3
 subq.w #1,d3
.pair_second5:
 add.w d4,d2
.pair_last5:
 addq.l #1,a3
 dbra d3,.pair_loaded5
 movea.l (a0),a3
 move.l 4(a0),d3
 subq.w #1,d3
.pair_loaded5:
 move.b (a3),d0
 move.b (0,a1,d0.w),d1
.pair_next5:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .pair_next6
 add.w d4,d2
 bcs.s .pair_last6
 addq.l #1,a3
 dbra d3,.pair_second6
 movea.l (a0),a3
 move.l 4(a0),d3
 subq.w #1,d3
.pair_second6:
 add.w d4,d2
.pair_last6:
 addq.l #1,a3
 dbra d3,.pair_loaded6
 movea.l (a0),a3
 move.l 4(a0),d3
 subq.w #1,d3
.pair_loaded6:
 move.b (a3),d0
 move.b (0,a1,d0.w),d1
.pair_next6:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .pair_next7
 add.w d4,d2
 bcs.s .pair_last7
 addq.l #1,a3
 dbra d3,.pair_second7
 movea.l (a0),a3
 move.l 4(a0),d3
 subq.w #1,d3
.pair_second7:
 add.w d4,d2
.pair_last7:
 addq.l #1,a3
 dbra d3,.pair_loaded7
 movea.l (a0),a3
 move.l 4(a0),d3
 subq.w #1,d3
.pair_loaded7:
 move.b (a3),d0
 move.b (0,a1,d0.w),d1
.pair_next7:
 dbra d6,.pair_sample
 movem.l (sp)+,d2-d7/a2-a4
 rts

.multi_generic_entry:
 ; Eight outputs amortize loop control while retaining every exact transition.
 move.w #31,d6
 moveq #0,d0
 move.b (a3),d0
 move.b (0,a1,d0.w),d1
.multi_sample:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .multi_next0
.multi_phase0:
 addq.l #1,a3
 dbra d3,.multi_period0
 movea.l (a0),a3
 move.l 4(a0),d3
 subq.w #1,d3
.multi_period0:
 add.w d4,d2
 bcc.s .multi_phase0
 move.b (a3),d0
 move.b (0,a1,d0.w),d1
.multi_next0:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .multi_next1
.multi_phase1:
 addq.l #1,a3
 dbra d3,.multi_period1
 movea.l (a0),a3
 move.l 4(a0),d3
 subq.w #1,d3
.multi_period1:
 add.w d4,d2
 bcc.s .multi_phase1
 move.b (a3),d0
 move.b (0,a1,d0.w),d1
.multi_next1:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .multi_next2
.multi_phase2:
 addq.l #1,a3
 dbra d3,.multi_period2
 movea.l (a0),a3
 move.l 4(a0),d3
 subq.w #1,d3
.multi_period2:
 add.w d4,d2
 bcc.s .multi_phase2
 move.b (a3),d0
 move.b (0,a1,d0.w),d1
.multi_next2:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .multi_next3
.multi_phase3:
 addq.l #1,a3
 dbra d3,.multi_period3
 movea.l (a0),a3
 move.l 4(a0),d3
 subq.w #1,d3
.multi_period3:
 add.w d4,d2
 bcc.s .multi_phase3
 move.b (a3),d0
 move.b (0,a1,d0.w),d1
.multi_next3:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .multi_next4
.multi_phase4:
 addq.l #1,a3
 dbra d3,.multi_period4
 movea.l (a0),a3
 move.l 4(a0),d3
 subq.w #1,d3
.multi_period4:
 add.w d4,d2
 bcc.s .multi_phase4
 move.b (a3),d0
 move.b (0,a1,d0.w),d1
.multi_next4:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .multi_next5
.multi_phase5:
 addq.l #1,a3
 dbra d3,.multi_period5
 movea.l (a0),a3
 move.l 4(a0),d3
 subq.w #1,d3
.multi_period5:
 add.w d4,d2
 bcc.s .multi_phase5
 move.b (a3),d0
 move.b (0,a1,d0.w),d1
.multi_next5:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .multi_next6
.multi_phase6:
 addq.l #1,a3
 dbra d3,.multi_period6
 movea.l (a0),a3
 move.l 4(a0),d3
 subq.w #1,d3
.multi_period6:
 add.w d4,d2
 bcc.s .multi_phase6
 move.b (a3),d0
 move.b (0,a1,d0.w),d1
.multi_next6:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .multi_next7
.multi_phase7:
 addq.l #1,a3
 dbra d3,.multi_period7
 movea.l (a0),a3
 move.l 4(a0),d3
 subq.w #1,d3
.multi_period7:
 add.w d4,d2
 bcc.s .multi_phase7
 move.b (a3),d0
 move.b (0,a1,d0.w),d1
.multi_next7:
 dbra d6,.multi_sample
 movem.l (sp)+,d2-d7/a2-a4
 rts

.long_entry:
 move.w #127,d6
 moveq #0,d0
 move.b (a3),d0
 move.b (0,a1,d0.w),d1
.long_sample:
 ; Two output samples per loop: halve the loop-control branches without
 ; changing phase advancement, reload handling or the sample rate.
 move.b d1,(a2)+
 sub.l d5,d2
 bgt.s .long_next0
.long_phase0:
 addq.l #1,a3
 cmpa.l a4,a3
 bne.s .long_period0
 movea.l (a0),a3
 movea.l a3,a4
 adda.l 4(a0),a4
.long_period0:
 add.l d4,d2
 ble.s .long_phase0
 ; Repeated output samples reuse the scaled byte; skipped source samples
 ; need no memory read. Live music phase is still advanced elsewhere.
 move.b (a3),d0
 move.b (0,a1,d0.w),d1
.long_next0:
 move.b d1,(a2)+
 sub.l d5,d2
 bgt.s .long_next1
.long_phase1:
 addq.l #1,a3
 cmpa.l a4,a3
 bne.s .long_period1
 movea.l (a0),a3
 movea.l a3,a4
 adda.l 4(a0),a4
.long_period1:
 add.l d4,d2
 ble.s .long_phase1
 move.b (a3),d0
 move.b (0,a1,d0.w),d1
.long_next1:
 dbra d6,.long_sample
 movem.l (sp)+,d2-d7/a2-a4
 rts

.span_begin:
 ; Fetches use a next-source cursor; skipped bytes still advance explicitly.
 ; The general multi-transition fallback retains its current-source cursor.
 move.l d5,d7
 add.w d7,d7
 add.w d5,d7
 cmp.w d7,d4
 blo.w .span_short_entry
 movea.w d7,a4
 add.w d5,d7
 move.w #63,d6
 moveq #0,d0
 move.b (a3)+,d0
 move.b (0,a1,d0.w),d1
.span_batch:
 cmp.w a4,d2
 bcs.s .span_separate
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 sub.w d7,d2
 bcs.w .span_batch_phase3
 bra.w .span_batch_next3
.span_separate:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .span_batch_next0
.span_batch_phase0:
.span_batch_period0:
 add.w d4,d2
 move.b (a3)+,d0
 move.b (0,a1,d0.w),d1
.span_batch_next0:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .span_batch_next1
.span_batch_phase1:
.span_batch_period1:
 add.w d4,d2
 move.b (a3)+,d0
 move.b (0,a1,d0.w),d1
.span_batch_next1:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .span_batch_next2
.span_batch_phase2:
.span_batch_period2:
 add.w d4,d2
 move.b (a3)+,d0
 move.b (0,a1,d0.w),d1
.span_batch_next2:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .span_batch_next3
.span_batch_phase3:
.span_batch_period3:
 add.w d4,d2
 move.b (a3)+,d0
 move.b (0,a1,d0.w),d1
.span_batch_next3:
 dbra d6,.span_batch
 movem.l (sp)+,d2-d7/a2-a4
 rts

.span_short_entry:
 ; With period >= output step, an underflow crosses exactly one source
 ; boundary. Keep the general transition loop for faster source rates.
 cmp.w d5,d4
 blo.w .span_multi_entry
 ; Eight outputs per loop for short-period notes
 ; amortize DBRA without extra phase tests or changes to source reloads.
 move.w #31,d6
 moveq #0,d0
 move.b (a3)+,d0
 move.b (0,a1,d0.w),d1
.span_sample:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .span_next0
.span_phase0:
.span_period0:
 add.w d4,d2
 move.b (a3)+,d0
 move.b (0,a1,d0.w),d1
.span_next0:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .span_next1
.span_phase1:
.span_period1:
 add.w d4,d2
 move.b (a3)+,d0
 move.b (0,a1,d0.w),d1
.span_next1:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .span_next2
.span_phase2:
.span_period2:
 add.w d4,d2
 move.b (a3)+,d0
 move.b (0,a1,d0.w),d1
.span_next2:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .span_next3
.span_phase3:
.span_period3:
 add.w d4,d2
 move.b (a3)+,d0
 move.b (0,a1,d0.w),d1
.span_next3:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .span_next4
.span_phase4:
.span_period4:
 add.w d4,d2
 move.b (a3)+,d0
 move.b (0,a1,d0.w),d1
.span_next4:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .span_next5
.span_phase5:
.span_period5:
 add.w d4,d2
 move.b (a3)+,d0
 move.b (0,a1,d0.w),d1
.span_next5:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .span_next6
.span_phase6:
.span_period6:
 add.w d4,d2
 move.b (a3)+,d0
 move.b (0,a1,d0.w),d1
.span_next6:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .span_next7
.span_phase7:
.span_period7:
 add.w d4,d2
 move.b (a3)+,d0
 move.b (0,a1,d0.w),d1
.span_next7:
 dbra d6,.span_sample
 movem.l (sp)+,d2-d7/a2-a4
 rts

.span_multi_entry:
 ; When output spans at most two source periods, the second transition
 ; is bounded: avoid jumping back through the general transition loop.
 move.w d4,d7
 add.w d7,d7
 cmp.w d5,d7
 blo.w .span_multi_generic_entry
 move.w #31,d6
 moveq #0,d0
 move.b (a3)+,d0
 move.b (0,a1,d0.w),d1
.span_pair_sample:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .span_pair_next0
 add.w d4,d2
 bcs.s .span_pair_last0
 addq.l #1,a3
.span_pair_second0:
 add.w d4,d2
.span_pair_last0:
.span_pair_loaded0:
 move.b (a3)+,d0
 move.b (0,a1,d0.w),d1
.span_pair_next0:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .span_pair_next1
 add.w d4,d2
 bcs.s .span_pair_last1
 addq.l #1,a3
.span_pair_second1:
 add.w d4,d2
.span_pair_last1:
.span_pair_loaded1:
 move.b (a3)+,d0
 move.b (0,a1,d0.w),d1
.span_pair_next1:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .span_pair_next2
 add.w d4,d2
 bcs.s .span_pair_last2
 addq.l #1,a3
.span_pair_second2:
 add.w d4,d2
.span_pair_last2:
.span_pair_loaded2:
 move.b (a3)+,d0
 move.b (0,a1,d0.w),d1
.span_pair_next2:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .span_pair_next3
 add.w d4,d2
 bcs.s .span_pair_last3
 addq.l #1,a3
.span_pair_second3:
 add.w d4,d2
.span_pair_last3:
.span_pair_loaded3:
 move.b (a3)+,d0
 move.b (0,a1,d0.w),d1
.span_pair_next3:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .span_pair_next4
 add.w d4,d2
 bcs.s .span_pair_last4
 addq.l #1,a3
.span_pair_second4:
 add.w d4,d2
.span_pair_last4:
.span_pair_loaded4:
 move.b (a3)+,d0
 move.b (0,a1,d0.w),d1
.span_pair_next4:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .span_pair_next5
 add.w d4,d2
 bcs.s .span_pair_last5
 addq.l #1,a3
.span_pair_second5:
 add.w d4,d2
.span_pair_last5:
.span_pair_loaded5:
 move.b (a3)+,d0
 move.b (0,a1,d0.w),d1
.span_pair_next5:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .span_pair_next6
 add.w d4,d2
 bcs.s .span_pair_last6
 addq.l #1,a3
.span_pair_second6:
 add.w d4,d2
.span_pair_last6:
.span_pair_loaded6:
 move.b (a3)+,d0
 move.b (0,a1,d0.w),d1
.span_pair_next6:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .span_pair_next7
 add.w d4,d2
 bcs.s .span_pair_last7
 addq.l #1,a3
.span_pair_second7:
 add.w d4,d2
.span_pair_last7:
.span_pair_loaded7:
 move.b (a3)+,d0
 move.b (0,a1,d0.w),d1
.span_pair_next7:
 dbra d6,.span_pair_sample
 movem.l (sp)+,d2-d7/a2-a4
 rts

.span_multi_generic_entry:
 ; Eight outputs amortize loop control while retaining every exact transition.
 move.w #31,d6
 moveq #0,d0
 move.b (a3),d0
 move.b (0,a1,d0.w),d1
.span_multi_sample:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .span_multi_next0
.span_multi_phase0:
 addq.l #1,a3
.span_multi_period0:
 add.w d4,d2
 bcc.s .span_multi_phase0
 move.b (a3),d0
 move.b (0,a1,d0.w),d1
.span_multi_next0:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .span_multi_next1
.span_multi_phase1:
 addq.l #1,a3
.span_multi_period1:
 add.w d4,d2
 bcc.s .span_multi_phase1
 move.b (a3),d0
 move.b (0,a1,d0.w),d1
.span_multi_next1:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .span_multi_next2
.span_multi_phase2:
 addq.l #1,a3
.span_multi_period2:
 add.w d4,d2
 bcc.s .span_multi_phase2
 move.b (a3),d0
 move.b (0,a1,d0.w),d1
.span_multi_next2:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .span_multi_next3
.span_multi_phase3:
 addq.l #1,a3
.span_multi_period3:
 add.w d4,d2
 bcc.s .span_multi_phase3
 move.b (a3),d0
 move.b (0,a1,d0.w),d1
.span_multi_next3:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .span_multi_next4
.span_multi_phase4:
 addq.l #1,a3
.span_multi_period4:
 add.w d4,d2
 bcc.s .span_multi_phase4
 move.b (a3),d0
 move.b (0,a1,d0.w),d1
.span_multi_next4:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .span_multi_next5
.span_multi_phase5:
 addq.l #1,a3
.span_multi_period5:
 add.w d4,d2
 bcc.s .span_multi_phase5
 move.b (a3),d0
 move.b (0,a1,d0.w),d1
.span_multi_next5:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .span_multi_next6
.span_multi_phase6:
 addq.l #1,a3
.span_multi_period6:
 add.w d4,d2
 bcc.s .span_multi_phase6
 move.b (a3),d0
 move.b (0,a1,d0.w),d1
.span_multi_next6:
 move.b d1,(a2)+
 sub.w d5,d2
 bcc.s .span_multi_next7
.span_multi_phase7:
 addq.l #1,a3
.span_multi_period7:
 add.w d4,d2
 bcc.s .span_multi_phase7
 move.b (a3),d0
 move.b (0,a1,d0.w),d1
.span_multi_next7:
 dbra d6,.span_multi_sample
 movem.l (sp)+,d2-d7/a2-a4
 rts


 xdef _nv_hybrid_speech
; (left, right, contiguous PCM, scaled-speech word row, sample count as long)
_nv_hybrid_speech:
 xref _nv_speech_words
 cmpi.l #_nv_speech_words+32768,16(sp)
 beq.w _nv_hybrid_speech_unity
 movem.l d2-d3/a2-a4,-(sp)
 movea.l 24(sp),a0
 movea.l 28(sp),a1
 movea.l 32(sp),a2
 movea.l 36(sp),a3
 move.l 40(sp),d3
 beq.s .done
 xref _nv_average
 lea _nv_average+32768,a4
 subq.w #1,d3
 ; Enter a four-sample loop at the right point for a partial first group.
 ; This retains exact byte reads for odd PCM addresses and short tails.
 move.w d3,d1
 andi.w #3,d1
 lsr.w #2,d3
 add.w d1,d1
 move.w .entry(pc,d1.w),d1
 jmp .entry(pc,d1.w)
.entry:
 dc.w .mix3-.entry,.mix2-.entry,.mix1-.entry,.mix0-.entry
.mix0:
 moveq #0,d2
 move.b (a2)+,d2
 add.w d2,d2
 move.w (0,a3,d2.w),d0
 move.b (a0),d0
 move.b (0,a4,d0.w),(a0)+
 move.b (a1),d0
 move.b (0,a4,d0.w),(a1)+
.mix1:
 moveq #0,d2
 move.b (a2)+,d2
 add.w d2,d2
 move.w (0,a3,d2.w),d0
 move.b (a0),d0
 move.b (0,a4,d0.w),(a0)+
 move.b (a1),d0
 move.b (0,a4,d0.w),(a1)+
.mix2:
 moveq #0,d2
 move.b (a2)+,d2
 add.w d2,d2
 move.w (0,a3,d2.w),d0
 move.b (a0),d0
 move.b (0,a4,d0.w),(a0)+
 move.b (a1),d0
 move.b (0,a4,d0.w),(a1)+
.mix3:
 moveq #0,d2
 move.b (a2)+,d2
 add.w d2,d2
 ; Word table places scaled speech in the high byte. Each music byte
 ; completes a signed 16-bit index into the exact signed-average table.
 move.w (0,a3,d2.w),d0
 move.b (a0),d0
 move.b (0,a4,d0.w),(a0)+
 move.b (a1),d0
 move.b (0,a4,d0.w),(a1)+
 dbra d3,.mix0
.done:
 movem.l (sp)+,d2-d3/a2-a4
 rts

 xdef _nv_hybrid_half
; (left, right, sample count as long); arithmetic shift preserves odd negatives.
_nv_hybrid_half:
 movea.l 4(sp),a0
 movea.l 8(sp),a1
 move.l 12(sp),d0
 beq.s .done
 subq.w #1,d0
.half:
 move.b (a0),d1
 asr.b #1,d1
 move.b d1,(a0)+
 move.b (a1),d1
 asr.b #1,d1
 move.b d1,(a1)+
 dbra d0,.half
.done:
 rts

 xdef _nv_hybrid_speech_only
; (left, right, contiguous PCM, half-amplitude byte row, count as long)
; Identical signed rounding to mixing speech with silent music on both sides.
_nv_hybrid_speech_only:
 ; Normal gain needs only an exact signed half. Keep other gains on the LUT.
 xref _nv_half_amplitude
 cmpi.l #_nv_half_amplitude+64*256,16(sp)
 beq.w _nv_hybrid_speech_only_unity
 xdef _nv_hybrid_speech_only_lut
_nv_hybrid_speech_only_lut:
 movem.l d2/a2-a3,-(sp)
 movea.l 16(sp),a0
 movea.l 20(sp),a1
 movea.l 24(sp),a2
 movea.l 28(sp),a3
 move.l 32(sp),d2
 beq.s .done
 moveq #0,d0
 subq.w #1,d2
 move.w d2,d1
 andi.w #3,d1
 lsr.w #2,d2
 add.w d1,d1
 move.w .entry(pc,d1.w),d1
 jmp .entry(pc,d1.w)
.entry:
 dc.w .sample3-.entry,.sample2-.entry,.sample1-.entry,.sample0-.entry
.sample0:
 move.b (a2)+,d0
 move.b (0,a3,d0.w),d1
 move.b d1,(a0)+
 move.b d1,(a1)+
.sample1:
 move.b (a2)+,d0
 move.b (0,a3,d0.w),d1
 move.b d1,(a0)+
 move.b d1,(a1)+
.sample2:
 move.b (a2)+,d0
 move.b (0,a3,d0.w),d1
 move.b d1,(a0)+
 move.b d1,(a1)+
.sample3:
 move.b (a2)+,d0
 move.b (0,a3,d0.w),d1
 move.b d1,(a0)+
 move.b d1,(a1)+
 dbra d2,.sample0
.done:
 movem.l (sp)+,d2/a2-a3
 rts

; For periods of two to under nine output steps, count complete source runs
; once: K=floor((e+(N-1)*step)/period). The final run uses the output tail.
; SUB remainder / ADD step on borrow keeps phase e in [0,step).
; Bound the initial latched prefix to nine outputs; other layouts fall back.
 xdef _nv_hybrid_channel_runs
_nv_hybrid_channel_runs:
 move.l 12(sp),d0
 beq.w .fallback
 cmpi.l #16383,d0
 bhi.w .fallback
 movea.l 4(sp),a0
 move.l 24(a0),d1
 add.l d0,d0
 cmp.l d0,d1
 blo.w .fallback
 cmpi.l #65535,d1
 bhi.w .fallback
 move.l 12(sp),d0
 lsl.l #3,d0
 cmp.l d0,d1
 bcs.s .period_supported
 add.l 12(sp),d0
 cmp.l d0,d1
 bhs.w .fallback
.period_supported:
 movea.l d0,a1
 move.l 28(a0),d1
 sub.l 20(a0),d1
 cmp.l a1,d1
 bhi.w .fallback
 cmpi.l #65536,4(a0)
 bhi.w .fallback
 movea.l 8(a0),a1
 adda.l 12(a0),a1
 move.l a1,d1
 sub.l 8(a0),d1
 sub.l 16(a0),d1
 cmpi.l #65536,d1
 bhi.w .fallback
 movem.l d2-d7/a2-a4,-(sp)
 movea.l 40(sp),a0
 movea.l 44(sp),a1
 movea.l 52(sp),a2
 movea.l 8(a0),a3
 adda.l 16(a0),a3
 move.l 12(a0),d3
 sub.l 16(a0),d3
 subq.w #1,d3
 move.l 48(sp),d5
 move.l 24(a0),d4
 divu.w d5,d4
 moveq #0,d7
 move.w d4,d7
 move.w d7,d0
 subq.w #2,d0
 add.w d0,d0
 move.w .offsets(pc,d0.w),d0
 lea .runs(pc),a4
 adda.w d0,a4
 swap d4
 move.l 28(a0),d2
 sub.l 20(a0),d2
_nv_project_runs_ready equ *
_nv_project_run_offsets equ .offsets
_nv_project_run_table equ .runs
 move.w #256,d6
 moveq #0,d0
 move.b (a3),d0
 move.b (a1,d0.w),d1
.prefix:
 move.b d1,(a2)+
 subq.w #1,d6
 beq.w .done
 sub.l 48(sp),d2
 bhi.s .prefix
 neg.w d2
 moveq #0,d0
 move.w d6,d0
 subq.w #1,d0
 mulu.w 50(sp),d0
 moveq #0,d1
 move.w d2,d1
 add.l d1,d0
 divu.w 26(a0),d0
 move.w d0,d6
 subq.w #1,d6
 ; K complete runs plus the first and final source advances must fit.
 move.w d6,d0
 addq.w #2,d0
 cmp.w d0,d3
 blo.s .runs_regular
 move.w d7,d0
 subq.w #2,d0
 add.w d0,d0
 lea .span_offsets(pc),a4
 move.w (a4,d0.w),d0
 lea .span_runs(pc),a4
 adda.w d0,a4
.runs_regular:
 moveq #0,d0
.advance:
 addq.l #1,a3
 dbra d3,.loaded
 movea.l (a0),a3
 move.l 4(a0),d3
 subq.w #1,d3
.loaded:
 move.b (a3),d0
 move.b (a1,d0.w),d1
 jmp (a4)
.offsets:
 dc.w .entry2-.runs,.entry3-.runs,.entry4-.runs,.entry5-.runs,.entry6-.runs,.entry7-.runs,.entry8-.runs
.runs:
.entry2:
 movea.l 52(sp),a4
 adda.w #256,a4
 bra.s .run2
.advance2:
 addq.l #1,a3
 dbra d3,.loaded2
 movea.l (a0),a3
 move.l 4(a0),d3
 subq.w #1,d3
.loaded2:
 move.b (a3),d0
 move.b (a1,d0.w),d1
.run2:
 sub.w d4,d2
 bcc.s .emit2
 add.w d5,d2
 move.b d1,(a2)+
.emit2:
 move.b d1,(a2)+
 move.b d1,(a2)+
 dbra d6,.advance2
 bra.w .final_advance
.entry3:
 movea.l 52(sp),a4
 adda.w #256,a4
 bra.s .run3
.advance3:
 addq.l #1,a3
 dbra d3,.loaded3
 movea.l (a0),a3
 move.l 4(a0),d3
 subq.w #1,d3
.loaded3:
 move.b (a3),d0
 move.b (a1,d0.w),d1
.run3:
 sub.w d4,d2
 bcc.s .emit3
 add.w d5,d2
 move.b d1,(a2)+
.emit3:
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 dbra d6,.advance3
 bra.w .final_advance
.entry4:
 movea.l 52(sp),a4
 adda.w #256,a4
 bra.s .run4
.advance4:
 addq.l #1,a3
 dbra d3,.loaded4
 movea.l (a0),a3
 move.l 4(a0),d3
 subq.w #1,d3
.loaded4:
 move.b (a3),d0
 move.b (a1,d0.w),d1
.run4:
 sub.w d4,d2
 bcc.s .emit4
 add.w d5,d2
 move.b d1,(a2)+
.emit4:
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 dbra d6,.advance4
 bra.w .final_advance
.entry5:
 movea.l 52(sp),a4
 adda.w #256,a4
 bra.s .run5
.advance5:
 addq.l #1,a3
 dbra d3,.loaded5
 movea.l (a0),a3
 move.l 4(a0),d3
 subq.w #1,d3
.loaded5:
 move.b (a3),d0
 move.b (a1,d0.w),d1
.run5:
 sub.w d4,d2
 bcc.s .emit5
 add.w d5,d2
 move.b d1,(a2)+
.emit5:
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 dbra d6,.advance5
 bra.w .final_advance
.entry6:
 movea.l 52(sp),a4
 adda.w #256,a4
 bra.s .run6
.advance6:
 addq.l #1,a3
 dbra d3,.loaded6
 movea.l (a0),a3
 move.l 4(a0),d3
 subq.w #1,d3
.loaded6:
 move.b (a3),d0
 move.b (a1,d0.w),d1
.run6:
 sub.w d4,d2
 bcc.s .emit6
 add.w d5,d2
 move.b d1,(a2)+
.emit6:
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 dbra d6,.advance6
 bra.w .final_advance
.entry7:
 movea.l 52(sp),a4
 adda.w #256,a4
 bra.s .run7
.advance7:
 addq.l #1,a3
 dbra d3,.loaded7
 movea.l (a0),a3
 move.l 4(a0),d3
 subq.w #1,d3
.loaded7:
 move.b (a3),d0
 move.b (a1,d0.w),d1
.run7:
 sub.w d4,d2
 bcc.s .emit7
 add.w d5,d2
 move.b d1,(a2)+
.emit7:
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 dbra d6,.advance7
 bra.w .final_advance
.entry8:
 movea.l 52(sp),a4
 adda.w #256,a4
 bra.s .run8
.advance8:
 addq.l #1,a3
 dbra d3,.loaded8
 movea.l (a0),a3
 move.l 4(a0),d3
 subq.w #1,d3
.loaded8:
 move.b (a3),d0
 move.b (a1,d0.w),d1
.run8:
 sub.w d4,d2
 bcc.s .emit8
 add.w d5,d2
 move.b d1,(a2)+
.emit8:
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 dbra d6,.advance8
 bra.w .final_advance
.final_advance:
 addq.l #1,a3
 dbra d3,.final_loaded
 movea.l (a0),a3
.final_loaded:
 move.b (a3),d0
 move.b (a1,d0.w),d1
 move.w a4,d6
 sub.w a2,d6
 subq.w #1,d6
.tail:
 move.b d1,(a2)+
 dbra d6,.tail
.done:
 movem.l (sp)+,d2-d7/a2-a4
 rts
.fallback:
 jmp _nv_hybrid_channel


_nv_asr_run_offsets equ .asr_offsets
_nv_asr_run_table equ .asr_runs
_nv_asr_span_offsets equ .asr_span_offsets
_nv_asr_span_table equ .asr_span_runs
.asr_offsets:
 dc.w .asr_entry2-.asr_runs,0,.asr_entry4-.asr_runs
.asr_runs:
.asr_entry2:
 movea.l 52(sp),a4
 adda.w #256,a4
 bra.s .asr_run2
.asr_advance2:
 addq.l #1,a3
 dbra d3,.asr_loaded2
 movea.l (a0),a3
 move.l 4(a0),d3
 subq.w #1,d3
.asr_loaded2:
 move.b (a3),d1
 asr.b #2,d1
.asr_run2:
 sub.w d4,d2
 bcc.s .asr_emit2
 add.w d5,d2
 move.b d1,(a2)+
.asr_emit2:
 move.b d1,(a2)+
 move.b d1,(a2)+
 dbra d6,.asr_advance2
 bra.w .final_advance
.asr_entry4:
 ; Bound each segment once; D7 retains the complete runs still to render.
 cmpi.l #16,4(a0)
 bcs.w .old_asr_entry4
 movea.l 52(sp),a4
 adda.w #256,a4
 addq.l #1,a3
.chunk_setup4:
 move.w d6,d7
 cmp.w d3,d6
 bls.s .chunk_fits4
 move.w d3,d6
.chunk_fits4:
 sub.w d6,d7
 sub.w d6,d3
 bra.s .chunk_run4
.chunk_advance4:
 move.b (a3)+,d1
 asr.b #2,d1
.chunk_run4:
 sub.w d4,d2
 bcc.s .chunk_emit4
 add.w d5,d2
 move.b d1,(a2)+
.chunk_emit4:
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 dbra d6,.chunk_advance4
 tst.w d7
 beq.s .chunk_done4
 move.w d7,d6
 subq.w #1,d6
 movea.l (a0),a3
 move.l 4(a0),d3
 subq.w #1,d3
 move.b (a3)+,d1
 asr.b #2,d1
 bra.s .chunk_setup4
.chunk_done4:
 subq.l #1,a3
 bra.w .final_advance
.old_asr_entry4:
 movea.l 52(sp),a4
 adda.w #256,a4
 bra.s .asr_run4
.asr_advance4:
 addq.l #1,a3
 dbra d3,.asr_loaded4
 movea.l (a0),a3
 move.l 4(a0),d3
 subq.w #1,d3
.asr_loaded4:
 move.b (a3),d1
 asr.b #2,d1
.asr_run4:
 sub.w d4,d2
 bcc.s .asr_emit4
 add.w d5,d2
 move.b d1,(a2)+
.asr_emit4:
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 dbra d6,.asr_advance4
 bra.w .final_advance

.asr_span_offsets:
 dc.w .asr_span_entry2-.asr_span_runs,0,.asr_span_entry4-.asr_span_runs
.asr_span_runs:
.asr_span_entry2:
 addq.l #1,a3
 movea.l 52(sp),a4
 adda.w #256,a4
 ; Enter the partial first group, then render four complete source runs.
 move.w d6,d7
 andi.w #3,d7
 lsr.w #2,d6
 add.w d7,d7
 move.w .asr_span_table2(pc,d7.w),d7
 jmp .asr_span_table2(pc,d7.w)
.asr_span_table2:
 dc.w .asr_span_emit2_3-.asr_span_table2,.asr_span_emit2_2-.asr_span_table2,.asr_span_emit2_1-.asr_span_table2,.asr_span_emit2_0-.asr_span_table2
.asr_span_advance2_0:
 move.b (a3)+,d1
 asr.b #2,d1
.asr_span_emit2_0:
 sub.w d4,d2
 bcc.s .asr_span_output2_0
 add.w d5,d2
 move.b d1,(a2)+
.asr_span_output2_0:
 move.b d1,(a2)+
 move.b d1,(a2)+
.asr_span_advance2_1:
 move.b (a3)+,d1
 asr.b #2,d1
.asr_span_emit2_1:
 sub.w d4,d2
 bcc.s .asr_span_output2_1
 add.w d5,d2
 move.b d1,(a2)+
.asr_span_output2_1:
 move.b d1,(a2)+
 move.b d1,(a2)+
.asr_span_advance2_2:
 move.b (a3)+,d1
 asr.b #2,d1
.asr_span_emit2_2:
 sub.w d4,d2
 bcc.s .asr_span_output2_2
 add.w d5,d2
 move.b d1,(a2)+
.asr_span_output2_2:
 move.b d1,(a2)+
 move.b d1,(a2)+
.asr_span_advance2_3:
 move.b (a3)+,d1
 asr.b #2,d1
.asr_span_emit2_3:
 sub.w d4,d2
 bcc.s .asr_span_output2_3
 add.w d5,d2
 move.b d1,(a2)+
.asr_span_output2_3:
 move.b d1,(a2)+
 move.b d1,(a2)+
 dbra d6,.asr_span_advance2_0
 bra.w .span_final_advance
.asr_span_entry4:
 addq.l #1,a3
 movea.l 52(sp),a4
 adda.w #256,a4
 ; Enter the partial first group, then render four complete source runs.
 move.w d6,d7
 andi.w #3,d7
 lsr.w #2,d6
 add.w d7,d7
 move.w .asr_span_table4(pc,d7.w),d7
 jmp .asr_span_table4(pc,d7.w)
.asr_span_table4:
 dc.w .asr_span_emit4_3-.asr_span_table4,.asr_span_emit4_2-.asr_span_table4,.asr_span_emit4_1-.asr_span_table4,.asr_span_emit4_0-.asr_span_table4
.asr_span_advance4_0:
 move.b (a3)+,d1
 asr.b #2,d1
.asr_span_emit4_0:
 sub.w d4,d2
 bcc.s .asr_span_output4_0
 add.w d5,d2
 move.b d1,(a2)+
.asr_span_output4_0:
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
.asr_span_advance4_1:
 move.b (a3)+,d1
 asr.b #2,d1
.asr_span_emit4_1:
 sub.w d4,d2
 bcc.s .asr_span_output4_1
 add.w d5,d2
 move.b d1,(a2)+
.asr_span_output4_1:
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
.asr_span_advance4_2:
 move.b (a3)+,d1
 asr.b #2,d1
.asr_span_emit4_2:
 sub.w d4,d2
 bcc.s .asr_span_output4_2
 add.w d5,d2
 move.b d1,(a2)+
.asr_span_output4_2:
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
.asr_span_advance4_3:
 move.b (a3)+,d1
 asr.b #2,d1
.asr_span_emit4_3:
 sub.w d4,d2
 bcc.s .asr_span_output4_3
 add.w d5,d2
 move.b d1,(a2)+
.asr_span_output4_3:
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 dbra d6,.asr_span_advance4_0
 bra.w .span_final_advance

_nv_project_asr_ready equ *
 move.w #256,d6
 moveq #0,d0
 move.b (a3),d0
 move.b (a1,d0.w),d1
.asr_prefix:
 move.b d1,(a2)+
 subq.w #1,d6
 beq.w .done
 sub.l 48(sp),d2
 bhi.s .asr_prefix
 neg.w d2
 moveq #0,d0
 move.w d6,d0
 subq.w #1,d0
 mulu.w 50(sp),d0
 moveq #0,d1
 move.w d2,d1
 add.l d1,d0
 divu.w 26(a0),d0
 move.w d0,d6
 subq.w #1,d6
 move.w d6,d0
 addq.w #2,d0
 cmp.w d0,d3
 blo.s .asr_regular_ready
 move.w d7,d0
 subq.w #2,d0
 add.w d0,d0
 lea .asr_span_offsets(pc),a4
 move.w (a4,d0.w),d0
 lea .asr_span_runs(pc),a4
 adda.w d0,a4
.asr_regular_ready:
 moveq #0,d0
 addq.l #1,a3
 dbra d3,.asr_first_loaded
 movea.l (a0),a3
 move.l 4(a0),d3
 subq.w #1,d3
.asr_first_loaded:
 move.b (a3),d1
 asr.b #2,d1
 jmp (a4)

.span_offsets:
 dc.w .span_entry2-.span_runs,.span_entry3-.span_runs,.span_entry4-.span_runs,.span_entry5-.span_runs,.span_entry6-.span_runs,.span_entry7-.span_runs,.span_entry8-.span_runs
.span_runs:
 ; The first checked fetch left A3 at the current byte. Each entry converts
 ; it once to the next unread byte; subsequent fetches advance implicitly.
.span_entry2:
 addq.l #1,a3
 movea.l 52(sp),a4
 adda.w #256,a4
 ; Enter the partial first group, then render four complete source runs.
 move.w d6,d7
 andi.w #3,d7
 lsr.w #2,d6
 add.w d7,d7
 move.w .span_table2(pc,d7.w),d7
 jmp .span_table2(pc,d7.w)
.span_table2:
 dc.w .span_emit2_3-.span_table2,.span_emit2_2-.span_table2,.span_emit2_1-.span_table2,.span_emit2_0-.span_table2
.span_advance2_0:
 move.b (a3)+,d0
 move.b (a1,d0.w),d1
.span_emit2_0:
 sub.w d4,d2
 bcc.s .span_output2_0
 add.w d5,d2
 move.b d1,(a2)+
.span_output2_0:
 move.b d1,(a2)+
 move.b d1,(a2)+
.span_advance2_1:
 move.b (a3)+,d0
 move.b (a1,d0.w),d1
.span_emit2_1:
 sub.w d4,d2
 bcc.s .span_output2_1
 add.w d5,d2
 move.b d1,(a2)+
.span_output2_1:
 move.b d1,(a2)+
 move.b d1,(a2)+
.span_advance2_2:
 move.b (a3)+,d0
 move.b (a1,d0.w),d1
.span_emit2_2:
 sub.w d4,d2
 bcc.s .span_output2_2
 add.w d5,d2
 move.b d1,(a2)+
.span_output2_2:
 move.b d1,(a2)+
 move.b d1,(a2)+
.span_advance2_3:
 move.b (a3)+,d0
 move.b (a1,d0.w),d1
.span_emit2_3:
 sub.w d4,d2
 bcc.s .span_output2_3
 add.w d5,d2
 move.b d1,(a2)+
.span_output2_3:
 move.b d1,(a2)+
 move.b d1,(a2)+
 dbra d6,.span_advance2_0
 bra.w .span_final_advance
.span_entry3:
 addq.l #1,a3
 movea.l 52(sp),a4
 adda.w #256,a4
 ; Enter the partial first group, then render four complete source runs.
 move.w d6,d7
 andi.w #3,d7
 lsr.w #2,d6
 add.w d7,d7
 move.w .span_table3(pc,d7.w),d7
 jmp .span_table3(pc,d7.w)
.span_table3:
 dc.w .span_emit3_3-.span_table3,.span_emit3_2-.span_table3,.span_emit3_1-.span_table3,.span_emit3_0-.span_table3
.span_advance3_0:
 move.b (a3)+,d0
 move.b (a1,d0.w),d1
.span_emit3_0:
 sub.w d4,d2
 bcc.s .span_output3_0
 add.w d5,d2
 move.b d1,(a2)+
.span_output3_0:
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
.span_advance3_1:
 move.b (a3)+,d0
 move.b (a1,d0.w),d1
.span_emit3_1:
 sub.w d4,d2
 bcc.s .span_output3_1
 add.w d5,d2
 move.b d1,(a2)+
.span_output3_1:
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
.span_advance3_2:
 move.b (a3)+,d0
 move.b (a1,d0.w),d1
.span_emit3_2:
 sub.w d4,d2
 bcc.s .span_output3_2
 add.w d5,d2
 move.b d1,(a2)+
.span_output3_2:
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
.span_advance3_3:
 move.b (a3)+,d0
 move.b (a1,d0.w),d1
.span_emit3_3:
 sub.w d4,d2
 bcc.s .span_output3_3
 add.w d5,d2
 move.b d1,(a2)+
.span_output3_3:
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 dbra d6,.span_advance3_0
 bra.w .span_final_advance
.span_entry4:
 addq.l #1,a3
 movea.l 52(sp),a4
 adda.w #256,a4
 ; Enter the partial first group, then render four complete source runs.
 move.w d6,d7
 andi.w #3,d7
 lsr.w #2,d6
 add.w d7,d7
 move.w .span_table4(pc,d7.w),d7
 jmp .span_table4(pc,d7.w)
.span_table4:
 dc.w .span_emit4_3-.span_table4,.span_emit4_2-.span_table4,.span_emit4_1-.span_table4,.span_emit4_0-.span_table4
.span_advance4_0:
 move.b (a3)+,d0
 move.b (a1,d0.w),d1
.span_emit4_0:
 sub.w d4,d2
 bcc.s .span_output4_0
 add.w d5,d2
 move.b d1,(a2)+
.span_output4_0:
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
.span_advance4_1:
 move.b (a3)+,d0
 move.b (a1,d0.w),d1
.span_emit4_1:
 sub.w d4,d2
 bcc.s .span_output4_1
 add.w d5,d2
 move.b d1,(a2)+
.span_output4_1:
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
.span_advance4_2:
 move.b (a3)+,d0
 move.b (a1,d0.w),d1
.span_emit4_2:
 sub.w d4,d2
 bcc.s .span_output4_2
 add.w d5,d2
 move.b d1,(a2)+
.span_output4_2:
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
.span_advance4_3:
 move.b (a3)+,d0
 move.b (a1,d0.w),d1
.span_emit4_3:
 sub.w d4,d2
 bcc.s .span_output4_3
 add.w d5,d2
 move.b d1,(a2)+
.span_output4_3:
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 dbra d6,.span_advance4_0
 bra.w .span_final_advance
.span_entry5:
 addq.l #1,a3
 movea.l 52(sp),a4
 adda.w #256,a4
 ; Enter the partial first group, then render four complete source runs.
 move.w d6,d7
 andi.w #3,d7
 lsr.w #2,d6
 add.w d7,d7
 move.w .span_table5(pc,d7.w),d7
 jmp .span_table5(pc,d7.w)
.span_table5:
 dc.w .span_emit5_3-.span_table5,.span_emit5_2-.span_table5,.span_emit5_1-.span_table5,.span_emit5_0-.span_table5
.span_advance5_0:
 move.b (a3)+,d0
 move.b (a1,d0.w),d1
.span_emit5_0:
 sub.w d4,d2
 bcc.s .span_output5_0
 add.w d5,d2
 move.b d1,(a2)+
.span_output5_0:
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
.span_advance5_1:
 move.b (a3)+,d0
 move.b (a1,d0.w),d1
.span_emit5_1:
 sub.w d4,d2
 bcc.s .span_output5_1
 add.w d5,d2
 move.b d1,(a2)+
.span_output5_1:
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
.span_advance5_2:
 move.b (a3)+,d0
 move.b (a1,d0.w),d1
.span_emit5_2:
 sub.w d4,d2
 bcc.s .span_output5_2
 add.w d5,d2
 move.b d1,(a2)+
.span_output5_2:
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
.span_advance5_3:
 move.b (a3)+,d0
 move.b (a1,d0.w),d1
.span_emit5_3:
 sub.w d4,d2
 bcc.s .span_output5_3
 add.w d5,d2
 move.b d1,(a2)+
.span_output5_3:
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 dbra d6,.span_advance5_0
 bra.w .span_final_advance
.span_entry6:
 addq.l #1,a3
 movea.l 52(sp),a4
 adda.w #256,a4
 ; Enter the partial first group, then render four complete source runs.
 move.w d6,d7
 andi.w #3,d7
 lsr.w #2,d6
 add.w d7,d7
 move.w .span_table6(pc,d7.w),d7
 jmp .span_table6(pc,d7.w)
.span_table6:
 dc.w .span_emit6_3-.span_table6,.span_emit6_2-.span_table6,.span_emit6_1-.span_table6,.span_emit6_0-.span_table6
.span_advance6_0:
 move.b (a3)+,d0
 move.b (a1,d0.w),d1
.span_emit6_0:
 sub.w d4,d2
 bcc.s .span_output6_0
 add.w d5,d2
 move.b d1,(a2)+
.span_output6_0:
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
.span_advance6_1:
 move.b (a3)+,d0
 move.b (a1,d0.w),d1
.span_emit6_1:
 sub.w d4,d2
 bcc.s .span_output6_1
 add.w d5,d2
 move.b d1,(a2)+
.span_output6_1:
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
.span_advance6_2:
 move.b (a3)+,d0
 move.b (a1,d0.w),d1
.span_emit6_2:
 sub.w d4,d2
 bcc.s .span_output6_2
 add.w d5,d2
 move.b d1,(a2)+
.span_output6_2:
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
.span_advance6_3:
 move.b (a3)+,d0
 move.b (a1,d0.w),d1
.span_emit6_3:
 sub.w d4,d2
 bcc.s .span_output6_3
 add.w d5,d2
 move.b d1,(a2)+
.span_output6_3:
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 dbra d6,.span_advance6_0
 bra.w .span_final_advance
.span_entry7:
 addq.l #1,a3
 movea.l 52(sp),a4
 adda.w #256,a4
 ; Enter the partial first group, then render four complete source runs.
 move.w d6,d7
 andi.w #3,d7
 lsr.w #2,d6
 add.w d7,d7
 move.w .span_table7(pc,d7.w),d7
 jmp .span_table7(pc,d7.w)
.span_table7:
 dc.w .span_emit7_3-.span_table7,.span_emit7_2-.span_table7,.span_emit7_1-.span_table7,.span_emit7_0-.span_table7
.span_advance7_0:
 move.b (a3)+,d0
 move.b (a1,d0.w),d1
.span_emit7_0:
 sub.w d4,d2
 bcc.s .span_output7_0
 add.w d5,d2
 move.b d1,(a2)+
.span_output7_0:
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
.span_advance7_1:
 move.b (a3)+,d0
 move.b (a1,d0.w),d1
.span_emit7_1:
 sub.w d4,d2
 bcc.s .span_output7_1
 add.w d5,d2
 move.b d1,(a2)+
.span_output7_1:
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
.span_advance7_2:
 move.b (a3)+,d0
 move.b (a1,d0.w),d1
.span_emit7_2:
 sub.w d4,d2
 bcc.s .span_output7_2
 add.w d5,d2
 move.b d1,(a2)+
.span_output7_2:
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
.span_advance7_3:
 move.b (a3)+,d0
 move.b (a1,d0.w),d1
.span_emit7_3:
 sub.w d4,d2
 bcc.s .span_output7_3
 add.w d5,d2
 move.b d1,(a2)+
.span_output7_3:
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 dbra d6,.span_advance7_0
 bra.w .span_final_advance
.span_entry8:
 addq.l #1,a3
 movea.l 52(sp),a4
 adda.w #256,a4
 ; Enter the partial first group, then render four complete source runs.
 move.w d6,d7
 andi.w #3,d7
 lsr.w #2,d6
 add.w d7,d7
 move.w .span_table8(pc,d7.w),d7
 jmp .span_table8(pc,d7.w)
.span_table8:
 dc.w .span_emit8_3-.span_table8,.span_emit8_2-.span_table8,.span_emit8_1-.span_table8,.span_emit8_0-.span_table8
.span_advance8_0:
 move.b (a3)+,d0
 move.b (a1,d0.w),d1
.span_emit8_0:
 sub.w d4,d2
 bcc.s .span_output8_0
 add.w d5,d2
 move.b d1,(a2)+
.span_output8_0:
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
.span_advance8_1:
 move.b (a3)+,d0
 move.b (a1,d0.w),d1
.span_emit8_1:
 sub.w d4,d2
 bcc.s .span_output8_1
 add.w d5,d2
 move.b d1,(a2)+
.span_output8_1:
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
.span_advance8_2:
 move.b (a3)+,d0
 move.b (a1,d0.w),d1
.span_emit8_2:
 sub.w d4,d2
 bcc.s .span_output8_2
 add.w d5,d2
 move.b d1,(a2)+
.span_output8_2:
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
.span_advance8_3:
 move.b (a3)+,d0
 move.b (a1,d0.w),d1
.span_emit8_3:
 sub.w d4,d2
 bcc.s .span_output8_3
 add.w d5,d2
 move.b d1,(a2)+
.span_output8_3:
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 move.b d1,(a2)+
 dbra d6,.span_advance8_0
 bra.w .span_final_advance
.span_final_advance:
.span_final_loaded:
 move.b (a3)+,d0
 move.b (a1,d0.w),d1
 move.w a4,d6
 sub.w a2,d6
 subq.w #1,d6
.span_tail:
 move.b d1,(a2)+
 dbra d6,.span_tail
.span_done:
 movem.l (sp)+,d2-d7/a2-a4
 rts

 xdef _nv_hybrid_speech_unity
; Same five-argument ABI as nv_hybrid_speech; count 0..65535.
; The scaled row argument is unused at unity gain.
; Peel an odd source byte before reading aligned pairs.
_nv_hybrid_speech_unity:
 move.l 20(sp),d0
 cmpi.l #32,d0
 blo.w _nv_hybrid_speech_unity_bytes
 movem.l d2-d6/a2/a4,-(sp)
 movea.l 32(sp),a0
 movea.l 36(sp),a1
 movea.l 40(sp),a2
 move.l 48(sp),d3
 beq.w .done
 move.l a0,d0
 move.l a1,d1
 or.l d1,d0
 move.l a2,d1
 or.l d1,d0
 btst #0,d0
 bne.w .bytes
 ; Packed words require disjoint output and source spans. The original byte
 ; helper retains the exact behaviour for odd pointers and overlapping spans.
 move.l a0,d0
 add.l d3,d0
 bcs.w .bytes
 cmp.l a1,d0
 bls.s .outputs_separate
 move.l a1,d0
 add.l d3,d0
 bcs.w .bytes
 cmp.l a0,d0
 bhi.w .bytes
.outputs_separate:
 move.l a2,d0
 add.l d3,d0
 bcs.w .bytes
 cmp.l a0,d0
 bls.s .source_left_separate
 move.l a0,d0
 add.l d3,d0
 bcs.w .bytes
 cmp.l a2,d0
 bhi.w .bytes
.source_left_separate:
 move.l a2,d0
 add.l d3,d0
 cmp.l a1,d0
 bls.s .source_right_separate
 move.l a1,d0
 add.l d3,d0
 bcs.w .bytes
 cmp.l a2,d0
 bhi.w .bytes
.source_right_separate:
 move.w d3,d6
 andi.w #1,d6
 lsr.w #1,d3
 beq.w .tail
 subq.w #1,d3
 move.w #$fefe,d4
 move.w #$8080,d5
 ; Bias both signed bytes, average independent unsigned lanes, then unbias.
 ; Clearing each lane's low bit before shifting prevents cross-byte carries.
 move.w d3,d0
 andi.w #3,d0
 lsr.w #2,d3
 add.w d0,d0
 move.w .entry(pc,d0.w),d0
 jmp .entry(pc,d0.w)
.entry:
 dc.w .pair3-.entry,.pair2-.entry,.pair1-.entry,.pair0-.entry
.pair0:
 move.w (a2)+,d2
 eor.w d5,d2
 move.w (a0),d0
 move.w d2,d1
 eor.w d5,d0
 eor.w d0,d1
 and.w d2,d0
 and.w d4,d1
 lsr.w #1,d1
 add.w d1,d0
 eor.w d5,d0
 move.w d0,(a0)+
 move.w (a1),d0
 move.w d2,d1
 eor.w d5,d0
 eor.w d0,d1
 and.w d2,d0
 and.w d4,d1
 lsr.w #1,d1
 add.w d1,d0
 eor.w d5,d0
 move.w d0,(a1)+
.pair1:
 move.w (a2)+,d2
 eor.w d5,d2
 move.w (a0),d0
 move.w d2,d1
 eor.w d5,d0
 eor.w d0,d1
 and.w d2,d0
 and.w d4,d1
 lsr.w #1,d1
 add.w d1,d0
 eor.w d5,d0
 move.w d0,(a0)+
 move.w (a1),d0
 move.w d2,d1
 eor.w d5,d0
 eor.w d0,d1
 and.w d2,d0
 and.w d4,d1
 lsr.w #1,d1
 add.w d1,d0
 eor.w d5,d0
 move.w d0,(a1)+
.pair2:
 move.w (a2)+,d2
 eor.w d5,d2
 move.w (a0),d0
 move.w d2,d1
 eor.w d5,d0
 eor.w d0,d1
 and.w d2,d0
 and.w d4,d1
 lsr.w #1,d1
 add.w d1,d0
 eor.w d5,d0
 move.w d0,(a0)+
 move.w (a1),d0
 move.w d2,d1
 eor.w d5,d0
 eor.w d0,d1
 and.w d2,d0
 and.w d4,d1
 lsr.w #1,d1
 add.w d1,d0
 eor.w d5,d0
 move.w d0,(a1)+
.pair3:
 move.w (a2)+,d2
 eor.w d5,d2
 move.w (a0),d0
 move.w d2,d1
 eor.w d5,d0
 eor.w d0,d1
 and.w d2,d0
 and.w d4,d1
 lsr.w #1,d1
 add.w d1,d0
 eor.w d5,d0
 move.w d0,(a0)+
 move.w (a1),d0
 move.w d2,d1
 eor.w d5,d0
 eor.w d0,d1
 and.w d2,d0
 and.w d4,d1
 lsr.w #1,d1
 add.w d1,d0
 eor.w d5,d0
 move.w d0,(a1)+
 dbra d3,.pair0
.tail:
 tst.w d6
 beq.s .done
 lea _nv_average+32768,a4
 moveq #0,d0
 move.b (a2),d0
 lsl.w #8,d0
 move.b (a0),d0
 move.b (a4,d0.w),(a0)
 move.b (a1),d0
 move.b (a4,d0.w),(a1)
.done:
 movem.l (sp)+,d2-d6/a2/a4
 rts
.bytes:
 movem.l (sp)+,d2-d6/a2/a4
 jmp _nv_hybrid_speech_unity_bytes

 xdef _nv_hybrid_speech_unity_bytes
_nv_hybrid_speech_unity_bytes:
 movem.l d2-d3/a2/a4,-(sp)
 movea.l 20(sp),a0
 movea.l 24(sp),a1
 movea.l 28(sp),a2
 move.l 36(sp),d3
 beq.w .done
 lea _nv_average+32768,a4
 move.l a2,d0
 btst #0,d0
 beq.s .words
 moveq #0,d0
 move.b (a2)+,d0
 lsl.w #8,d0
 move.b (a0),d0
 move.b (a4,d0.w),(a0)+
 move.b (a1),d0
 move.b (a4,d0.w),(a1)+
 subq.w #1,d3
 beq.s .done
.words:
 move.w d3,d1
 andi.w #1,d1
 lsr.w #1,d3
 beq.s .tail
 subq.w #1,d3
.pair:
 move.w (a2)+,d0
 move.w d0,d2
 move.b (a0),d0
 move.b (a4,d0.w),(a0)+
 move.b (a1),d0
 move.b (a4,d0.w),(a1)+
 lsl.w #8,d2
 move.b (a0),d2
 move.b (a4,d2.w),(a0)+
 move.b (a1),d2
 move.b (a4,d2.w),(a1)+
 dbra d3,.pair
.tail:
 tst.w d1
 beq.s .done
 moveq #0,d0
 move.b (a2)+,d0
 lsl.w #8,d0
 move.b (a0),d0
 move.b (a4,d0.w),(a0)+
 move.b (a1),d0
 move.b (a4,d0.w),(a1)+
.done:
 movem.l (sp)+,d2-d3/a2/a4
 rts

 xdef _nv_hybrid_speech_only_unity
; Same arguments as nv_hybrid_speech_only. Caller selects this only for
; speech gain64 (including the clamped greater-than64 case).
_nv_hybrid_speech_only_unity:
 move.l 20(sp),d0
 beq.w .empty
 cmpi.l #16,d0
 blo.w .fallback
 cmpi.l #65536,d0
 bhi.w .fallback
 move.l 4(sp),d0
 or.l 8(sp),d0
 or.l 12(sp),d0
 btst #0,d0
 bne.w .fallback
 movem.l d2-d5/a2-a3,-(sp)
 movea.l 28(sp),a0
 movea.l 32(sp),a1
 movea.l 36(sp),a2
 movea.l 40(sp),a3
 move.l 44(sp),d2
 move.l d2,d5
 lsr.l #2,d5
 andi.w #3,d2
 subq.w #1,d5
 move.l #$fefefefe,d3
 move.l #$80808080,d4
.long:
 move.l (a2)+,d0
 move.l d0,d1
 and.l d3,d0
 lsr.l #1,d0
 and.l d4,d1
 or.l d1,d0
 move.l d0,(a0)+
 move.l d0,(a1)+
 dbra d5,.long
 tst.w d2
 beq.s .done
 moveq #0,d0
 subq.w #1,d2
.byte:
 move.b (a2)+,d0
 move.b (0,a3,d0.w),d1
 move.b d1,(a0)+
 move.b d1,(a1)+
 dbra d2,.byte
.done:
 movem.l (sp)+,d2-d5/a2-a3
.empty:
 rts
.fallback:
 jmp _nv_hybrid_speech_only_lut


 xdef _nv_hybrid_fused_unity
; Full contiguous unity speech, q2..7, and a non-reloading source span.
; Arguments: snapshot, music word row, output step, output, speech, average base.
_nv_hybrid_fused_unity:
 movem.l d2-d7/a2-a6,-(sp)
 movea.l 48(sp),a0
 movea.l 52(sp),a1
 move.l 56(sp),d5
 movea.l 60(sp),a2
 movea.l 64(sp),a5
 move.l 68(sp),d3
 movea.l 8(a0),a3
 adda.l 16(a0),a3
 move.l 24(a0),d4
 divu.w d5,d4
 moveq #0,d7
 move.w d4,d7
 swap d4
 move.l 28(a0),d2
 sub.l 20(a0),d2
 move.w #256,d6
 moveq #0,d0
 move.b (a3),d0
 add.w d0,d0
 move.w (a1,d0.w),d1
 movea.l d3,a6
 adda.w d1,a6
 moveq #0,d0
.prefix:
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 subq.w #1,d6
 beq.w .span_done
 sub.l 56(sp),d2
 bhi.s .prefix
 neg.w d2
 moveq #0,d0
 move.w d6,d0
 subq.w #1,d0
 mulu.w 58(sp),d0
 moveq #0,d1
 move.w d2,d1
 add.l d1,d0
 divu.w 26(a0),d0
 move.w d0,d6
 subq.w #1,d6
 move.w d7,d0
 subq.w #2,d0
 add.w d0,d0
 lea .span_offsets(pc),a4
 move.w (a4,d0.w),d0
 lea .span_runs(pc),a4
 adda.w d0,a4
 addq.l #1,a3
 moveq #0,d0
 move.b (a3),d0
 add.w d0,d0
 move.w (a1,d0.w),d1
 movea.l d3,a6
 adda.w d1,a6
 moveq #0,d0
 jmp (a4)
.span_offsets:
 dc.w .span_entry2-.span_runs,.span_entry3-.span_runs,.span_entry4-.span_runs,.span_entry5-.span_runs,.span_entry6-.span_runs,.span_entry7-.span_runs
.span_runs:
.span_entry2:
 addq.l #1,a3
 movea.l 60(sp),a4
 adda.w #256,a4
 ; Enter the partial first group, then render four complete source runs.
 move.w d6,d7
 andi.w #3,d7
 lsr.w #2,d6
 add.w d7,d7
 move.w .span_table2(pc,d7.w),d7
 jmp .span_table2(pc,d7.w)
.span_table2:
 dc.w .span_emit2_3-.span_table2,.span_emit2_2-.span_table2,.span_emit2_1-.span_table2,.span_emit2_0-.span_table2
.span_advance2_0:
 move.b (a3)+,d0
 add.w d0,d0
 move.w (a1,d0.w),d1
 movea.l d3,a6
 adda.w d1,a6
 moveq #0,d0
.span_emit2_0:
 sub.w d4,d2
 bcc.s .span_output2_0
 add.w d5,d2
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
.span_output2_0:
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
.span_advance2_1:
 move.b (a3)+,d0
 add.w d0,d0
 move.w (a1,d0.w),d1
 movea.l d3,a6
 adda.w d1,a6
 moveq #0,d0
.span_emit2_1:
 sub.w d4,d2
 bcc.s .span_output2_1
 add.w d5,d2
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
.span_output2_1:
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
.span_advance2_2:
 move.b (a3)+,d0
 add.w d0,d0
 move.w (a1,d0.w),d1
 movea.l d3,a6
 adda.w d1,a6
 moveq #0,d0
.span_emit2_2:
 sub.w d4,d2
 bcc.s .span_output2_2
 add.w d5,d2
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
.span_output2_2:
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
.span_advance2_3:
 move.b (a3)+,d0
 add.w d0,d0
 move.w (a1,d0.w),d1
 movea.l d3,a6
 adda.w d1,a6
 moveq #0,d0
.span_emit2_3:
 sub.w d4,d2
 bcc.s .span_output2_3
 add.w d5,d2
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
.span_output2_3:
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 dbra d6,.span_advance2_0
 bra.w .span_final_advance
.span_entry3:
 addq.l #1,a3
 movea.l 60(sp),a4
 adda.w #256,a4
 ; Enter the partial first group, then render four complete source runs.
 move.w d6,d7
 andi.w #3,d7
 lsr.w #2,d6
 add.w d7,d7
 move.w .span_table3(pc,d7.w),d7
 jmp .span_table3(pc,d7.w)
.span_table3:
 dc.w .span_emit3_3-.span_table3,.span_emit3_2-.span_table3,.span_emit3_1-.span_table3,.span_emit3_0-.span_table3
.span_advance3_0:
 move.b (a3)+,d0
 add.w d0,d0
 move.w (a1,d0.w),d1
 movea.l d3,a6
 adda.w d1,a6
 moveq #0,d0
.span_emit3_0:
 sub.w d4,d2
 bcc.s .span_output3_0
 add.w d5,d2
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
.span_output3_0:
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
.span_advance3_1:
 move.b (a3)+,d0
 add.w d0,d0
 move.w (a1,d0.w),d1
 movea.l d3,a6
 adda.w d1,a6
 moveq #0,d0
.span_emit3_1:
 sub.w d4,d2
 bcc.s .span_output3_1
 add.w d5,d2
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
.span_output3_1:
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
.span_advance3_2:
 move.b (a3)+,d0
 add.w d0,d0
 move.w (a1,d0.w),d1
 movea.l d3,a6
 adda.w d1,a6
 moveq #0,d0
.span_emit3_2:
 sub.w d4,d2
 bcc.s .span_output3_2
 add.w d5,d2
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
.span_output3_2:
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
.span_advance3_3:
 move.b (a3)+,d0
 add.w d0,d0
 move.w (a1,d0.w),d1
 movea.l d3,a6
 adda.w d1,a6
 moveq #0,d0
.span_emit3_3:
 sub.w d4,d2
 bcc.s .span_output3_3
 add.w d5,d2
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
.span_output3_3:
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 dbra d6,.span_advance3_0
 bra.w .span_final_advance
.span_entry4:
 addq.l #1,a3
 movea.l 60(sp),a4
 adda.w #256,a4
 ; Enter the partial first group, then render four complete source runs.
 move.w d6,d7
 andi.w #3,d7
 lsr.w #2,d6
 add.w d7,d7
 move.w .span_table4(pc,d7.w),d7
 jmp .span_table4(pc,d7.w)
.span_table4:
 dc.w .span_emit4_3-.span_table4,.span_emit4_2-.span_table4,.span_emit4_1-.span_table4,.span_emit4_0-.span_table4
.span_advance4_0:
 move.b (a3)+,d0
 add.w d0,d0
 move.w (a1,d0.w),d1
 movea.l d3,a6
 adda.w d1,a6
 moveq #0,d0
.span_emit4_0:
 sub.w d4,d2
 bcc.s .span_output4_0
 add.w d5,d2
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
.span_output4_0:
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
.span_advance4_1:
 move.b (a3)+,d0
 add.w d0,d0
 move.w (a1,d0.w),d1
 movea.l d3,a6
 adda.w d1,a6
 moveq #0,d0
.span_emit4_1:
 sub.w d4,d2
 bcc.s .span_output4_1
 add.w d5,d2
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
.span_output4_1:
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
.span_advance4_2:
 move.b (a3)+,d0
 add.w d0,d0
 move.w (a1,d0.w),d1
 movea.l d3,a6
 adda.w d1,a6
 moveq #0,d0
.span_emit4_2:
 sub.w d4,d2
 bcc.s .span_output4_2
 add.w d5,d2
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
.span_output4_2:
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
.span_advance4_3:
 move.b (a3)+,d0
 add.w d0,d0
 move.w (a1,d0.w),d1
 movea.l d3,a6
 adda.w d1,a6
 moveq #0,d0
.span_emit4_3:
 sub.w d4,d2
 bcc.s .span_output4_3
 add.w d5,d2
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
.span_output4_3:
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 dbra d6,.span_advance4_0
 bra.w .span_final_advance
.span_entry5:
 addq.l #1,a3
 movea.l 60(sp),a4
 adda.w #256,a4
 ; Enter the partial first group, then render four complete source runs.
 move.w d6,d7
 andi.w #3,d7
 lsr.w #2,d6
 add.w d7,d7
 move.w .span_table5(pc,d7.w),d7
 jmp .span_table5(pc,d7.w)
.span_table5:
 dc.w .span_emit5_3-.span_table5,.span_emit5_2-.span_table5,.span_emit5_1-.span_table5,.span_emit5_0-.span_table5
.span_advance5_0:
 move.b (a3)+,d0
 add.w d0,d0
 move.w (a1,d0.w),d1
 movea.l d3,a6
 adda.w d1,a6
 moveq #0,d0
.span_emit5_0:
 sub.w d4,d2
 bcc.s .span_output5_0
 add.w d5,d2
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
.span_output5_0:
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
.span_advance5_1:
 move.b (a3)+,d0
 add.w d0,d0
 move.w (a1,d0.w),d1
 movea.l d3,a6
 adda.w d1,a6
 moveq #0,d0
.span_emit5_1:
 sub.w d4,d2
 bcc.s .span_output5_1
 add.w d5,d2
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
.span_output5_1:
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
.span_advance5_2:
 move.b (a3)+,d0
 add.w d0,d0
 move.w (a1,d0.w),d1
 movea.l d3,a6
 adda.w d1,a6
 moveq #0,d0
.span_emit5_2:
 sub.w d4,d2
 bcc.s .span_output5_2
 add.w d5,d2
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
.span_output5_2:
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
.span_advance5_3:
 move.b (a3)+,d0
 add.w d0,d0
 move.w (a1,d0.w),d1
 movea.l d3,a6
 adda.w d1,a6
 moveq #0,d0
.span_emit5_3:
 sub.w d4,d2
 bcc.s .span_output5_3
 add.w d5,d2
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
.span_output5_3:
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 dbra d6,.span_advance5_0
 bra.w .span_final_advance
.span_entry6:
 addq.l #1,a3
 movea.l 60(sp),a4
 adda.w #256,a4
 ; Enter the partial first group, then render four complete source runs.
 move.w d6,d7
 andi.w #3,d7
 lsr.w #2,d6
 add.w d7,d7
 move.w .span_table6(pc,d7.w),d7
 jmp .span_table6(pc,d7.w)
.span_table6:
 dc.w .span_emit6_3-.span_table6,.span_emit6_2-.span_table6,.span_emit6_1-.span_table6,.span_emit6_0-.span_table6
.span_advance6_0:
 move.b (a3)+,d0
 add.w d0,d0
 move.w (a1,d0.w),d1
 movea.l d3,a6
 adda.w d1,a6
 moveq #0,d0
.span_emit6_0:
 sub.w d4,d2
 bcc.s .span_output6_0
 add.w d5,d2
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
.span_output6_0:
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
.span_advance6_1:
 move.b (a3)+,d0
 add.w d0,d0
 move.w (a1,d0.w),d1
 movea.l d3,a6
 adda.w d1,a6
 moveq #0,d0
.span_emit6_1:
 sub.w d4,d2
 bcc.s .span_output6_1
 add.w d5,d2
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
.span_output6_1:
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
.span_advance6_2:
 move.b (a3)+,d0
 add.w d0,d0
 move.w (a1,d0.w),d1
 movea.l d3,a6
 adda.w d1,a6
 moveq #0,d0
.span_emit6_2:
 sub.w d4,d2
 bcc.s .span_output6_2
 add.w d5,d2
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
.span_output6_2:
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
.span_advance6_3:
 move.b (a3)+,d0
 add.w d0,d0
 move.w (a1,d0.w),d1
 movea.l d3,a6
 adda.w d1,a6
 moveq #0,d0
.span_emit6_3:
 sub.w d4,d2
 bcc.s .span_output6_3
 add.w d5,d2
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
.span_output6_3:
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 dbra d6,.span_advance6_0
 bra.w .span_final_advance
.span_entry7:
 addq.l #1,a3
 movea.l 60(sp),a4
 adda.w #256,a4
 ; Enter the partial first group, then render four complete source runs.
 move.w d6,d7
 andi.w #3,d7
 lsr.w #2,d6
 add.w d7,d7
 move.w .span_table7(pc,d7.w),d7
 jmp .span_table7(pc,d7.w)
.span_table7:
 dc.w .span_emit7_3-.span_table7,.span_emit7_2-.span_table7,.span_emit7_1-.span_table7,.span_emit7_0-.span_table7
.span_advance7_0:
 move.b (a3)+,d0
 add.w d0,d0
 move.w (a1,d0.w),d1
 movea.l d3,a6
 adda.w d1,a6
 moveq #0,d0
.span_emit7_0:
 sub.w d4,d2
 bcc.s .span_output7_0
 add.w d5,d2
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
.span_output7_0:
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
.span_advance7_1:
 move.b (a3)+,d0
 add.w d0,d0
 move.w (a1,d0.w),d1
 movea.l d3,a6
 adda.w d1,a6
 moveq #0,d0
.span_emit7_1:
 sub.w d4,d2
 bcc.s .span_output7_1
 add.w d5,d2
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
.span_output7_1:
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
.span_advance7_2:
 move.b (a3)+,d0
 add.w d0,d0
 move.w (a1,d0.w),d1
 movea.l d3,a6
 adda.w d1,a6
 moveq #0,d0
.span_emit7_2:
 sub.w d4,d2
 bcc.s .span_output7_2
 add.w d5,d2
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
.span_output7_2:
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
.span_advance7_3:
 move.b (a3)+,d0
 add.w d0,d0
 move.w (a1,d0.w),d1
 movea.l d3,a6
 adda.w d1,a6
 moveq #0,d0
.span_emit7_3:
 sub.w d4,d2
 bcc.s .span_output7_3
 add.w d5,d2
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
.span_output7_3:
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 dbra d6,.span_advance7_0
 bra.w .span_final_advance
.span_final_advance:
.span_final_loaded:
 move.b (a3)+,d0
 add.w d0,d0
 move.w (a1,d0.w),d1
 movea.l d3,a6
 adda.w d1,a6
 moveq #0,d0
 move.w a4,d6
 sub.w a2,d6
 subq.w #1,d6
.span_tail:
 move.b (a5)+,d0
 move.b (a6,d0.w),(a2)+
 dbra d6,.span_tail
.span_done:
 movem.l (sp)+,d2-d7/a2-a6
 rts


 xref _nv_half_amplitude
 xref _nv_hybrid_channel_ahead_fallback
; Render an active normalized channel ahead by at most 256 output steps.
; Project source/phase directly into the existing kernels without changing live
; DMA state. Exceptional step/period layouts retain the C snapshot fallback.
 xdef _nv_hybrid_channel_ahead
_nv_hybrid_channel_ahead:
 move.l 12(sp),d0
 beq.w .fallback
 cmpi.l #8191,d0
 bhi.w .fallback
 movea.l 4(sp),a0
 move.l 24(a0),d1
 cmp.l d0,d1
 blo.w .fallback
 lsl.l #3,d0
 cmp.l d0,d1
 bcs.s .period_supported
 add.l 12(sp),d0
 cmp.l d0,d1
 bhs.w .fallback
 cmpi.l #65535,d1
 bhi.w .fallback
.period_supported:
 movem.l d2-d7/a2-a4,-(sp)
 movea.l 40(sp),a0
 movea.l 44(sp),a1
 move.l 48(sp),d5
 movea.l 52(sp),a2
 move.l 56(sp),d6
 move.l 24(a0),d4
 move.l 28(a0),d2
 sub.l 20(a0),d2
 movea.l 8(a0),a3
 movea.l a3,a4
 adda.l 12(a0),a4
 cmp.l d2,d6
 bcs.w .old_prefix
 sub.l d2,d6
 divu.w d4,d6
 moveq #0,d3
 move.w d6,d3
 addq.l #1,d3
 add.l 16(a0),d3
 clr.w d6
 swap d6
 move.l d4,d2
 sub.l d6,d2
 cmp.l 12(a0),d3
 bcs.s .position
 sub.l 12(a0),d3
 move.l 4(a0),d1
 cmp.l d1,d3
 bcs.s .reload
 divu.w d1,d3
 clr.w d3
 swap d3
.reload:
 movea.l (a0),a3
 movea.l a3,a4
 adda.l d1,a4
.position:
 adda.l d3,a3
 bra.s .select
.old_prefix:
 sub.l d6,d2
 adda.l 16(a0),a3
.select:
 move.l d5,d0
 add.l d0,d0
 cmp.l d0,d4
 blo.w .generic
 move.l d5,d0
 lsl.l #3,d0
 cmp.l d0,d2
 bls.s .prefix_supported
 add.l d5,d0
 cmp.l d0,d2
 bhi.w .generic
.prefix_supported:
 cmpi.l #65536,4(a0)
 bhi.w .generic
 move.l a4,d3
 sub.l a3,d3
 cmpi.l #65536,d3
 bhi.w .generic
 subq.w #1,d3
 divu.w d5,d4
 moveq #0,d7
 move.w d4,d7
 cmpa.l #_nv_half_amplitude+8192,a1
 bne.s .asr_ordinary_select
 cmpi.w #2,d7
 beq.s .asr_select
 cmpi.w #4,d7
 bne.s .asr_ordinary_select
.asr_select:
 move.w d7,d0
 subq.w #2,d0
 add.w d0,d0
 lea _nv_asr_run_offsets(pc),a4
 move.w (a4,d0.w),d0
 lea _nv_asr_run_table(pc),a4
 adda.w d0,a4
 swap d4
 bra.w _nv_project_asr_ready
.asr_ordinary_select:
 move.w d7,d0
 subq.w #2,d0
 add.w d0,d0
 lea _nv_project_run_offsets(pc),a4
 move.w (a4,d0.w),d0
 lea _nv_project_run_table(pc),a4
 adda.w d0,a4
 swap d4
 bra.w _nv_project_runs_ready
.generic:
 move.l d2,d3
 moveq #0,d2
 bra.w _nv_project_generic_ready

.fallback:
 jmp _nv_hybrid_channel_ahead_fallback
