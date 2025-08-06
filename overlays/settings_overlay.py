from PyQt5 import QtWidgets, QtCore, QtGui

class SettingsOverlay(QtWidgets.QWidget):
    closed = QtCore.pyqtSignal()

    def __init__(self, config, save_callback, position=(500, 500)):
        super().__init__()
        self.config = config
        self.save_callback = save_callback
        self.drag_pos = None

        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.WindowStaysOnTopHint |
            QtCore.Qt.Tool
        )
        self.setGeometry(position[0], position[1], 360, 200)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        # Drop shadow
        shadow = QtWidgets.QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QtGui.QColor(0, 0, 0, 160))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)

        # Dark background
        self.container = QtWidgets.QFrame(self)
        self.container.setGeometry(0, 0, 360, 200)
        self.container.setStyleSheet("""
            QFrame {
                background-color: rgba(40, 40, 40, 230);
                border-radius: 8px;
            }
        """)

        layout = QtWidgets.QVBoxLayout(self.container)
        layout.setContentsMargins(25, 15, 25, 15)
        layout.setSpacing(12)

        # Title
        title = QtWidgets.QLabel("Settings")
        title.setStyleSheet("""
            color: white;
            font-size: 16px;
            font-weight: bold;
            padding-left: 10px;
            padding-right: 10px;
        """)
        layout.addWidget(title)

        # Confidence slider label
        self.label_conf = QtWidgets.QLabel()
        self.label_conf.setStyleSheet("""
            color: white;
            font-size: 14px;
            padding-left: 10px;
            padding-right: 10px;
        """)
        layout.addWidget(self.label_conf)

        # Confidence slider
        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(100)
        self.slider.setValue(int(self.config.get("text_match_confidence", 0.7) * 100))
        self.slider.valueChanged.connect(self.update_confidence_label)
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

        # Horizontal row for slider + default button
        slider_row = QtWidgets.QHBoxLayout()
        slider_row.addWidget(self.slider)

        default_btn = QtWidgets.QPushButton("Default")
        default_btn.setFixedSize(70, 24)
        default_btn.setStyleSheet("""
            QPushButton {
                background-color: #555;
                color: white;
                border-radius: 5px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #777;
            }
        """)
        default_btn.clicked.connect(self.reset_confidence)
        slider_row.addWidget(default_btn)

        layout.addLayout(slider_row)

        # Debug mode checkbox
        self.debug_checkbox = QtWidgets.QCheckBox("Enable Debug Mode")
        self.debug_checkbox.setStyleSheet("""
            color: white;
            font-size: 13px;
            padding-left: 10px;
            padding-right: 10px;
        """)
        self.debug_checkbox.setChecked(self.config.get("debug_mode", False))
        self.debug_checkbox.stateChanged.connect(self.toggle_debug_mode)
        layout.addWidget(self.debug_checkbox)

        # Always show overlay checkbox
        self.always_show_checkbox = QtWidgets.QCheckBox("Always Show Event Overlay")
        self.always_show_checkbox.setStyleSheet("""
            color: white;
            font-size: 13px;
            padding-left: 10px;
            padding-right: 10px;
        """)
        self.always_show_checkbox.setChecked(self.config.get("always_show_overlay", False))
        self.always_show_checkbox.stateChanged.connect(self.toggle_always_show)
        layout.addWidget(self.always_show_checkbox)

        self.update_confidence_label()
        
    def toggle_always_show(self, state):
        self.config["always_show_overlay"] = (state == QtCore.Qt.Checked)
        self.save_callback(self.config)


    def update_confidence_label(self):
        val = self.slider.value() / 100
        self.label_conf.setText(f"Text Match Confidence: {val:.2f}")
        self.config["text_match_confidence"] = val
        self.save_callback(self.config)

    def reset_confidence(self):
        """Reset confidence slider to default (0.7)."""
        self.slider.setValue(70)

    def toggle_debug_mode(self, state):
        self.config["debug_mode"] = (state == QtCore.Qt.Checked)
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
