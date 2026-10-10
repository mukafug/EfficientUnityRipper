# SPDX-License-Identifier: GPL-3.0-only
"""Exercise real GUI worker/queue, importer, preview and export without file dialogs."""
import sys
import time
from pathlib import Path
from PySide6.QtWidgets import QApplication, QPushButton
from PySide6.QtCore import QTimer, Qt
from PySide6.QtTest import QTest
from eur.core import Index, Queue
from eur.gui import MainWindow

source, output = sys.argv[1:]
output = Path(output).resolve(); output.mkdir(parents=True, exist_ok=True)
app = QApplication([]); app.setStyle("Fusion")
app.setStyleSheet("QWidget{background:#20252e;color:#e2e5ec;font-family:'Segoe UI';font-size:10pt;}QTreeWidget,QPlainTextEdit,QLineEdit{background:#171c24;}QHeaderView::section,QDockWidget::title{background:#2b3340;padding:5px;}QPushButton{background:#303947;padding:6px;}")
window = MainWindow(); window.queue = Queue(output / "test-queue.json")
window.show(); window.input.setText(str(Path(source).resolve()))
window.queue.add({"operation": "scan", "paths": [str(Path(source).resolve())], "output": str(output / "index")})
window.refresh_queue(); window.run_queue()
stage, started = 0, time.monotonic()
def tick():
    global stage
    try:
        assert time.monotonic() - started < 180, "GUI pipeline timeout"
        assert not any(j["status"] == "failed" for j in window.queue.jobs), window.queue.jobs
        if window.worker: return
        if stage == 0:
            assert window.index and window.queue.jobs[0]["status"] == "done"
            texture = next(id for id, r in window.index.rows.items() if r["name"] == "checker" and r["class_id"] == 28)
            for i in range(window.tree.topLevelItemCount()):
                item=window.tree.topLevelItem(i)
                if item.data(0,Qt.ItemDataRole.UserRole)==texture: window.tree.setCurrentItem(item); break
            button=next(b for b in window.findChildren(QPushButton) if b.text()=="Decode selected preview")
            stage=1; QTest.mouseClick(button,Qt.MouseButton.LeftButton)
        elif stage == 1:
            assert window.image.pixmap() and not window.image.pixmap().isNull(), "PNG preview missing"
            assert window.image.pixmap().width() > 0
            window.grab().save(str(output / "gui-png.png"))
            mesh=next(id for id,r in window.index.rows.items() if r["name"]=="triangle" and r["class_id"]==43)
            window.queue.add({"operation":"export","manifest":str(window.index.path),"ids":[mesh],"output":str(output / "package"),"media":True})
            window.refresh_queue(); stage=2; window.run_queue()
        elif stage == 2:
            assert window.queue.jobs[-1]["status"]=="done"
            assert Index(output / "package/manifest.json").rows
            mesh_file=next((output / "package/media").glob("*.glb")); window.mesh.load(mesh_file)
            window.preview.setCurrentWidget(window.mesh)
            stage=3
        elif stage == 3:
            window.grab().save(str(output / "gui-mesh.png"))
            assert window.mesh.vertices and window.mesh.triangles
            print("GUI pipeline passed: engine scan, queue, decoded PNG preview, media/JSON export, rendered wireframe")
            timer.stop(); window.close(); app.quit()
    except Exception:
        import traceback
        traceback.print_exc(); timer.stop(); window.backend.close(); app.exit(1)
timer=QTimer(); timer.timeout.connect(tick); timer.start(100)
sys.exit(app.exec())
