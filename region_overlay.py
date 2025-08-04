from PyQt5 import QtWidgets, QtCore, QtGui

class RegionSelector(QtWidgets.QWidget):
    def __init__(self, region=(596, 382, 355, 74)):
        super().__init__()
        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.WindowStaysOnTopHint |
            QtCore.Qt.Tool
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setGeometry(*region)
        self.resize_handle_size = 10
        self.dragging = False
        self.resizing = False
        self.resize_dir = None
        self.old_pos = None
        self.show()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        fill_color = QtGui.QColor(255, 0, 0, 60)
        painter.setBrush(fill_color)
        border_color = QtGui.QColor(139, 0, 0)
        painter.setPen(QtGui.QPen(border_color, 3))
        painter.drawRect(0, 0, self.width(), self.height())

        handle_size = self.resize_handle_size
        handle_color = QtGui.QColor(139, 0, 0)
        painter.setBrush(handle_color)
        painter.setPen(QtCore.Qt.NoPen)

        # Draw handles for all 4 corners
        painter.drawRect(0, 0, handle_size, handle_size)  # top-left
        painter.drawRect(self.width() - handle_size, 0, handle_size, handle_size)  # top-right
        painter.drawRect(0, self.height() - handle_size, handle_size, handle_size)  # bottom-left
        painter.drawRect(self.width() - handle_size, self.height() - handle_size, handle_size, handle_size)  # bottom-right

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.old_pos = event.globalPos()
            self.resize_dir = self.get_resize_direction(event.pos())
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
            self.resize_window(event.globalPos())
        else:
            direction = self.get_resize_direction(event.pos())
            if direction:
                self.setCursor(QtCore.Qt.SizeFDiagCursor)
            else:
                self.setCursor(QtCore.Qt.ArrowCursor)

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.dragging = False
            self.resizing = False
            self.resize_dir = None

    def get_resize_direction(self, pos):
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

    def resize_window(self, global_pos):
        delta = global_pos - self.old_pos
        x, y, w, h = self.geometry().x(), self.geometry().y(), self.width(), self.height()

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

        self.setGeometry(x, y, max(w, 50), max(h, 50))
        self.old_pos = global_pos
