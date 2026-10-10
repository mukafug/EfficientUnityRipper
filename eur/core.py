# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time
import uuid
import queue
import re

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get("LOCALAPPDATA", str(ROOT / ".local"))) / "EfficientUnityRipper"
UPSTREAM = "beeb50ee1c223e856c860caa338e5309404956a3"
BACKEND_REVISION = 2


def export_name(name, id):
    """Readable Windows filename; stable suffix distinguishes duplicate asset names."""
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', str(name or 'Asset'))[:80].strip(' .') or 'Asset'
    return stem + '__' + hashlib.sha256(id.encode('utf-8')).hexdigest()[:12]


def atomic_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    temp.replace(path)


def outside_inputs(paths, destination):
    destination = Path(destination).resolve()
    for source in paths:
        source = Path(source).resolve()
        boundary = source if source.is_dir() else source.parent
        if destination == boundary or boundary in destination.parents:
            raise ValueError("Output must be outside input installation; inputs are read-only")


def prepare_index(destination):
    marker = destination / ".eur-index.json"
    expected = {"application": "EfficientUnityRipper", "kind": "index"}
    if destination.exists() and any(destination.iterdir()):
        if marker.exists():
            if json.loads(marker.read_text(encoding="utf-8")) != expected:
                raise ValueError("Index ownership marker mismatch")
        else:
            manifest = destination / "manifest.json"
            if not manifest.exists() or json.loads(manifest.read_text(encoding="utf-8")).get("engine_commit") != UPSTREAM:
                raise FileExistsError("Nonempty output is not an EfficientUnityRipper index")
    destination.mkdir(parents=True, exist_ok=True)
    atomic_json(marker, expected)


def fingerprint(paths, event=lambda _: None):
    """Content hash, including resource/assembly sidecars. Never follows directory links."""
    entries = []
    for input_path in sorted({str(Path(p).resolve()) for p in paths}):
        path = Path(input_path)
        if not path.exists():
            raise FileNotFoundError(path)
        files = [path] if path.is_file() else sorted(p for p in path.rglob("*") if p.is_file())
        for i, file in enumerate(files):
            if file.is_symlink():
                raise ValueError(f"Symlink input unsupported: {file}")
            event({"kind": "phase", "message": f"Fingerprint {i + 1}/{len(files)}: {file.name}"})
            digest = hashlib.sha256()
            with file.open("rb") as stream:
                while chunk := stream.read(1024 * 1024):
                    digest.update(chunk)
            entries.append({"input": input_path, "relative_path": str(file.relative_to(path.parent if path.is_file() else path)), "sha256": digest.hexdigest(), "bytes": file.stat().st_size})
    # Source relocation does not change content token, but input order/namespace does.
    token = hashlib.sha256(json.dumps([(e["relative_path"], e["sha256"]) for e in entries], separators=(",", ":")).encode()).hexdigest()
    return token, entries


