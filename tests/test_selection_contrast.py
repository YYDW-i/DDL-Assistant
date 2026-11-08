import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase, QFont
from PySide6.QtWidgets import QApplication, QListWidget
from app.ui.main_window import LIGHT_QSS, DARK_QSS
import pytest


@pytest.mark.parametrize("stylesheet,background,foreground", [(LIGHT_QSS, "#e7efff", "#1e345c"), (DARK_QSS, "#344865", "#ffffff")])
def test_selected_item_keeps_explicit_readable_colors(stylesheet, background, foreground):
    app = QApplication.instance() or QApplication([])
    widget = QListWidget()
    widget.setStyleSheet(stylesheet)
    widget.resize(350, 100)
    widget.addItem("TASK TEST")
    widget.setCurrentRow(0)
    widget.show()
    app.processEvents()
    for focused in (True, False):
        widget.setFocus() if focused else widget.clearFocus()
        app.processEvents()
        image = widget.grab().toImage()
        rect = widget.visualItemRect(widget.item(0))
        assert image.pixelColor(rect.right() - 25, rect.center().y()).name() == background
        assert any(image.pixelColor(x, y).name() == foreground
                   for x in range(rect.left() + 15, min(rect.right() - 15, 160))
                   for y in range(rect.top() + 8, rect.bottom() - 8))
    widget.close()
