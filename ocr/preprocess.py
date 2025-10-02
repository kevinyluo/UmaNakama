"""
OCR preprocessing + text filtering helpers.

Responsibilities
- Provide a single, reusable image preprocessing pipeline for Tesseract that mirrors
  the working flow in the app (resize → grayscale → invert → contrast → threshold).
- Provide a simple post-OCR filter that keeps only lines that look like real text
  (mostly letters), so downstream fuzzy-matching sees less junk.

Notes
- Keep this conservative to avoid deleting valid text. The resize is mild (1.2x).
- The whitelist is letters + space (and a few safe marks); tune if your data needs more.
"""

from typing import List
from PIL import Image, ImageOps, ImageEnhance

# Characters we allow to survive the post-OCR cleanup step.
DEFAULT_WHITELIST = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz -'&"

def preprocess_pil_for_ocr(pil_img: Image.Image, resize_factor: float = 1.2) -> Image.Image:
    """
    Prepare a PIL image for Tesseract.

    Steps
    - Optional upscaling (BICUBIC) for small UI text (~<300dpi equivalent).
    - Grayscale → invert (white text on dark UI) → contrast tweak → hard threshold.

    Args
    - pil_img: Source PIL image (RGB from screenshot).
    - resize_factor: Uniform scale factor; 1.0 disables resizing.

    Returns
    - PIL.Image in mode '1' (binary), ready to pass to pytesseract.
    """
    img = pil_img
    if resize_factor and resize_factor != 1.0:
        w, h = img.size
        img = img.resize((int(w * resize_factor), int(h * resize_factor)), Image.BICUBIC)

    gray = img.convert("L")
    inverted = ImageOps.invert(gray)
    # Keep contrast tweak gentle; 1.0 = no change (matches previous working pipeline)
    high_contrast = ImageEnhance.Contrast(inverted).enhance(1.0)
    # Same threshold as the working version
    thresholded = high_contrast.point(lambda x: 0 if x < 50 else 255, mode="1")
    return thresholded


def filter_letters_only(
    lines: List[str],
    allowed: str = DEFAULT_WHITELIST,
    min_alpha_ratio: float = 0.60,
    min_len: int = 2,
) -> List[str]:
    """
    Keep only lines that look like real text (mostly letters).

    How it works
    - Removes characters not in `allowed`.
    - Computes the fraction of alphabetic chars among the remaining (non-space) chars.
      Keeps the line if that ratio >= `min_alpha_ratio`.

    Args
    - lines: OCR output lines (already stripped/normalized upstream).
    - allowed: Whitelisted characters to keep (others are dropped).
    - min_alpha_ratio: Threshold in [0..1] for “how letter-ish” a line must be.
    - min_len: Minimum length (ignoring spaces) after stripping.

    Returns
    - Filtered list of cleaned lines.
    """
    allowed_set = set(allowed)
    out: List[str] = []
    for ln in lines:
        # Strip everything not in the whitelist (keep spaces and a few safe marks)
        cleaned = "".join(ch for ch in ln if ch in allowed_set)
        compact = cleaned.replace(" ", "")
        if len(compact) < min_len:
            continue
        alpha = sum(ch.isalpha() for ch in compact)
        ratio = alpha / max(1, len(compact))
        if ratio >= min_alpha_ratio:
            out.append(cleaned.strip())
    return out
