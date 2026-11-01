# Validation

## 68000 audio deadline investigation and sample loops

The previous hybrid (`5c559be2...`) spent up to 19,566 PAL E-clock ticks (27.58 ms) rendering a 256-sample buffer with an 8,243-tick (11.62 ms) deadline. In an isolated instrumented FS-UAE run with a 68000, real/A500 speed, cycle-exact timing, Kickstart 1.3, PAL, 1 MB Chip and 8 MB Fast RAM, consecutive samples showed the late-buffer counter increasing on every rendered buffer. The debugger stopped inside the music sample loop with interrupt level 7. The original executable and patched executable without the talkie loader both reached their initial visible screen under the same guest configuration. The full previous hybrid eventually reached title graphics in the 235-second standard-FS-UAE capture; an initially blank screen was therefore not proof of a permanent lockup.

The replacement uses plain 68000 assembly for the two music resamplers, signed speech addition and fixed headroom. Music phase still advances separately on the native clock; rendering changes only local snapshots. Speech is consumed once and mixed into Paula channels 0/1, one per side. Original music/SFX channels 2/3 remain direct hardware channels. Sample rate, speech archive, gain, channel routing and mapping are unchanged.

The current full engine is `88891edba0aa7b8052c37bcac2f9ed47c976d56828e7c694cab0322d531c8405`. Compiled 68000 tests passed, including 128 deterministic differential cases against the previous renderer with byte-identical output and matching speech/live music state, ring wrap, short tails, cancellation, signed limits, muted music, loop reloads and varying sample periods. A representative music-plus-speech IRQ fell from 18,561 to 9,049 instructions; idle IRQ counts were 669 and 658. A second build reproduced the full engine hash.

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
