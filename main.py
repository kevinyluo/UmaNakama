import sys
import pytesseract
import pyautogui
import keyboard
import difflib
import json
import time
import os
from PIL import ImageEnhance, ImageOps
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtWidgets import QSplashScreen
from PyQt5.QtGui import QPixmap
import threading
import pygetwindow as gw
import cv2
import numpy as np
from overlays.text_overlay import TextOverlay
from overlays.region_overlay import RegionSelector
from overlays.status_overlay import StatusOverlay
from overlays.settings_overlay import SettingsOverlay
import Levenshtein


# ---------------- Global Variables ----------------
settings_overlay_pos = (500, 200)
settings_overlay = None
selector = None

CONFIG_FILE = "config.json"
default_config = {
    "region": {"x_offset": 596, "y_offset": 382, "width": 355, "height": 74},
    "overlay_position": {"x_offset": 1200, "y_offset": 400},
    "status_position": {"x_offset": 50, "y_offset": 50},
    "scan_speed": 0.5,
    "scanning_enabled": False,
    "text_match_confidence": 0.7,
    "debug_mode": False,
    "always_show_overlay": False   # ✅ New toggle
}

class AppController(QtCore.QObject):
    open_settings_signal = QtCore.pyqtSignal()
    open_region_selector_signal = QtCore.pyqtSignal()

controller = AppController()

# ---------------- CONFIG HANDLING ----------------
def load_config():
    if not os.path.exists(CONFIG_FILE):
        save_config(default_config)
        return default_config.copy()

    config = default_config.copy()
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            loaded = json.load(f)

            for key in ["region", "overlay_position", "status_position"]:
                if key in loaded and "x" in loaded[key]:
                    loaded[key]["x_offset"] = loaded[key].pop("x")
                    loaded[key]["y_offset"] = loaded[key].pop("y")

            for key, value in default_config.items():
                if key not in loaded:
                    loaded[key] = value
            config.update(loaded)
            save_config(config)
    except Exception as e:
        print(f"Error loading config file: {e}")
        save_config(default_config)
        return default_config.copy()
    return config

def save_config(config):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        print(f"Error saving config file: {e}")

config = load_config()
scanning_enabled = config.get("scanning_enabled", False)

# ---------------- OCR CONFIG ----------------
pytesseract.pytesseract.tesseract_cmd = r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"

# ---------------- HELPERS ----------------
def get_umamusume_window():
    try:
        windows = gw.getWindowsWithTitle("Umamusume")
        if windows:
            win = windows[0]
            if win.isMinimized:
                return None
            return win
    except Exception as e:
        print(f"Error finding Umamusume window: {e}")
    return None

def get_absolute_region():
    win = get_umamusume_window()
    if not win:
        return (
            config["region"]["x_offset"],
            config["region"]["y_offset"],
            config["region"]["width"],
            config["region"]["height"]
        )
    return (
        win.left + config["region"]["x_offset"],
        win.top + config["region"]["y_offset"],
        config["region"]["width"],
        config["region"]["height"]
    )

# ---------------- EVENT MATCHING ----------------
def load_events(category):
    filename = os.path.join("events", f"{category}_events.json")
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {filename}: {e}")
        return {}

def find_best_match(event_line, category):
    if len(event_line) < 4:
        return None, None
    
    events = load_events(category)
    candidates = list(events.keys())
    confidence = config.get("text_match_confidence", 0.7)

    special_events = ["inspiration", "summer camp"]
    if any(special_event in event_line.lower() for special_event in special_events):
        confidence = 0.95

    matches = difflib.get_close_matches(event_line, candidates, n=1, cutoff=confidence)
    if matches:
        event_name = matches[0]
        return event_name, events[event_name]
    return None, None

