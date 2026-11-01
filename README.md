# The Secret of Monkey Island: Amiga Talkie Edition

Add Ultimate Talkie speech to the original Amiga game, preserving its graphics and all four music/SFX parts, with speech on both stereo outputs.

## What you need

- The original English Amiga game files, including `music.dat` and `sample.dat`.
- The matching `Monkey_Island` executable or disk 1 ADF.
- `monster.sou` from the English **Monkey Island Special Edition Ultimate Talkie**.

The builder supports uncompressed `monster.sou` files. Compressed `.sog` and `.so3` files are not supported.

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

## Amiga compatibility

- PAL Amiga with Kickstart 1.3 or later and storage for the game.
- A 68020 or faster is recommended. A 68000 at A500 speed cannot keep up with real-time playback.
- Fast RAM is not required.

Tested on a PAL A2000 with a TF536/68030, where it runs well. Also tested in an emulator with a 68020 and 1 MB Chip RAM, 1 MB Slow RAM and no Fast RAM. At A500 speed, some scenes slow down; A1200 speed or faster is recommended.

## Development and credits

See [Building from source](source/BUILDING.md) for the C++ builder and native Amiga code.

Speech comes from **Monkey Island Special Edition Ultimate Talkie**.

[GPL-3.0-or-later](LICENSE) | [Third-party credits](source/THIRD-PARTY-NOTICES.md)
