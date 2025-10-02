"""
UmaNakama — Application entrypoint.

Responsibilities
- Bootstraps the Qt app (splash, overlays, hotkeys) and owns the worker thread that
  continuously reads the screen. It wires all cross-module signals so UI updates
  always happen on the main thread.
- Splits the configured rectangle into two live subregions:
  LEFT (yellow square) for portrait detection and RIGHT (red rectangle) for OCR text.
  The left square’s side equals the full height; the right region takes the remaining width.
- Runs the end-to-end loop: OCR → (optional) portrait detect/prompt → event match →
  HUD updates (text/skills/conditions). This centralizes the gating logic that avoids
  false prompts during UI transitions and only asks for a character when it must.
- Manages shutdown (stop event + aboutToQuit) and keeps the app alive during modal dialogs
  (`setQuitOnLastWindowClosed(False)`) so the worker doesn’t die when the picker closes.
"""

import sys, json, time, threading
import pytesseract, keyboard
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtWidgets import QSplashScreen
from PyQt5.QtGui import QPixmap

from overlays.text_overlay import TextOverlay
from overlays.region_overlay import RegionSelector
from overlays.status_overlay import StatusOverlay
from overlays.settings_overlay import SettingsOverlay
from overlays.skill_overlay import SkillInfoOverlay
from overlays.condtion_overlay import ConditionInfoOverlay

from core.config import load_config, save_config
from core.window import get_umamusume_window, get_absolute_region
from services.portraits import ensure_dirs, load_portraits
from ui.ui_proxy import UiProxy
from ocr.reader import read_once
from ocr.debug import show_thresholded_image

# --------- Globals (runtime state) ---------
settings_overlay = None
settings_overlay_pos = (500, 200)
selector = None
scanning_enabled = False

# --------- Data files ---------
with open("events/parsed_skills.json", "r", encoding="utf-8") as f:
    parsed_skills = json.load(f)
with open("events/conditions.json", "r", encoding="utf-8") as f:
    condition_keywords = json.load(f)

