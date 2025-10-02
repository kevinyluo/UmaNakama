"""
Modal dialog for labeling unknown portraits.

Responsibilities
- Presents a small, always-on-top dialog with an optional preview image and an editable
  combobox of trainee names (from `events/trainee_names.json` or learned portraits).
- Returns the selected/typed name and lets the caller persist a portrait screenshot
  immediately after confirmation.

Notes
- Must be invoked on the Qt main thread. Worker threads should emit a signal that a
  main-thread slot handles by constructing and `exec_()`-ing the dialog.
- Keep the preview tiny (e.g., ~96px) to avoid covering the game UI while labeling.
- Only one dialog instance can be open at a time; subsequent requests will focus the
  existing dialog and immediately release the requester.
"""

from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QComboBox, QDialogButtonBox, QHBoxLayout
from PyQt5.QtGui import QPixmap
import threading

def pil_to_qimage(pil_img):
    """
    Convert a PIL.Image to QImage safely (no ImageQt dependency).

    Args:
        pil_img (PIL.Image.Image): Source image.

    Returns:
        QtGui.QImage: Detached QImage copy.
    """
    if pil_img.mode != "RGBA":
        pil_img = pil_img.convert("RGBA")
    w, h = pil_img.size
    buf = pil_img.tobytes("raw", "RGBA")
    qimg = QtGui.QImage(buf, w, h, QtGui.QImage.Format_RGBA8888)
    return qimg.copy()

class CharacterPicker(QDialog):
    """
    Simple 'Who's this?' modal dialog with an optional portrait preview and
    a searchable dropdown of names.
    """
    def __init__(self, names, preview_qimage=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Who's this?")
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)
        self.setModal(True)

        layout = QVBoxLayout(self)
        if preview_qimage is not None:
            h = QHBoxLayout()
            lbl = QLabel()
            pix = QPixmap.fromImage(preview_qimage)
            pix = pix.scaled(96, 96, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
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

class CharPickerBridge(QtCore.QObject):
    """
    Main-thread bridge. Worker threads emit `request` with a payload:
        {"names": [...], "qimage": QImage|None, "event": threading.Event, "out": dict}
    """
    request = QtCore.pyqtSignal(object)

bridge = CharPickerBridge()

# ---- Single-instance guard ----
_active_dialog = None  # type: CharacterPicker | None

def _on_request(payload):
    """
    Slot executed on the main thread when a worker wants to show the picker.

    Enforces single-instance:
    - If a dialog is already open, bring it to front and immediately release
      the new requester (their Event is set, and result remains unset/None).
    - Otherwise, open the dialog modally and fill the result into `out["name"]`.
    """
    global _active_dialog

    names = payload.get("names", [])
    qimage = payload.get("qimage")
    ev: threading.Event = payload.get("event")
    out: dict = payload.get("out")

    # If a dialog is already open, just focus it and don't open another
    if _active_dialog is not None and _active_dialog.isVisible():
        # Bring existing dialog to front
        _active_dialog.raise_()
        _active_dialog.activateWindow()
        try:
            # Immediately release the duplicate requester (no result)
            if ev:
                ev.set()
        finally:
            return

    dlg = CharacterPicker(names, qimage)
    _active_dialog = dlg
    try:
        result = dlg.exec_()
        out["name"] = dlg.selected_name() if result == QDialog.Accepted else None
    finally:
        _active_dialog = None
        if ev:
            ev.set()

bridge.request.connect(_on_request)

def prompt_character_from_worker(names, qimage, timeout=20.0):
    """
    Worker-side helper: emits a request and waits (with timeout) for the user
    to answer. If a dialog is already open, this call returns quickly (None).

    Args:
        names (list[str]): Options for the combobox.
        qimage (QtGui.QImage|None): Small preview image.
        timeout (float): Seconds to wait for a response.

    Returns:
        str | None: Selected/typed name, or None on cancel/timeout/duplicate.
    """
    done = threading.Event()
    out = {}
    bridge.request.emit({"names": names or [], "qimage": qimage, "event": done, "out": out})
    done.wait(timeout=timeout)
    return out.get("name")
