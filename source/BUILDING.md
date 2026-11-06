# Development

## Current runtime

The Windows and Linux builders embed this matched runtime:

- Engine: `2e0a21cdda321e4200b7267f58c545e9aaaaa7c2024ff26717cfda52129923fa`
- Loader: `7d7d0112df0e127a8b8f453c7e6f15ce053a0d9e7fca8bc7ebd7d2f8ca5eb39a`
- Manifest: `192db48730c7459ac7ea1bd3422fefbe79327d0efe2fa25a40e2747adac21f44`

The native build uses `--candidate --hybrid-mix --planar-cache --planar-chip-fallback --glyph-cache --skip-fixture-tests`.
See [native/BUILDING.md](native/BUILDING.md) for the complete command and toolchain.
The source pipeline and standalone Windows/Linux generation checks pass;
[VALIDATION.md](VALIDATION.md) records the measurements.

The runtime plays all four music/SFX parts directly through Paula between speech
lines. During speech, channels 0/1 mix music with centered stereo voice, then
return to native playback after the speech tail drains. Original script/frame
caps and speech samples/rate remain unchanged. Optional costume, graphics and font
caches accelerate drawing, with the original renderers as fallback.

The C++ builder generates `native-planar.dat` from the selected Amiga files and
checks its SHA-256 against the runtime manifest. The runtime trusts generated
pixel content, like prepared voice PCM, and checks bounds, alignment, live
source, palette, history and pixels before using it. The graphics format is documented
in [native/engine/art/FORMAT.md](native/engine/art/FORMAT.md). The builder also
generates `native-font-2.dat` and `native-font-4.dat` from the selected game files.
These font programs use the live palette and share the costume-cache allocation;
costume drawing revokes them before that memory can be reused.

All development files live here; the two runnable builders stay at the repository root.

| Directory | Purpose |
| --- | --- |
| `builder` | Shared C++17 Windows/Linux builder |
| `assets` | Hash-pinned engine delta, dialogue recipe and our loader/worker binaries |
| `native` | Corresponding Amiga engine/loader/worker source |
| `third_party` | Vendored C++ headers and licences |
| `cmake` | Embeds the payload in the executable |
| `tests` | Integration checks using owned game inputs |

The Amiga `MonkeyTalkie` launcher is included: `native/audio/server_probe.c`
contains the loader code selected by `NATIVE_GAME_LOADER`, `call_game.s` enters
the original game, and `build_loader.py` builds it against the patched engine
manifest. `native/audio/worker` contains the `VoiceServer` source, and
`native/engine` contains our engine modifications.

## Build the desktop builder

Install CMake 3.20+, a C++17 compiler and Python 3.8+ for the automated tests.
Python is not required to run the finished builder. From the repository root:

```powershell
# Windows: Visual Studio C++ desktop tools
powershell -NoProfile -ExecutionPolicy Bypass -File source/build.ps1
```

```sh
# Linux: C++ toolchain and CMake
sh source/build.sh
```

Both helpers compile, run CTest, and update the appropriate root executable. Intermediate outputs go into the ignored root `build` directory. No dependencies are downloaded: the required headers are vendored. Windows links the C/C++ runtime statically; Linux uses the usual system C/C++ libraries.

Generic CMake commands, also from the repository root:

```sh
cmake -S source -B build/local -DCMAKE_BUILD_TYPE=Release
cmake --build build/local --config Release --parallel
ctest --test-dir build/local -C Release --output-on-failure
```

## GitHub Actions

Pushes to `main` build and test the Windows x64 and Linux x64 tools, then upload the executables as workflow artifacts. The Build workflow can also be run manually from `main`; other branches are skipped.

Pushing a tag creates a GitHub release with both freshly built executables and `SHA256SUMS`. The tagged commit must be in `main`'s history; tags on other branches are rejected before compilation. Release publishing waits for both platforms to build and pass CTest. For example, after committing and pushing your changes to `main`:

```sh
git tag v1.0.0
git push origin v1.0.0
```

The workflows share `build-tools.yml` for the main-commit check, CMake builds, tests and artifacts. They build the desktop tools using the embedded Amiga runtime assets; they do not rebuild the native Amiga components.

## Verification

Run `--help` or `--verify-payload` on either executable. Automated game builds accept `--amiga <folder> --sou <monster.sou> --engine <original-executable-or-disk1.adf> --output <new-folder>`.

`tests/Smoke.ps1` and `tests/smoke.sh` exercise full builds and rejection paths with your owned inputs. See [VALIDATION.md](VALIDATION.md) for the bounded validation performed. The `--self-test` command checks embedded data and format vectors without game files.

CTest also runs `builder_lifecycle`, using synthetic inputs and temporary Unicode
paths. It checks exception cleanup and retry, optional retention, existing output
preservation, malformed staging paths, competing processes, forced termination
and explicit recovery, and streamed PCM bytes against an independent fixture.
The speech archive is hashed in chunks and read one recording at a time; the
Amiga room files remain in memory for dialogue, graphics and font preparation.
Full supported-game output hashes still need the owned-input smoke tests.

## Builder troubleshooting

The builder writes to `<output>.building` and publishes the finished folder only
after verification. Existing output folders are preserved, and errors clean up
the temporary folder automatically. Command-line builds accept
`--keep-failed-build` alongside the four input/output options to retain failed
output for debugging.

Forced termination or power loss can leave the temporary folder behind. The
builder reports its path when you retry. After checking that no build is still
running, move or remove that folder, or choose another output destination.
The builder does not reuse it or remove another build's files.

For the Amiga code, see [native/BUILDING.md](native/BUILDING.md). Its developer Python scripts are separate from the C++ application and are not required by end users.

`assets/sha256.json` pins embedded payload bytes; refresh it intentionally when changing assets. The repository's `.gitattributes` preserves these exact bytes across Windows/Linux checkouts. See [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md) for attribution. There are no original game files, recordings, emulator or ROM fixtures in this source tree.
