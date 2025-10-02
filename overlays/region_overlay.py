"""
Region selector overlay (split visual: yellow + red).

Responsibilities
- Provides a single draggable/resizable rectangle that VISUALLY splits into:
  a yellow square on the left (portrait) and a red rectangle on the right (OCR).
  The left square’s side equals the overall height of the full selector.
- Draws translucent fills and corner resize handles; only the full rect is persisted
  and subregions are derived at paint/use time.

Notes
- This widget is purely visual/interactive; it stores no app state itself.
- Keep pen/alpha conservative so the underlying game UI remains legible during setup.
"""

from PyQt5 import QtWidgets, QtCore, QtGui

class RegionSelector(QtWidgets.QWidget):
    """
    Composite overlay:
      ┌─────────────── total width (w) ────────────────┐
      │  yellow square (size=h)  |   red OCR region    │
      └──────────────────────────┴─────────────────────┘
    - Yellow left is always square (size = height).
    - Red right is the remaining width (w - h), clamped to a small minimum.
    """
    def __init__(self, region=(596, 382, 355, 74), min_right_width=50):
        super().__init__()
        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.WindowStaysOnTopHint |
            QtCore.Qt.Tool
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        self.resize_handle_size = 10
        self.dragging = False
        self.resizing = False
        self.resize_dir = None
        self.old_pos = None

        self.min_right_width = int(min_right_width)

        # Ensure starting geometry leaves room for the right (red) segment
        x, y, w, h = region
        if w < h + self.min_right_width:
            w = h + self.min_right_width
        self.setGeometry(x, y, w, h)

        self.show()

    # ---------- Public helpers to consume the two subregions ----------
    def get_left_rect(self):
        """Absolute screen rect of the yellow square (x, y, w, h)."""
        gx, gy, w, h = self.geometry().getRect()
        s = h  # square side = height
        return (gx, gy, s, h)

    def get_right_rect(self):
        """Absolute screen rect of the red OCR region (x, y, w, h)."""
        gx, gy, w, h = self.geometry().getRect()
        s = h
        return (gx + s, gy, max(0, w - s), h)

    def get_subregions(self):
        """(left_rect, right_rect) as absolute screen rect tuples."""
        return self.get_left_rect(), self.get_right_rect()

    # ------------------------ Painting ------------------------
    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        w, h = self.width(), self.height()
        s = h  # yellow square width

        # Safety: if somehow width got too small, just early out with a border
        if w <= 0 or h <= 0:
            return

        # --- left (yellow square) ---
        yellow_fill = QtGui.QColor(255, 255, 0, 80)
        yellow_border = QtGui.QColor(180, 140, 0)
        painter.setBrush(yellow_fill)
        painter.setPen(QtGui.QPen(yellow_border, 2))
        painter.drawRect(0, 0, min(s, w), h)

        # --- right (red area) ---
        right_x = s
        right_w = max(0, w - s)
        red_fill = QtGui.QColor(255, 0, 0, 60)
        red_border = QtGui.QColor(139, 0, 0)
        painter.setBrush(red_fill)
        painter.setPen(QtGui.QPen(red_border, 2))
        if right_w > 0:
            painter.drawRect(right_x, 0, right_w, h)

        # Divider line between yellow and red (visual)
        painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 160), 1, QtCore.Qt.DotLine))
        painter.drawLine(right_x, 0, right_x, h)

        # Outer border for the whole selector
        painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 200), 2))
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.drawRect(0, 0, w, h)

        # Resize handles (4 corners)
        handle = self.resize_handle_size
        painter.setBrush(QtGui.QColor(255, 255, 255, 220))
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawRect(0, 0, handle, handle)  # TL
        painter.drawRect(w - handle, 0, handle, handle)  # TR
        painter.drawRect(0, h - handle, handle, handle)  # BL
        painter.drawRect(w - handle, h - handle, handle, handle)  # BR

    # --------------------- Mouse interaction ---------------------
    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.old_pos = event.globalPos()
            self.resize_dir = self._get_resize_direction(event.pos())
            if self.resize_dir:
                self.resizing = True
            else:
                self.dragging = True

    def mouseMoveEvent(self, event):
        if self.dragging:
            delta = event.globalPos() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPos()
        elif self.resizing:
            self._resize_window(event.globalPos())
        else:
            direction = self._get_resize_direction(event.pos())
            if direction == "top-left" or direction == "bottom-right":
                self.setCursor(QtCore.Qt.SizeFDiagCursor)
            elif direction == "top-right" or direction == "bottom-left":
                self.setCursor(QtCore.Qt.SizeBDiagCursor)
            else:
                self.setCursor(QtCore.Qt.ArrowCursor)

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.dragging = False
            self.resizing = False
            self.resize_dir = None

    # ------------------------ Resizing ------------------------
    def _get_resize_direction(self, pos):
        hs = self.resize_handle_size
        if pos.x() <= hs and pos.y() <= hs:
            return "top-left"
        elif pos.x() >= self.width() - hs and pos.y() <= hs:
            return "top-right"
        elif pos.x() <= hs and pos.y() >= self.height() - hs:
            return "bottom-left"
        elif pos.x() >= self.width() - hs and pos.y() >= self.height() - hs:
            return "bottom-right"
        return None

    def _resize_window(self, global_pos):
        delta = global_pos - self.old_pos
        geom = self.geometry()
        x, y, w, h = geom.x(), geom.y(), geom.width(), geom.height()

        # Apply raw deltas based on which corner is grabbed
        if self.resize_dir == "bottom-right":
            w += delta.x()
            h += delta.y()
        elif self.resize_dir == "bottom-left":
            x += delta.x()
            w -= delta.x()
            h += delta.y()
        elif self.resize_dir == "top-left":
            x += delta.x()
            y += delta.y()
            w -= delta.x()
            h -= delta.y()
        elif self.resize_dir == "top-right":
            y += delta.y()
            w += delta.x()
            h -= delta.y()

        # Minimum height
        h = max(h, 50)

        # Enforce that the right red area keeps a small minimum width
        # total width must be at least h (for the square) + min_right_width
        min_total_w = h + self.min_right_width
        if w < min_total_w:
            if self.resize_dir in ("top-left", "bottom-left"):
                # Keep right edge fixed; grow to the left
                x -= (min_total_w - w)
            w = min_total_w

        self.setGeometry(x, y, w, h)
        self.old_pos = global_pos
