import os
import threading
import cv2
import numpy as np
from PIL import Image
import json

PORTRAIT_DIR = "assets/portraits"

_portrait_templates = {}   # name -> gray np.array
_portrait_lock = threading.Lock()

def ensure_dir():
    os.makedirs(PORTRAIT_DIR, exist_ok=True)

def load_portraits():
    """Load/refresh templates from disk."""
    ensure_dir()
    loaded = {}
    for fname in os.listdir(PORTRAIT_DIR):
        name, ext = os.path.splitext(fname)
        if ext.lower() not in (".png", ".jpg", ".jpeg"): continue
        path = os.path.join(PORTRAIT_DIR, fname)
        img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if img is not None:
            loaded[name] = img
    with _portrait_lock:
        _portrait_templates.clear()
        _portrait_templates.update(loaded)
    print(f"[portrait] loaded {len(_portrait_templates)} templates")

def _add_template(name: str, pil_img: Image.Image):
    arr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2GRAY)
    with _portrait_lock:
        _portrait_templates[name] = arr

def save_portrait(name: str, pil_img: Image.Image) -> str | None:
    ensure_dir()
    safe = "".join(ch for ch in name.strip() if ch not in "\\/:*?\"<>|").strip()
    if not safe:
        return None
    path = os.path.join(PORTRAIT_DIR, f"{safe}.png")
    pil_img.save(path)
    _add_template(safe, pil_img)
    print(f"[portrait] saved: {path}")
    return path

def detect_character(pil_img: Image.Image, min_score=0.7):
    """Return (name, score) or (None, best_score)."""
    with _portrait_lock:
        templates = dict(_portrait_templates)

    if not templates:
        load_portraits()
        with _portrait_lock:
            templates = dict(_portrait_templates)
    if not templates:
        return None, 0.0

    roi = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2GRAY)
    roi = cv2.equalizeHist(roi)

    best_name, best_score = None, -1.0
    for name, templ in templates.items():
        th, tw = templ.shape[:2]
        if roi.shape[0] < th or roi.shape[1] < tw:
            scale = max(th / max(1, roi.shape[0]), tw / max(1, roi.shape[1]))
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

def load_trainee_names():
    path = os.path.join("events", "trainee_names.json")
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "names" in data:
                return data["names"]
            if isinstance(data, list):
                return data
        except Exception:
            pass
    # fallback: names from portraits on disk
    with _portrait_lock:
        return sorted(list(_portrait_templates.keys()))
