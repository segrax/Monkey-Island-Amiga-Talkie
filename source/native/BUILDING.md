# Rebuilding the native code

End users only need the ready-to-run C++ builder in the repository root. This directory supplies the corresponding source for the native hybrid driver, loader and voice worker, including optional older backends used by the build scripts. No game or emulator fixtures are supplied.

For source development on Windows:

1. Install Python 3.11+ and the VBCC m68k-amigaos compiler, VASM, VLINK and Amiga NDK headers/libraries. The current configuration expects `D:/Tools/amiga-dev`; adjust tool paths in `audio/kick13.cfg`, `audio/build_loader.py`, `audio/worker/build_worker.py` and the engine component scripts if necessary. These tools are external dependencies and are not bundled.
2. Work from this `source/native` directory. Install analysis dependencies using `python -m pip install --target tools/python -r requirements-dev.txt` (development only).
3. Place the hash-matched original Amiga `Monkey_Island` executable at `data/original/Monkey_Island`. It is the executable inside original disk 1, not the ScummVM data files and not a previously patched executable.
4. Run `python engine/build.py --candidate --hybrid-mix --skip-fixture-tests --output build/hybrid`. A new output directory is required. This compiles the core, applies the scaling/stripe changes, creates the module manifest and builds the matched loader. The flag omits an execution test requiring an owned game RAM snapshot that is deliberately not distributed; patch construction and relocation checks still run.
5. `build/hybrid/module/Monkey_Talkie_Test` is the new engine, `module.json` its matching manifest, and `loader-build/MonkeyTalkie` its matching loader. Keep all three together.

The default source headers in `audio/worker` bind the expanded archive/map profile. Build that worker with `python audio/worker/build_worker.py`. To build the standard Ultimate Talkie profile, first copy the three headers from `standard-bindings` over their equivalents in `audio/worker`, then run the same command. This changes data bindings only. The output is `audio/worker/VoiceServer_PreparedOnly` (installed as `VoiceServer`).

`audio/build_pcm.py` is the original developer implementation of VOC-to-prepared-PCM conversion and independent sample verification. The C++ builder in the repository's `source/builder` implements the same conversion, reconstructs the map and applies the engine delta without requiring Python or compiler tools at runtime. `source/assets/patches/map-recipe.json` contains source-stream offsets and numeric mapping metadata, not dialogue text; `source/assets/supported-inputs.json` pins the inputs and generated files. Full and standard prepared data remain separate profiles.

The software is GPL-3.0-or-later; see `../../LICENSE`. MD5 code is adapted from ScummVM's implementation by Christophe Devine, with original notices preserved in `native_md5.c`; see `SCUMMVM-COPYRIGHT`. VBCC/VASM/VLINK/NDK and their standard libraries are external toolchain dependencies governed by their own terms. Generated original-game content is not covered by our software licence and is not supplied here.

AI assistance was used for this unofficial local modification. The hybrid source is compiled for 68000 instructions but that does not establish stock A500 performance. Positive user feedback is separate from the bounded emulator tests; those tests alone are not physical hardware certification.
