from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QComboBox, QDialogButtonBox, QHBoxLayout
from PyQt5.QtGui import QPixmap, QImage
import threading

class CharacterPicker(QDialog):
    def __init__(self, names, preview_qimage: QImage | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Who's this?")
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)
        self.setModal(True)

        layout = QVBoxLayout(self)

        if preview_qimage is not None:
            h = QHBoxLayout()
            lbl = QLabel()
            pix = QPixmap.fromImage(preview_qimage).scaled(96, 96, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
            lbl.setPixmap(pix)
            h.addWidget(lbl)
            h.addWidget(QLabel("Select the trainee for this portrait:"))
            layout.addLayout(h)
        else:
            layout.addWidget(QLabel("Select the trainee:"))

        self.combo = QComboBox()
        self.combo.setEditable(True)
        self.combo.addItems(names)
        self.combo.setInsertPolicy(QComboBox.NoInsert)
        layout.addWidget(self.combo)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_name(self):
        return self.combo.currentText().strip()

class _PickerBridge(QtCore.QObject):
    request = QtCore.pyqtSignal(object)  # payload: {"names":[...], "qimage": QImage|None, "event": Event, "out": dict}

_bridge = _PickerBridge()

def _on_request(payload):
    names = payload.get("names", [])
    qimage = payload.get("qimage")
    ev = payload.get("event")
    out = payload.get("out", {})
    dlg = CharacterPicker(names, qimage)
    result = dlg.exec_()
    out["name"] = dlg.selected_name() if result == QDialog.Accepted else None
    if ev:
        ev.set()

_bridge.request.connect(_on_request)

def choose_character(names, preview_qimage=None, timeout=15.0):
    """
    Thread-safe, blocking helper: shows the picker on the GUI thread.
    Returns the selected name or None (timeout/cancel).
    """
    done = threading.Event()
    out = {}
    _bridge.request.emit({"names": names, "qimage": preview_qimage, "event": done, "out": out})
    done.wait(timeout=timeout)
    return out.get("name")
