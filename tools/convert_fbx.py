# SPDX-License-Identifier: GPL-3.0-only
import sys
import bpy
from pathlib import Path
import re

source, destination = sys.argv[sys.argv.index("--") + 1:]
if Path(destination).exists():
    raise FileExistsError(destination)
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=source)
if not any(obj.type == "MESH" and len(obj.data.vertices) and len(obj.data.polygons) for obj in bpy.context.scene.objects):
    raise ValueError("No nonempty mesh in GLB")
# FBX cannot encode Blender's glTF texture/vertex-color multiply graph. Keep the
# image directly on Base Color; vertex colors remain in mesh data for the consumer.
def image_for_socket(socket, visited):
    for link in socket.links:
        node = link.from_node
        if node.as_pointer() in visited:
            continue
        visited.add(node.as_pointer())
        if node.type == 'TEX_IMAGE' and node.image:
            return node
        for input in node.inputs:
            found = image_for_socket(input, visited)
            if found:
                return found
    return None

for material in bpy.data.materials:
    if not material.use_nodes:
        continue
    for node in material.node_tree.nodes:
        if node.type == 'BSDF_PRINCIPLED':
            image_node = image_for_socket(node.inputs['Base Color'], set())
            if image_node:
                material.node_tree.links.new(image_node.outputs['Color'], node.inputs['Base Color'])
# GLB images have no extension by default; Unity cannot import extensionless FBX media.
textures = Path(destination).with_suffix('')
textures = textures.with_name(textures.name + '_textures')
for number, image in enumerate(list(bpy.data.images)):
    if not image.packed_file:
        continue
    textures.mkdir(exist_ok=True)
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', image.name)[:80].strip(' .') or 'Image'
    path = textures / (stem + '_' + str(number) + '.png')
    if path.exists():
        raise FileExistsError(path)
    packed = bytes(image.packed_file.data)
    if packed.startswith(b'\x89PNG\r\n\x1a\n'):
        with path.open('xb') as file:
            file.write(packed)
    else:
        image.filepath_raw = str(path)
        image.file_format = 'PNG'
        image.save()
    image.filepath = str(path)
    image.name = path.name
bpy.ops.export_scene.fbx(filepath=destination, use_selection=False, add_leaf_bones=False, bake_anim=False, path_mode="COPY", embed_textures=True)
