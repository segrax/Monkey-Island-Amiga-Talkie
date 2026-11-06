# Validation

## Builder lifecycle and streaming (2026-11-06)

Windows MSVC Release and Linux GCC Release builds pass all three CTest targets:
embedded payload verification, format self-tests, and the new builder lifecycle
suite. The lifecycle suite uses synthetic speech and Unicode paths to test
exception cleanup/retry, retained failures, output collisions, malformed staging,
competing processes, forced termination/recovery, unsupported-input diagnostics,
and streamed PCM generation against independently constructed expected bytes.
Malformed and truncated speech inputs are rejected. Full supported-game builds,
peak process memory and interactive folder dialogs were not measured in this
check. Native Amiga runtime performance and hardware qualification are unchanged.

## Current runtime: native music between speech lines (2026-11-04)

Engine: `2e0a21cdda321e4200b7267f58c545e9aaaaa7c2024ff26717cfda52129923fa`.
Loader: `7d7d0112df0e127a8b8f453c7e6f15ce053a0d9e7fca8bc7ebd7d2f8ca5eb39a`.
Manifest: `192db48730c7459ac7ea1bd3422fefbe79327d0efe2fa25a40e2747adac21f44`.

Quiet music now uses the four original Paula channels. The software stereo
mixer runs during speech and its tail, then hands music back to Paula. Both
handover directions mute the owned channels and allow the previous DMA state
to drain before clearing its request and starting the new buffers. Speech starts
with one prepared bank; the initial fetch unmutes before preparing the next.
Over-budget preparation is rejected before stopping native music or consuming
speech. Music uses fixed half gain throughout, without ducking.

On PAL cycle-exact 68000 at 7,093,790 Hz, 1 MiB Chip + 1 MiB Slow and no Fast
RAM, matched quiet Scumm Bar crossings fell from approximately 4.2 seconds to
3.1 seconds (25-30% less time). Other visible actors were excluded from the
comparison. The same graphics/font/costume cache tiers remained available.
A separate native-music control is still faster; full speed parity is unproven.

Normal FS-UAE opening checks on Kickstart 1.3 and 3.1 completed all 15 speech
clips, returned to native music, and observed zero speech underruns, transport
resynchronisations or preparation retries. Clocked stereo recordings matched
observed speech prefixes in both channels. Existing host telemetry showed zero
underruns across 6,673 and 7,022 collected completed frames respectively.
These are bounded emulator checks, not a full playthrough or a new physical
hardware qualification.

All 28 targeted native audio suites pass, including restart/rollback, pending
interrupts, reloads, cancellation, sample arithmetic and register/CCR envelopes.
A separate full core rebuild reproduced the tested linked core byte for byte.
The existing prepared graphics and font formats are unchanged.

A fresh build of the packaged native source passed 98 pipeline scripts
with the unavailable owned-RAM fixture execution test omitted. Its engine,
loader and manifest match the emulator-tested runtime byte for byte. Windows
and Linux CTest each pass 2/2; standalone generation produces identical hashes
for all 25 output files, with invalid inputs rejected and existing outputs
preserved.

For development, `MonkeyTalkie --boot-param=28` starts in the populated Scumm Bar.
The normal startup path is unchanged. A guarded one-word correction also fixes
an original PCM initialization clear through the wrong address register.

## NTSC opening check (2026-11-04)

The same runtime passed a focused FS-UAE opening check with a cycle-exact
68030 at 14,318,180 Hz, Kickstart 3.1, 1 MiB Chip + 1 MiB Slow and no Fast
RAM. The effective emulator log confirms NTSC at 60.0544 Hz. Intro and Lookout
screens rendered correctly. All 21 observed speech generations reached the
completed counter, and music returned to native playback. Speech underruns,
transport resynchronisations and preparation refusals remained zero. Host
audio telemetry recorded zero underruns across 7,181 completed frames.
Read-only PCM-prefix comparisons found speech in both recorded stereo outputs.

Evidence: local `build/validation/quiet23-030-ks31-ntsc-v3` contains configuration,
screenshots, capture, waveform audit, counters and qualification report. The
initial run stayed PAL despite `ntsc_mode`; only the repeat with effective UAE
NTSC enabled counts as NTSC evidence. These checks cover the intro and opening
conversation, not a full NTSC playthrough or physical NTSC hardware. No runtime
changes were needed. The audio-prefix audit uses the NTSC Paula clock; exact
PAL/NTSC pitch and script-timing parity were not established.
