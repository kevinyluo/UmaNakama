import pygetwindow as gw

def get_umamusume_window():
    """
    Find the Umamusume game window via pygetwindow.

    What it does
    - Returns the first window titled "Umamusume" if present and not minimized.
    - Returns None otherwise.

    Used by
    - `get_absolute_region()` and by main.py when placing overlays relative to the game.

    Returns
    - pygetwindow.Window | None
    """
    try:
        windows = gw.getWindowsWithTitle("Umamusume")
        if windows:
            win = windows[0]
            if win.isMinimized:
                return None
            return win
    except Exception:
        pass
    return None


def get_absolute_region(config: dict) -> tuple[int, int, int, int]:
    """
    Convert stored offsets into an absolute (x, y, w, h) screen rectangle.

    What it does
    - If the game window exists, offsets are added to the window’s top-left.
    - If not, offsets are treated as absolute screen coordinates.

    Used by
    - main.py worker loop to capture screenshots.
    - overlays.region_overlay.RegionSelector initialization.

    Args
    - config: The runtime config containing `config["region"]`.

    Returns
    - (x, y, w, h): Absolute rectangle in screen pixels.
    """
    win = get_umamusume_window()
    if not win:
        r = config["region"]
        return (r["x_offset"], r["y_offset"], r["width"], r["height"])
    return (
        win.left + config["region"]["x_offset"],
        win.top + config["region"]["y_offset"],
        config["region"]["width"],
        config["region"]["height"],
    )


def split_region(full_rect: tuple[int, int, int, int]) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
    """
    Split the full selector into two subregions: portrait (left/yellow) and OCR (right/red).

    What it does
    - Left area is a square whose side = full height (clamped to width if needed).
    - Right area consumes the remaining width. Coordinates are kept consistent even when w < h.

    Used by
    - `get_char_region()` and `get_ocr_region()`; called indirectly by main.py.

    Args
    - full_rect: (x, y, w, h) absolute rectangle.

    Returns
    - (left_rect, right_rect): Two absolute rectangles.
    """
    x, y, w, h = full_rect
    s = h  # intended left square side
    s_eff = min(s, w)  # effective left width (clamped)
    left = (x, y, s_eff, h)
    right_w = max(0, w - s_eff)
    right = (x + s_eff, y, right_w, h)
    return left, right


def get_char_region(config: dict) -> tuple[int, int, int, int]:
    """
    Get the portrait (yellow) subregion from the current absolute region.

    Used by
    - main.py before portrait detection.

    Args
    - config: Runtime config.

    Returns
    - (x, y, w, h): Absolute rectangle for portrait matching.
    """
    return split_region(get_absolute_region(config))[0]


def get_ocr_region(config: dict) -> tuple[int, int, int, int]:
    """
    Get the OCR (red) subregion from the current absolute region.

    Used by
    - main.py before running Tesseract.

    Args
    - config: Runtime config.

    Returns
    - (x, y, w, h): Absolute rectangle for text OCR.
    """
    return split_region(get_absolute_region(config))[1]
