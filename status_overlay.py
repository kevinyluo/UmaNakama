from PyQt5 import QtWidgets, QtCore, QtGui

class StatusOverlay(QtWidgets.QWidget):
    toggle_scanning = QtCore.pyqtSignal()  # Signal to pause/resume
    quit_app = QtCore.pyqtSignal()         # Signal to quit app
    position_changed = QtCore.pyqtSignal(int, int) 
    open_settings = QtCore.pyqtSignal()  #

    def __init__(self, position=(50, 50), color=QtGui.QColor(0, 200, 0)):
        super().__init__()
        self.drag_pos = None
        self.color = color
        self.is_scanning = True
        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.WindowStaysOnTopHint |
            QtCore.Qt.Tool
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setGeometry(position[0], position[1], 30, 30)
        self.show()

    def set_color(self, color):
        self.color = color
        self.update()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.drag_pos = event.globalPos() - self.frameGeometry().topLeft()
        elif event.button() == QtCore.Qt.RightButton:
            self.show_context_menu(event.globalPos())

    def mouseMoveEvent(self, event):
        if self.drag_pos and event.buttons() & QtCore.Qt.LeftButton:
            self.move(event.globalPos() - self.drag_pos)

    def mouseReleaseEvent(self, event):
        self.drag_pos = None

    def show_context_menu(self, pos):
        """Unified context menu for pause/resume, open settings, quit."""
        menu = QtWidgets.QMenu(self)
        toggle_action = menu.addAction("Pause Scanning" if self.is_scanning else "Resume Scanning")
        settings_action = menu.addAction("Open Settings")
        quit_action = menu.addAction("Quit App")

        action = menu.exec_(self.mapToGlobal(self.rect().bottomLeft()))

        if action == toggle_action:
            self.is_scanning = not self.is_scanning
            self.toggle_scanning.emit()
            self.set_color(QtGui.QColor(0, 200, 0) if self.is_scanning else QtGui.QColor(200, 0, 0))
        elif action == settings_action:
            self.open_settings.emit()
        elif action == quit_action:
            self.quit_app.emit()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setBrush(self.color)
        painter.setPen(QtGui.QPen(QtCore.Qt.black, 2))
        painter.drawEllipse(0, 0, self.width(), self.height())
