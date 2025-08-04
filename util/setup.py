import sys
import pyperclip
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore import Qt, QRect, QPoint
from PyQt5.QtGui import QPainter, QColor

class RegionSelector(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Select Screen Region")
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.setWindowState(Qt.WindowFullScreen)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.origin = QPoint()
        self.current = QPoint()
        self.rubberBandActive = False

    def paintEvent(self, event):
        if self.rubberBandActive:
            painter = QPainter(self)
            painter.setPen(QColor(0, 180, 255))
            painter.setBrush(QColor(0, 180, 255, 50))
            rect = QRect(self.origin, self.current)
            painter.drawRect(rect.normalized())

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.origin = event.pos()
            self.current = event.pos()
            self.rubberBandActive = True
            self.update()

    def mouseMoveEvent(self, event):
        if self.rubberBandActive:
            self.current = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.rubberBandActive = False
            self.current = event.pos()
            rect = QRect(self.origin, self.current).normalized()
            left = rect.left()
            top = rect.top()
            width = rect.width()
            height = rect.height()

            region = (left, top, width, height)
            print("Selected region:", region)

            pyperclip.copy(str(region))
            print("Copied to clipboard!")

            self.close()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    selector = RegionSelector()
    selector.show()
    sys.exit(app.exec_())
