# Validation

## 68020 at A500 speed

Playback testing on 2 November 2026 confirmed that an emulated 68020 runs with 1 MB Chip RAM, 1 MB Slow RAM and no Fast RAM. Further testing found slowdowns in some scenes at A500 speed, so the README recommends A1200 speed or faster. A 68000 at A500 speed cannot keep up. These are emulator settings; they do not establish equivalent performance for every physical 68020 system.

## Kickstart 3 music timer ownership

Reproduced repeating music in the opening conversation with PAL 68020 timing at 7,093,790 and 14,187,580 Hz, cycle-exact disabled, 1 MB Chip, no Fast RAM and 1 MB Slow RAM, using Kickstart 3.1 rev 40.63. A matching Kickstart 1.3 run continued to advance the music. Speech buffers continued without underruns or late buffers in the failing 3.1 runs.

The trace identified `timer.device` changing CIAB timer B to one-shot operation and stopping it after the original TFMX player had started it continuously. The recorded guest writes came from ROM addresses `00fbcb44` and `00fbcb48`; the player's own start came from its offset `161a`. The stopped timer left the last music samples looping. This was a timer ownership conflict, not an audio-buffer underrun.

On Exec V39 and later, TFMX now uses the CIAA timer reserved through `cia.resource`. Its original tempo writes target that reserved timer, and its music tick runs from the registered callback. The player leaves the OS CIAB timer, pending flags and level-6 vector alone. Speech timing uses the OS E-clock after removing that conflict. Shutdown restores the original player bytes, removes the callback and closes the device. Kickstart 1.3/2.x retains its existing owned-clock path. All four music/SFX parts and stereo speech mixing are retained.

Compiled 68000 tests cover both available CIAA timer choices, tempo-register routing, active/inactive music callbacks, unchanged OS level-6 vector, system-clock reads, exact restoration of the player, resource exhaustion, device-open failure and rejection of an unexpected player layout. Existing clock preemption/lifecycle and hybrid mixing/table checks pass.

The corrected engine was run through the same opening under 3.1 at both CPU speeds and under 1.3 at 7 MHz. In five-second opening-room samples, the failing 3.1 runs had one unchanged music-register snapshot; corrected runs had 98 and 99 distinct snapshots, versus 98 for the 1.3 control. All three progressed to the village with no recorded speech underruns or late buffers. Emulator output was muted during these tests; these are sequencer, timing and gameplay-progress checks, not a new listening comparison or full playthrough.

The graphics lookup table no longer requires Fast/Slow RAM: DOS can place it in Chip RAM when necessary. The previous flag caused `LoadSeg` error 103 under the low-memory 3.1 configuration despite free Chip RAM. The corrected allocation starts successfully there. Table contents and rendering code are unchanged.

The matched engine is `53b0f07e17dda2a00f0ee67ff44907a7c7db565324e07bab15b7738edc0e3153`. The local prepared folders and three-file update package contain the rebuilt engine, loader and manifest. Both desktop builders embed that matched set.

Both desktop builds passed their payload/format CTests and standalone standard-SOU generation, output checksum and invalid-input checks. Linux integration passed on its native filesystem. An earlier WSL run targeting the Windows-mounted filesystem hit a permission error while renaming its completed staging directory; that run was not counted as a pass. Local launcher hash/configuration checks also passed.

## 68000 gameplay slowdown confirmed

The current full-audio hybrid remains unsuitable for smooth 7 MHz 68000 gameplay despite meeting audio-buffer deadlines. Diagnostic builds compared the current mixer with the same patched engine using original hardware music playback and speech disabled. Both retained the original graphics routines for this comparison. Settings were PAL 68000 at 7,093,790 Hz, CPU/memory/blitter cycle-exact options, JIT off, Kickstart 2.04, 1 MB Chip and 8 MB Fast RAM, SDL dummy audio.

In bounded roughly 30-second opening-room samples, the hybrid averaged 1.38 calls/second to its dialogue-update hook, versus 5.59 for the hardware-music control. These are update-call counts rather than display FPS, and the animation/dialogue phases were not synchronized. Accumulated renderer timings consumed 55.5% of elapsed native clock time in that mixed music/speech interval, excluding work elsewhere in the audio IRQ and speech hooks. Mean speech-buffer render time was 6,354 E-clock ticks: about 77% of the 8,243-tick buffer interval. Audio can therefore avoid underruns while starving the game.

