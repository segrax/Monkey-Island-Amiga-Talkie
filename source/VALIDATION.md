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

## Workbench launch and automatic pirate wheel (2026-11-08)

The launcher now handles Workbench startup by opening a console and starting a
CLI instance with a 64 KiB stack. This avoids the original game waiting for the
Workbench startup message already consumed by the launcher's C runtime.
The console remains open until Return is pressed after the game returns.

Generated `Rooms/disk01.lec` has two fixed-size script edits: the Enter prompt
advances after a delay, and the correct year enters one digit at a time. The
original rendering, answer-string mutation, comparison and cleanup are retained.
The engine binary, remaining room files, graphics and prepared audio are unchanged.

Windows and Linux CTest each pass 5/5, including mocked Workbench directory,
console and Shell startup paths and script-patch checksum/bounds rejection.
A standalone Windows build with the standard speech profile passes the full
owned-input smoke test, including the patched room checksum, generated-file
hashes, existing-output preservation and bad-input rejection.

`native/engine/core/test_pirate_wheel.py` checks that generated folder using the
shipped 68000 VM in Unicorn: all 256 possible years (1506–1761) produce the
expected five answer-string states (empty, then one through four digits), and
the original comparison takes its success branch. It also checks the automated
Enter wait and scripted delays. Rendering, input and timer scheduling are
modeled; these changes have not yet been checked on a physical Amiga or in a
full AmigaOS emulator session.

## Voice worker startup diagnostics (2026-11-08)

The loader now receives worker startup errors through an extended Workbench
message, making profile, file, signal and ring-allocation failures visible in
the launcher console. Ordinary Workbench/CLI worker launches still work without
the extension. The ring prefers non-Chip memory and retries with any public
memory when that allocation fails; Paula uses separate DMA buffers.

Both speech-profile workers and the matched loader were rebuilt for 68000 and
Kickstart 1.3. The new host regression checks cover extension size/magic guards,
bounded error copying, preferred-memory success, Chip fallback and allocation
failure. These checks do not establish the cause of the reported icon startup
failure; an AmigaOS retry is needed to read its specific error.

Windows and Linux CTest each pass 6/6. A fresh standalone Windows build with
the standard speech profile passes the owned-input smoke test, including all
generated-file hashes, existing-output preservation and invalid-input rejection.

## Invisible mouse pointer correction (2026-11-08)

The original pointer initializer allocates 96 cleared Chip bytes. Its invisible
pointer starts at byte 72, leaving 24 blank bytes, but its SetPointer call
requests a 16-row sprite requiring 72 bytes. Neighboring allocation contents
can therefore appear as a stray cursor during the pirate screen and intro.
The correction changes only the hidden-pointer dimensions at code offset
`0x15130`: height 1, width 16, requiring 12 blank bytes. The visible gameplay
cursor routine and its dimensions are unchanged.

The 288-case native regression test executes the original and corrected hidden
pointer routines plus the visible cursor routine on 68000, 68020 and 68030,
with all 32 incoming CCR states. Nonzero neighboring memory reproduces the
old out-of-bounds sprite; the corrected call remains blank and within the
allocation. Patch footprint, repeated application and relocation overlap guards
also pass. Intuition's SetPointer call is mocked; physical Amiga/AmigaOS visual
verification remains outstanding.

Both desktop builders pass 6/6 CTest checks. The fresh standard-profile output
passes the owned-input smoke test and matches the corrected engine and matched
launcher. The pirate-wheel VM regression still passes all 256 possible years.
