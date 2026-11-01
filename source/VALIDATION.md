# Validation

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
