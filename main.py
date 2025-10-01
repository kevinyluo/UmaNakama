import sys
import pytesseract
import pyautogui
import keyboard
import difflib
import json
import time
import os
from PIL import ImageEnhance, ImageOps, Image
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtWidgets import QSplashScreen, QDialog, QVBoxLayout, QLabel, QComboBox, QDialogButtonBox, QHBoxLayout
from PyQt5.QtGui import QPixmap
import threading
import pygetwindow as gw
import cv2
import numpy as np
from overlays.text_overlay import TextOverlay
from overlays.region_overlay import RegionSelector
from overlays.status_overlay import StatusOverlay
from overlays.settings_overlay import SettingsOverlay
from overlays.skill_overlay import SkillInfoOverlay
from overlays.condtion_overlay import ConditionInfoOverlay

# ================= PIL -> QImage helper (no ImageQt) ==================
def pil_to_qimage(pil_img: Image.Image) -> QtGui.QImage:
    """Safe, dependency-free conversion of a PIL Image to QImage."""
    if pil_img.mode != "RGBA":
        pil_img = pil_img.convert("RGBA")
    w, h = pil_img.size
    buf = pil_img.tobytes("raw", "RGBA")
    qimg = QtGui.QImage(buf, w, h, QtGui.QImage.Format_RGBA8888)
    return qimg.copy()  # detach from Python buffer so it won't GC

# ================= Portrait matching (template) ==================
PORTRAIT_DIR = "assets/portraits"     # 1 image per character here (PNG/JPG)
portrait_templates = {}               # name -> gray image
portrait_lock = threading.Lock()      # guard templates while hot-updating

def _ensure_dirs():
    os.makedirs(PORTRAIT_DIR, exist_ok=True)

def _load_portraits():
    """Load/refresh portrait templates from disk."""
    global portrait_templates
    _ensure_dirs()
    loaded = {}
    for fname in os.listdir(PORTRAIT_DIR):
        name, ext = os.path.splitext(fname)
        if ext.lower() not in {".png", ".jpg", ".jpeg"}:
            continue
        path = os.path.join(PORTRAIT_DIR, fname)
        img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if img is not None:
            loaded[name] = img
    with portrait_lock:
        portrait_templates = loaded
    print(f"[portrait] loaded {len(portrait_templates)} templates")

def _add_portrait_template(name: str, pil_img: Image.Image):
    """Add/update an in-memory template from a PIL image for immediate use."""
    arr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2GRAY)
    with portrait_lock:
        portrait_templates[name] = arr