# ---------------- OCR FUNCTION ----------------
def read_text_from_screen(text_overlay):
    screenshot = pyautogui.screenshot(region=get_absolute_region())
    gray = screenshot.convert("L")
    inverted = ImageOps.invert(gray)
    enhancer = ImageEnhance.Contrast(inverted)
    high_contrast = enhancer.enhance(1.0)
    thresholded = high_contrast.point(lambda x: 0 if x < 50 else 255, mode='1')

    text = pytesseract.image_to_string(thresholded, config="--psm 6").strip()
    lines = [line.replace("|", "").strip() for line in text.split('\n') if line.strip()]

    if len(lines) < 2:
        if not config.get("always_show_overlay", False):
            text_overlay.hide()
        return

    category_line = lines[0].lower()
    event_line = lines[1]
    if "trainee" in category_line:
        category = "trainee"
    elif "support" in category_line:
        category = "support"
    else:
        if not config.get("always_show_overlay", False):
            text_overlay.hide()
        return

    event_name, event_options = find_best_match(event_line, category)
    if event_name:
        overlay_lines = [event_name]
        for option, effect in event_options.items():
            effect_lines = effect.split('\n')
            overlay_lines.append(f"{option}: {effect_lines[0]}")
            for extra in effect_lines[1:]:
                overlay_lines.append(extra)
        text_overlay.update_text(overlay_lines)
        text_overlay.show()
    else:
        if not config.get("always_show_overlay", False):
            text_overlay.hide()

# ---------------- CONTINUOUS SCAN ----------------
def continuous_scan(text_overlay, stop_event, status_overlay):
    global scanning_enabled
    while not stop_event.is_set():
        if scanning_enabled:
            read_text_from_screen(text_overlay)
            status_overlay.is_scanning = True
            status_overlay.update()             
        else:
            if not config.get("always_show_overlay", False):
                text_overlay.hide()
            status_overlay.is_scanning = False
            status_overlay.update()
        time.sleep(config.get("scan_speed", 0.5))

# ---------------- REGION SELECTOR ----------------
def save_region_from_selector():
    global REGION
    new_region = (selector.x(), selector.y(), selector.width(), selector.height())
    win = get_umamusume_window()
    if win:
        config["region"] = {
            "x_offset": new_region[0] - win.left,
            "y_offset": new_region[1] - win.top,
            "width": new_region[2],
            "height": new_region[3]
        }
    else:
        config["region"] = {
            "x_offset": new_region[0],
            "y_offset": new_region[1],
            "width": new_region[2],
            "height": new_region[3]
        }
    save_config(config)
    print(f"Region updated: {get_absolute_region()}")

# ---------------- SETTINGS TOGGLE ----------------
def toggle_settings():
    global settings_overlay, settings_overlay_pos
    if settings_overlay and settings_overlay.isVisible():
        settings_overlay_pos = (settings_overlay.x(), settings_overlay.y())
        save_region_from_selector()
        settings_overlay.close_overlay()
        selector.hide()
        settings_overlay = None
        print("Settings & Region selector closed. Changes saved.")
        return

    settings_overlay = SettingsOverlay(config, save_config, settings_overlay_pos)
    settings_overlay.closed.connect(lambda: print("Settings overlay closed"))
    settings_overlay.show()

    win = get_umamusume_window()
    if win:
        selector.setGeometry(*get_absolute_region())
        selector.show()
        print("Settings & Region selector opened.")
    else:
        print("Umamusume window not found. Region selector not shown.")

controller.open_settings_signal.connect(toggle_settings)

# ---------------- Debugging ----------------
def show_thresholded_image():
    if not config.get("debug_mode", False):
        print("Debug mode is disabled.")
        return

    screenshot = pyautogui.screenshot(region=get_absolute_region())
    gray = screenshot.convert("L")
    inverted = ImageOps.invert(gray)
    enhancer = ImageEnhance.Contrast(inverted)
    high_contrast = enhancer.enhance(1.0)
    thresholded = high_contrast.point(lambda x: 0 if x < 50 else 255, mode='1')

    text = pytesseract.image_to_string(thresholded, config="--psm 6").strip()
    lines = [line.replace("|", "").strip() for line in text.split('\n') if line.strip()]

    print(f"Raw text is: {text}")
    print(f"Processed text is: {lines}")

    cv_img = cv2.cvtColor(np.array(thresholded.convert("L")), cv2.COLOR_GRAY2BGR)
    cv2.imshow("Thresholded OCR Image", cv_img)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

