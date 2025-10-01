from PyQt5 import QtWidgets, QtCore, QtGui

class TraineePickerOverlay(QtWidgets.QWidget):
    selected = QtCore.pyqtSignal(str)  # emits RAW name (as shown on site)
    canceled = QtCore.pyqtSignal()

    def __init__(self, names, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.WindowStaysOnTopHint |
            QtCore.Qt.Tool
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        # ---- panel ----
        panel = QtWidgets.QFrame()
        panel.setStyleSheet("""
            QFrame {
                background: rgba(30, 30, 30, 220);
                border: 1px solid #888;
                border-radius: 10px;
            }
            QLabel { color: #fff; font-size: 13px; }
            QComboBox, QPushButton {
                background: #2f2f2f; color: #fff; border: 1px solid #555;
                padding: 4px; border-radius: 6px;
            }
            QPushButton:hover { border-color: #aaa; }
        """)

        title = QtWidgets.QLabel("Who is this?")
        self.combo = QtWidgets.QComboBox()
        self.combo.addItems(sorted(names))      # raw names as-is
        btn_save = QtWidgets.QPushButton("Save")
        btn_cancel = QtWidgets.QPushButton("Cancel")

        btns = QtWidgets.QHBoxLayout()
        btns.addStretch(1)
        btns.addWidget(btn_save)
        btns.addWidget(btn_cancel)

        lay = QtWidgets.QVBoxLayout(panel)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)
        lay.addWidget(title)
        lay.addWidget(self.combo)
        lay.addLayout(btns)

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(panel)

        btn_save.clicked.connect(self._on_save)
        btn_cancel.clicked.connect(self.canceled.emit)

        # default size
        self.resize(320, 120)

    def _on_save(self):
        self.selected.emit(self.combo.currentText())

    def show_centered(self):
        screen = QtWidgets.QApplication.primaryScreen().geometry()
        self.move(screen.center().x() - self.width() // 2,
                  screen.center().y() - self.height() // 2)
        self.show()
