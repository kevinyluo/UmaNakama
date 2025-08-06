from PyQt5 import QtWidgets, QtCore, QtGui

ICON_SIZE = 100

class StatusOverlay(QtWidgets.QWidget):
    toggle_scanning = QtCore.pyqtSignal()
    quit_app = QtCore.pyqtSignal()
    position_changed = QtCore.pyqtSignal(int, int)
    open_settings = QtCore.pyqtSignal()

    def __init__(self, position=(50, 50), is_scanning=True):
        super().__init__()
        self.drag_pos = None
        self.is_scanning = is_scanning

        # Load icons
        self.icon_running = QtGui.QPixmap("assets/companionRunning.PNG").scaled(
            ICON_SIZE, ICON_SIZE, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation
        )
        self.icon_paused = QtGui.QPixmap("assets/companionPaused.png").scaled(
            ICON_SIZE, ICON_SIZE, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation
        )

        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.WindowStaysOnTopHint |
            QtCore.Qt.Tool
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setGeometry(position[0], position[1], ICON_SIZE, ICON_SIZE)
        self.setToolTip("UmaNakama Status")
        self.show()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.drag_pos = event.globalPos() - self.frameGeometry().topLeft()
        elif event.button() == QtCore.Qt.RightButton:
            self.show_context_menu(event.globalPos())

    def mouseMoveEvent(self, event):
        if self.drag_pos and event.buttons() & QtCore.Qt.LeftButton:
            self.move(event.globalPos() - self.drag_pos)

    def mouseDoubleClickEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.is_scanning = not self.is_scanning
            self.toggle_scanning.emit()
            self.update()


    def mouseReleaseEvent(self, event):
        self.drag_pos = None
        # self.position_changed.emit(self.x(), self.y())  # Save position on release

    def show_context_menu(self, pos):
        """Unified context menu for pause/resume, open settings, save location, quit."""
        menu = QtWidgets.QMenu(self)
        toggle_action = menu.addAction("Pause Scanning" if self.is_scanning else "Resume Scanning")
        settings_action = menu.addAction("Open Settings")
        save_location_action = menu.addAction("Save Status Location")
        quit_action = menu.addAction("Quit App")

        action = menu.exec_(self.mapToGlobal(self.rect().bottomLeft()))

        if action == toggle_action:
            self.is_scanning = not self.is_scanning
            self.toggle_scanning.emit()
            self.update()
        elif action == settings_action:
            self.open_settings.emit()
        elif action == save_location_action:
            self.save_status_location()
        elif action == quit_action:
            self.quit_app.emit()

    def save_status_location(self):
        """Emit a signal to save current location."""
        self.position_changed.emit(self.x(), self.y())

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        # ✅ Choose the icon based on status
        icon = self.icon_running if self.is_scanning else self.icon_paused
        painter.drawPixmap(0, 0, icon)
