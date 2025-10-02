"""
Event text HUD overlay.

Responsibilities
- Always-on-top, semi-transparent widget rendering the matched event title and option
  effects as multi-line text. Designed to be readable without stealing focus.
- Supports drag-to-move and emits `position_changed(x, y)` so callers can persist the
  location relative to the game window.
- Dynamically resizes HEIGHT up to MAX_HEIGHT and WIDTH between MIN_WIDTH..MAX_WIDTH.
  Vertical scrollbar appears only if height exceeds MAX_HEIGHT.

Notes
- Update only from the main thread via signals to avoid race conditions.
- Wide lines are elided once width hits MAX_WIDTH so nothing draws past the edge.
"""

from PyQt5 import QtWidgets, QtCore, QtGui


class InnerWidget(QtWidgets.QWidget):
    """Canvas inside the scroll area; delegates actual painting back to the overlay."""
    def __init__(self, overlay):
        super().__init__()
        self.overlay = overlay
        # Let the background show through rounded corners
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

    def paintEvent(self, event):
        self.overlay.paint_inner(event, self)


class TextOverlay(QtWidgets.QScrollArea):
    position_changed = QtCore.pyqtSignal(int, int)
    moving = QtCore.pyqtSignal(int, int, int, int) 

    def __init__(
        self,
        position,
        parsed_skills=None,
        min_width=420,
        max_width=900,
        max_height=600,
        min_height=140,
    ):
        super().__init__()
        self.text_lines = []
        self.parsed_skills = parsed_skills or {}
        self.skill_names_lower = [name.lower() for name in self.parsed_skills.keys()]

        # Sizing policy
        self._min_width = int(min_width)
        self._max_width = int(max_width)
        self._max_height = int(max_height)
        self._min_height = int(min_height)
        self._last_applied_height = 0
        self._last_applied_width = 0

        # Window/appearance
        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint
            | QtCore.Qt.WindowStaysOnTopHint
            | QtCore.Qt.Tool
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.viewport().setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)

        # Scrollbars: horizontal OFF, vertical only when needed
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)

        # Initial bounds
        self.setGeometry(position[0], position[1], self._min_width, self._min_height)
        self.setFixedWidth(self._min_width)

        # Inner canvas
        self.inner_widget = InnerWidget(self)
        self.setWidget(self.inner_widget)
        self.setWidgetResizable(True)

        # Assets
        self.logo = QtGui.QPixmap("assets/UmaNakamaLogoWhite.png")
        self.logo_size = 60

        # Drag state + event filtering (drag on viewport or inner both work)
        self._drag_pos = None
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self.inner_widget.setMouseTracking(True)
        self.viewport().installEventFilter(self)
        self.inner_widget.installEventFilter(self)

        self.show()

    # ---------- Drag handling via event filter (works for viewport/inner) ----------
    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.MouseButtonPress and event.button() == QtCore.Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
            return True

        if event.type() == QtCore.QEvent.MouseMove and self._drag_pos and (event.buttons() & QtCore.Qt.LeftButton):
            self.move(event.globalPos() - self._drag_pos)
            event.accept()
            return True

        if event.type() == QtCore.QEvent.MouseButtonRelease and event.button() == QtCore.Qt.LeftButton:
            if self._drag_pos:
                self._drag_pos = None
                self.position_changed.emit(self.x(), self.y())
                event.accept()
                return True

        return super().eventFilter(obj, event)
    
    def moveEvent(self, event: QtGui.QMoveEvent):
        super().moveEvent(event)
        self.moving.emit(self.x(), self.y(), self.width(), self.height())

    def resizeEvent(self, event: QtGui.QResizeEvent):
        super().resizeEvent(event)
        self.moving.emit(self.x(), self.y(), self.width(), self.height())

    # (Keep these in case something else calls them directly)
    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & QtCore.Qt.LeftButton:
            self.move(event.globalPos() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        if self._drag_pos:
            self._drag_pos = None
            self.position_changed.emit(self.x(), self.y())

    # ---------- Public API ----------
    def update_text(self, lines):
        """Replace overlay content; triggers repaint if changed."""
        if lines != self.text_lines:
            self.text_lines = lines
            self.inner_widget.update()

    # ---------- Internal: dynamic size ----------
    def _apply_dynamic_height(self, content_height: int):
        """Adjust the scroll area height (cap at max_height)."""
        desired = max(self._min_height, min(self._max_height, content_height))
        if desired != self._last_applied_height:
            self._last_applied_height = desired
            self.setFixedHeight(desired)

    def _apply_dynamic_width(self, content_width: int):
        """Adjust the scroll area width (clamp between min_width and max_width)."""
        desired = max(self._min_width, min(self._max_width, content_width))
        if desired != self._last_applied_width:
            self._last_applied_width = desired
            self.setFixedWidth(desired)

    # Measure the natural width needed for current content (no wrapping),
    # including margins and label column.
    def _measure_natural_width(self, painter: QtGui.QPainter, rect: QtCore.QRect) -> int:
        margin = 15
        label_col_width = 140
        gap = 10  # between label col and content
        title_font = QtGui.QFont("Segoe UI", 14, QtGui.QFont.Bold)
        base_font = QtGui.QFont("Segoe UI", 12)

        max_px = 0

        # Title width (no wrapping for measurement — we allow widening instead)
        painter.setFont(title_font)
        tm = painter.fontMetrics()
        if self.text_lines:
            title_text = self.text_lines[0]
            max_px = max(max_px, 2 * margin + tm.horizontalAdvance(title_text))

        # Body width: label col + content
        painter.setFont(base_font)
        bm = painter.fontMetrics()
        text_start_x = margin + label_col_width + gap

        for line in self.text_lines[1:]:
            if ": " in line:
                label, content = line.split(": ", 1)
                content_w = bm.horizontalAdvance(content.strip())
                total = margin + label_col_width + gap + content_w + margin
            else:
                content_w = bm.horizontalAdvance(line.strip())
                total = text_start_x + content_w + margin
            max_px = max(max_px, total)

        # Never return less than min width
        return max(self._min_width, int(max_px))

    # ---------- Painting ----------
    def paint_inner(self, event, widget: QtWidgets.QWidget):
        painter = QtGui.QPainter(widget)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)

        # Before drawing, compute and apply dynamic WIDTH from content
        natural_width = self._measure_natural_width(painter, widget.rect())
        self._apply_dynamic_width(natural_width)

        rect = widget.rect()

        # Background panel
        painter.setBrush(QtGui.QColor(46, 46, 46, 250))
        painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255), 1))
        painter.drawRoundedRect(rect, 8, 8)

        if not self.text_lines:
            # Keep inner minimum height aligned with outer min to avoid tiny panel flicker
            self.inner_widget.setMinimumHeight(self._min_height)
            self._apply_dynamic_height(self._min_height)
            return

        margin = 15
        spacing = 8
        top_padding = 40
        bottom_padding = 40
        line_padding = 2
        block_vertical_padding = 6

        # Fonts/colors
        title_font = QtGui.QFont("Segoe UI", 14, QtGui.QFont.Bold)
        base_font = QtGui.QFont("Segoe UI", 12)
        label_font = QtGui.QFont("Segoe UI", 12, QtGui.QFont.Bold)

        label_color = QtGui.QColor(255, 255, 255)
        text_color = QtGui.QColor(255, 255, 255)
        highlight_color = QtGui.QColor(39, 218, 245)

        label_col_width = 140
        gap = 10
        text_col_start = margin + label_col_width + gap
        y = top_padding

        # Logo (optional)
        if not self.logo.isNull():
            scaled_logo = self.logo.scaled(
                self.logo_size,
                self.logo_size,
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation,
            )
            logo_x = rect.width() - scaled_logo.width() - margin
            logo_y = margin
            painter.drawPixmap(logo_x, logo_y, scaled_logo)

        # ----- Dynamic, wrapped TITLE (prevents cut off on 2+ lines) -----
        painter.setFont(title_font)
        painter.setPen(label_color)
        title_text = self.text_lines[0]

        # Title wraps within current width; use boundingRect with TextWordWrap
        title_area = QtCore.QRect(
            margin,
            y,
            rect.width() - 2 * margin,
            10_000,
        )
        title_flags = QtCore.Qt.TextWordWrap | QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop

        title_metrics = painter.fontMetrics()
        title_bound = title_metrics.boundingRect(title_area, title_flags, title_text)
        painter.drawText(title_bound, title_flags, title_text)

        y = title_bound.bottom() + 1 + spacing + 12

        # Group following lines into blocks by the presence of ": " labels
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

        # Body: use lineSpacing() to ensure descenders never clip
        painter.setFont(base_font)
        line_metrics = painter.fontMetrics()
        line_height = line_metrics.lineSpacing()  # includes ascent+descent+leading

        # Available width for content text (right column)
        avail_content_w = rect.width() - text_col_start - margin

        for block in blocks:
            block_height = ((line_height + line_padding) * len(block)) + (2 * block_vertical_padding)

            # Shadow
            shadow_rect = QtCore.QRect(margin + 3, y + 3, rect.width() - 2 * margin, block_height)
            painter.setBrush(QtGui.QColor(0, 0, 0, 80))
            painter.setPen(QtCore.Qt.NoPen)
            painter.drawRoundedRect(shadow_rect, 8, 8)

            # Card
            block_rect = QtCore.QRect(margin, y, rect.width() - 2 * margin, block_height)
            painter.setBrush(QtGui.QColor(56, 56, 56, 230))
            painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255), 1))
            painter.drawRoundedRect(block_rect, 8, 8)

            y_inner = y + block_vertical_padding
            for raw in block:
                content_text = raw.strip()
                x = text_col_start

                # Optional label cell
                if ": " in raw:
                    label, content = raw.split(": ", 1)
                    painter.setFont(label_font)
                    painter.setPen(label_color)
                    painter.drawText(
                        margin + 10,
                        y_inner,
                        label_col_width,
                        line_height + line_padding,
                        QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
                        label,
                    )
                    painter.setFont(base_font)
                    painter.setPen(text_color)
                    content_text = content.strip()

                # Skill-name highlighting + ELISION when needed
                content_lower = content_text.lower()
                matched_name = None
                for skill_name in self.skill_names_lower:
                    if skill_name in content_lower:
                        matched_name = skill_name
                        break

                baseline = y_inner + line_metrics.ascent()
                full_w = line_metrics.horizontalAdvance(content_text)

                if matched_name:
                    i = content_lower.index(matched_name)
                    before = content_text[:i]
                    match = content_text[i : i + len(matched_name)]
                    after = content_text[i + len(matched_name) :]

                    before_w = line_metrics.horizontalAdvance(before)
                    match_w = line_metrics.horizontalAdvance(match)

                    # If even before+match exceed avail, elide everything simply
                    if before_w + match_w > avail_content_w:
                        elided = line_metrics.elidedText(content_text, QtCore.Qt.ElideRight, avail_content_w)
                        painter.setPen(text_color)
                        painter.drawText(x, baseline, elided)
                    else:
                        painter.setPen(text_color)
                        painter.drawText(x, baseline, before)
                        x += before_w

                        painter.setPen(highlight_color)
                        painter.drawText(x, baseline, match)
                        x += match_w

                        # Elide only the "after" tail if needed
                        remain = avail_content_w - (before_w + match_w)
                        if remain < 0:
                            remain = 0
                        painter.setPen(text_color)
                        tail = line_metrics.elidedText(after, QtCore.Qt.ElideRight, remain)
                        painter.drawText(x, baseline, tail)
                else:
                    # No highlight; draw with elision if needed
                    if full_w > avail_content_w:
                        elided = line_metrics.elidedText(content_text, QtCore.Qt.ElideRight, avail_content_w)
                        painter.setPen(text_color)
                        painter.drawText(x, baseline, elided)
                    else:
                        painter.setPen(text_color)
                        painter.drawText(x, baseline, content_text)

                y_inner += line_height + line_padding

            y += block_height + spacing

        y += bottom_padding

        # Compute full content height & apply dynamic height cap
        total_content_height = int(y + line_metrics.descent() + 2)
        self.inner_widget.setMinimumHeight(total_content_height)
        self._apply_dynamic_height(total_content_height)
