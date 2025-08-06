from PyQt5 import QtWidgets, QtCore, QtGui

class TextOverlay(QtWidgets.QScrollArea):
    position_changed = QtCore.pyqtSignal(int, int)

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

        self.logo = QtGui.QPixmap("assets/UmaNakamaLogoWhite.png")
        self.logo_size = 60  # Adjust as needed


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

        # --- Draw Logo on Top Right ---
        if not self.logo.isNull():
            scaled_logo = self.logo.scaled(self.logo_size, self.logo_size, 
                                        QtCore.Qt.KeepAspectRatio, 
                                        QtCore.Qt.SmoothTransformation)
            logo_x = rect.width() - scaled_logo.width() - margin
            logo_y = margin
            painter.drawPixmap(logo_x, logo_y, scaled_logo)

        # --- Event Title ---
        painter.setFont(title_font)
        painter.setPen(label_color)
        painter.drawText(margin, y, rect.width() - 2 * margin, line_height + line_padding,
                        QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter, self.text_lines[0])
        
        y += line_height + spacing + line_padding + 20  # Extra spacing below title

        # --- Build option blocks ---
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

        for block in blocks:
            block_height = ((line_height + line_padding) * len(block)) + (2 * block_vertical_padding)

            # Drop shadow
            shadow_rect = QtCore.QRect(margin + 3, y + 3, rect.width() - 2 * margin, block_height)
            painter.setBrush(QtGui.QColor(0, 0, 0, 80))
            painter.setPen(QtCore.Qt.NoPen)
            painter.drawRoundedRect(shadow_rect, 8, 8)

            # Main block
            block_rect = QtCore.QRect(margin, y, rect.width() - 2 * margin, block_height)
            painter.setBrush(QtGui.QColor(56, 56, 56, 230))
            painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255), 1))
            painter.drawRoundedRect(block_rect, 8, 8)

            y_inner = y + block_vertical_padding
            for line in block:
                if ": " in line:
                    label, content = line.split(": ", 1)
                    painter.setFont(label_font)
                    painter.setPen(label_color)
                    painter.drawText(margin + 10, y_inner, label_col_width, line_height + line_padding,
                                    QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter, label)

                    painter.setFont(base_font)
                    painter.setPen(text_color)
                    painter.drawText(text_col_start, y_inner, rect.width() - text_col_start - margin, line_height + line_padding,
                                    QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter, content)
                else:
                    painter.setFont(base_font)
                    painter.setPen(text_color)
                    painter.drawText(text_col_start, y_inner, rect.width() - text_col_start - margin, line_height + line_padding,
                                    QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter, line)

                y_inner += line_height + line_padding

            y += block_height + spacing

        y += bottom_padding
        self.inner_widget.setMinimumHeight(y)
