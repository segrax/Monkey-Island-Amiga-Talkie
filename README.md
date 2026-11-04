# The Secret of Monkey Island: Amiga Talkie Edition

Add Ultimate Talkie speech to the original Amiga game, preserving its graphics and all four music/SFX parts, with speech on both stereo outputs.

## What you need

- The complete original English Amiga game data in a folder, including `music.dat` and `sample.dat`. If starting from ADFs, extract the game data from **all disks** into that folder first.
- The matching `Monkey_Island` executable. If it is missing from your folder, the builder can extract it from disk 1 ADF.
- `monster.sou` from the English **Monkey Island Special Edition Ultimate Talkie**.

The builder supports uncompressed `monster.sou` files. Compressed `.sog` and `.so3` files are not supported.

## Get the builder

Download the Windows or Linux builder from [GitHub Releases](https://github.com/segrax/Monkey-Island-Amiga-Talkie/releases). The latest `main` builds are also available as artifacts in [GitHub Actions](https://github.com/segrax/Monkey-Island-Amiga-Talkie/actions/workflows/build.yml).

You can also [build it yourself from source](source/BUILDING.md#build-the-desktop-builder).

## Build and play

1. On Windows, run **Build Amiga Talkie.exe**. On Linux, run `./build-amiga-talkie` (run `chmod +x build-amiga-talkie` first if needed).
2. Select your Amiga game folder, executable or disk 1 ADF, and `monster.sou`.
3. Choose an output folder.
4. Copy the finished folder to your Amiga.
5. Open an Amiga Shell, change to that folder and run:

   ```text
   Execute Play
   ```

The generated `Play` script runs `MonkeyTalkie --skip-pirate-check` to skip the pirate-wheel screen. To show the screen, run `MonkeyTalkie` without the option instead.

The finished game includes prepared speech audio, so you do not need to copy `monster.sou` separately. See `VOICE-COVERAGE.txt` in the output folder for speech coverage.

## Amiga requirements

- PAL Amiga with a 68000 CPU or better.
- Kickstart 1.3 or later.
- 1 MB Chip RAM and 512 KB Slow RAM. Fast RAM is not required.
- 200 MB of free hard-drive space.

Tested on a PAL A2000 with a TF536/68030 and Kickstart 3.1; it runs well.

## Development and credits

See [Building from source](source/BUILDING.md) for the C++ builder and native Amiga code.

Speech comes from **Monkey Island Special Edition Ultimate Talkie**.

[GPL-3.0-or-later](LICENSE) | [Third-party credits](source/THIRD-PARTY-NOTICES.md)
