# SPDX-License-Identifier: GPL-3.0-only
"""Optional real Unity-editor-authored binary fixture; set EUR_BUNDLE_FIXTURE."""
import os
from pathlib import Path
import tempfile
import unittest
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


if __name__ == "__main__": unittest.main()
