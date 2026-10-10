# SPDX-License-Identifier: GPL-3.0-only
"""Independent Assimp reader for meshes; Qt decoder for PNGs. No game data copied."""
import argparse
import json
import math
from pathlib import Path
import assimp_py
from PySide6.QtGui import QImage

parser = argparse.ArgumentParser(); parser.add_argument("directory"); parser.add_argument("--report", required=True)
args = parser.parse_args(); result = []
for file in sorted(Path(args.directory).rglob("*")):
    if file.suffix.lower() in (".glb", ".fbx"):
        scene = assimp_py.import_file(str(file), assimp_py.Process_Triangulate)
        vertices = sum(mesh.num_vertices for mesh in scene.meshes)
        triangles = sum(mesh.num_faces for mesh in scene.meshes)
        assert vertices > 0 and triangles > 0, file
        assert all(math.isfinite(float(v)) for mesh in scene.meshes for v in mesh.vertices), file
        result.append({"file": file.name, "format": file.suffix[1:], "reader": "Assimp via assimp_py 1.2.0", "meshes": len(scene.meshes), "vertices": vertices, "triangles": triangles, "bytes": file.stat().st_size})
    elif file.suffix.lower() == ".png":
        image = QImage(str(file)); assert not image.isNull() and image.width() > 0 and image.height() > 0, file
        first = image.pixel(0, 0)
        varied = any(image.pixel(x, y) != first for x in range(0, image.width(), max(1, image.width() // 32)) for y in range(0, image.height(), max(1, image.height() // 32)))
        result.append({"file": file.name, "format": "png", "reader": "Qt QImage", "width": image.width(), "height": image.height(), "bytes": file.stat().st_size, "sampled_pixels_vary": varied})
assert result, "No media to validate"
Path(args.report).write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps({"validated": len(result), "report": args.report}))
