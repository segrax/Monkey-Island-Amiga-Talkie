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
Ultimate Talkie, first copy the three headers from standard-bindings over their
counterparts in audio/worker, then build. Headers must match the archive and
map; the desktop builder selects the matching embedded worker automatically.