def load_trainee_names():
    """
    Load selectable trainee names for the character picker.

    What it does
    - Tries to read `events/trainee_names.json`. Accepts either a list or a dict {"names": [...] }.
    - If unavailable or malformed, returns an empty list (the picker will still allow free text).

    Used by
    - The OCR worker (via `read_once`) to populate the CharacterPicker options.

    Returns
    - list[str]: Candidate trainee display names (can be empty).
    """
    try:
        with open("events/trainee_names.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and "names" in data:
            return data["names"]
        if isinstance(data, list):
            return data
    except Exception as e:
        print(f"Error loading trainee_names.json: {e}")
    return []

# --------- Tesseract ---------
# Set the tesseract binary path; adjust if your install differs.
pytesseract.pytesseract.tesseract_cmd = r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"

# --------- App Controller ---------
class AppController(QtCore.QObject):
    """
    Thin signal bus for actions invoked via hotkeys or status overlay buttons.

    Signals
    - open_settings_signal: toggles the settings overlay + region selector.
    """
    open_settings_signal = QtCore.pyqtSignal()
controller = AppController()

# --------- Region save ---------
def save_region_from_selector(config):
    """
    Persist the current RegionSelector geometry back into `config["region"]`.

    Behavior
    - If the Umamusume window is present, saves offsets relative to its top-left.
      Otherwise, saves absolute coordinates.
    - Writes the updated config to disk.

    Args
    - config (dict): Runtime configuration that will be mutated & saved.

    Returns
    - None
    """
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
    print(f"Region updated (full): {get_absolute_region(config)}")

# --------- Settings toggle ---------
def toggle_settings(config):
    """
    Open/close the settings overlay and show/hide the RegionSelector.

    Behavior
    - If already open: saves region, closes the settings overlay, hides the selector.
    - If closed: opens settings overlay (at last position), shows selector if game window is found.

    Args
    - config (dict): Current configuration passed to the settings overlay.

    Returns
    - None
    """
    global settings_overlay, settings_overlay_pos, selector
    if settings_overlay and settings_overlay.isVisible():
        settings_overlay_pos = (settings_overlay.x(), settings_overlay.y())
        save_region_from_selector(config)
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
        selector.setGeometry(*get_absolute_region(config))
        selector.show()
        print("Settings & Region selector opened.")
    else:
        print("Umamusume window not found. Region selector not shown.")

# --------- Splash ---------
def show_splash(app: QtWidgets.QApplication) -> None:
    """
    Display a brief, centered splash with fade-in/out while the app warms up.

    Args
    - app: The running QApplication (used to find screen geometry & own animations).

    Returns
    - None
    """
    splash_pix = QPixmap("assets/UmaNakamaLoading.PNG")
    scaled_pix = splash_pix.scaled(400, 300, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
    splash = QSplashScreen(scaled_pix)
    splash.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint)
    screen_geometry = app.primaryScreen().geometry()
    splash.move(screen_geometry.center().x() - splash.width() // 2,
                screen_geometry.center().y() - splash.height() // 2)
    opacity_effect = QtWidgets.QGraphicsOpacityEffect()
    splash.setGraphicsEffect(opacity_effect)
    fade_in = QtCore.QPropertyAnimation(opacity_effect, b"opacity")
    fade_in.setDuration(800); fade_in.setStartValue(0); fade_in.setEndValue(1)
    fade_out = QtCore.QPropertyAnimation(opacity_effect, b"opacity")
    fade_out.setDuration(800); fade_out.setStartValue(1); fade_out.setEndValue(0)
    splash.show(); fade_in.start()
    QtCore.QTimer.singleShot(2000, fade_out.start)
    loop = QtCore.QEventLoop()
    QtCore.QTimer.singleShot(2800, loop.quit)
    loop.exec_()
    splash.close()

# --------- Worker loop ---------
def continuous_scan(config: dict,
                    ui_proxy: UiProxy,
                    text_overlay: TextOverlay,
                    status_overlay: StatusOverlay,
                    skill_overlay: SkillInfoOverlay,
                    condition_overlay: ConditionInfoOverlay,
                    stop_event: threading.Event) -> None:
    """
    Background loop that performs OCR + matching while scanning is enabled.

    Behavior
    - If scanning: calls `read_once(...)` for a single OCR/match/update pass, then updates
      the status overlay spinner and sleeps per `config["scan_speed"]`.
    - If disabled: hides UI (via `ui_proxy.hide_all`) and just updates the status overlay.
    - Exits cleanly when `stop_event` is set (e.g., app quitting).

    Args
    - config: Live configuration dict (read for scan speed, thresholds, flags).
    - ui_proxy: Signal bridge for UI-safe updates (text/skills/hide).
    - text_overlay/status_overlay/skill_overlay/condition_overlay: UI elements controlled by the loop.
    - stop_event: Threading event to terminate the loop.

    Returns
    - None
    """
    global scanning_enabled
    while not stop_event.is_set():
        if scanning_enabled:
            try:
                read_once(config, ui_proxy, text_overlay, skill_overlay, condition_overlay,
                          parsed_skills, condition_keywords, load_trainee_names)
            except Exception as e:
                print(f"[worker] scan error: {e}")
            status_overlay.is_scanning = True
            status_overlay.update()
        else:
            ui_proxy.hide_all.emit()
            status_overlay.is_scanning = False
            status_overlay.update()
        time.sleep(config.get("scan_speed", 0.5))

# --------- Main ---------
def main() -> None:
    """
    Application entry point.

    Flow
    - Prepare portrait storage and load any existing templates.
    - Load config (positions, flags), initialize Qt (keep alive during dialogs),
      show splash, and build overlays.
    - Wire UI proxy signals so the OCR worker can update overlays safely.
    - Place status overlay and RegionSelector; install hotkeys (Alt+J, Alt+Q, Z).
    - Spawn the worker thread with a stop event tied to app shutdown.
    """
    global selector, scanning_enabled
    print("Starting UmaNakama...")

    # Portrait storage & cache
    ensure_dirs()
    load_portraits()

    # Config + initial scan state
    config = load_config()
    scanning_enabled = config.get("scanning_enabled", False)

    # Qt app
    app = QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # keep worker alive while dialogs are open
    show_splash(app)

    print("Running OCR. Press 'Alt+J' for settings & region selector. 'Alt+Q' to quit.")

    # Overlays
    text_overlay = TextOverlay(
        (config["overlay_position"]["x_offset"], config["overlay_position"]["y_offset"]),
        parsed_skills=parsed_skills
    )
    text_overlay.hide()
    skill_overlay = SkillInfoOverlay(); skill_overlay.hide()
    condition_overlay = ConditionInfoOverlay(); condition_overlay.hide()

    # --- Dock skill & condition overlays to text overlay in real time ---
    def follow_text_overlay(x: int, y: int, w: int, h: int) -> None:
        """
        Dock the skill/condition panels to the right edge of the text overlay.
        Called whenever TextOverlay moves or resizes (via TextOverlay.moving).
        """
        # Dock skill overlay directly to the right of text panel
        skill_overlay.move(x + w, y)
        # Dock condition panel to the right of the skill panel
        condition_overlay.move(skill_overlay.x() + skill_overlay.width(), y)

    # Connect the live geometry signal you added in TextOverlay
    try:
        text_overlay.moving.connect(follow_text_overlay)
    except Exception:
        # If 'moving' isn't present for any reason, we just won't auto-dock live.
        pass

    # Also perform an initial dock based on current geometry
    follow_text_overlay(text_overlay.x(), text_overlay.y(), text_overlay.width(), text_overlay.height())

    # If the skill overlay can change width after content updates, keep condition attached
    class _SkillResizeWatcher(QtCore.QObject):
        def eventFilter(self, obj, event):
            if event.type() == QtCore.QEvent.Resize:
                condition_overlay.move(skill_overlay.x() + skill_overlay.width(), skill_overlay.y())
            return False
    _skill_resize_watcher = _SkillResizeWatcher()
    skill_overlay.installEventFilter(_skill_resize_watcher)

    # UI proxy wiring
    ui_proxy = UiProxy()
    ui_proxy.set_overlay.connect(text_overlay.update_text)
    ui_proxy.show_overlay.connect(text_overlay.show)

    def _hide_all():
        if not config.get("always_show_overlay", False):
            text_overlay.hide(); skill_overlay.hide(); condition_overlay.hide()
    ui_proxy.hide_all.connect(_hide_all)

    def _update_skills(matched_skills):
        """
        Update the skill and condition overlays from a list of matched skills.

        Args
        - matched_skills: list[tuple[str, dict]] pairs of (skill_name, skill_data)
        """
        if matched_skills:
            skill_overlay.set_text(matched_skills)
            # This move is redundant with follow_text_overlay but harmless:
            skill_overlay.move(text_overlay.x() + text_overlay.width(), text_overlay.y())
            skill_overlay.show()
            # condition viewer
            found = []
            for _, sk in matched_skills:
                cond = sk.get("conditons", "").lower()
                for kw in condition_keywords:
                    if kw in cond and kw not in found:
                        found.append(kw)
            if not config.get("hide_condition_viewer", False) and found:
                data_list = [(kw, condition_keywords[kw]) for kw in found]
                condition_overlay.set_text(data_list)
                condition_overlay.move(skill_overlay.x() + skill_overlay.width(), skill_overlay.y())
                condition_overlay.show()
            else:
                condition_overlay.hide()
        else:
            skill_overlay.hide(); condition_overlay.hide()
    ui_proxy.update_skills.connect(_update_skills)

    # Persist overlay drag position
    def on_overlay_moved(x, y):
        """
        Persist text overlay position as offsets relative to the game window (if present).
        """
        win = get_umamusume_window()
        if win:
            config["overlay_position"] = {"x_offset": x - win.left, "y_offset": y - win.top}
        else:
            config["overlay_position"] = {"x_offset": x, "y_offset": y}
        save_config(config)
    text_overlay.position_changed.connect(on_overlay_moved)

    # Status overlay placement & handlers
    win = get_umamusume_window()
    if win:
        initial_x = win.left + config["status_position"]["x_offset"]
        initial_y = win.top + config["status_position"]["y_offset"]
    else:
        screen_geometry = QtWidgets.QApplication.primaryScreen().geometry()
        initial_x = screen_geometry.center().x() - 15
        initial_y = screen_geometry.center().y() - 15

    status_overlay = StatusOverlay((initial_x, initial_y), is_scanning=False)

    def on_status_toggle():
        """
        Toggle scanning on/off from the status overlay button.
        Updates both `config["scanning_enabled"]` (persisted) and the global flag.
        """
        nonlocal_scanning = not bool(config.get("scanning_enabled", False))
        config["scanning_enabled"] = nonlocal_scanning
        save_config(config)
        # reflect in outer var too
        global scanning_enabled
        scanning_enabled = nonlocal_scanning

    def on_status_quit():
        """Quit the application (emits aboutToQuit → worker’s stop_event)."""
        app.quit()

    def on_status_moved(x, y):
        """
        Persist status overlay position as offsets relative to the game window (if present).
        """
        win2 = get_umamusume_window()
        if win2:
            config["status_position"] = {"x_offset": x - win2.left, "y_offset": y - win2.top}
        else:
            config["status_position"] = {"x_offset": x, "y_offset": y}
        save_config(config)
        print("Status location saved to config")

    status_overlay.position_changed.connect(on_status_moved)
    status_overlay.toggle_scanning.connect(on_status_toggle)
    status_overlay.quit_app.connect(on_status_quit)
    status_overlay.open_settings.connect(lambda: toggle_settings(config))
    status_overlay.is_scanning = scanning_enabled
    status_overlay.update()

    # Region selector (hidden until settings opened)
    selector = RegionSelector(get_absolute_region(config))
    selector.hide()

    # Hotkeys
    keyboard.add_hotkey('alt+j', lambda: toggle_settings(config))
    keyboard.add_hotkey('alt+q', lambda: app.quit())
    keyboard.add_hotkey('z', lambda: show_thresholded_image(config))

    # Worker thread
    stop_event = threading.Event()
    QtWidgets.QApplication.instance().aboutToQuit.connect(stop_event.set)

    t = threading.Thread(
        target=continuous_scan,
        args=(config, ui_proxy, text_overlay, status_overlay, skill_overlay, condition_overlay, stop_event),
        daemon=True
    )
    t.start()

    try:
        sys.exit(app.exec_())
    finally:
        stop_event.set()

if __name__ == "__main__":
    main()
