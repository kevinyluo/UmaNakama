from PyQt5 import QtWidgets, QtCore, QtGui
import requests

class SkillInfoOverlay(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.WindowStaysOnTopHint |
            QtCore.Qt.Tool
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
                color: #e0e0e0;
                border: 1px solid #444;
                border-radius: 10px;
                font-size: 14px;
            }
            QLabel {
                font-size: 14px;
                background-color: transparent;
                border: none;
            }
            QLabel#title {
                font-weight: bold;
                font-size: 16px;
                color: #27DAF5;
            }
        """)

        self.setGeometry(0, 0, 350, 300)

        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(5, 0, 5, 0)

        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)

        self.inner_widget = QtWidgets.QWidget()
        self.inner_layout = QtWidgets.QVBoxLayout(self.inner_widget)
        self.inner_layout.setContentsMargins(5, 5, 5, 5)
        self.inner_layout.setSpacing(0)

        self.scroll_area.setWidget(self.inner_widget)
        self.layout.addWidget(self.scroll_area)
        self.setVisible(False)

    def set_text(self, skill_data_list):
        for i in reversed(range(self.inner_layout.count())):
            widget = self.inner_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        for index, (name, skill_data) in enumerate(skill_data_list):
            container = QtWidgets.QWidget()
            container.setStyleSheet("border: none;")
            container_layout = QtWidgets.QVBoxLayout(container)
            container_layout.setContentsMargins(5, 5, 5, 5) #margin between the overlay and the containers inside
            container_layout.setSpacing(0)  # Spacing between containers


            # Top row: image + name
            top_row = QtWidgets.QHBoxLayout()
            image_label = QtWidgets.QLabel()
            image_label.setAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft)
            image_label.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)

            img_url = "https://gametora.com" + skill_data.get("img_src", "")
            try:
                response = requests.get(img_url)
                img = QtGui.QPixmap()
                img.loadFromData(response.content)

                # crop the image
                cropped = img.copy(3, 3, img.width()-6, img.height()-6)

                # Create rounded corners
                radius = 6
                rounded = QtGui.QPixmap(cropped.size())
                rounded.fill(QtCore.Qt.transparent)

                painter = QtGui.QPainter(rounded)
                painter.setRenderHint(QtGui.QPainter.Antialiasing)
                path = QtGui.QPainterPath()
                path.addRoundedRect(0, 0, cropped.width(), cropped.height(), radius, radius)
                painter.setClipPath(path)
                painter.drawPixmap(0, 0, cropped)
                painter.end()

                image_label.setPixmap(rounded.scaled(50, 50, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))



            except Exception:
                image_label.setText("[Image failed]")

            name_label = QtWidgets.QLabel(name)
            name_label.setObjectName("title")
            name_label.setAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft)

            top_row.addWidget(image_label)
            top_row.addSpacing(10)
            top_row.addWidget(name_label)
            top_row.addStretch()
            top_row_widget = QtWidgets.QWidget()
            top_row_widget.setLayout(top_row)
            top_row_layout = QtWidgets.QHBoxLayout()
            top_row_layout.setContentsMargins(0, 0, 0, 0)
            top_row_layout.addStretch()
            top_row_layout.addWidget(top_row_widget)
            top_row_layout.addStretch()


            container_layout.addLayout(top_row_layout)


            def add_field(label_text, value_text, color="#ccc"):
                if not value_text:
                    return
                label = QtWidgets.QLabel(
                    f"<span style='font-weight:bold; color:#ccc'>{label_text}</span> "
                    f"<span style='color:{color}'>{value_text}</span>"
                )
                label.setWordWrap(True)
                container_layout.addWidget(label)


            add_field("Description (in-game):", skill_data.get("description_game", ""))
            add_field("Description (detailed):", skill_data.get("description_detailed", ""))
            add_field("Rarity:", skill_data.get("rarity", ""))
            add_field("Activation:", skill_data.get("activation", ""))
            add_field("Base cost:", skill_data.get("base_cost", ""))
            add_field("Conditions:", skill_data.get("conditons", ""), color='#ff8800')
            add_field("Base duration:", skill_data.get("base_duration", ""))
            add_field("Effect:", skill_data.get("effect", ""))

            self.inner_layout.addWidget(container)

            # Add horizontal separator (except after last)
            if index < len(skill_data_list) - 1:
                line = QtWidgets.QFrame()
                line.setFrameShape(QtWidgets.QFrame.HLine)
                line.setFrameShadow(QtWidgets.QFrame.Sunken)
                line.setStyleSheet("color: #444;")
                self.inner_layout.addWidget(line)

        self.adjust_overlay_height()

    def adjust_overlay_height(self):
        QtCore.QTimer.singleShot(50, self._finalize_height)

    def _finalize_height(self):
        self.inner_widget.adjustSize()
        content_height = self.inner_widget.sizeHint().height()
        new_height = min(content_height + 30, 700)
        self.setFixedHeight(new_height)
