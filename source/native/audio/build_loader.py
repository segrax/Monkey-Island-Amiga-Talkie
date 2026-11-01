"""Compile local loader against the exact linked module export manifest."""
import json
import hashlib
import os
from pathlib import Path
import subprocess
import argparse

here = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--module-dir', type=Path, default=here.parent / 'build/engine/module')
parser.add_argument('--output-dir', type=Path, default=here)
args = parser.parse_args()
output = args.output_dir.resolve()
output.mkdir(parents=True, exist_ok=True)
module = json.loads((args.module_dir / 'module.json').read_text())
names = {"CONTROL": "_nv_control", "END": "_nv_driver_end", "SHUTDOWN": "_nv_game_shutdown"}
lines = ["/* Generated from module.json; GPL-3.0-or-later. */"]
image = (args.module_dir / 'Monkey_Talkie_Test').read_bytes()
if hashlib.sha256(image).hexdigest() != module["sha256"]:
    raise ValueError("Module image and export manifest disagree")
fingerprint = 2166136261
for byte in image:
    fingerprint = ((fingerprint ^ byte) * 16777619) & 0xffffffff
lines += [f"#define NV_MODULE_BYTES {len(image)}UL", f"#define NV_MODULE_FNV 0x{fingerprint:08x}UL"]
for name, symbol in names.items():
    value = module["exports"][symbol]
    for field in ("hunk", "offset"):
        lines.append(f"#define NV_{name}_{field.upper()} {value[field]}")
(output / "module_exports.h").write_text("\n".join(lines) + "\n")
source = here / 'server_probe.c'
if output != here:
    source = output / 'server_probe.c'
    source.write_text((here / 'server_probe.c').read_text())
env = dict(os.environ, VBCC="D:/Tools/amiga-dev/targets/m68k-amigaos",
           PATH="D:/Tools/amiga-dev/bin;" + os.environ["PATH"])
subprocess.run(["D:/Tools/amiga-dev/bin/vc.exe", "+" + str(here / "kick13.cfg"), "-O2",
                "-DNATIVE_GAME_LOADER", '-I' + str(here / 'worker'),
                '-I' + str(here.parent / 'engine/core'),
                '-I' + str(output), '-I' + str(here), "-o", str(output / "MonkeyTalkie"),
                str(source), str(here / "call_game.s")], env=env, check=True)
