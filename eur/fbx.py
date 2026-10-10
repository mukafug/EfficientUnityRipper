# SPDX-License-Identifier: GPL-3.0-only
"""Optional external conversion. Core extraction does not depend on Blender."""
from pathlib import Path
import subprocess
from .core import ROOT


def convert(glb, blender):
    glb = Path(glb).resolve()
    target = glb.with_suffix(".fbx")
    if target.exists():
        raise FileExistsError(target)
    result = subprocess.run([str(blender), "--background", "--factory-startup", "--python", str(ROOT / "tools" / "convert_fbx.py"), "--", str(glb), str(target)], capture_output=True, text=True, timeout=180, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode or not target.exists():
        raise RuntimeError((result.stderr + result.stdout)[-2000:])
    if not target.read_bytes().startswith(b"Kaydara FBX Binary  \x00\x1a\x00"):
        raise ValueError("Converter did not create binary FBX")
    return target
