# The Secret of Monkey Island: Amiga Talkie Edition

Add Ultimate Talkie speech to the native Amiga version of Monkey Island, keeping its original graphics and all four music/SFX voices.

## Build your game

1. **Windows:** double-click **Build Amiga Talkie.exe**. **Linux:** run `./build-amiga-talkie` (use `chmod +x build-amiga-talkie` first if needed).
2. Select your English Amiga game data, Ultimate Talkie `monster.sou`, and original Amiga executable or disk 1 ADF.
3. Choose where to create the finished game folder.
4. Copy that folder's contents to your Amiga. Change to it in an Amiga Shell and run **`Execute Play`**.

No Python, .NET, compiler or internet connection is needed. The builder uses local files and preserves your originals and existing output folders. Linux uses standard system C/C++ libraries, with file pickers where available and terminal prompts otherwise.

## Requirements

- Supported original English Amiga data (`000.LFL`, `901.LFL`–`904.LFL`, four `disk*.lec` files, `music.dat`, `sample.dat`). A folder containing `Rooms` also works.
- Matching original `Monkey_Island` executable or original uncompressed DOS0 disk 1 ADF.
- Supported uncompressed English Ultimate Talkie `monster.sou`. Compressed `.sog`/`.so3` and other versions/languages are not supported. [Supported input hashes](source/assets/supported-inputs.json).
- A PAL Amiga with storage and Fast RAM (8 MB recommended). An accelerator is not an enforced requirement, but smooth performance on an unaccelerated A500 with the current hybrid mixer has not been established.

The native code targets the 68000 and uses Kickstart 1.3-compatible startup. Kickstart 1.3 is a compatibility target, rather than a verified minimum for the current hybrid release; that release still needs a fresh 1.3 test. Booting from a hard drive under 1.3 also depends on suitable controller/boot support, or a boot floppy.

The standard SOU lacks the 16 supplemental recordings used by the expanded development archive. Both archives are supported; the output reports the 16 omitted mappings when using the standard archive. Existing speech coverage limitations still apply.

The Amiga output uses prepared audio; it does not need `monster.sou` copied across. Keep its files together. The supplied `Play` script includes the temporary pirate-screen bypass used during development.

## Source and credits

Everything needed for development is in [source](source/BUILDING.md), including CMake build instructions, native Amiga code, tests and third-party notices. The Windows/Linux builders produce matching game files from the same inputs.

Speech comes from **Monkey Island Special Edition Ultimate Talkie** and the user's own archive. No original game files, dialogue transcript, recordings, emulator or Kickstart ROM are bundled. Generated game folders must not be committed to this repository.

Our software is GPL-3.0-or-later: [licence](LICENSE), [third-party credits](source/THIRD-PARTY-NOTICES.md). This is an unofficial, AI-assisted modification, not an official LucasArts, Lucasfilm Games, Disney or ScummVM release.