class Backend:
    def __init__(self, event=lambda _: None):
        self.event = event
        self.process = None
        self.loaded = None
        self.log_path = DATA / "logs" / (time.strftime("session_%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8] + ".ndjson")
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_lock = threading.Lock()

    def emit(self, message):
        with self.log_lock, self.log_path.open("a", encoding="utf-8") as log:
            log.write(json.dumps(message, ensure_ascii=False) + "\n")
        self.event(message)

    def start(self):
        if self.process and self.process.poll() is None:
            return
        executable = ROOT / ".local" / "backend" / "EfficientUnityRipper.Backend.exe"
        if not executable.exists():
            raise FileNotFoundError("Backend missing. Run setup.ps1 first.")
        environment = dict(os.environ)
        runtime = ROOT / ".local" / "dotnet"
        if runtime.exists():
            environment["DOTNET_ROOT"] = str(runtime)
        self.process = subprocess.Popen([str(executable)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), env=environment)
        process = self.process
        self.messages = queue.Queue()
        messages = self.messages
        def read():
            for line in process.stdout: messages.put(line)
            messages.put(None)
        threading.Thread(target=read, daemon=True).start()
        def drain():
            for line in process.stderr:
                self.emit({"kind": "log", "level": "stderr", "message": line.rstrip()})
        threading.Thread(target=drain, daemon=True).start()

    def request(self, command):
        self.start()
        self.process.stdin.write(json.dumps(command) + "\n")
        self.process.stdin.flush()
        last_output = time.monotonic()
        while True:
            try: line = self.messages.get(timeout=1)
            except queue.Empty:
                if time.monotonic() - last_output > 300:
                    self.close()
                    raise TimeoutError("Backend produced no output for 300 seconds; checkpoint retained")
                continue
            if line is None: break
            last_output = time.monotonic()
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                raise RuntimeError("Backend protocol violation: " + line[:200])
            self.emit(message)
            if message["kind"] == "error":
                raise RuntimeError(message["message"])
            if message["kind"] in ("complete", "ready"):
                return message
        raise RuntimeError(f"Backend exited unexpectedly ({self.process.poll()})")

    def close(self):
        if self.process and self.process.poll() is None:
            self.process.kill()
            self.process.wait(timeout=10)
        self.loaded = None

    def scan(self, paths, destination: Path, force=False, token=None, sources=None):
        paths = [str(Path(p).resolve()) for p in paths]
        destination = destination.resolve()
        outside_inputs(paths, destination)
        prepare_index(destination)
        if token is None:
            token, sources = fingerprint(paths, self.event)
        manifest_path = destination / "manifest.json"
        cache_allowed = all(Path(p).is_dir() for p in paths)
        if manifest_path.exists() and not force and cache_allowed:
            previous = json.loads(manifest_path.read_text(encoding="utf-8"))
            if previous.get("input_fingerprint") == token and previous.get("engine_commit") == UPSTREAM and previous.get("backend_revision") == BACKEND_REVISION and previous.get("schema_version") == 1:
                index = Index(manifest_path)
                if all(index.valid_object(row["id"]) for row in index.rows.values()):
                    self.event({"kind": "complete", "operation": "scan", "manifest": str(manifest_path), "count": len(index.rows), "cached": True})
                    return index
        self.request({"command": "scan", "paths": paths, "output": str(destination), "fingerprint": token if cache_allowed else None})
        index = Index(manifest_path)
        index.manifest["input_fingerprint"] = token
        index.manifest["source_files"] = sources
        for row in index.rows.values():
            row["sha256"] = hashlib.sha256(index.object_path(row["id"]).read_bytes()).hexdigest()
        atomic_json(manifest_path, index.manifest)
        index.derive()
        self.loaded = (tuple(paths), token)
        return index

    def media(self, index, ids, destination, collection=None):
        paths = index.manifest["sources"]
        outside_inputs(paths, destination)
        token, sources = fingerprint(paths, self.event)
        if token != index.manifest.get("input_fingerprint"):
            raise ValueError("Source changed since scan; rescan before media export")
        if self.loaded != (tuple(paths), token):
            self.scan(paths, index.directory, force=True, token=token, sources=sources)
        if collection is not None:
            result = self.request({"command": "export-scene", "collection": collection, "output": str(destination)})
        else:
            result = self.request({"command": "export", "ids": ids, "output": str(destination), "format": "media"})
        try:
            for item in result["results"]:
                if item.get("path"):
                    source = Path(item["path"])
                    target = source.with_name(export_name(item.get("name"), item["id"]) + source.suffix)
                    if target.exists():
                        raise FileExistsError(target)
                    source.rename(target)
                    item["path"] = str(target)
        finally:
            atomic_json(Path(destination) / "export-results.json", result["results"])
        return result


class Index:
    def __init__(self, manifest_path):
        self.path = Path(manifest_path).resolve()
        self.directory = self.path.parent
        self.manifest = json.loads(self.path.read_text(encoding="utf-8"))
        if self.manifest.get("schema_version") != 1:
            raise ValueError("Unsupported manifest schema")
        self.rows = {row["id"]: row for row in self.manifest["assets"]}
        if len(self.rows) != len(self.manifest["assets"]):
            raise ValueError("Duplicate object IDs")

    def object_path(self, id):
        relative = Path(self.rows[id]["object_file"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Invalid relative object path")
        path = (self.directory / relative).resolve()
        if self.directory not in path.parents:
            raise ValueError("Object path escapes index")
        return path

    def object(self, id):
        raw = self.object_path(id).read_bytes()
        checksum = self.rows[id].get("sha256")
        if checksum and hashlib.sha256(raw).hexdigest() != checksum:
            raise ValueError("Object checksum mismatch; rescan source")
        data = json.loads(raw)
        if data.get("id") != id:
            raise ValueError("Object ID mismatch")
        return data

    def valid_object(self, id):
        path = self.object_path(id)
        try:
            return hashlib.sha256(path.read_bytes()).hexdigest() == self.rows[id].get("sha256") and self.object(id)["id"] == id
        except (OSError, ValueError):
            return False

    def closure(self, ids):
        seen, pending = set(), list(ids)
        while pending:
            id = pending.pop()
            if id in seen:
                continue
            if id not in self.rows:
                raise KeyError(id)
            seen.add(id)
            pending.extend(d["target"] for d in self.object(id)["dependencies"] if d.get("target") in self.rows and d["target"] not in seen)
        return sorted(seen)

    def scene_ids(self, collection):
        return self.closure([id for id, row in self.rows.items() if row["collection"] == collection])

    def derive(self, write=True):
        nodes, transforms, edges = {}, {}, []
        for id, row in self.rows.items():
            data = self.object(id)
            dependencies = data["dependencies"]
            edges.extend({"source": id, **dependency} for dependency in dependencies)
            if row["class_id"] == 1:
                nodes[id] = {"id": id, "name": row["name"], "collection": row["collection"], "parent": None, "children": [], "components": [d["target"] for d in dependencies if d.get("target")], "status": "derived", "provenance": {"object": id, "rule": "Transform.m_Father -> Transform.m_GameObject"}}
            if row["class_id"] in (4, 224):
                owner = next((d.get("target") for d in dependencies if "gameobject" in d["field"].lower()), None)
                father = next((d for d in dependencies if "father" in d["field"].lower()), None)
                transforms[id] = (owner, father, data.get("properties") or {})
        for transform, (owner, father, props) in transforms.items():
            if owner not in nodes:
                continue
            node = nodes[owner]
            node["transform"] = transform
            node["local_transform"] = {name: props.get(name) for name in ("m_LocalPosition", "m_LocalRotation", "m_LocalScale", "m_AnchorMin", "m_AnchorMax", "m_AnchoredPosition", "m_SizeDelta", "m_Pivot") if name in props}
            if father:
                parent = transforms.get(father.get("target"), (None,))[0]
                node["parent"] = parent
                node["parent_status"] = "derived" if parent in nodes else "unavailable"
                if parent in nodes:
                    nodes[parent]["children"].append(owner)
            else:
                node["parent_status"] = "recovered_null"
        if write:
            atomic_json(self.directory / "hierarchy.json", {"schema_version": 1, "status": "derived", "nodes": list(nodes.values()), "limitations": ["Collection membership alone does not prove a scene. Prefabs may also have GameObjects. Local transforms preserved; no world-transform inference."]})
            atomic_json(self.directory / "dependencies.json", {"schema_version": 1, "status": "recovered", "edges": edges})
            (self.directory / "agent-context.md").write_text(f"# Unity reconstruction context\n\nStart with `{self.path}`. Use `hierarchy.json` and `dependencies.json`, then only the needed `objects/*.json`.\n\nObject IDs and PathID strings are authoritative; serialized JSON integers require an arbitrary-precision reader. Preserve recovered local transforms and serialized settings. Inspect provenance, warnings, status, and engine-injected collections. Derived media and injected placeholders are not original source evidence. Do not infer script logic, executable shaders, missing dependencies, or automatic 1:1 fidelity. No gameplay inference is supplied.\n\nExport a selected object or scene dependency closure through `eur.cli export` when a smaller package is needed. REA remains a separate application.\n", encoding="utf-8")
        return nodes

    def export_json(self, ids, destination):
        destination = Path(destination).resolve()
        # Never export into source installation or existing user directory contents.
        outside_inputs(self.manifest.get("sources", []), destination)
        destination.mkdir(parents=True, exist_ok=False)
        (destination / "objects").mkdir()
        ids = sorted(set(ids))
        rows = []
        for id in ids:
            row = dict(self.rows[id])
            row["object_file"] = 'objects/' + export_name(row.get("name"), id) + '.json'
            shutil.copyfile(self.object_path(id), destination / row["object_file"])
            raw_file = self.object(id).get("raw_file")
            if raw_file:
                source = (self.directory / raw_file).resolve()
                if self.directory not in source.parents: raise ValueError("Raw path escapes index")
                shutil.copyfile(source, destination / raw_file)
            rows.append(row)
        manifest = dict(self.manifest, assets=rows, export={"status": "derived", "selected_ids": ids, "missing_dependencies": [d for id in ids for d in self.object(id)["dependencies"] if d.get("target") not in ids]})
        atomic_json(destination / "manifest.json", manifest)
        Index(destination / "manifest.json").derive()
        return destination


class Queue:
    def __init__(self, path):
        self.path = Path(path)
        self.jobs = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else []
        for job in self.jobs:
            if job["status"] == "running":
                job["status"] = "pending"
        self.save()

    def save(self):
        atomic_json(self.path, self.jobs)

    def add(self, command):
        job = {"id": uuid.uuid4().hex, "status": "pending", "command": command, "error": None}
        self.jobs.append(job)
        self.save()
        return job

    def set(self, job, status, error=None):
        job["status"], job["error"] = status, error
        self.save()


def fresh_export(parent):
    return Path(parent) / (time.strftime("export_%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8])
