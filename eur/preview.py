# SPDX-License-Identifier: GPL-3.0-only
import json
import math
import struct
from pathlib import Path
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPainter, QColor
from PySide6.QtWidgets import QWidget


def read_glb(path):
    data = Path(path).read_bytes()
    magic, version, length = struct.unpack_from("<III", data)
    if magic != 0x46546C67 or version != 2 or length != len(data):
        raise ValueError("Invalid GLB header")
    offset, document, binary = 12, None, None
    while offset < len(data):
        size, kind = struct.unpack_from("<II", data, offset)
        chunk = data[offset + 8:offset + 8 + size]
        if len(chunk) != size:
            raise ValueError("Truncated GLB chunk")
        if kind == 0x4E4F534A:
            document = json.loads(chunk)
        elif kind == 0x004E4942:
            binary = chunk
        offset += 8 + size
    if document is None or binary is None:
        raise ValueError("Missing GLB chunks")
    def accessor(number):
        entry = document["accessors"][number]
        view = document["bufferViews"][entry["bufferView"]]
        width = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[entry["type"]]
        format = {5121: "B", 5123: "H", 5125: "I", 5126: "f"}[entry["componentType"]]
        item = struct.Struct("<" + format * width)
        stride = view.get("byteStride", item.size)
        start = view.get("byteOffset", 0) + entry.get("byteOffset", 0)
        return [item.unpack_from(binary, start + i * stride) for i in range(entry["count"])]
    vertices, triangles = [], []
    for mesh in document.get("meshes", []):
        for primitive in mesh["primitives"]:
            if primitive.get("mode", 4) != 4:
                continue
            base = len(vertices)
            points = accessor(primitive["attributes"]["POSITION"])
            vertices.extend(points)
            indices = [value[0] for value in accessor(primitive["indices"])] if "indices" in primitive else list(range(len(points)))
            if len(indices) % 3 or any(i >= len(points) for i in indices):
                raise ValueError("Invalid triangle indices")
            triangles.extend(tuple(base + n for n in indices[i:i + 3]) for i in range(0, len(indices), 3))
    if not vertices or not triangles or not all(math.isfinite(n) for v in vertices for n in v):
        raise ValueError("No finite triangle geometry")
    return vertices, triangles


class MeshPreview(QWidget):
    def __init__(self):
        super().__init__()
        self.vertices, self.triangles = [], []
        self.angle, self.zoom = 0.5, 1
        self.last = None
        self.setMinimumSize(240, 180)

    def load(self, path):
        vertices, self.triangles = read_glb(path)
        center = [sum(v[i] for v in vertices) / len(vertices) for i in range(3)]
        extent = max(max(abs(v[i] - center[i]) for v in vertices) for i in range(3)) or 1
        self.vertices = [tuple((v[i] - center[i]) / extent for i in range(3)) for v in vertices]
        self.zoom = 1
        self.update()

    def paintEvent(self, _):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#14181f"))
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QColor("#80bad6"))
        if not self.vertices:
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No mesh preview")
            return
        scale = min(self.width(), self.height()) * 0.35 * self.zoom
        c, s = math.cos(self.angle), math.sin(self.angle)
        points = [QPointF(self.width() / 2 + (v[0] * c + v[2] * s) * scale, self.height() / 2 - (v[1] * 0.9 + (v[2] * c - v[0] * s) * 0.3) * scale) for v in self.vertices]
        # shortcut: cap interactive wireframe to 20000 triangles; use external viewer for large meshes.
        for triangle in self.triangles[:20000]:
            for a, b in ((0, 1), (1, 2), (2, 0)):
                painter.drawLine(points[triangle[a]], points[triangle[b]])

    def mousePressEvent(self, event):
        self.last = event.position().x()

    def mouseMoveEvent(self, event):
        if self.last is not None:
            self.angle += (event.position().x() - self.last) * 0.01
            self.last = event.position().x()
            self.update()

    def mouseReleaseEvent(self, event):
        self.last = None

    def wheelEvent(self, event):
        self.zoom = max(0.2, min(5, self.zoom * (1.1 if event.angleDelta().y() > 0 else 0.9)))
        self.update()
