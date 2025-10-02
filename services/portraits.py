"""
Portrait management & template matching.

Responsibilities
- Store and load character portraits in `assets/portraits/` (one file per character).
  Filenames double as the display names used to look up per-character events.
- Maintain an in-memory, thread-safe cache of grayscale templates. The worker thread can
  add new templates immediately after the user labels an unknown portrait.
- Detect the character by TM_CCOEFF_NORMED against the yellow ROI, histogram-equalizing
  the ROI and upscaling if the ROI is smaller than a template.

Notes
- Template matching is simple and fast; resolution mismatches are partially handled
  via ROI upscaling. For best results, save portraits cropped tightly and consistently.
- Name sanitization is applied when saving to the filesystem; keep JSON keys identical
  to the final sanitized filenames to avoid lookup surprises.
"""

from __future__ import annotations
import os
import threading
from typing import Optional, Tuple, Dict

import cv2
import numpy as np
from PIL import Image

# Default on-disk location for learned portraits
PORTRAIT_DIR = "assets/portraits"

# Global in-memory template cache and lock
portrait_templates: Dict[str, np.ndarray] = {}  # name -> grayscale image
portrait_lock = threading.Lock()


def ensure_dirs(portrait_dir: str = PORTRAIT_DIR) -> None:
    """
    Ensure the portrait storage directory exists.

    Used by
    - `load_portraits()` and `save_portrait()`.

    Args
    - portrait_dir: Directory to create if missing. Defaults to PORTRAIT_DIR.

    Returns
    - None
    """
    os.makedirs(portrait_dir, exist_ok=True)


def load_portraits(portrait_dir: str = PORTRAIT_DIR) -> Dict[str, np.ndarray]:
    """
    Populate (or refresh) the in-memory portrait templates cache from disk.

    What it does
    - Scans `portrait_dir` for .png/.jpg/.jpeg.
    - Reads each image as grayscale (OpenCV) and stores under key = filename without extension.
    - Replaces the global `portrait_templates` under a lock to keep reads thread-safe.

    Used by
    - Startup (main) and on-demand from `detect_from_roi()` if the cache is empty.

    Args
    - portrait_dir: Folder that contains portrait images.

    Returns
    - dict: A shallow copy of the newly loaded cache (name -> np.ndarray).
    """
    ensure_dirs(portrait_dir)
    loaded: Dict[str, np.ndarray] = {}

    for fname in os.listdir(portrait_dir):
        name, ext = os.path.splitext(fname)
        if ext.lower() not in {".png", ".jpg", ".jpeg"}:
            continue
        path = os.path.join(portrait_dir, fname)
        img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if img is not None:
            loaded[name] = img

    with portrait_lock:
        portrait_templates.clear()
        portrait_templates.update(loaded)

    print(f"[portrait] loaded {len(portrait_templates)} templates")
    return loaded.copy()


def _add_template(name: str, pil_img: Image.Image) -> None:
    """
    Convert a PIL image to grayscale and insert/update it in the in-memory cache.

    Used by
    - `save_portrait()` after saving to disk so future detections work immediately.

    Args
    - name: Portrait key (should match the filename sans extension).
    - pil_img: PIL image (color OK).

    Returns
    - None
    """
    arr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2GRAY)
    with portrait_lock:
        portrait_templates[name] = arr


def detect_from_roi(pil_img: Image.Image, min_score: float = 0.7) -> Tuple[Optional[str], float]:
    """
    Identify a character by template matching against the ROI.

    Algorithm
    - Convert ROI to grayscale, equalize histogram, and (if needed) upscale the ROI so it
      is at least as large as the template (so the template can slide).
    - Use TM_CCOEFF_NORMED; choose the template with the max score.
    - If the best score >= min_score, return (name, score); else (None, best_score).

    Used by
    - OCR reader when the header says "Trainee Event".

    Args
    - pil_img: PIL image of the portrait ROI (color or grayscale).
    - min_score: Threshold in [0..1] to accept a match.

    Returns
    - (name, score): (None, best_score) if below threshold or cache empty.
    """
    with portrait_lock:
        templates = portrait_templates.copy()

    if not templates:
        load_portraits()  # refresh from disk
        with portrait_lock:
            templates = portrait_templates.copy()
    if not templates:
        return None, 0.0

    roi = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2GRAY)
    roi = cv2.equalizeHist(roi)

    best_name: Optional[str] = None
    best_score: float = -1.0

    for name, templ in templates.items():
        th, tw = templ.shape[:2]

        # If ROI smaller than template, upscale ROI so template can slide
        if roi.shape[0] < th or roi.shape[1] < tw:
            scale_y = th / max(1, roi.shape[0])
            scale_x = tw / max(1, roi.shape[1])
            scale = max(scale_x, scale_y)
            roi_resized = cv2.resize(roi, (int(roi.shape[1] * scale), int(roi.shape[0] * scale)))
        else:
            roi_resized = roi

        res = cv2.matchTemplate(roi_resized, templ, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(res)
        if max_val > best_score:
            best_score = float(max_val)
            best_name = name

    if best_score >= min_score:
        return best_name, best_score
    return None, best_score


def save_portrait(name: str, pil_img: Image.Image, portrait_dir: str = PORTRAIT_DIR) -> Optional[str]:
    """
    Save a newly labeled portrait to disk and update the in-memory cache.

    What it does
    - Sanitizes the filename (removes invalid characters).
    - Saves as PNG under `portrait_dir`.
    - Immediately inserts the grayscale template into `portrait_templates`.

    Used by
    - OCR reader after the user picks a character in the picker dialog.

    Args
    - name: Display name (will become the filename stem).
    - pil_img: The portrait image captured from the yellow ROI (PIL image).
    - portrait_dir: Where to save the file. Defaults to PORTRAIT_DIR.

    Returns
    - str | None: Full file path if saved, else None (e.g., empty/invalid name).
    """
    ensure_dirs(portrait_dir)
    safe = "".join(ch for ch in name.strip() if ch not in "\\/:*?\"<>|").strip()
    if not safe:
        return None

    path = os.path.join(portrait_dir, f"{safe}.png")
    pil_img.save(path)
    _add_template(safe, pil_img)
    print(f"[portrait] saved: {path}")
    return path
    