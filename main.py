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
import threading
import pygetwindow as gw
import cv2
import numpy as np
from text_overlay import TextOverlay
from region_overlay import RegionSelector
from status_overlay import StatusOverlay
from settings_overlay import SettingsOverlay
import Levenshtein

# ---------------- Global Variables----------------
settings_overlay_pos = (500, 200)
settings_overlay = None
selector = None
last_detected_time = 0

CONFIG_FILE = "config.json"
default_config = {
    "region": {"x_offset": 596, "y_offset": 382, "width": 355, "height": 74},
    "overlay_position": {"x_offset": 1200, "y_offset": 400},
    "status_position": {"x_offset": 50, "y_offset": 50},
    "scan_speed": 0.5,
    "scanning_enabled": True,
    "text_match_confidence": 0.7,
    "debug_mode": False
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
scanning_enabled = config.get("scanning_enabled", True)

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

REGION = get_absolute_region()

# ---------------- EVENT MATCHING ----------------
def load_events(category):
    filename = f"{category}_events.json"
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
    matches = difflib.get_close_matches(event_line, candidates, n=1, cutoff=confidence)
    if matches:
        event_name = matches[0]
        return event_name, events[event_name]
    return None, None

# def find_best_match(event_line, category):
#     if len(event_line) < 4:
#         return None, None
#     events = load_events(category)
#     candidates = list(events.keys())
#     confidence = config.get("text_match_confidence", 0.7)

#     best_match = None
#     best_score = 0

#     for candidate in candidates:
#         score = 1 - (Levenshtein.distance(event_line, candidate) / max(len(event_line), len(candidate)))
#         if score > best_score:
#             best_score = score
#             best_match = candidate

#     if best_match and best_score >= confidence:
#         return best_match, events[best_match]
#     return None, None


# ---------------- OCR FUNCTION ----------------
def read_text_from_screen(text_overlay):
    global last_detected_time
    screenshot = pyautogui.screenshot(region=get_absolute_region())
    gray = screenshot.convert("L")
    inverted = ImageOps.invert(gray)
    enhancer = ImageEnhance.Contrast(inverted)
    high_contrast = enhancer.enhance(1.0)
    thresholded = high_contrast.point(lambda x: 0 if x < 50 else 255, mode='1')

    text = pytesseract.image_to_string(thresholded, config="--psm 6").strip()
    lines = [line.replace("|", "").strip() for line in text.split('\n') if line.strip()]

    if len(lines) < 2 and time.time() - last_detected_time > 2:
        text_overlay.hide()
        return
    elif len(lines) < 2:
        return
    
    last_detected_time = time.time()

    category_line = lines[0].lower()
    event_line = lines[1]
    if "trainee" in category_line:
        category = "trainee"
    elif "support" in category_line:
        category = "support"
    else:
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
        text_overlay.hide()

# ---------------- CONTINUOUS SCAN ----------------
def continuous_scan(text_overlay, stop_event, status_overlay):
    global scanning_enabled
    while not stop_event.is_set():
        if scanning_enabled:
            read_text_from_screen(text_overlay)
            status_overlay.set_color(QtGui.QColor(0, 200, 0))
        else:
            text_overlay.hide()
            status_overlay.set_color(QtGui.QColor(200, 0, 0))
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
    REGION = get_absolute_region()
    print(f"Region updated: {REGION}")

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

# ---------------- MAIN ----------------
def main():
    global scanning_enabled, selector

    print("Running OCR. Press 'Alt+J' for settings & region selector. 'q' to quit.")
    app = QtWidgets.QApplication(sys.argv)

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

    status_overlay = StatusOverlay(
        (config["status_position"]["x_offset"], config["status_position"]["y_offset"])
    )
    status_overlay.set_color(QtGui.QColor(0, 200, 0) if scanning_enabled else QtGui.QColor(200, 0, 0))

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
            config["status_position"] = {"x_offset": x - win.left, "y_offset": y - win.top}
        else:
            config["status_position"] = {"x_offset": x, "y_offset": y}
        save_config(config)

    status_overlay.toggle_scanning.connect(on_status_toggle)
    status_overlay.quit_app.connect(on_status_quit)
    status_overlay.position_changed.connect(on_status_moved)
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
