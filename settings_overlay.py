from PyQt5 import QtWidgets, QtCore, QtGui

class SettingsOverlay(QtWidgets.QWidget):
    closed = QtCore.pyqtSignal()

    def __init__(self, config, save_callback, position=(200, 200)):
        super().__init__()
        self.config = config
        self.save_callback = save_callback
        self.drag_pos = None

        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.WindowStaysOnTopHint |
            QtCore.Qt.Tool
        )
        self.setGeometry(position[0], position[1], 320, 100)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        # Dark background frame
        self.container = QtWidgets.QFrame(self)
        self.container.setGeometry(0, 0, 320, 100)
        self.container.setStyleSheet("""
            QFrame {
                background-color: rgba(40, 40, 40, 230);
                border-radius: 8px;
            }
        """)

        layout = QtWidgets.QVBoxLayout(self.container)
        layout.setContentsMargins(10, 10, 10, 10)

        # White label
        self.label = QtWidgets.QLabel()
        self.label.setStyleSheet("color: white; font-size: 14px;")
        layout.addWidget(self.label)

        # White slider
        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(100)
        self.slider.setValue(int(self.config.get("text_match_confidence", 0.7) * 100))
        self.slider.valueChanged.connect(self.update_label)
        self.slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #555;
                height: 8px;
                background: #222;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: white;
                border: 1px solid #aaa;
                width: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }
            QSlider::sub-page:horizontal {
                background: #999;
                border-radius: 4px;
            }
            QSlider::add-page:horizontal {
                background: #444;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.slider)

        self.update_label()

    def update_label(self):
        val = self.slider.value() / 100
        self.label.setText(f"Text Match Confidence: {val:.2f}")
        self.config["text_match_confidence"] = val
        self.save_callback(self.config)

    def close_overlay(self):
        self.closed.emit()
        self.close()

    # ---- Dragging overlay ----
    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.drag_pos = event.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self.drag_pos and event.buttons() & QtCore.Qt.LeftButton:
            self.move(event.globalPos() - self.drag_pos)

    def mouseReleaseEvent(self, event):
        self.drag_pos = None
