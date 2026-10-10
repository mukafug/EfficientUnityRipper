# SPDX-License-Identifier: GPL-3.0-only
"""Optional real Unity-editor-authored binary fixture; set EUR_BUNDLE_FIXTURE."""
import os
from pathlib import Path
import tempfile
import unittest
import json
import struct
import subprocess
from eur.core import Backend
from eur.preview import read_glb
from PySide6.QtGui import QImage


@unittest.skipUnless(os.environ.get("EUR_BUNDLE_FIXTURE"), "Build authorized synthetic Unity bundles; set EUR_BUNDLE_FIXTURE")
class UnityBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(); cls.directory = Path(cls.temp.name)
        cls.backend = Backend()
        cls.index = cls.backend.scan([os.environ["EUR_BUNDLE_FIXTURE"]], cls.directory / "index")
        cls.objects = [cls.index.object(id) for id, row in cls.index.rows.items() if row["status"] == "recovered"]
    @classmethod
    def tearDownClass(cls): cls.backend.close(); cls.temp.cleanup()

    def test_monobehaviour_config_ui_physics_and_scene(self):
        mechanics = next(o for o in self.objects if (o["properties"].get("m_Structure") or {}).get("moveSpeed") == 4.25)
        structure = mechanics["properties"]["m_Structure"]
        self.assertEqual(structure["lives"], 7)
        self.assertEqual(structure["checkpoint"], {"x": 3, "y": 4, "z": 5})
        self.assertTrue(any(d["field"].endswith("config") and d["target"] for d in mechanics["dependencies"]))
        config = next(o for o in self.objects if o["name"] == "config")
        self.assertEqual(config["properties"]["m_Structure"]["jumpHeight"], 2.75)
        body = next(o for o in self.objects if o["type"] == "Rigidbody")
        self.assertEqual(body["properties"]["m_Mass"], 3.5)
        self.assertTrue(any(o["type"] == "RectTransform" for o in self.objects))
        self.assertTrue(any(o["type"] == "TerrainData" for o in self.objects))
        self.assertTrue(any(o["type"] == "NavMeshSettings" for o in self.objects))
        self.assertTrue(any(c["kind"] == "scene" for c in self.index.manifest["collections"]))

    def test_rig_animation_and_media(self):
        self.assertTrue(any(o["type"] == "SkinnedMeshRenderer" for o in self.objects))
        self.assertTrue(any(o["type"] == "AnimationClip" for o in self.objects))
        self.assertTrue(any(o["type"] == "AnimatorController" for o in self.objects))
        mesh = next(o for o in self.objects if o["name"] == "triangle" and o["class_id"] == 43)
        texture = next(o for o in self.objects if o["name"] == "checker" and o["class_id"] == 28)
        result = self.backend.media(self.index, [mesh["id"], texture["id"]], self.directory / "media")
        self.assertEqual(result["failed"], 0)
        glb = next(r["path"] for r in result["results"] if r["path"].endswith(".glb"))
        vertices, triangles = read_glb(glb)
        self.assertEqual(len(vertices), 3); self.assertEqual(len(triangles), 1)
        image = QImage(next(r["path"] for r in result["results"] if r["path"].endswith(".png")))
        self.assertEqual((image.width(), image.height()), (4, 4))

    def test_scene_glb_preserves_static_hierarchy_and_embeds_texture(self):
        collection = next(c for c in self.index.manifest['collections'] if c['kind'] == 'scene' and c['origin'] == 'serialized_input')
        result = self.backend.media(self.index, [], self.directory / 'scene-media', collection=collection['id'])
        self.assertEqual(result['failed'], 0)
        data = Path(result['results'][0]['path']).read_bytes()
        size, kind = struct.unpack_from('<II', data, 12)
        self.assertEqual(kind, 0x4e4f534a)
        gltf = json.loads(data[20:20 + size])
        self.assertTrue(gltf.get('meshes'))
        self.assertTrue(gltf.get('images'))
        self.assertTrue(all('bufferView' in image for image in gltf['images']))
        self.assertTrue(any('baseColorTexture' in material.get('pbrMetallicRoughness', {}) for material in gltf['materials']))
        self.assertTrue(any(node.get('children') for node in gltf['nodes']))
        self.assertTrue(any(node.get('translation') or node.get('matrix') for node in gltf['nodes']))

    def test_scene_export_rejects_asset_only_collection(self):
        collection = next(c for c in self.index.manifest['collections'] if c['kind'] == 'asset_collection' and c['origin'] == 'serialized_input')
        with self.assertRaises(RuntimeError):
            self.backend.media(self.index, [], self.directory / 'not-a-scene', collection=collection['id'])

    @unittest.skipUnless(os.environ.get('EUR_BLENDER_EXE'), 'Set EUR_BLENDER_EXE for actual textured FBX regression')
    def test_vertex_colored_textured_fbx_preserves_png_binding(self):
        from eur.fbx import convert
        collection = next(c for c in self.index.manifest['collections'] if c['kind'] == 'scene' and c['origin'] == 'serialized_input')
        result = self.backend.media(self.index, [], self.directory / 'fbx-regression', collection=collection['id'])
        raw = Path(result['results'][0]['path']).read_bytes()
        size = struct.unpack_from('<I', raw, 12)[0]
        gltf = json.loads(raw[20:20 + size])
        binary_size = struct.unpack_from('<I', raw, 20 + size)[0]
        binary = bytearray(raw[28 + size:28 + size + binary_size])
        # Reproduce the real-game case: textured materials on vertex-colored geometry.
        for mesh in gltf['meshes']:
            for primitive in mesh['primitives']:
                count = gltf['accessors'][primitive['attributes']['POSITION']]['count']
                colors = struct.pack('<4f', .25, .5, .75, 1) * count
                gltf['bufferViews'].append(dict(buffer=0, byteOffset=len(binary), byteLength=len(colors), target=34962))
                gltf['accessors'].append(dict(bufferView=len(gltf['bufferViews']) - 1, componentType=5126, count=count, type='VEC4'))
                primitive['attributes']['COLOR_0'] = len(gltf['accessors']) - 1
                binary.extend(colors)
        gltf['buffers'][0]['byteLength'] = len(binary)
        document = json.dumps(gltf).encode()
        document += b' ' * (-len(document) % 4)
        binary.extend(b'\0' * (-len(binary) % 4))
        colored = self.directory / 'colored.glb'
        colored.write_bytes(struct.pack('<III', 0x46546c67, 2, 28 + len(document) + len(binary)) + struct.pack('<II', len(document), 0x4e4f534a) + document + struct.pack('<II', len(binary), 0x004e4942) + binary)
        target = convert(colored, os.environ['EUR_BLENDER_EXE'])
        reader = self.directory / 'read_textured_fbx.py'
        reader.write_text('''import bpy,sys
from pathlib import Path
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.fbx(filepath=sys.argv[sys.argv.index("--")+1])
meshes=[o for o in bpy.context.scene.objects if o.type=="MESH"]
assert meshes and all(len(o.data.color_attributes)>0 for o in meshes)
for material in {s.material for o in meshes for s in o.material_slots if s.material}:
    nodes=[n for n in material.node_tree.nodes if n.type=="TEX_IMAGE" and n.image]
    assert nodes and all(n.image.size[0]>0 and Path(n.image.filepath).suffix.lower()==".png" for n in nodes), material.name
''')
        completed = subprocess.run([os.environ['EUR_BLENDER_EXE'], '--background', '--factory-startup', '--python-exit-code', '1', '--python', str(reader), '--', str(target)], capture_output=True, text=True, timeout=180, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)


if __name__ == "__main__": unittest.main()
