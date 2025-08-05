from PyQt5 import QtWidgets, QtCore, QtGui

class TextOverlay(QtWidgets.QScrollArea):
    position_changed = QtCore.pyqtSignal(int, int)  # Signal for postion change

    def __init__(self, position):
        super().__init__()
        self.text_lines = []
        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.WindowStaysOnTopHint |
            QtCore.Qt.Tool
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setGeometry(position[0], position[1], 450, 450)

        self.inner_widget = QtWidgets.QWidget()
        self.setWidget(self.inner_widget)
        self.setWidgetResizable(True)

        self.inner_widget.paintEvent = self.paint_inner
        self.show()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.drag_pos = event.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self.drag_pos and event.buttons() & QtCore.Qt.LeftButton:
            self.move(event.globalPos() - self.drag_pos)

    def mouseReleaseEvent(self, event):
        self.drag_pos = None

    def update_text(self, lines):
        self.text_lines = lines
        self.inner_widget.update()

    def paint_inner(self, event):
        painter = QtGui.QPainter(self.inner_widget)
        rect = self.inner_widget.rect()

        painter.setBrush(QtGui.QColor(46, 46, 46, 240))
        painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255), 1))
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.drawRoundedRect(rect, 8, 8)

        if not self.text_lines:
            return

        margin = 15
        spacing = 8
        top_padding = 40
        bottom_padding = 40
        line_padding = 6
        block_vertical_padding = 6
        line_height = painter.fontMetrics().height()

        title_font = QtGui.QFont("Segoe UI", 14, QtGui.QFont.Bold)
        base_font = QtGui.QFont("Segoe UI", 12)
        label_font = QtGui.QFont("Segoe UI", 12, QtGui.QFont.Bold)

        label_color = QtGui.QColor(255, 255, 255)
        text_color = QtGui.QColor(255, 255, 255)

        label_col_width = 140
        text_col_start = margin + label_col_width + 10

        y = top_padding
        painter.setFont(title_font)
        painter.setPen(label_color)
        painter.drawText(margin, y, rect.width() - 2 * margin, line_height + line_padding,
                         QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter, self.text_lines[0])
        y += line_height + spacing + line_padding

        blocks = []
        current_block = []
        for line in self.text_lines[1:]:
            if ": " in line and current_block:
                blocks.append(current_block)
                current_block = [line]
            else:
                current_block.append(line)
        if current_block:
            blocks.append(current_block)

        for idx, block in enumerate(blocks):
            bg_color = QtGui.QColor(56, 56, 56, 230) if idx % 2 == 0 else QtGui.QColor(66, 66, 66, 230)
            block_height = ((line_height + line_padding) * len(block)) + (2 * block_vertical_padding)

            block_x = margin - 5 # Left margin
            block_width = rect.width() - 2 * margin + 10 # Right margin
            painter.fillRect(block_x, y, block_width, block_height, bg_color)

            y += block_vertical_padding
            for line in block:
                if ": " in line:
                    label, content = line.split(": ", 1)
                    painter.setFont(label_font)
                    painter.setPen(label_color)
                    painter.drawText(margin, y, label_col_width, line_height + line_padding,
                                     QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter, label)

                    painter.setFont(base_font)
                    painter.setPen(text_color)
                    painter.drawText(text_col_start, y, rect.width() - text_col_start - margin, line_height + line_padding,
                                     QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter, content)
                else:
                    painter.setFont(base_font)
                    painter.setPen(text_color)
                    painter.drawText(text_col_start, y, rect.width() - text_col_start - margin, line_height + line_padding,
                                     QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter, line)

                y += line_height + line_padding

            y += block_vertical_padding

            if idx < len(blocks) - 1:
                painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255), 2))
                painter.drawLine(0, y, rect.width(), y)
                y += spacing

        y += bottom_padding
        self.inner_widget.setMinimumHeight(y)