A trial moving full-buffer temporary music samples from Chip RAM to ordinary scratch memory retained identical output/state across 128 differential cases. It did not meaningfully improve this run: 1.38 update calls/second, 55.4% render time and 6,339 ticks per speech buffer. The trial was discarded; neither its code nor the diagnostic probes were deployed. The engine measured at that time was `7e925bd3c7e148f2580f887e9852417f30d4da3c7e42f9ce38cd7a643fdaa4f0`. Local raw counters and the summary are in the development project's `build/validation/game-duty-*-v2/` and `game-duty-summary.json`. Keeping all four music/SFX parts and the current stereo speech quality at normal game speed on a 7 MHz 68000 remains unresolved.

## Hybrid mixer optimization with unchanged audio

Current engine: `7e925bd3c7e148f2580f887e9852417f30d4da3c7e42f9ce38cd7a643fdaa4f0`.

The hybrid retains all four music/SFX parts and mixes speech into both outputs at the existing sample rate and gain. The two direct hardware channels are unchanged. The software resamplers count down to source transitions and reuse a scaled byte when successive output samples repeat it. With no speech bytes, exact half-gain tables remove a separate output pass. A signed-pair lookup replaces the two per-sample speech additions and arithmetic shifts. All tables are generated during the native build; the original unsigned gain calculation's negative rounding is preserved exactly.

The tables occupy 132,096 bytes of ordinary read-only memory, replacing the previous 16,640-byte runtime amplitude array. They need no extra Chip RAM. This is a CPU/memory tradeoff for the existing Fast RAM configuration, not a reduction in speech quality or a claim of compatibility with an unexpanded A500.

The compiled final engine passes the clock lifecycle/preemption tests and hybrid driver tests. An exhaustive test verifies all 65 gain rows and all 65,536 signed music/speech pairs through the assembly mixer on both outputs. Differential tests against the previous engine pass 128 deterministic cases with identical output buffers, speech state, live music phase and hardware register state, including partial/ring-wrapped speech, gain limits, cancellation, changing sample periods and loop lengths. In representative compiled 68000 measurements, music-only IRQ instructions fall from 7,141 to 4,313 (39.6%), music plus speech from 9,049 to 6,770 (25.2%), and silent IRQs from 658 to 646. These are instructions with mocked OS/clock calls, not measured game frame rates.

An intermediate engine with the same tables/resampler, before moving unused speech-table address calculation out of silent buffers, was compared against the previous release in instrumented FS-UAE. Tests used PAL 68000 at 7,093,790 Hz, CPU/memory/blitter cycle-exact options, JIT off, 1 MB Chip and 8 MB Fast RAM. Under Kickstart 2.04 the new run reached the opening conversation and completed speech generation 21 with matching rendered/played counters, zero underruns and zero late buffers. Its title-stage peak rendering interval was 3,827 E-clock ticks; the old run was still earlier in startup at the matching sample and recorded 6,585 ticks. The new peak reached 6,562 ticks during speech later in the run. A Kickstart 1.3 run reached the opening scene and Guybrush walking away, with zero reported underruns/late buffers in its final samples; those samples do not establish speech completion under 1.3. Escape was sent again after titles became visible because the first attempt occurred during startup. No full playthrough or smooth stock-A500 certification is claimed.

The final engine was checked separately under Kickstart 2.04 at the same configured 7.09 MHz. The 68000 reached the opening conversation, completed speech generation 18 with matching rendered/played counters, and recorded zero underruns/late buffers with a 6,505-tick peak. The 68030 reached Part One, with matching generation 35 counters, zero underruns/late buffers and a 1,738-tick peak. These instrumented runs used SDL dummy audio with volume zero. Windows and Linux builder payload/format tests and full standard-SOU generation/checksum/rejection smoke checks passed after embedding the new matched module, loader and manifest. Local prepared/update folders contain that final engine. The normal launcher retains its 68030/50 MHz settings.

## Deferred CIA callback and startup audio reset

Previous engine: `612ab79a69be45a44de51dbddf8134ea7531070dc2779610305b7280bf4aff28`.

A compiled regression reproduces a clock race in the previous `9aa421...` release: an audio IRQ can preempt the CIA resource dispatcher after the pending overflow bit is consumed but before its callback extends the epoch. That implementation returned 15 ticks after previously returning 65,435. Counter deltas now account for that wrap, and callback epochs retain complete periods during gaps between polls. A deferred callback does not double-count a wrap already observed by polling. The archived previous core fails this test; the rebuilt core passes it, the V34/V37 lifecycle tests and the compiled hybrid audio tests. These checks now run automatically in hybrid native builds.