# ---------------- Splash Screen ----------------
def show_splash(app):
    splash_pix = QPixmap("assets/UmaNakamaLoading.PNG")
    scaled_pix = splash_pix.scaled(400, 300, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)

    splash = QSplashScreen(scaled_pix)
    splash.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint)

    screen_geometry = app.primaryScreen().geometry()
    splash.move(
        screen_geometry.center().x() - splash.width() // 2,
        screen_geometry.center().y() - splash.height() // 2
    )

    opacity_effect = QtWidgets.QGraphicsOpacityEffect()
    splash.setGraphicsEffect(opacity_effect)

    fade_in = QtCore.QPropertyAnimation(opacity_effect, b"opacity")
    fade_in.setDuration(800)
    fade_in.setStartValue(0)
    fade_in.setEndValue(1)

    fade_out = QtCore.QPropertyAnimation(opacity_effect, b"opacity")
    fade_out.setDuration(800)
    fade_out.setStartValue(1)
    fade_out.setEndValue(0)

    splash.show()
    fade_in.start()

    QtCore.QTimer.singleShot(2000, fade_out.start)

    loop = QtCore.QEventLoop()
    QtCore.QTimer.singleShot(2800, loop.quit)
    loop.exec_()

    splash.close()

# ---------------- MAIN ----------------
def main():
    global scanning_enabled, selector
    print("Starting UmaNakama...")

    app = QtWidgets.QApplication(sys.argv)
    show_splash(app)

    print("Running OCR. Press 'Alt+J' for settings & region selector. 'q' to quit.")

    text_overlay = TextOverlay(
        (config["overlay_position"]["x_offset"], config["overlay_position"]["y_offset"])
    )
    text_overlay.hide()

    def on_overlay_moved(x, y):
        win = get_umamusume_window()
        if win:
            config["overlay_position"] = {"x_offset": x - win.left, "y_offset": y - win.top}
        else:
            config["overlay_position"] = {"x_offset": x, "y_offset": y}
        save_config(config)

    text_overlay.position_changed.connect(on_overlay_moved)

    # ------------ status overlay position ------------
    def on_status_toggle():
        global scanning_enabled
        scanning_enabled = not scanning_enabled
        config["scanning_enabled"] = scanning_enabled
        save_config(config)

    def on_status_quit():
        app.quit()

    def on_status_moved(x, y):
        win = get_umamusume_window()
        if win:
            config["status_position"] = {
                "x_offset": x - win.left,
                "y_offset": y - win.top
            }
        else:
            config["status_position"] = {"x_offset": x, "y_offset": y}
        save_config(config)
        print("Status location saved to config")

    win = get_umamusume_window()
    if win:
        initial_x = win.left + config["status_position"]["x_offset"]
        initial_y = win.top + config["status_position"]["y_offset"]
    else:
        screen_geometry = QtWidgets.QApplication.primaryScreen().geometry()
        initial_x = screen_geometry.center().x() - 15
        initial_y = screen_geometry.center().y() - 15

    status_overlay = StatusOverlay((initial_x, initial_y), is_scanning=False)
    status_overlay.position_changed.connect(on_status_moved)

    status_overlay.is_scanning = scanning_enabled
    status_overlay.update()

    status_overlay.toggle_scanning.connect(on_status_toggle)
    status_overlay.quit_app.connect(on_status_quit)
    status_overlay.open_settings.connect(lambda: controller.open_settings_signal.emit())

    selector = RegionSelector(get_absolute_region())
    selector.hide()

    keyboard.add_hotkey('alt+j', lambda: controller.open_settings_signal.emit())
    keyboard.add_hotkey('q', lambda: app.quit())
    keyboard.add_hotkey('z', show_thresholded_image)

    stop_event = threading.Event()
    threading.Thread(
        target=continuous_scan,
        args=(text_overlay, stop_event, status_overlay),
        daemon=True
    ).start()

    try:
        sys.exit(app.exec_())
    finally:
        stop_event.set()

if __name__ == "__main__":
    main()
