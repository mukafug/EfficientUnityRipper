# SPDX-License-Identifier: GPL-3.0-only
import sys
import bpy
from pathlib import Path

source, destination = sys.argv[sys.argv.index("--") + 1:]
if Path(destination).exists():
    raise FileExistsError(destination)
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=source)
if not any(obj.type == "MESH" and len(obj.data.vertices) and len(obj.data.polygons) for obj in bpy.context.scene.objects):
    raise ValueError("No nonempty mesh in GLB")
bpy.ops.export_scene.fbx(filepath=destination, use_selection=False, add_leaf_bones=False, bake_anim=False)
