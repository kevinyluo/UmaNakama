"""
Condition keywords overlay.

Responsibilities
- Shows human-readable explanations for any condition keywords detected in the
  currently matched skills (from `events/conditions.json`).
- Stacks to the right of the skill overlay so the user can glance across all
  relevant info in a single line.

Notes
- Only visible when at least one keyword is present and the viewer isn’t hidden.
- Keep content purely informative—no interactions—to reduce cognitive load mid-run.
"""


from PyQt5 import QtWidgets, QtCore, QtGui
import html

class ConditionInfoOverlay(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.WindowStaysOnTopHint |
            QtCore.Qt.Tool
        )
        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
                color: #e0e0e0;
                border: 1px solid #444;
                border-radius: 10px;
                font-size: 14px;
            }
            QLabel {
                background-color: transparent;
                border: none;
                font-size: 14px;
            }
            QLabel#title {
                font-weight: bold;
                font-size: 16px;
                color: #27DAF5;
            }
        """)

        self.setMinimumSize(250, 100)
        self.setMaximumSize(350, 600)  # allow tall content but clip if needed

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(0)

        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        main_layout.addWidget(self.scroll_area)

        self.container = QtWidgets.QWidget()
        self.container_layout = QtWidgets.QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(10, 10, 10, 10)
        self.container_layout.setSpacing(8)
        self.scroll_area.setWidget(self.container)
        self._last_conditions = []
        self.setVisible(False)

    def set_text(self, conditions_list):
        # If same content, keep scroll position
        is_same = conditions_list == self._last_conditions
        self._last_conditions = conditions_list.copy()

        scroll_value = self.scroll_area.verticalScrollBar().value() if is_same else 0

        # Clear old widgets
        for i in reversed(range(self.container_layout.count())):
            widget = self.container_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        # Add new content
        for keyword, data in conditions_list:
            example_html = html.escape(data['example'])  # Escapes <, >, &
            label = QtWidgets.QLabel(
                f"<b style='color:#ffa500'>{data.get('expression', keyword)}</b><br>"
                f"<b>Description:</b> {data['description']}<br>"
                f"<b>Example:</b> {example_html}<br>"
                f"<b>Meaning:</b> {data['meaning']}<br><br>"
            )

            label.setWordWrap(True)
            self.container_layout.addWidget(label)

        self.container.adjustSize()
        self.adjustSize()

        # Restore scroll only if content is same
        QtCore.QTimer.singleShot(0, lambda: self.scroll_area.verticalScrollBar().setValue(scroll_value))

