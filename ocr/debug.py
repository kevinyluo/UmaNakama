"""
Debug viewer for OCR preprocessing.

Responsibilities
- Run the exact same preprocessing and Tesseract config used by the live pipeline,
  then print raw/filtered lines and show the thresholded image in an OpenCV window.
"""

import cv2
import numpy as np
import pyautogui
import pytesseract
from PIL import Image

from core.window import get_ocr_region
from ocr.preprocess import preprocess_pil_for_ocr, filter_letters_only


def show_thresholded_image(config):
    """
    Capture the OCR region, preprocess it identically to the live reader, run Tesseract
    with the same config, and display the thresholded frame for tuning.

    Args
    - config: Runtime config (uses 'debug_mode' and region offsets).

    Returns
    - None
    """
    if not config.get("debug_mode", False):
        print("Debug mode is disabled.")
        return

    ocr_rect = get_ocr_region(config)
    screenshot = pyautogui.screenshot(region=ocr_rect)  # PIL image

    # Same preprocessing as reader.py
    thresholded = preprocess_pil_for_ocr(screenshot, resize_factor=1.2)

    tess_cfg = (
        "--psm 6 "
        "-c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz "
        "-c preserve_interword_spaces=1"
    )
    text = pytesseract.image_to_string(thresholded, config=tess_cfg).strip()
    lines = [ln.replace("|", "").strip() for ln in text.split("\n") if ln.strip()]
    lines = filter_letters_only(lines, min_alpha_ratio=0.60)

    print(f"Raw text is: {text}")
    print(f"Processed text is: {lines}")

    # Show the thresholded image via OpenCV
    # Convert PIL '1'/'L' to BGR for cv2.imshow
    cv_img = cv2.cvtColor(np.array(thresholded.convert("L")), cv2.COLOR_GRAY2BGR)
    cv2.imshow("Thresholded OCR Image (RED region)", cv_img)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