Startup and shutdown now mute all four Paula volumes, including the two direct music channels. Tests seed all four with nonzero volumes and verify that none remain audible. No manual AUDxDAT writes or per-sentence music muting were added. This closes an incomplete reset, but does not establish that stale output caused the reported intro buzz on physical hardware.

A bounded standard FS-UAE file-only capture on PAL 68020, configured 7.09 MHz and Kickstart 2.04, reached the titles, opening conversation and Part One with both the previous and rebuilt executables. Instrumented Kickstart 2.04 runs at the same configured frequency reached Part One on both 68020 and 68030, with zero speech underruns and zero late buffers in the final samples. Peak render intervals were 2,822 and 1,892 E-clock ticks respectively. Separate instrumented Kickstart 1.3 testing reached the opening conversation and Guybrush walking away. The 1.3 run's host memory counter read failed with a permission error; its screenshots establish progress, not zero underruns. Captures are available locally under `build/validation/music-startup-{before,after}` in the development project. A capture alone does not certify removal of an audible buzz or repeating notes, and no new physical-hardware result is claimed.

## CPU comparison and independent CIAA clock

Matched instrumented FS-UAE tests used the same current game files, Kickstart 2.04, PAL, 1 MB Chip/8 MB Fast RAM, 24-bit addressing, JIT off, CPU/memory/blitter cycle-exact options and a configured 7,093,790 Hz. The previous `88891edb...` engine reached gameplay on both 68020 and 68030 during the bounded run; their blank-screen failure was not reproduced with these settings. The 68000 progressed to title graphics but remained much slower.

The 68000 clock measurements exposed a separate bug: a persistent peak render interval of `4294908775` ticks represents a backwards clock reading near a 16-bit wrap, not a render that really took thousands of seconds. There were 449 recorded late-buffer events. The original executable's code at `0x1608`–`0x165e` takes over the CIAB level-6 vector and reads the whole CIAB interrupt register, bypassing normal CIA resource dispatch. This is a concrete conflict with relying on the shared OS timer during the game; the precise internal ReadEClock race has not been independently reconstructed.

The replacement uses a timer allocated through **ciaa.resource** on both Kickstart 1.3 and later systems. It reconciles counter snapshots with resource callbacks and never borrows either CIAB timer. Polling does not consume pending resource interrupts. If both CIAA timers are occupied, acquisition fails instead of stealing a timer. The resource callback supplies whole-period epochs and polling observes counter deltas; the original game keeps its CIAB timer and interrupt handler. The clock's selected hardware address is exported for diagnostic checks. Compiled 68000 lifecycle tests cover V34/V37, ownership failure, pending/callback wraps, wrap during snapshot, modulo-32-bit rollover, raw master/CPU-mask preservation, fallback to the other CIAA timer and release. The existing compiled hybrid audio tests also pass.

An intermediate build using the same CIAA clock path removed the backwards readings on the 68000: 4,508,672 frames, zero late render buffers and a 6,729-tick peak (9.49 ms) in the final sample. It reached title graphics. This is **not** a claim of smooth stock-A500 gameplay or a final-build 68000 playthrough; substantial CPU load and long startup remain limitations.

Previous engine `9aa421218894c1e7db80c7ee2996f76364c80378a57c412ca6b00ba0b666db5e` was checked on 68020 and 68030 at the same configured 7.09 MHz under Kickstart 2.04. After Escape skipped the titles, both reached the opening conversation and Part One screen. The last samples reported matching rendered/played speech generations, no underruns, no late buffers, and CIAA timer A (`0xbfe401`). A separate 68020/Kickstart 1.3 run reached the opening conversation and Guybrush's walk away; its final sample showed speech playing with no underruns or missed render deadlines. These runs used SDL's dummy audio driver and volume zero, verified in logs; they establish graphics, game progress and DMA speech state, not a new listening-quality certification or physical-hardware result.

Windows/Linux payload and format tests plus full standard-SOU builder smoke checks passed after embedding the matched engine, loader and manifest. Local prepared/update folders were refreshed. `tests/write_cpu_comparison.ps1` in the local development project generates three WinUAE comparison configurations using one validated runtime, ROM, memory and addressing setup, changing only the CPU model at 7.09 MHz. The previously tested default launcher remains 68030/50 MHz. Existing saved emulator configurations can contain other differences; no user configuration or raw hard disk was changed by these tests.

## 68000 audio deadline investigation and sample loops

