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
from text_overlay import TextOverlay
from region_overlay import RegionSelector
from status_overlay import StatusOverlay

CONFIG_FILE = "config.json"
default_config = {
    "region": {"x": 596, "y": 382, "width": 355, "height": 74},
    "overlay_position": {"x": 1200, "y": 400},
    "status_position": {"x": 50, "y": 50},
    "scan_speed": 0.5,
    "scanning_enabled": True
}

def load_config():
    config = default_config.copy()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                # Merge existing config with defaults
                for key, value in default_config.items():
                    if key not in loaded:
                        loaded[key] = value
                config.update(loaded)
        except Exception as e:
            print(f"Error loading config file: {e}")
    return config


def save_config(config):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        print(f"Error saving config file: {e}")

config = load_config()
REGION = (
    config["region"]["x"],
    config["region"]["y"],
    config["region"]["width"],
    config["region"]["height"]
)
scanning_enabled = config.get("scanning_enabled", True)

pytesseract.pytesseract.tesseract_cmd = r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"

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
    matches = difflib.get_close_matches(event_line, candidates, n=1, cutoff=0.7)
    if matches:
        event_name = matches[0]
        return event_name, events[event_name]
    return None, None

def read_text_from_screen(text_overlay):
    screenshot = pyautogui.screenshot(region=REGION)
    gray = screenshot.convert("L")
    inverted = ImageOps.invert(gray)
    enhancer = ImageEnhance.Contrast(inverted)
    high_contrast = enhancer.enhance(1.0)
    thresholded = high_contrast.point(lambda x: 0 if x < 50 else 255, mode='1')

    text = pytesseract.image_to_string(thresholded, config="--psm 6").strip()
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    if len(lines) < 2:
        text_overlay.hide()
        return

    category_line = lines[0].lower()
    event_line = lines[1].lower()
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

def continuous_scan(text_overlay, stop_event, status_overlay):
    global scanning_enabled
    while not stop_event.is_set():
        if scanning_enabled:
            read_text_from_screen(text_overlay)
            status_overlay.set_color(QtGui.QColor(0, 200, 0))  # Green
        else:
            text_overlay.hide()
            status_overlay.set_color(QtGui.QColor(200, 0, 0))  # Red
        time.sleep(config.get("scan_speed", 0.5))

def main():
    global scanning_enabled
    print("Running continuous OCR scan. Press 'Alt+J' to toggle region selector. Press 'q' to quit.")

    app = QtWidgets.QApplication(sys.argv)

    # Text overlay
    text_overlay_pos = (config["overlay_position"]["x"], config["overlay_position"]["y"])
    text_overlay = TextOverlay(text_overlay_pos)
    text_overlay.hide()

    def on_overlay_moved(x, y):
        config["overlay_position"] = {"x": x, "y": y}
        save_config(config)

    text_overlay.position_changed.connect(on_overlay_moved)

    # Status overlay
    status_pos = (config["status_position"]["x"], config["status_position"]["y"])
    status_overlay = StatusOverlay(status_pos)
    status_overlay.set_color(QtGui.QColor(0, 200, 0) if scanning_enabled else QtGui.QColor(200, 0, 0))

    def on_status_toggle():
        global scanning_enabled
        scanning_enabled = not scanning_enabled
        config["scanning_enabled"] = scanning_enabled
        save_config(config)

    def on_status_quit():
        app.quit()

    def on_status_moved(x, y):
        config["status_position"] = {"x": x, "y": y}
        save_config(config)

    status_overlay.toggle_scanning.connect(on_status_toggle)
    status_overlay.quit_app.connect(on_status_quit)
    status_overlay.position_changed.connect(on_status_moved)

    # Region selector
    selector = RegionSelector(REGION)

    def toggle_selector():
        if selector.isVisible():
            selector.hide()
        else:
            selector.show()

    def update_region(new_region):
        global REGION
        REGION = new_region
        config["region"] = {
            "x": new_region[0],
            "y": new_region[1],
            "width": new_region[2],
            "height": new_region[3]
        }
        save_config(config)
        print(f"Updated screenshot region: {REGION}")

    selector.region_changed.connect(update_region)
    selector.hide()

    keyboard.add_hotkey('alt+j', toggle_selector)
    keyboard.add_hotkey('q', lambda: app.quit())

    stop_event = threading.Event()
    threading.Thread(target=continuous_scan, args=(text_overlay, stop_event, status_overlay), daemon=True).start()

    try:
        sys.exit(app.exec_())
    finally:
        stop_event.set()

if __name__ == "__main__":
    main()
