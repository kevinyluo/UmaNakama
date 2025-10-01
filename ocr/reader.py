import pyautogui
from PIL import ImageEnhance, ImageOps
from PIL import Image
import pytesseract
import pygetwindow as gw

# split the configured rectangle into (left square, right remainder)
def split_region(rect):
    x, y, w, h = rect
    s = min(h, w)  # square width
    left = (x, y, s, h)           # portrait
    right = (x + s, y, max(0, w - s), h)  # text
    return left, right

def get_umamusume_window():
    try:
        wins = gw.getWindowsWithTitle("Umamusume")
        if wins:
            win = wins[0]
            if win.isMinimized:
                return None
            return win
    except Exception:
        pass
    return None

def absolute_region(cfg_region):
    win = get_umamusume_window()
    if not win:
        return (
            cfg_region["x_offset"],
            cfg_region["y_offset"],
            cfg_region["width"],
            cfg_region["height"],
        )
    return (
        win.left + cfg_region["x_offset"],
        win.top + cfg_region["y_offset"],
        cfg_region["width"],
        cfg_region["height"],
    )

def _ocr_lines(pil_img) -> list:
    gray = pil_img.convert("L")
    inverted = ImageOps.invert(gray)
    high_contrast = ImageEnhance.Contrast(inverted).enhance(1.0)
    thresh = high_contrast.point(lambda x: 0 if x < 50 else 255, mode="1")
    text = pytesseract.image_to_string(thresh, config="--psm 6").strip()
    return [line.replace("|", "").strip() for line in text.split("\n") if line.strip()]

def read_once(config) -> dict:
    """
    Returns:
    {
      "category": "trainee"/"support"/None,
      "event_line": str or None,
      "portrait_img": PIL.Image or None,  # raw (color)
      "text_img": PIL.Image or None,
      "lines": list[str]
    }
    """
    rect = absolute_region(config["region"])
    left_rect, right_rect = split_region(rect)

    text_img = pyautogui.screenshot(region=right_rect)
    lines = _ocr_lines(text_img)

    portrait_img = pyautogui.screenshot(region=left_rect)  # leave color as-is

    category = None
    event_line = None
    if len(lines) >= 2:
        c0 = lines[0].lower()
        if "trainee" in c0:
            category = "trainee"
        elif "support" in c0:
            category = "support"
        event_line = lines[1]

    return {
        "category": category,
        "event_line": event_line,
        "portrait_img": portrait_img,
        "text_img": text_img,
        "lines": lines,
    }
