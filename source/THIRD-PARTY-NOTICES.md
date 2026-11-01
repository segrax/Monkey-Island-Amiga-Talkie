# Third-party notices

The C++ builder incorporates these vendored, unmodified headers:

| Library | Version | Licence |
| --- | --- | --- |
| [JSON for Modern C++](https://github.com/nlohmann/json) | v3.12.0 | [MIT](third_party/JSON-LICENSE.MIT) |
| [PicoSHA2](https://github.com/okdshin/PicoSHA2) | commit `161cb3fc4170fa7a3eca9e582cebd27cc4d1fe29` | [MIT](third_party/PICOSHA2-LICENSE) |
| [Portable File Dialogs](https://github.com/samhocevar/portable-file-dialogs) | commit `c12ea8c9a727f5320a2b4570aee863bbede2a204` | [WTFPL v2](third_party/PFD-COPYING) |

Their source headers retain their copyright notices. The builder does not include Python or .NET. Windows uses the MSVC standard runtime; Linux uses its standard C/C++ runtime libraries.

Amiga MD5 code is adapted from ScummVM's GPL implementation by Christophe Devine. Original notices are preserved in `native/audio/worker/native_md5.c`; [native/SCUMMVM-COPYRIGHT](native/SCUMMVM-COPYRIGHT) preserves the referenced credits. Our source is GPL-3.0-or-later under the root LICENSE.

Amiga development uses the external VBCC/VASM/VLINK toolchain and Amiga NDK. Those tools are not bundled. Their standard runtime/startup support is linked into our native loader and worker; retain the supplied source and existing notices when distributing those binaries.

**Monkey Island Special Edition Ultimate Talkie** is the upstream speech mod used with the user's own archive. No affiliation or endorsement is claimed. Its game resources, original LucasArts/Lucasfilm Games assets and recordings are not included and are not relicensed by this project. Generated game files must not be committed to this repository.
