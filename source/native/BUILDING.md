# Rebuilding the native code

The desktop builder embeds the engine delta, MonkeyTalkie loader and VoiceServer
worker. This directory contains their source. See [../BUILDING.md](../BUILDING.md)
for the Windows/Linux tools and [../VALIDATION.md](../VALIDATION.md) for checks.

## Toolchain

Use Python 3.11+, VBCC m68k-amigaos, VASM, VLINK and the Amiga NDK.
Build scripts expect the toolchain at D:/Tools/amiga-dev; the compiler
configuration is audio/kick13.cfg.

From source/native, install the test dependencies:

```sh
python -m pip install --target tools/python -r requirements-dev.txt
```

Place the original Amiga executable at data/original/Monkey_Island.
Its SHA-256 must be
`1ac24b2fa0e4f9e454a5523bb57e48496805e8c4fa3dfa07efb6855a1bfa7725`.

## Build the current engine and loader

From source/native:

```sh
python engine/build.py --candidate --hybrid-mix --planar-cache --planar-chip-fallback --glyph-cache --skip-fixture-tests --output build/talkie
```

Choose a new output directory beneath build for each build. The command
compiles the components, applies the engine patches, runs their checks and
builds the matched loader. The skip-fixture-tests flag omits the one execution
test that needs the external combined-ram.bin snapshot.

Keep these outputs together:

| Output | Installed name |
| --- | --- |
| build/talkie/module/Monkey_Talkie_Test | Monkey_Talkie |
| build/talkie/module/loader-build/MonkeyTalkie | MonkeyTalkie |
| build/talkie/module/module.json | module.json |

Workbench startup is handled by `audio/workbench_launch.h`: the launcher uses
`Execute` to start a CLI instance in the icon's directory, sets a 65536-byte
stack and starts `MonkeyTalkie`. The original game must enter through
its CLI startup path because the launcher's runtime has already received the
Workbench startup message. On Kickstart 1.3, `Execute` needs `C:Run` available.
The console stays open until Return is pressed so startup errors can be read.
The loader and worker exchange a bounded error string in an extended Workbench
startup message, so worker failures are visible even though its C runtime sends
standard output to `NIL:`. Rebuild and install both together. The voice ring
prefers Fast/Slow RAM and falls back to any public RAM, including Chip RAM.

The desktop builder applies `assets/patches/pirate-wheel.json` to its output
copy of `Rooms/disk01.lec`. Two fixed-size script edits automate the Enter
prompt and enter `(correct_year - entered_prefix) / digit_place` one digit
at a time. The original drawing, answer-string updates, year comparison and
cleanup remain intact. The first digit waits 90 script ticks; subsequent
digits wait 12 ticks each. Input files and script/resource offsets are preserved.
Source bytes and complete input/output hashes are checked before publishing.

Verify all 256 possible wheel years in the shipped 68000 script interpreter
against a generated game folder (native Python test dependencies required):

```sh
python engine/core/test_pirate_wheel.py --game-dir /path/to/generated/game
```

The check executes the patched arithmetic, original string mutation and original
success comparison. Drawing, input and timer scheduling are modeled, so this
does not replace an Amiga startup/rendering check.

The final `engine/cursor/patch.py` stage corrects the original invisible pointer:
its blank image starts 72 bytes into a 96-byte cleared Chip allocation, but the
original SetPointer call requests 16 rows (72 bytes). The patched call requests
one row (12 bytes), entirely inside the blank tail. Normal gameplay still uses
the original 16-row cursor. `engine/cursor/test_pointer.py` reproduces the old
overread with nonzero neighboring memory and checks the corrected hidden and
normal visible pointer calls on 68000, 68020 and 68030; Intuition is mocked.

The desktop builder generates native-planar.dat, native-font-2.dat,
native-font-4.dat and native-voice.pcm from the selected game inputs.
Native compilation alone does not produce these assets. Graphics must match
the module manifest. Missing or unsuitable graphics use the original drawing
paths. See [engine/art/FORMAT.md](engine/art/FORMAT.md) and
[engine/scaling/CACHE.md](engine/scaling/CACHE.md) for their formats and
allocation rules.

## Audio and tests

The hybrid driver plays all four music/SFX parts directly through Paula between
speech lines. During speech, channels 0/1 mix music with centered voice while
channels 2/3 remain native. Handover waits for the previous DMA state to drain,
unmutes on the initial fetch and restores unconsumed speech if preparation
exceeds its budget. Gain stays fixed, without ducking.

Hybrid builds define NV_QUIET_NATIVE for the driver and register adapters and
link engine/core/native_hw_read.s. The driver uses -O=65535 -schedule -speed;
all native code targets the 68000.

The engine build runs audio, rendering, relocation, cache and ABI checks.
The test_quiet_restart.py and test_quiet_prime.py suites cover handover and
pending interrupts. Mixer tests enter MIX through the actual READY/service
path. Individual tests use MONKEY_ENGINE_BUILD to select their build directory.

The graphics game, scope, loop, C2P, prewarm and payload-version checks share
`engine/art/art_fixture.py`. Its `ArtEnvironment` owns a candidate's relocated
images and synthetic resource description; each `Fixture` gets a separate CPU,
memory, file contents and I/O history. Importing the helper does not load a
candidate or parse command-line arguments.

Check the shared fixture without original game files or the Amiga toolchain:

```sh
python -m unittest discover -s engine/art -p test_art_fixture.py -v
```

These checks use the Python dependencies above and a generated three-hunk
executable with real 68000 instructions. To run a graphics suite against a built
candidate, pass its executable explicitly, for example:

```sh
python engine/art/test_game.py --candidate build/talkie/module/Monkey_Talkie_Test
```

Render statistics are disabled in release builds. Set MONKEY_RENDER_STATS=1
for diagnostic builds; the manifest records whether those counters are active.
Speech underrun and scheduling checks remain active in release builds.

For a populated Scumm Bar development start, run on the Amiga:

```text
MonkeyTalkie --boot-param=28
```

## Voice worker

From source/native:

```sh
python audio/worker/build_worker.py
```

The output is audio/worker/VoiceServer_PreparedOnly, installed as VoiceServer.
The worker supports prepared NPC1 audio and monster.sou fallback. The
PreparedOnly marker requires matched prepared PCM and disables that fallback.
The direct and continuous-stereo engine backends remain available in the source.

Default worker headers bind the expanded archive/map profile. For standard
Ultimate Talkie, first copy the three headers from `native/standard-bindings` over their
counterparts in audio/worker, then build. Headers must match the archive and
map; the desktop builder selects the matching embedded worker automatically.
