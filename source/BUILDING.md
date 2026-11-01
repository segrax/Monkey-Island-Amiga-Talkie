# Development

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

Install CMake 3.20+ and a C++17 compiler. From the repository root:

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

For the Amiga code, see [native/BUILDING.md](native/BUILDING.md). Its developer Python scripts are separate from the C++ application and are not required by end users.

`assets/sha256.json` pins embedded payload bytes; refresh it intentionally when changing assets. The repository's `.gitattributes` preserves these exact bytes across Windows/Linux checkouts. See [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md) for attribution. There are no original game files, recordings, emulator or ROM fixtures in this source tree.