def detect_character_from_roi(pil_img, min_score=0.7):
    """
    Simple TM_CCOEFF_NORMED template match against each stored portrait.
    Returns (name, score) or (None, best_score).
    """
    with portrait_lock:
        templates = portrait_templates.copy()

    if not templates:
        _load_portraits()
        with portrait_lock:
            templates = portrait_templates.copy()

    if not templates:
        return None, 0.0

    roi = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2GRAY)
    roi = cv2.equalizeHist(roi)

    best_name, best_score = None, -1.0
    for name, templ in templates.items():
        th, tw = templ.shape[:2]
        # Resize ROI up if needed so template can slide
        if roi.shape[0] < th or roi.shape[1] < tw:
            scale_y = th / max(1, roi.shape[0])
            scale_x = tw / max(1, roi.shape[1])
            scale = max(scale_x, scale_y)
            roi_resized = cv2.resize(roi, (int(roi.shape[1]*scale), int(roi.shape[0]*scale)))
        else:
            roi_resized = roi

        res = cv2.matchTemplate(roi_resized, templ, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(res)
        if max_val > best_score:
            best_score = max_val
            best_name = name

    if best_score >= min_score:
        return best_name, float(best_score)
    return None, float(best_score)

# ================= Character picker dialog (main-thread) ==================
class CharacterPicker(QDialog):
    def __init__(self, names, preview_qimage=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Who's this?")
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)
        self.setModal(True)

        layout = QVBoxLayout(self)

        # Optional portrait preview
        if preview_qimage is not None:
            h = QHBoxLayout()
            lbl = QLabel()
            pix = QPixmap.fromImage(preview_qimage)
            pix = pix.scaled(96, 96, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
            lbl.setPixmap(pix)
            h.addWidget(lbl)
            h.addWidget(QLabel("Select the trainee for this portrait:"))
            layout.addLayout(h)
        else:
            layout.addWidget(QLabel("Select the trainee:"))

        self.combo = QComboBox()
        self.combo.setEditable(True)  # quick type-to-filter
        self.combo.addItems(names)
        self.combo.setInsertPolicy(QComboBox.NoInsert)
        layout.addWidget(self.combo)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_name(self):
        return self.combo.currentText().strip()

# Bridge to safely invoke dialog from worker thread
class CharPickerBridge(QtCore.QObject):
    request = QtCore.pyqtSignal(object)  # payload: {"names":[...], "qimage":QImage|None, "event":threading.Event, "out":dict}

char_picker_bridge = CharPickerBridge()

def _on_char_picker_request(payload):
    names = payload.get("names", [])
    qimage = payload.get("qimage")
    ev = payload.get("event")
    out = payload.get("out")
    dlg = CharacterPicker(names, qimage)
    result = dlg.exec_()
    out["name"] = dlg.selected_name() if result == QDialog.Accepted else None
    if ev:
        ev.set()

char_picker_bridge.request.connect(_on_char_picker_request)

# ----- UI proxy to marshal UI calls to the main thread -----
class UiProxy(QtCore.QObject):
    set_overlay = QtCore.pyqtSignal(list)  # overlay lines
    show_overlay = QtCore.pyqtSignal()
    hide_all = QtCore.pyqtSignal()
    update_skills = QtCore.pyqtSignal(list)  # [(skill_name, data), ...]

ui_proxy = None

# ================= Global Variables =================
settings_overlay_pos = (500, 200)
settings_overlay = None
selector = None

# ------------- Load Skill/Condition JSON ---------------------
with open("events/parsed_skills.json", "r", encoding="utf-8") as f:
    parsed_skills = json.load(f)
with open("events/conditions.json", "r", encoding="utf-8") as f:
    condition_keywords = json.load(f)

# ------------- Load Names for Picker -------------------------
def load_trainee_names():
    try:
        with open("events/trainee_names.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and "names" in data:
            return data["names"]
        if isinstance(data, list):
            return data
    except Exception as e:
        print(f"Error loading trainee_names.json: {e}")
    with portrait_lock:
        return sorted(list(portrait_templates.keys()))

trainee_names_cache = None

# ------------- Load config ---------------------
CONFIG_FILE = "config.json"
default_config = {
    "region": {"x_offset": 596, "y_offset": 382, "width": 355, "height": 74},
    "overlay_position": {"x_offset": 1200, "y_offset": 400},
    "status_position": {"x_offset": 50, "y_offset": 50},
    "scan_speed": 0.5,
    "scanning_enabled": False,
    "text_match_confidence": 0.7,
    "debug_mode": False,
    "always_show_overlay": False,
    "hide_condition_viewer": False,
    "portrait_match_threshold": 0.70,  # threshold for auto-detect
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

def split_region(full_rect):
    """Return (left_yellow, right_red) from a saved full rect (x,y,w,h)."""
    x, y, w, h = full_rect
    s = h  # yellow square side equals full height
    left = (x, y, min(s, w), h)
    right_w = max(0, w - s)
    right = (x + s, y, right_w, h)
    return left, right

def get_char_region():  # yellow
    return split_region(get_absolute_region())[0]

def get_ocr_region():   # red
    return split_region(get_absolute_region())[1]

# -------- optional: per-character trainee events ----------
_events_by_char = None
def load_events_by_char():
    """Load trainee events keyed by character name."""
    global _events_by_char
    if _events_by_char is not None:
        return _events_by_char

    # Prefer the new filename, but accept the old one as a fallback
    candidates = [
        os.path.join("events", "trainee_events_by_character.json"),  # NEW
        os.path.join("events", "trainee_by_character.json"),         # legacy
    ]

    for path in candidates:
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    _events_by_char = json.load(f)
                print(f"[events] loaded {os.path.basename(path)} "
                      f"({len(_events_by_char)} trainees)")
                return _events_by_char
            except Exception as e:
                print(f"[events] error loading {path}: {e}")

    _events_by_char = {}
    print("[events] no trainee-by-character file found; will fall back to global list.")
    return _events_by_char


# ---------------- EVENT MATCHING ----------------
def load_events(category):
    filename = os.path.join("events", f"{category}_events.json")
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {filename}: {e}")
        return {}

def find_best_match(event_line, category, character_name=None):
    """
    If category is 'trainee' and we have a detected character, look up only that
    character's events from trainee_events_by_character.json. Otherwise fall back
    to the global {category}_events.json.
    """
    if not event_line or len(event_line) < 4:
        return None, None

    candidates_map = None

    if category == "trainee":
        by_char = load_events_by_char()
        if character_name:
            # exact match on the key as written in the JSON (raw name)
            candidates_map = by_char.get(character_name)
            if candidates_map is None:
                # Optional: try a very light normalization if your portrait filenames
                # sometimes differ in whitespace; otherwise you can remove this.
                candidates_map = by_char.get(character_name.strip())

            if candidates_map:
                print(f"[events] matching within {character_name} ({len(candidates_map)} events)")
        # If we still don't have a map, fall back to global trainee_events.json
        if candidates_map is None:
            candidates_map = load_events("trainee")

    else:
        # support events unchanged
        candidates_map = load_events(category)

    if not candidates_map:
        return None, None

    candidates = list(candidates_map.keys())
    confidence = float(config.get("text_match_confidence", 0.7))

    special_events = ["inspiration", "summer camp"]
    if any(s in event_line.lower() for s in special_events):
        confidence = 0.95

    matches = difflib.get_close_matches(event_line, candidates, n=1, cutoff=confidence)
    if matches:
        event_name = matches[0]
        return event_name, candidates_map[event_name]
    return None, None


# ---------------- Character learn/save ----------------
def save_portrait_image(name: str, pil_img: Image.Image):
    _ensure_dirs()
    safe = name.strip()
    safe = "".join(ch for ch in safe if ch not in "\\/:*?\"<>|").strip()
    if not safe:
        return None
    path = os.path.join(PORTRAIT_DIR, f"{safe}.png")
    pil_img.save(path)
    _add_portrait_template(safe, pil_img)
    print(f"[portrait] saved: {path}")
    return path

# To avoid prompting repeatedly for the same screen line
_prompt_cache = {}  # key -> last_time

def should_prompt_again(key: str, cooldown=4.0):
    now = time.time()
    last = _prompt_cache.get(key, 0.0)
    if now - last >= cooldown:
        _prompt_cache[key] = now
        return True
    return False

# ---------------- OCR FUNCTION ----------------
def read_text_from_screen(text_overlay, skill_overlay, condition_overlay):
    global trainee_names_cache, ui_proxy

    # ---- capture subregions ----
    ocr_rect = get_ocr_region()   # right/red
    char_rect = get_char_region() # left/yellow

    # ---- OCR from the red region ----
    screenshot = pyautogui.screenshot(region=ocr_rect)
    gray = screenshot.convert("L")
    inverted = ImageOps.invert(gray)
    enhancer = ImageEnhance.Contrast(inverted)
    high_contrast = enhancer.enhance(1.0)
    thresholded = high_contrast.point(lambda x: 0 if x < 50 else 255, mode='1')

    text = pytesseract.image_to_string(thresholded, config="--psm 6").strip()
    lines = [line.replace("|", "").strip() for line in text.split('\n') if line.strip()]

    # --- debug print of OCR ---
    print(f"[ocr] lines -> {lines}")

    if len(lines) < 2:
        ui_proxy.hide_all.emit()
        return

    category_line = lines[0].lower()
    event_line = lines[1]

    # Optional: detect character (yellow region) only for trainee category
    detected_char = None
    if "trainee" in category_line:
        category = "trainee"
        try:
            char_img = pyautogui.screenshot(region=char_rect)  # keep as color
            thr = float(config.get("portrait_match_threshold", 0.70))
            name, score = detect_character_from_roi(char_img, min_score=thr)
            if name:
                detected_char = name
                print(f"[char] detected: {name} ({score:.2f})")
            else:
                # Ask user who this is (with a small cooldown so we don't spam)
                key = f"{category}|{event_line}"
                if should_prompt_again(key):
                    if trainee_names_cache is None:
                        trainee_names_cache = load_trainee_names()

                    # Build preview QImage for dialog (no ImageQt)
                    qimage = pil_to_qimage(char_img)
                    done = threading.Event()
                    out = {}

                    # Trigger dialog in GUI thread
                    char_picker_bridge.request.emit({
                        "names": trainee_names_cache or [],
                        "qimage": qimage,
                        "event": done,
                        "out": out
                    })
                    # Wait for user selection
                    done.wait(timeout=15.0)  # avoid blocking forever
                    selected = out.get("name")
                    if selected:
                        detected_char = selected
                        save_portrait_image(selected, char_img)
        except Exception as e:
            print(f"[char] detection error: {e}")

    elif "support" in category_line:
        category = "support"
    else:
        ui_proxy.hide_all.emit()
        return

    print(f"[ocr] category={category} | event_line='{event_line}'")
    if detected_char:
        print(f"[char] using character: {detected_char}")

    # ---- Event matching (optionally scoped by detected_char for trainee) ----
    event_name, event_options = find_best_match(event_line, category, detected_char)
    if event_name:
        title = f"{event_name}" if not detected_char else f"{detected_char} — {event_name}"
        overlay_lines = [title]
        matched_skills = []

        for option, effect in event_options.items():
            effect_lines = effect.split('\n')
            overlay_lines.append(f"{option}: {effect_lines[0]}")
            for extra in effect_lines[1:]:
                overlay_lines.append(extra)

        for line in overlay_lines:
            for skill_name, data in parsed_skills.items():
                if skill_name.lower() in line.lower():
                    matched_skills.append((skill_name, data))

        ui_proxy.set_overlay.emit(overlay_lines)
        ui_proxy.show_overlay.emit()
        ui_proxy.update_skills.emit(matched_skills)
    else:
        ui_proxy.hide_all.emit()

# ---------------- CONTINUOUS SCAN ----------------
def continuous_scan(text_overlay, stop_event, status_overlay, skill_overlay, condition_overlay):
    global scanning_enabled
    while not stop_event.is_set():
        if scanning_enabled:
            try:
                read_text_from_screen(text_overlay, skill_overlay, condition_overlay)
            except Exception as e:
                print(f"[worker] scan error: {e}")
            status_overlay.is_scanning = True
            status_overlay.update()
        else:
            ui_proxy.hide_all.emit()
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
    print(f"Region updated (full): {get_absolute_region()}")
    ly, rr = get_char_region(), get_ocr_region()
    print(f"  Left (yellow): {ly} | Right (red): {rr}")

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

    ocr_rect = get_ocr_region()
    screenshot = pyautogui.screenshot(region=ocr_rect)
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
    cv2.imshow("Thresholded OCR Image (RED region)", cv_img)
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
    global scanning_enabled, selector, trainee_names_cache, ui_proxy
    print("Starting UmaNakama...")

    _ensure_dirs()
    _load_portraits()  # load any existing portraits first

    app = QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # <-- keep app alive after dialogs close

    show_splash(app)

    print("Running OCR. Press 'Alt+J' for settings & region selector. 'q' to quit.")

    # ---------- text overlay declaration ----------------
    text_overlay = TextOverlay(
        (config["overlay_position"]["x_offset"], config["overlay_position"]["y_offset"]), parsed_skills=parsed_skills
    )
    text_overlay.hide()

    # ---------- skill and condition overlay declaration ----------------
    skill_overlay = SkillInfoOverlay()
    skill_overlay.hide()

    condition_overlay = ConditionInfoOverlay()
    condition_overlay.hide()

    # ---------- UI proxy wiring (GUI thread) ------------
    ui_proxy = UiProxy()
    ui_proxy.set_overlay.connect(text_overlay.update_text)
    ui_proxy.show_overlay.connect(text_overlay.show)

    def _hide_everything():
        if not config.get("always_show_overlay", False):
            text_overlay.hide()
            skill_overlay.hide()
            condition_overlay.hide()

    ui_proxy.hide_all.connect(_hide_everything)

    def update_overlay_from_signal(matched_skills):
        if matched_skills:
            skill_overlay.set_text(matched_skills)
            skill_overlay.move(text_overlay.x() + text_overlay.width(), text_overlay.y())
            skill_overlay.show()

            found_keywords = []
            for _, skill in matched_skills:
                cond = skill.get("conditons", "").lower()
                for keyword in condition_keywords:
                    if keyword in cond and keyword not in found_keywords:
                        found_keywords.append(keyword)

            if not config.get("hide_condition_viewer", False) and found_keywords:
                data_list = [(kw, condition_keywords[kw]) for kw in found_keywords]
                condition_overlay.set_text(data_list)
                condition_overlay.move(skill_overlay.x() + skill_overlay.width(), skill_overlay.y())
                condition_overlay.show()
            else:
                condition_overlay.hide()
        else:
            skill_overlay.hide()
            condition_overlay.hide()

    ui_proxy.update_skills.connect(update_overlay_from_signal)

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

    # Warm-load names for picker
    trainee_names_cache = load_trainee_names()

    # ----------- hotkeys --------------
    keyboard.add_hotkey('alt+j', lambda: controller.open_settings_signal.emit())
    keyboard.add_hotkey('alt+q', lambda: app.quit())
    keyboard.add_hotkey('z', show_thresholded_image)

    # ----------- threading -------------
    stop_event = threading.Event()

    QtWidgets.QApplication.instance().aboutToQuit.connect(stop_event.set)

    thread = threading.Thread(
        target=continuous_scan,
        args=(text_overlay, stop_event, status_overlay, skill_overlay, condition_overlay),
        daemon=True
    )
    thread.start()

    try:
        sys.exit(app.exec_())
    finally:
        stop_event.set()

if __name__ == "__main__":
    main()