The previous hybrid (`5c559be2...`) spent up to 19,566 PAL E-clock ticks (27.58 ms) rendering a 256-sample buffer with an 8,243-tick (11.62 ms) deadline. In an isolated instrumented FS-UAE run with a 68000, real/A500 speed, cycle-exact timing, Kickstart 1.3, PAL, 1 MB Chip and 8 MB Fast RAM, consecutive samples showed the late-buffer counter increasing on every rendered buffer. The debugger stopped inside the music sample loop with interrupt level 7. The original executable and patched executable without the talkie loader both reached their initial visible screen under the same guest configuration. The full previous hybrid eventually reached title graphics in the 235-second standard-FS-UAE capture; an initially blank screen was therefore not proof of a permanent lockup.

The replacement uses plain 68000 assembly for the two music resamplers, signed speech addition and fixed headroom. Music phase still advances separately on the native clock; rendering changes only local snapshots. Speech is consumed once and mixed into Paula channels 0/1, one per side. Original music/SFX channels 2/3 remain direct hardware channels. Sample rate, speech archive, gain, channel routing and mapping are unchanged.

That earlier tested engine is `88891edba0aa7b8052c37bcac2f9ed47c976d56828e7c694cab0322d531c8405`. Compiled 68000 tests passed, including 128 deterministic differential cases against the previous renderer with byte-identical output and matching speech/live music state, ring wrap, short tails, cancellation, signed limits, muted music, loop reloads and varying sample periods. A representative music-plus-speech IRQ fell from 18,561 to 9,049 instructions; idle IRQ counts were 669 and 658. A second build reproduced the full engine hash.

The same instrumented 68000/1.3 setup reached the opening scene after Escape skipped the titles. At the final counter sample, 5,174,528 frames had been produced, the peak render time was 7,144 E-clock ticks (10.07 ms), and zero render deadlines had been missed. These counters exclude work elsewhere in the IRQ and game; they do not certify overall smoothness. Standard FS-UAE 3.1.66 independently reached the title graphics in its 235-second capture. Opening speech and a full stock-A500 playthrough are not established by these captures. The instrumented emulator used SDL audio despite the requested OpenAL file-only setting, so its session was stopped; no file-only audio-quality claim is made for it.

Both Windows and Linux builders were rebuilt with the matched engine, loader and manifest. Their payload/format tests and standalone standard-SOU generation, exact-output hashes and invalid-input checks passed. The local prepared folders and existing three-file update folder contain the same new engine. The local launcher's normal profile remains the previously tested 68030/50 MHz setup; selecting a 68000 manually is a separate compatibility test.

## Controlled startup configuration check

The normal local launcher still selected the older dedicated-channel package while its hybrid alternative selected the current hybrid and different CPU timing. The local launchers now select the same matched current package, use an explicit PAL 68030/50 MHz profile with 24-bit addressing, JIT off, cycle-exact CPU/memory/blitter options, 1 MB Chip and 8 MB Fast RAM, and preserve existing saves. Amiga startup scripts are normalized to LF for 1.3. The launcher's read-only hash checks tolerate an emulator holding a shared file handle. Generated configurations and both entry points are checked for identical guest settings, unique options and the expected runtime folder.

In FS-UAE 3.1.66, current engine `5c559be247c96c6793d785d65a3787e841401e92561bc6bd44e78cb0e11c0d0c` stalled with 32-bit addressing under Kickstart 2.04. Changing only the addressing option to 24-bit (same CPU, ROM, code and game files) reached the title sequence and opening conversation. File-only audio matched the opening recording with correlation 0.520 at 143.255 seconds. The original user-approved hybrid was also tried under the same 32/24-bit configurations but did not progress beyond startup in the bounded runs; those baseline attempts are not passes.

The current build was then checked under Kickstart 1.3 with the fixed 24-bit profile and reached opening speech (correlation 0.628 at 151.027 seconds). This establishes reproducible startup and opening speech for the stated profile. It does not establish the internal cause of the 32-bit stall, reproduce a TF536 exactly, or certify a full playthrough, all reported intermittent behavior, or stock 68000 cycle-exact playback. No additional native-code change was made for this configuration correction.

## Hybrid render optimization

The mixer now snapshots speech state per buffer, uses two explicit music-channel snapshots instead of indexing an array per sample, and zeroes silent output buffers through the existing assembly helper. Zero-volume DMA continues to advance and generate events in the live timeline. No speech samples, output rate, music gain or channel routing were changed.

Compiled 68000 differential tests compare both output buffers, speech state/cursors, live virtual-channel state and hardware register state against the pre-optimization hybrid across 128 deterministic cases. They include ring wrap, cancellation, short/empty tails, EOF/starvation, muted channels, variable pitch/length and gain limits. The existing hybrid and both clock-backend tests pass.

