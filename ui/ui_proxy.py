from PyQt5 import QtCore

class UiProxy(QtCore.QObject):
    """
    Thread-safe signal bridge from the OCR worker thread to the Qt UI.

    Purpose
    -------
    The scanning loop runs in a background thread. Qt widgets must only be
    touched from the main GUI thread. This QObject exposes signals you can
    emit from the worker, and the main thread will handle them via slots
    connected in main.py.

    Threading / Connections
    -----------------------
    - PyQt signals are thread-safe: emitting from a non-GUI thread is OK.
    - Use default Qt.AutoConnection; across threads it becomes QueuedConnection,
      so slots run on the GUI thread automatically.

    Typical wiring (in main.py)
    ---------------------------
        ui_proxy = UiProxy()
        ui_proxy.set_overlay.connect(text_overlay.update_text)
        ui_proxy.show_overlay.connect(text_overlay.show)
        ui_proxy.hide_all.connect(hide_everything)
        ui_proxy.update_skills.connect(update_skill_overlay)

        # pass `ui_proxy` into the worker so it can emit:
        # ui_proxy.set_overlay.emit(lines)

    Signals
    -------
    set_overlay(list[str]):
        Update the main text overlay contents. Payload is the full list of
        overlay lines (title + options/effects).

    show_overlay():
        Make the text overlay visible (e.g., right after setting content).

    hide_all():
        Hide the text overlay and any auxiliary overlays (skill/condition)
        when OCR context is missing or not recognized.

    update_skills(list[tuple[str, dict]]):
        Update the skill/condition side overlays. Payload is a list of
        (skill_name, skill_data) tuples for the current event.
    """

    # Payload = overlay lines (title first, then option/effect lines)
    set_overlay = QtCore.pyqtSignal(list)

    # No payload; tells the UI to show the main text overlay
    show_overlay = QtCore.pyqtSignal()

    # No payload; tells the UI to hide text/skill/condition overlays
    hide_all = QtCore.pyqtSignal()

    # Payload = [(skill_name, data_dict), ...] for skill & condition overlays
    update_skills = QtCore.pyqtSignal(list)
