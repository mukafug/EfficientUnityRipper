# SPDX-License-Identifier: GPL-3.0-only
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from eur.core import ROOT, Backend, Index, Queue, atomic_json, fingerprint, export_name


class CoreTests(unittest.TestCase):
    def test_export_names_are_readable_safe_and_disambiguated(self):
        name = export_name('CON/<Wall>:*? .', 'first')
        self.assertTrue(name.startswith('CON__Wall____'))
        self.assertFalse(any(c in name for c in '<>:"/\\|?*'))
        self.assertNotEqual(export_name('Wall', 'first'), export_name('Wall', 'second'))
        self.assertLessEqual(len(export_name('x' * 500, 'first')), 94)
        self.assertTrue(export_name('...', 'first').startswith('Asset__'))
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
    def tearDown(self): self.temp.cleanup()

    def test_fingerprint_uses_contents_not_mtime(self):
        source = self.directory / "data"; source.mkdir(); file = source / "file"; file.write_bytes(b"a")
        first, _ = fingerprint([source]); modified = file.stat().st_mtime_ns
        file.write_bytes(b"b"); os.utime(file, ns=(modified, modified))
        self.assertNotEqual(first, fingerprint([source])[0])

    def test_queue_recovers_running_and_preserves_failure(self):
        queue = Queue(self.directory / "queue.json")
        first = queue.add({"operation": "scan"}); second = queue.add({"operation": "export"})
        queue.set(first, "running"); queue.set(second, "failed", "decode failed")
        restored = Queue(queue.path)
        self.assertEqual(restored.jobs[0]["status"], "pending")
        self.assertEqual(restored.jobs[1]["error"], "decode failed")

    def test_manifest_rejects_traversal(self):
        path = self.directory / "index" / "manifest.json"
        atomic_json(path, {"schema_version": 1, "assets": [{"id": "x", "object_file": "../../private.json"}]})
        with self.assertRaises(ValueError): Index(path).object("x")

    def test_source_directory_is_read_only(self):
        backend = Backend()
        with self.assertRaises(ValueError): backend.scan([self.directory], self.directory / "output")
        self.assertFalse((self.directory / "output").exists())

    def test_scan_does_not_overwrite_non_index_directory(self):
        source = self.directory / "input"; source.mkdir(); (source / "file").write_bytes(b"x")
        output = self.directory / "user-data"; output.mkdir(); user_file = output / "manifest.json"; user_file.write_text('{"user":"data"}')
        with self.assertRaises(FileExistsError): Backend().scan([source], output)
        self.assertEqual(user_file.read_text(), '{"user":"data"}')


class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.directory = Path(cls.temp.name)
        cls.source = cls.directory / "fixture"; cls.source.mkdir()
        executable = ROOT / ".local/backend/EfficientUnityRipper.Backend.exe"
        env = dict(os.environ, DOTNET_ROOT=str(ROOT / ".local/dotnet"))
        subprocess.run([str(executable), "fixture", str(cls.source / "level0")], check=True, env=env, capture_output=True)
        cls.events = []; cls.backend = Backend(cls.events.append)
        cls.index = cls.backend.scan([cls.source], cls.directory / "index")
    @classmethod
    def tearDownClass(cls): cls.backend.close(); cls.temp.cleanup()

    def test_actual_unity_engine_decodes_fields_and_hierarchy(self):
        source_rows = [r for r in self.index.rows.values() if r["collection_name"] == "level0"]
        self.assertEqual(len(source_rows), 8)
        self.assertTrue(all(row["status"] == "recovered" for row in source_rows))
        nodes = self.index.derive()
        root = next(n for n in nodes.values() if n["name"] == "Synthetic Root")
        child = next(n for n in nodes.values() if n["name"] == "Test Child")
        self.assertEqual(child["parent"], root["id"])
        self.assertEqual(child["local_transform"]["m_LocalPosition"], {"x": 1, "y": 2, "z": 3})
        self.assertEqual(child["local_transform"]["m_LocalScale"], {"x": 2, "y": 2, "z": 2})
        injected = [r for r in self.index.rows.values() if r["collection_name"] != "level0"]
        self.assertTrue(injected and all(r["status"] != "recovered" for r in injected))

    def test_texture_is_decoded_as_real_png(self):
        id = next(id for id, row in self.index.rows.items() if row["name"] == "Authored Checker")
        result = self.backend.media(self.index, [id], self.directory / "media")
        self.assertEqual(result["failed"], 0)
        from PySide6.QtGui import QImage
        image = QImage(result["results"][0]["path"])
        self.assertFalse(image.isNull()); self.assertEqual((image.width(), image.height()), (2, 2))
        self.assertEqual(image.pixelColor(0, 0).alpha(), 255)
        self.assertTrue(Path(result['results'][0]['path']).name.startswith('Authored Checker__'))

    def test_named_media_export_preserves_existing_file_and_failure_mapping(self):
        id = next(id for id, row in self.index.rows.items() if row['name'] == 'Authored Checker')
        destination = self.directory / 'name-collision'
        result = self.backend.media(self.index, [id], destination)
        existing = Path(result['results'][0]['path'])
        existing.write_bytes(b'user-file')
        with self.assertRaises(FileExistsError):
            self.backend.media(self.index, [id], destination)
        self.assertEqual(existing.read_bytes(), b'user-file')
        checkpoint = json.loads((destination / 'export-results.json').read_text())
        self.assertTrue(Path(checkpoint[0]['path']).is_file())

    def test_cache_integrity_rebuilds_corrupt_objects(self):
        cached = self.backend.scan([self.source], self.index.directory)
        self.assertTrue(any(e.get("cached") for e in self.events))
        id = next(id for id, r in cached.rows.items() if r["name"] == "Test Child")
        cached.object_path(id).write_text("corrupt", encoding="utf-8")
        restored = self.backend.scan([self.source], self.index.directory)
        self.assertTrue(restored.valid_object(id))
        self.assertEqual(restored.object(id)["name"], "Test Child")
        self.assertTrue(any(e.get("message", "").startswith("Checkpoint:") for e in self.events))

    def test_object_scene_exports_and_no_overwrite(self):
        id = next(id for id, r in self.index.rows.items() if r["name"] == "Test Child")
        ids = self.index.scene_ids(self.index.rows[id]["collection"])
        destination = self.directory / "package"
        self.index.export_json(ids, destination)
        exported = Index(destination / "manifest.json")
        self.assertEqual(len(exported.rows), 8)
        self.assertEqual(exported.object(id)["id"], id)
        self.assertTrue(Path(exported.rows[id]['object_file']).name.startswith('Test Child__'))
        self.assertTrue(exported.valid_object(id))
        self.assertNotEqual(exported.rows[id]['object_file'], self.index.rows[id]['object_file'])
        with self.assertRaises(FileExistsError): self.index.export_json(ids, destination)

    def test_invalid_input_error_does_not_kill_protocol(self):
        with self.assertRaises(RuntimeError): self.backend.request({"command": "scan", "paths": [str(self.directory / "missing")], "output": str(self.directory / "bad")})
        self.assertEqual(self.backend.request({"command": "ping"})["engine"], "AssetRipper")


if __name__ == "__main__": unittest.main()