With mocked clock/OS calls, a silent IRQ fell from 25,063 to 669 instructions. Separate representative measurements were 41,235 to 15,119 for music, 33,800 to 9,720 for speech, and 49,972 to 18,242 for music plus speech. These are instruction counts, not measured 68000 cycle budgets or a guarantee of stock A500 performance.

FS-UAE 3.1.66 with a 68030, configured 50 MHz, CPU/memory/blitter cycle-exact options enabled, JIT off, PAL, 1 MB Chip and 8 MB Fast RAM (no Slow RAM or second Fast block) reached the opening conversation under Kickstart 1.3. File-only captured audio contains the opening recording with correlation 0.612 at 153.158 seconds. This establishes progress and speech output in that configuration; it does not prove perfect audio or reproduce TF536 timing exactly. Earlier cycle-exact 68000 runs with the inherited Slow/second-Fast memory configuration did not pass (blank/yellow displays); the specific cause is unresolved and those attempts are not counted as compatibility passes.

The same 68030 cycle-exact configuration also reached the opening conversation under Kickstart 2.04 rev 37.175; captured opening speech correlation was 0.472 at 142.072 seconds. These captures establish recognizable output, not an audio-quality certification. Both test sessions were stopped after conversation progress was observed, with no full playthrough performed.

Both desktop builders embed the updated matched engine/loader/manifest. Standalone standard-profile generation and invalid-input checks passed on Windows and Linux after refreshing the payload.

## Kickstart 1.3 clock fix

The hybrid clock previously returned failure on Exec versions below V36, preventing the audio driver from starting. The new 1.3 backend allocates a free CIA timer through `cia.resource`, extends its counter using overflow interrupts, and releases it on shutdown. The V36+ `ReadEClock` path is retained.

Compiled 68000 lifecycle checks cover resource exhaustion, pending underflows, an underflow during a snapshot, callback-driven counter extension, idempotent startup/shutdown, interrupt-master preservation, and the existing V36+ success/error paths. The compiled hybrid mixer checks also pass.

FS-UAE 3.1.66 with a Kickstart 1.3 rev 34.5 ROM ran the standalone clock probe at PAL A500/68000 real/cycle-exact speed: allocation succeeded and sampled ticks advanced across multiple wraps. A separate full-game run used PAL 68020 maximum speed with JIT disabled. Its file-only audio capture contains the opening 7,572-sample speech recording with normalized waveform correlation 0.959 at 105.735 seconds, after resampling at the PAL Paula output rate. This verifies speech output under 1.3; it is not a physical-hardware test, a full playthrough, or proof of smooth stock-A500 speech. An attempted JIT run aborted inside FS-UAE and was not counted as a pass.

An additional full-game run at PAL A500/68000 real/cycle-exact speed progressed through launcher startup to a blank blue display, but did not reach the opening conversation during the bounded capture. This attempt is not a pass; its cause has not been established.

Both desktop builders were rebuilt with the matched engine delta, loader and manifest. Windows and Linux standalone generation of the standard SOU profile passed exact output hashes and invalid-input rejection checks. The speech archive, map and prepared samples are unchanged by this fix.

## Desktop builder checks

The C++ builder was compiled with MSVC 19.50 on Windows x64 and GCC 11.4 on Ubuntu 22.04 x64. Both passed the CTest payload and binary-format self-tests.

Both platforms generated the expanded and standard profiles from the owned original Amiga data, original executable/disk 1 ADF, and corresponding SOU. The engine, loader, worker, map, prepared speech and room files match the pinned reference hashes. The expanded profile reproduces the user-tested hybrid package. Paths containing spaces and Unicode were exercised.

The Windows smoke script checks every output manifest hash, verifies the pinned engine/map/PCM/worker/room files, and rejects existing outputs, unsupported speech archives and invalid executable inputs. The Linux smoke script runs an isolated copy of the executable, checks output file hashes and exercises the same rejection paths. Invalid inputs are rejected before a playable output folder is created.

Windows dependency inspection shows only system DLLs; no .NET, Python, Visual C++ redistributable or separate patch files are required at runtime. The Linux executable uses the normal glibc/libstdc++/libgcc/libm system libraries.

These checks validate the builder and byte-identical generated game files. They are not a new game playthrough, GUI usability test, or claim of stock A500 performance. The standard SOU profile intentionally omits the 16 supplemental mapping keys absent from its source archive.

Run `ctest --test-dir <build-folder> -C Release --output-on-failure` for source self-tests. Use `source/tests/Smoke.ps1` on Windows or `source/tests/smoke.sh` on Linux for integration checks with your own supported game inputs. No proprietary fixtures are needed for the C++ builder tests.
