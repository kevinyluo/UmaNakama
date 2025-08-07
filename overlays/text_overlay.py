from PyQt5 import QtWidgets, QtCore, QtGui

class InnerWidget(QtWidgets.QWidget):
    def __init__(self, overlay):
        super().__init__()
        self.overlay = overlay

    def paintEvent(self, event):
        print("InnerWidget paintEvent called")
        self.overlay.paint_inner(event, self)


class TextOverlay(QtWidgets.QScrollArea):
    position_changed = QtCore.pyqtSignal(int, int)

    def __init__(self, position, parsed_skills=None):
        super().__init__()
        self.text_lines = []
        self.parsed_skills = parsed_skills or {}  # Store skills dict
        self.skill_names_lower = [name.lower() for name in self.parsed_skills.keys()]
        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.WindowStaysOnTopHint |
            QtCore.Qt.Tool
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setGeometry(position[0], position[1], 450, 450)

        self.inner_widget = InnerWidget(self)
        self.setWidget(self.inner_widget)
        self.setWidgetResizable(True)

        self.logo = QtGui.QPixmap("assets/UmaNakamaLogoWhite.png")
        self.logo_size = 60

        self.inner_widget.setMouseTracking(True)

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
        if lines != self.text_lines:
            self.text_lines = lines
            self.inner_widget.update()

    def paint_inner(self, event, widget):
        print("paint inner")
        painter = QtGui.QPainter(widget)
        rect = widget.rect()

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
        line_padding = 2
        block_vertical_padding = 6
        line_height = painter.fontMetrics().height() + 5

        title_font = QtGui.QFont("Segoe UI", 14, QtGui.QFont.Bold)
        base_font = QtGui.QFont("Segoe UI", 12)
        label_font = QtGui.QFont("Segoe UI", 12, QtGui.QFont.Bold)

        label_color = QtGui.QColor(255, 255, 255)
        text_color = QtGui.QColor(255, 255, 255)
        highlight_color = QtGui.QColor(39, 218, 245)

        label_col_width = 140
        text_col_start = margin + label_col_width + 10
        y = top_padding

        if not self.logo.isNull():
            scaled_logo = self.logo.scaled(self.logo_size, self.logo_size,
                                           QtCore.Qt.KeepAspectRatio,
                                           QtCore.Qt.SmoothTransformation)
            logo_x = rect.width() - scaled_logo.width() - margin
            logo_y = margin
            painter.drawPixmap(logo_x, logo_y, scaled_logo)

        painter.setFont(title_font)
        painter.setPen(label_color)
        painter.drawText(margin, y, rect.width() - 2 * margin, line_height + line_padding,
                         QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter, self.text_lines[0])
        y += line_height + spacing + line_padding + 20

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

            shadow_rect = QtCore.QRect(margin + 3, y + 3, rect.width() - 2 * margin, block_height)
            painter.setBrush(QtGui.QColor(0, 0, 0, 80))
            painter.setPen(QtCore.Qt.NoPen)
            painter.drawRoundedRect(shadow_rect, 8, 8)

            block_rect = QtCore.QRect(margin, y, rect.width() - 2 * margin, block_height)
            painter.setBrush(QtGui.QColor(56, 56, 56, 230))
            painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255), 1))
            painter.drawRoundedRect(block_rect, 8, 8)

            y_inner = y + block_vertical_padding
            for line in block:
                painter.setFont(base_font)
                metrics = painter.fontMetrics()
                y_baseline = y_inner + metrics.ascent()

                # Default label and content setup
                if ": " in line:
                    label, content = line.split(": ", 1)
                    painter.setFont(label_font)
                    painter.setPen(label_color)
                    painter.drawText(margin + 10, y_inner, label_col_width, line_height + line_padding,
                                    QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter, label)
                    painter.setFont(base_font)
                    text_to_check = content.strip()
                    x = text_col_start
                else:
                    text_to_check = line.strip()
                    x = text_col_start

                # Highlight matching skill name
                content_lower = text_to_check.lower()
                matched_name = None
                for skill_name in self.skill_names_lower:
                    if skill_name in content_lower:
                        matched_name = skill_name
                        break

                if matched_name:
                    i = content_lower.index(matched_name)
                    before = text_to_check[:i]
                    match = text_to_check[i:i + len(matched_name)]
                    after = text_to_check[i + len(matched_name):]

                    painter.setPen(text_color)
                    painter.drawText(x, y_baseline, before)
                    x += metrics.width(before)

                    painter.setPen(highlight_color)
                    painter.drawText(x, y_baseline, match)
                    x += metrics.width(match)

                    painter.setPen(text_color)
                    painter.drawText(x, y_baseline, after)
                else:
                    painter.setPen(text_color)
                    painter.drawText(x, y_baseline, text_to_check)

                y_inner += line_height + line_padding

            y += block_height + spacing

        y += bottom_padding
        self.inner_widget.setMinimumHeight(y)
