# SPDX-License-Identifier: GPL-3.0-only
"""Launch actual Qt GUI, exercise selection/filter/dependency navigation, capture window."""
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, Qt
from PySide6.QtTest import QTest
from eur.core import Index
from eur.gui import MainWindow

manifest, output = sys.argv[1:]
app = QApplication([]); app.setStyle("Fusion")
app.setStyleSheet("QWidget {background:#20252e;color:#e2e5ec;font-family:'Segoe UI';font-size:10pt;} QTreeWidget,QPlainTextEdit,QLineEdit {background:#171c24;} QHeaderView::section,QDockWidget::title {background:#2b3340;padding:5px;} QPushButton {background:#303947;padding:6px;}")
window = MainWindow(); window.show(); window.open_index(Index(manifest))
window.input.setText(window.index.manifest["sources"][0])
def check():
    try:
        QTest.keyClicks(window.search, "Authored Triangle")
        visible = [window.tree.topLevelItem(i) for i in range(window.tree.topLevelItemCount()) if not window.tree.topLevelItem(i).isHidden()]
        assert visible, "Search found no authored asset"
        window.tree.setCurrentItem(visible[0]); assert window.properties.toPlainText()
        window.search.clear()
        material = next(window.tree.topLevelItem(i) for i in range(window.tree.topLevelItemCount()) if window.tree.topLevelItem(i).text(0) == "material")
        window.tree.setCurrentItem(material); assert "_MainTex" in window.properties.toPlainText()
        assert window.dep_tree.topLevelItemCount()
        window.property_search.setText("_MainTex"); window.find_property(); assert window.properties.textCursor().selectedText() == "_MainTex"
        window.grab().save(output)
        assert Path(output).stat().st_size > 10000
        print("GUI smoke passed: search, selection, material properties, dependencies, rendered screenshot")
        window.close(); app.quit()
    except Exception as error:
        import traceback
        traceback.print_exc(); print("GUI smoke failed:", error); app.exit(1)
QTimer.singleShot(1500, check)
sys.exit(app.exec())
