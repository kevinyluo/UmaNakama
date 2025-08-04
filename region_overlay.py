from PyQt5 import QtWidgets, QtCore, QtGui

class RegionSelector(QtWidgets.QWidget):
    region_changed = QtCore.pyqtSignal(tuple)  # (x, y, width, height)

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
        self.resize_direction = None
        self.old_pos = None
        self.show()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        # Bright red semi-transparent fill
        fill_color = QtGui.QColor(255, 0, 0, 60)
        painter.setBrush(fill_color)

        # Dark red thick border
        border_color = QtGui.QColor(139, 0, 0)
        painter.setPen(QtGui.QPen(border_color, 3))
        painter.drawRect(0, 0, self.width(), self.height())

        # Draw corner handles (dark red squares)
        handle_size = self.resize_handle_size
        handle_color = QtGui.QColor(139, 0, 0)
        painter.setBrush(handle_color)
        painter.setPen(QtCore.Qt.NoPen)

        # Top-left
        painter.drawRect(0, 0, handle_size, handle_size)
        # Top-right
        painter.drawRect(self.width() - handle_size, 0, handle_size, handle_size)
        # Bottom-left
        painter.drawRect(0, self.height() - handle_size, handle_size, handle_size)
        # Bottom-right
        painter.drawRect(self.width() - handle_size, self.height() - handle_size, handle_size, handle_size)


    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.old_pos = event.globalPos()
            self.resizing = self.is_on_edge(event.pos())
            if not self.resizing:
                self.dragging = True

    def mouseMoveEvent(self, event):
        if self.dragging:
            delta = event.globalPos() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPos()
        elif self.resizing:
            self.resize_window(event.globalPos())
        else:
            # Change cursor on edge
            if self.is_on_edge(event.pos()):
                self.setCursor(QtCore.Qt.SizeFDiagCursor)
            else:
                self.setCursor(QtCore.Qt.ArrowCursor)

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.dragging = False
            self.resizing = False
            self.region_changed.emit((self.x(), self.y(), self.width(), self.height()))

    def is_on_edge(self, pos):
        return (
            pos.x() >= self.width() - self.resize_handle_size and
            pos.y() >= self.height() - self.resize_handle_size
        )

    def resize_window(self, global_pos):
        delta = global_pos - self.old_pos
        self.resize(self.width() + delta.x(), self.height() + delta.y())
        self.old_pos = global_pos
