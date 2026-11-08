# The Secret of Monkey Island: Amiga Talkie Edition

A full-speech version of The Secret of Monkey Island for the Amiga, combining the original Amiga game with voices from Monkey Island Special Edition Ultimate Talkie. Native audio and rendering optimisations are designed to make the speech-enabled game run on a 68000 Amiga without requiring a CPU accelerator.

## What you need

- The complete original English Amiga game data in a folder, including `music.dat` and `sample.dat`. If starting from ADFs, extract the game data from **all disks** into that folder first.
- The matching `Monkey_Island` executable. If it is missing from your folder, the builder can extract it from disk 1 ADF.
- `monster.sou` from the English **Monkey Island Special Edition Ultimate Talkie**.

The builder supports uncompressed `monster.sou` files. Compressed `.sog` and `.so3` files are not supported.
The builder checks SHA-256 hashes against the [supported input files](source/assets/supported-inputs.json). Modified or cracked executables are not accepted unless they match the supported executable exactly. ADF images themselves do not need to match a particular hash; the executable extracted from disk 1 does.

## Get the builder

Download the Windows or Linux builder from [GitHub Releases](https://github.com/segrax/Monkey-Island-Amiga-Talkie/releases). The latest `main` builds are also available as artifacts in [GitHub Actions](https://github.com/segrax/Monkey-Island-Amiga-Talkie/actions/workflows/build.yml).

You can also [build it yourself from source](source/BUILDING.md#build-the-desktop-builder).

## Build and play

1. On Windows, run **Build Amiga Talkie.exe**. On Linux, run `./build-amiga-talkie` (run `chmod +x build-amiga-talkie` first if needed).
2. Select your Amiga game folder, executable or disk 1 ADF, and `monster.sou`.
3. Choose an output folder.
4. Copy the finished folder to your Amiga.
   The folder includes the original Monkey Island Workbench icon for `MonkeyTalkie`.
5. Double-click `MonkeyTalkie` to play. The pirate-wheel screen appears briefly,
   automatically types the correct year, then continues into the game.
   The launcher opens a Shell window and keeps its messages visible until you
   press Return after the game exits. Alternatively, open an Amiga Shell,
   change to that folder and run:

   ```text
   Execute Play
   ```

For a manual Shell launch, run `Stack 65536` first, then `MonkeyTalkie`.
`Execute Play` also sets the stack. To skip the pirate-wheel screen entirely,
run `MonkeyTalkie --skip-pirate-check`.

If startup reports `Worker exited before initialization`, the next line gives
the worker's failure reason. Copy `MonkeyTalkie` and `VoiceServer` from the same
newly built output folder to get these diagnostics.

The finished game includes prepared speech audio, so you do not need to copy `monster.sou` separately. See `VOICE-COVERAGE.txt` in the output folder for speech coverage.

Existing output folders are preserved. If the default folder already exists, the
interactive builder offers a numbered folder such as `Monkey_Island_Amiga_Talkie-2`.
Failed builds clean up their temporary files. See [builder troubleshooting](source/BUILDING.md#builder-troubleshooting)
if a build is interrupted or you need to retain files for debugging.

## Native optimisations

These optimisations target the original 68000 CPU, reducing audio and drawing
work so the speech-enabled game can run without a CPU accelerator:

- **Direct Paula music playback.** Between speech lines, all four music and
  sound-effect parts play through the original hardware channels. During speech,
  two channels mix music with centred voice while the other two remain native.
  Direct playback resumes after the speech tail finishes.
- **Prepared speech.** The desktop builder converts and verifies the speech
  before you copy the game to the Amiga, avoiding VOC decoding during play.
- **Cached graphics and text.** Prepared planar graphics, costume caches and
  font drawing programs reduce repeated rendering work. The original drawing
  paths remain available when a cache cannot be used.
- **Less desktop memory use.** The Windows/Linux builder hashes the speech
  archive in chunks and processes one recording at a time.

In a matched quiet Scumm Bar test, the native-music changes reduced crossing time
from about **4.2 to 3.1 seconds** on a cycle-exact PAL 68000 with 1 MB Chip RAM,
1 MB Slow RAM and no Fast RAM. This measures one scene against the earlier
hybrid driver; speed parity with the unmodified game is still unproven.
Original script/frame caps and speech samples/rate are unchanged.
See [validation results](source/VALIDATION.md) for the test conditions and limits.

## Amiga requirements

- PAL Amiga with a 68000 CPU or better.
- Kickstart 1.3 or later.
- 1 MB Chip RAM and 512 KB Slow RAM. Fast RAM is not required.
- 200 MB of free hard-drive space.

Tested on a PAL A2000 with a TF536/68030 and Kickstart 3.1; it runs well.

NTSC intro and opening speech also tested in FS-UAE with a 68030 at 14.3 MHz, Kickstart 3.1, 1 MB Chip RAM and 1 MB Slow RAM, without Fast RAM.

## Development

See [Building from source](source/BUILDING.md) for the C++ builder and native Amiga code.
