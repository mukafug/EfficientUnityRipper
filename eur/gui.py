# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QSettings
from PySide6.QtGui import QPixmap, QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QDockWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QComboBox, QTreeWidget, QTreeWidgetItem, QPlainTextEdit, QTabWidget, QLabel, QFileDialog, QMessageBox, QProgressBar, QCheckBox, QAbstractItemView
from .core import ROOT, DATA, Backend, Index, Queue, fingerprint, fresh_export
from .preview import MeshPreview


class Worker(QThread):
    event = Signal(dict)
    result = Signal(object)
    failed = Signal(str)
    def __init__(self, function):
        super().__init__()
        self.function = function
    def run(self):
        try:
            def emit(message):
                if self.isInterruptionRequested(): raise RuntimeError("Cancelled; checkpoint retained")
                self.event.emit(message)
            result = self.function(emit)
            if self.isInterruptionRequested(): raise RuntimeError("Cancelled; checkpoint retained")
            self.result.emit(result)
        except Exception as error:
            self.failed.emit(str(error))


class MainWindow(QMainWindow):
    backend_event = Signal(dict)
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EfficientUnityRipper 0.1.0")
        self.resize(1440, 920)
        self.index, self.worker, self.selected_id, self.active_job = None, None, None, None
        self.backend_event.connect(self.on_event)
        self.backend = Backend(self.backend_event.emit)
        self.queue_running = False
        self.queue = Queue(DATA / "queue.json")
        self.settings = QSettings("EfficientUnityRipper", "Desktop-v2")
        central = QWidget(); central.setMaximumSize(0, 0); self.setCentralWidget(central)
        self.setDockNestingEnabled(True)
        self.docks = {}
        self.scan_panel = QWidget(); scan_layout = QVBoxLayout(self.scan_panel)
        self.input = QLineEdit(); self.input.setPlaceholderText("Unity data folder / serialized file / bundle")
        scan_layout.addWidget(self.input)
        controls = QHBoxLayout()
        for text, callback in (("File…", self.choose_file), ("Folder…", self.choose_folder), ("Scan / index", self.scan), ("Open index…", self.choose_index)):
            button = QPushButton(text); button.clicked.connect(callback); controls.addWidget(button)
        scan_layout.addLayout(controls)
        self.progress = QProgressBar(); self.progress.setRange(0, 1); self.progress.setValue(0); scan_layout.addWidget(self.progress)
        self.phase = QLabel("Ready"); self.phase.setWordWrap(True); scan_layout.addWidget(self.phase)
        scan_layout.addStretch()
        self.browser_panel = QWidget(); browser_layout = QVBoxLayout(self.browser_panel)
        filters = QHBoxLayout(); self.search = QLineEdit(); self.search.setPlaceholderText("Search name, type, collection or path ID")
        self.type_filter = QComboBox(); self.type_filter.addItem("All types")
        filters.addWidget(self.search, 2); filters.addWidget(self.type_filter, 1); browser_layout.addLayout(filters)
        self.tree = QTreeWidget(); self.tree.setHeaderLabels(["Asset", "Type", "Collection", "Status"])
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection); self.tree.setSortingEnabled(True)
        browser_layout.addWidget(self.tree)
        actions = QHBoxLayout(); self.dependencies = QCheckBox("Include dependencies"); self.dependencies.setChecked(True)
        self.media = QCheckBox("Decoded media"); self.media.setChecked(True)
        actions.addWidget(self.dependencies); actions.addWidget(self.media)
        self.export_button = QPushButton("Queue selected export…"); self.export_button.clicked.connect(self.queue_selected); actions.addWidget(self.export_button)
        browser_layout.addLayout(actions)
        self.search.textChanged.connect(self.filter); self.type_filter.currentTextChanged.connect(self.filter)
        self.tree.currentItemChanged.connect(self.inspect_item)
        self.hierarchy = QTreeWidget(); self.hierarchy.setHeaderLabels(["Scene / prefab hierarchy", "Type"])
        self.hierarchy.currentItemChanged.connect(self.inspect_item)
        hierarchy_panel = QWidget(); hierarchy_layout = QVBoxLayout(hierarchy_panel); hierarchy_layout.addWidget(self.hierarchy)
        scene_button = QPushButton("Queue collection / scene export…"); scene_button.clicked.connect(self.queue_scene); hierarchy_layout.addWidget(scene_button)
        self.inspector = QTabWidget()
        self.inspector.setMinimumHeight(260)
        self.properties = QPlainTextEdit(); self.properties.setReadOnly(True)
        properties_panel = QWidget(); properties_layout = QVBoxLayout(properties_panel)
        self.property_search = QLineEdit(); self.property_search.setPlaceholderText("Find serialized field / value; Enter for next")
        self.property_search.returnPressed.connect(self.find_property)
        properties_layout.addWidget(self.property_search); properties_layout.addWidget(self.properties)
        self.dep_tree = QTreeWidget(); self.dep_tree.setHeaderLabels(["Serialized field", "Target / unresolved pointer"]); self.dep_tree.itemDoubleClicked.connect(self.jump_dependency)
        self.provenance = QPlainTextEdit(); self.provenance.setReadOnly(True)
        self.inspector.addTab(properties_panel, "Properties"); self.inspector.addTab(self.dep_tree, "Dependencies"); self.inspector.addTab(self.provenance, "Provenance")
        self.preview = QTabWidget(); self.image = QLabel("No image preview"); self.image.setAlignment(Qt.AlignmentFlag.AlignCenter); self.image.setMinimumSize(240, 180)
        self.mesh = MeshPreview(); self.file_view = QPlainTextEdit(); self.file_view.setReadOnly(True)
        self.preview.addTab(self.image, "Image"); self.preview.addTab(self.mesh, "Mesh"); self.preview.addTab(self.file_view, "File / material")
        preview_panel = QWidget(); preview_layout = QVBoxLayout(preview_panel); preview_layout.addWidget(self.preview)
        preview_button = QPushButton("Decode selected preview"); preview_button.clicked.connect(self.decode_preview); preview_layout.addWidget(preview_button)
        self.logs = QPlainTextEdit(); self.logs.setReadOnly(True); self.logs.document().setMaximumBlockCount(2500)
        queue_panel = QWidget(); queue_layout = QVBoxLayout(queue_panel)
        self.queue_tree = QTreeWidget(); self.queue_tree.setHeaderLabels(["Job", "State", "Output / error"]); queue_layout.addWidget(self.queue_tree)
        queue_actions = QHBoxLayout()
        for text, callback in (("Run / resume", self.run_queue), ("Stop", self.stop), ("Retry failed", self.retry_failed)):
            button = QPushButton(text); button.clicked.connect(callback); queue_actions.addWidget(button)
        queue_layout.addLayout(queue_actions)
        self.dock("Input / scan", self.scan_panel, Qt.DockWidgetArea.LeftDockWidgetArea)
        self.dock("Asset browser", self.browser_panel, Qt.DockWidgetArea.LeftDockWidgetArea)
        self.dock("Scene hierarchy", hierarchy_panel, Qt.DockWidgetArea.LeftDockWidgetArea)
        self.dock("Preview", preview_panel, Qt.DockWidgetArea.RightDockWidgetArea)
        self.dock("Inspector", self.inspector, Qt.DockWidgetArea.RightDockWidgetArea)
        self.dock("Queue", queue_panel, Qt.DockWidgetArea.LeftDockWidgetArea)
        self.dock("Logs", self.logs, Qt.DockWidgetArea.LeftDockWidgetArea)
        self.splitDockWidget(self.docks["Input / scan"], self.docks["Logs"], Qt.Orientation.Vertical)
        self.splitDockWidget(self.docks["Input / scan"], self.docks["Queue"], Qt.Orientation.Horizontal)
        self.splitDockWidget(self.docks["Input / scan"], self.docks["Asset browser"], Qt.Orientation.Vertical)
        self.tabifyDockWidget(self.docks["Asset browser"], self.docks["Scene hierarchy"])
        self.splitDockWidget(self.docks["Preview"], self.docks["Inspector"], Qt.Orientation.Vertical)
        self.docks["Asset browser"].raise_()
        self.resizeDocks([self.docks["Asset browser"], self.docks["Queue"], self.docks["Preview"]], [540, 280, 560], Qt.Orientation.Horizontal)
        self.resizeDocks([self.docks["Input / scan"], self.docks["Asset browser"], self.docks["Queue"]], [150, 490, 180], Qt.Orientation.Vertical)
        QTimer.singleShot(100, lambda: self.resizeDocks([self.docks["Logs"]], [180], Qt.Orientation.Vertical))
        view = self.menuBar().addMenu("View")
        for dock in self.docks.values(): view.addAction(dock.toggleViewAction())
        view.addAction("Open local data", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(DATA))))
        state = self.settings.value("layout")
        if state is not None: self.restoreState(state)
        self.refresh_queue()

    def dock(self, title, panel, area):
        dock = QDockWidget(title, self); dock.setObjectName(title); dock.setWidget(panel)
        dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetClosable | QDockWidget.DockWidgetFeature.DockWidgetMovable)
        self.addDockWidget(area, dock); self.docks[title] = dock

    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Unity file")
        if path: self.input.setText(path)

    def choose_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Unity data folder")
        if path: self.input.setText(path)

    def choose_index(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open manifest", "", "Manifest (manifest.json)")
        if path:
            try: self.open_index(Index(path))
            except Exception as error: self.error(str(error))

    def work(self, function, on_result):
        if self.worker is not None:
            self.error("Another job is active"); return
        self.worker = Worker(function)
        self.worker.event.connect(self.on_event); self.worker.result.connect(on_result); self.worker.failed.connect(self.job_error)
        self.worker.finished.connect(self.work_finished); self.worker.start()

    def work_finished(self):
        self.backend.event = self.backend_event.emit
        self.worker.deleteLater(); self.worker = None
        successful = not self.active_job or self.active_job["status"] == "running"
        self.progress.setRange(0, 1); self.progress.setValue(1 if successful else 0)
        if self.active_job and self.active_job["status"] == "running": self.queue.set(self.active_job, "done")
        self.active_job = None; self.refresh_queue()

    def on_event(self, event):
        kind = event.get("kind")
        if kind == "progress":
            self.progress.setRange(0, event["total"]); self.progress.setValue(event["completed"])
            self.phase.setText(f'{event["completed"]}/{event["total"]} · {event["message"][:160]}')
        elif kind == "phase":
            self.progress.setRange(0, 0); self.phase.setText(event["message"])
        elif kind == "log":
            self.logs.appendPlainText(f'{event.get("level", "")} {event.get("category", "")} {event["message"]}')
        elif kind == "complete":
            self.logs.appendPlainText(json.dumps(event, ensure_ascii=False)[:1800]); self.phase.setText("Completed" + (" · cache reused" if event.get("cached") else ""))

    def scan(self):
        path = self.input.text().strip()
        if not path: return
        command = {"operation": "scan", "paths": [path], "output": str(DATA / "indices" / hashlib.sha256(str(Path(path).resolve()).encode()).hexdigest()[:20])}
        self.queue.add(command); self.refresh_queue(); self.run_queue()

    def open_index(self, index):
        self.index = index; self.tree.clear(); self.hierarchy.clear(); self.type_filter.blockSignals(True)
        self.type_filter.clear(); self.type_filter.addItem("All types"); self.type_filter.addItems(sorted({r["type"] for r in index.rows.values()})); self.type_filter.blockSignals(False)
        for id, row in index.rows.items():
            item = QTreeWidgetItem([row["name"], row["type"], row["collection_name"], row["status"]]); item.setData(0, Qt.ItemDataRole.UserRole, id); self.tree.addTopLevelItem(item)
        self.tree.setColumnWidth(0, 280); self.tree.setColumnWidth(1, 130); self.tree.setColumnWidth(2, 180)
        nodes = index.derive(write=False); items = {}
        for id, node in nodes.items():
            item = QTreeWidgetItem([node["name"], "GameObject"]); item.setData(0, Qt.ItemDataRole.UserRole, id); items[id] = item
        for id, node in nodes.items():
            parent = node["parent"]
            visited, cursor = {id}, parent
            while cursor in nodes and cursor not in visited:
                visited.add(cursor); cursor = nodes[cursor]["parent"]
            if parent in items and cursor not in visited:
                items[parent].addChild(items[id])
            else:
                self.hierarchy.addTopLevelItem(items[id])
            for component in node["components"]:
                if component in index.rows:
                    row = index.rows[component]; child = QTreeWidgetItem([row["name"], row["type"]]); child.setData(0, Qt.ItemDataRole.UserRole, component); items[id].addChild(child)
        self.hierarchy.expandToDepth(1); self.filter()
        self.statusBar().showMessage(f"{len(index.rows)} objects · {index.path}")
        if self.tree.topLevelItemCount(): self.tree.setCurrentItem(self.tree.topLevelItem(0))

    def filter(self):
        query = self.search.text().casefold(); type = self.type_filter.currentText()
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            id = item.data(0, Qt.ItemDataRole.UserRole)
            row = self.index.rows[id]
            match = query in " ".join([row["name"], row["type"], row["collection_name"], row["path_id"]]).casefold()
            item.setHidden(not match or type not in ("All types", row["type"]))

    def inspect_item(self, item, previous=None):
        if not item or not self.index: return
        id = item.data(0, Qt.ItemDataRole.UserRole)
        if id not in self.index.rows: return
        self.selected_id = id
        try:
            data = self.index.object(id)
            text = json.dumps(data.get("properties"), ensure_ascii=False, indent=2)
            self.properties.setPlainText(text[:250000] + ("\nDisplay truncated; full JSON remains on disk." if len(text) > 250000 else ""))
            self.provenance.setPlainText(json.dumps({k: v for k, v in data.items() if k not in ("properties", "dependencies")}, indent=2, ensure_ascii=False))
            self.dep_tree.clear()
            for dependency in data["dependencies"]:
                target = dependency.get("target")
                name = self.index.rows[target]["name"] if target in self.index.rows else f'UNRESOLVED FileID={dependency["file_id"]} PathID={dependency["path_id"]}'
                child = QTreeWidgetItem([dependency["field"], name]); child.setData(0, Qt.ItemDataRole.UserRole, target); self.dep_tree.addTopLevelItem(child)
            self.dep_tree.setColumnWidth(0, 230)
            self.file_view.setPlainText(text[:50000])
            self.image.clear(); self.image.setText("No image preview"); self.mesh.vertices = []; self.mesh.update()
            self.statusBar().showMessage(f'{data["name"]} · {data["status"]} · {id}')
        except Exception as error: self.error(str(error))

    def jump_dependency(self, item, column):
        id = item.data(0, Qt.ItemDataRole.UserRole)
        if id in self.index.rows:
            for i in range(self.tree.topLevelItemCount()):
                candidate = self.tree.topLevelItem(i)
                if candidate.data(0, Qt.ItemDataRole.UserRole) == id:
                    self.search.clear(); self.type_filter.setCurrentIndex(0); self.tree.setCurrentItem(candidate); break

    def find_property(self):
        query = self.property_search.text()
        if query and not self.properties.find(query):
            from PySide6.QtGui import QTextCursor
            cursor = self.properties.textCursor(); cursor.movePosition(QTextCursor.MoveOperation.Start); self.properties.setTextCursor(cursor)
            self.properties.find(query)

    def enqueue_export(self, ids):
        parent = QFileDialog.getExistingDirectory(self, "Export parent (new subfolder created)")
        if not parent: return
        if self.dependencies.isChecked(): ids = self.index.closure(ids)
        self.queue.add({"operation": "export", "manifest": str(self.index.path), "ids": ids, "output": str(fresh_export(parent)), "media": self.media.isChecked()})
        self.refresh_queue()

    def queue_selected(self):
        if not self.index: return
        ids = [item.data(0, Qt.ItemDataRole.UserRole) for item in self.tree.selectedItems()]
        if ids: self.enqueue_export(ids)

    def queue_scene(self):
        if self.index and self.selected_id:
            self.enqueue_export(self.index.scene_ids(self.index.rows[self.selected_id]["collection"]))

    def run_queue(self):
        self.queue_running = True
        self.run_next()

    def run_next(self):
        if not self.queue_running: return
        if self.worker: return
        job = next((j for j in self.queue.jobs if j["status"] == "pending"), None)
        if not job: return
        self.active_job = job; self.queue.set(job, "running"); self.refresh_queue()
        command = job["command"]
        def execute(event):
            self.backend.event = event
            if command["operation"] == "scan":
                return self.backend.scan(command["paths"], Path(command["output"]))
            index = Index(command["manifest"])
            output = Path(command["output"])
            if output.exists():
                # A interrupted package stays intact; retry creates a new attempt.
                output = fresh_export(output.parent); command["output"] = str(output); self.queue.save()
            index.export_json(command["ids"], output)
            if command["media"]:
                ids = [id for id in command["ids"] if index.rows[id]["class_id"] in (28, 43, 83)]
                result = self.backend.media(index, ids, output / "media")
                if result["failed"]: raise RuntimeError(f'{result["failed"]} media exports failed; JSON and successful files preserved at {output}')
            return output
        def completed(result):
            if isinstance(result, Index): self.open_index(result)
            else: self.logs.appendPlainText("Export: " + str(result))
        self.work(execute, completed)
        self.worker.finished.connect(lambda: QTimer.singleShot(50, self.run_next))

    def decode_preview(self):
        if not self.index or not self.selected_id or self.worker: return
        id = self.selected_id; index = self.index
        if index.rows[id]["class_id"] not in (28, 43, 83):
            self.preview.setCurrentWidget(self.file_view); return
        destination = fresh_export(DATA / "previews")
        def execute(event):
            self.backend.event = event
            return self.backend.media(index, [id], destination)
        def complete(result):
            item = result["results"][0]
            if not item.get("path"): self.error(item.get("error", "Preview unavailable")); return
            path = item["path"]
            if path.endswith(".png"):
                image = QPixmap(path)
                if image.isNull(): self.error("Image decoder rejected PNG"); return
                self.image.setPixmap(image.scaled(self.image.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)); self.preview.setCurrentWidget(self.image)
            elif path.endswith(".glb"):
                try: self.mesh.load(path); self.preview.setCurrentWidget(self.mesh)
                except Exception as error: self.error(str(error))
            else:
                self.file_view.setPlainText("Decoded audio: " + path); self.preview.setCurrentWidget(self.file_view)
        self.work(execute, complete)

    def refresh_queue(self):
        self.queue_tree.clear()
        for job in self.queue.jobs:
            self.queue_tree.addTopLevelItem(QTreeWidgetItem([job["command"]["operation"], job["status"], job.get("error") or job["command"]["output"]]))
        self.queue_tree.setColumnWidth(0, 90); self.queue_tree.setColumnWidth(1, 90)

    def retry_failed(self):
        for job in self.queue.jobs:
            if job["status"] in ("failed", "cancelled"): self.queue.set(job, "pending")
        self.refresh_queue()

    def stop(self):
        self.queue_running = False
        if self.worker: self.worker.requestInterruption()
        if self.active_job: self.queue.set(self.active_job, "cancelled", "Stopped; retry from checkpoint")
        self.backend.close(); self.phase.setText("Stopping")

    def job_error(self, message):
        if self.active_job and self.active_job["status"] != "cancelled": self.queue.set(self.active_job, "failed", message)
        self.logs.appendPlainText("ERROR " + message); self.phase.setText("Failed / stopped; outputs preserved")

    def error(self, message):
        QMessageBox.warning(self, "EfficientUnityRipper", message)

    def closeEvent(self, event):
        self.settings.setValue("layout", self.saveState()); self.backend.close()
        if self.worker and not self.worker.wait(10000):
            event.ignore(); self.phase.setText("Waiting for worker to stop"); return
        event.accept()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest")
    args = parser.parse_args()
    app = QApplication(sys.argv[:1]); app.setStyle("Fusion")
    app.setStyleSheet("QWidget { background: #20252e; color: #e2e5ec; font-family: 'Segoe UI'; font-size: 10pt; } QTreeWidget, QPlainTextEdit, QLineEdit { background: #171c24; border: 1px solid #3b4452; } QPushButton { background: #303947; border: 1px solid #4b586c; padding: 6px 10px; border-radius: 3px; } QPushButton:hover { background: #42536a; } QHeaderView::section, QDockWidget::title { background: #2b3340; padding: 5px; } QTreeWidget::item:selected { background: #355674; } QProgressBar::chunk { background: #6495bb; }")
    window = MainWindow(); window.show()
    if args.manifest: window.open_index(Index(args.manifest))
    return app.exec()


if __name__ == "__main__": sys.exit(main())
