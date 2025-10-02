"""
OCR pipeline helpers.

Responsibilities
- Capture a screenshot of the OCR subregion and extract structured lines using Tesseract
  (`--psm 6`). The first line is expected to contain the category, the second the event name.
- Preprocess to improve recognition (shared helper): resize → grayscale → invert → contrast → threshold.
- When the first OCR line reads "Trainee Event", attempt portrait matching in the left
  (yellow) region. Confirm a character after N consecutive hits; after M consecutive misses
  on the SAME event text, prompt the user to label and save the portrait.

Notes
- Output lines are normalized but we **preserve spaces** (no letters-only filter here).
- Includes miss/hit gating to avoid prompting during tab transitions or loading.
"""

from typing import Callable, Dict, Any, List, Tuple, Optional
import time
import unicodedata

import pytesseract
import pyautogui

from core.window import get_char_region, get_ocr_region
from core.events import find_best_match
from services.portraits import detect_from_roi, save_portrait
from ui.character_picker import pil_to_qimage, prompt_character_from_worker
from ocr.preprocess import preprocess_pil_for_ocr
import re

# Treat a wide range of Unicode space-separators as "space-like"
_SPACE_LIKE_CLASS = r"[ \t\u00A0\u1680\u2000-\u200A\u202F\u205F\u3000]"

def trim_after_big_gap(s: str, min_run: int = 4) -> str:
    """
    Remove everything from the first run of >= min_run space-like chars to the end.
    Also strips zero-width characters that can sneak in from OCR.
    """
    if not s:
        return s
    # Drop zero-width characters that can break matching
    s = s.replace("\u200B", "").replace("\uFEFF", "")
    # If a long gap exists, nuke the gap and everything after
    pattern = re.compile(fr"{_SPACE_LIKE_CLASS}{{{min_run},}}.*$")
    s = pattern.sub("", s)
    return s.rstrip()


# ---- portrait detection tuning ----
PORTRAIT_MATCH_THRESHOLD = 0.70  # template match score to count as a "hit"
PORTRAIT_REQUIRE_HITS    = 2     # consecutive hits to confirm a name

# ---- miss streak gating for picker ----
PORTRAIT_REQUIRE_MISSES = 2      # consecutive misses (same event) before prompting
PROMPT_COOLDOWN_SEC     = 15.0   # avoid re-prompting too quickly

# streak trackers (module-level)
_current_candidate: Optional[str] = None
_candidate_hits: int = 0
_consecutive_misses: int = 0
_last_key: str = ""              # binds miss streak to the same event context
_last_prompt_time: float = 0.0


def _normalize_spaces(s: str) -> str:
    """Map any unicode space separator to a plain ASCII space."""
    return "".join(
        " " if (c == " " or unicodedata.category(c) == "Zs") else c
        for c in s
    )


def reset_portrait_gating() -> None:
    """
    Reset streak/miss state used to decide when to confirm a portrait or prompt.

    Called when:
    - Leaving trainee flow (e.g., entering a support event), or
    - The OCR header doesn’t say “Trainee Event”, or
    - After a successful prompt/save.
    """
    global _current_candidate, _candidate_hits, _consecutive_misses, _last_key
    _current_candidate = None
    _candidate_hits = 0
    _consecutive_misses = 0
    _last_key = ""


def read_once(
    config: Dict[str, Any],
    ui_proxy: Any,
    text_overlay: Any,            # not used directly (signals go through ui_proxy)
    skill_overlay: Any,           # not used directly (signals go through ui_proxy)
    condition_overlay: Any,       # not used directly (signals go through ui_proxy)
    parsed_skills: Dict[str, Any],
    condition_keywords: Dict[str, Any],
    get_trainee_names: Callable[[], List[str]],
) -> None:
    """
    One full OCR/match/update tick.

    What it does
    - Screenshots the OCR (right/red) region, preprocesses, and runs Tesseract (PSM 6).
    - Preserves spaces by using `preserve_interword_spaces=1` and **no restrictive whitelist**.
    - If the first line says "Trainee Event", also screens the portrait (left/yellow) region
      and tries to detect the character via template matching:
        * Confirms after PORTRAIT_REQUIRE_HITS consecutive matches.
        * Counts consecutive misses ONLY when the OCR header is "Trainee Event".
        * Prompts the user after PORTRAIT_REQUIRE_MISSES misses on the SAME event line,
          respecting a PROMPT_COOLDOWN_SEC cooldown.
      If the user labels the portrait, the image is saved and the in-memory template
      cache is updated.
    - Uses `find_best_match` to fuzzy-match the event name (scoped to the detected character
      for trainee category when available), then updates UI via `ui_proxy` signals.

    Args
    - config: Runtime config dict (scan/threshold settings and region offsets).
    - ui_proxy: Object with Qt signals: set_overlay(list), show_overlay(), hide_all(), update_skills(list).
    - text_overlay, skill_overlay, condition_overlay: Present for signature compatibility; not used directly.
    - parsed_skills: Skill data used to populate the skill overlay.
    - condition_keywords: Keywords to show in the condition overlay (handled by main via ui_proxy).
    - get_trainee_names: Callable that returns the list of known trainee names (for the picker).

    Returns
    - None. UI is updated via signals; errors are logged to stdout.
    """
    global _current_candidate, _candidate_hits, _consecutive_misses, _last_key, _last_prompt_time

    # ---- OCR from the red region ----
    ocr_rect: Tuple[int, int, int, int] = get_ocr_region(config)
    screenshot = pyautogui.screenshot(region=ocr_rect)

    # Shared preprocessor (resize + gray + invert + contrast + threshold)
    thresholded = preprocess_pil_for_ocr(screenshot, resize_factor=1.2)

    # Ask Tesseract to keep spaces; avoid whitelisting letters only.
    tess_cfg = "--psm 6 --oem 3 -c preserve_interword_spaces=1"
    raw = pytesseract.image_to_string(thresholded, config=tess_cfg)

    # Split lines first, then normalize Unicode spaces; drop only empty lines.
    lines: List[str] = []
    for ln in raw.splitlines():
        ln = ln.replace("|", "").rstrip("\r")
        ln = _normalize_spaces(ln)
        if ln.strip():
            lines.append(ln)

    print(f"[ocr] lines -> {lines}")

    if len(lines) < 2:
        ui_proxy.hide_all.emit()
        return

    category_line = lines[0].lower()
    event_line_raw = lines[1]
    event_line = trim_after_big_gap(lines[1], min_run=4)    
    detected_char: Optional[str] = None

    if "trainee" in category_line:
        category = "trainee"
        is_trainee_event_line = ("trainee event" in lines[0].lower())

        try:
            # ---- portrait detection from the yellow region ----
            char_rect: Tuple[int, int, int, int] = get_char_region(config)
            char_img = pyautogui.screenshot(region=char_rect)  # keep color for saving
            thr = float(config.get("portrait_match_threshold", PORTRAIT_MATCH_THRESHOLD))

            name, score = detect_from_roi(char_img, min_score=thr)
            event_key = f"trainee|{event_line}"

            if name:
                # hit streak
                if _current_candidate == name:
                    _candidate_hits += 1
                else:
                    _current_candidate = name
                    _candidate_hits = 1

                print(f"[char] candidate '{_current_candidate}' streak={_candidate_hits} (score={score:.2f})")

                if _candidate_hits >= PORTRAIT_REQUIRE_HITS:
                    detected_char = _current_candidate
                    print(f"[char] CONFIRMED: {detected_char}")
                    # successful detection resets miss gating
                    _consecutive_misses = 0
                    _last_key = event_key

            else:
                # miss — only count if we truly see a Trainee Event line
                if is_trainee_event_line:
                    if event_key != _last_key:
                        _consecutive_misses = 1
                        _last_key = event_key
                    else:
                        _consecutive_misses += 1
                    print(f"[char] miss → streak={_consecutive_misses} key='{_last_key}'")

                    now = time.time()
                    if (_consecutive_misses >= PORTRAIT_REQUIRE_MISSES) and (now - _last_prompt_time > PROMPT_COOLDOWN_SEC):
                        _last_prompt_time = now

                        # Prompt user to label the portrait
                        names = get_trainee_names() or []
                        qimage = pil_to_qimage(char_img)
                        selected = prompt_character_from_worker(names, qimage, timeout=20.0)
                        if selected:
                            detected_char = selected
                            save_portrait(selected, char_img)
                            # reset after user labels it
                            _consecutive_misses = 0
                            _current_candidate = None
                            _candidate_hits = 0
                else:
                    # Not a Trainee Event line; don't count misses, reset gating.
                    if _consecutive_misses:
                        print("[char] non-trainee line → reset miss streak")
                    reset_portrait_gating()

        except Exception as e:
            print(f"[char] detection error: {e}")

    elif "support" in category_line:
        category = "support"
        reset_portrait_gating()
    else:
        ui_proxy.hide_all.emit()
        return

    print(f"[ocr] category={category} | event_line='{event_line}'")
    if detected_char:
        print(f"[char] using character: {detected_char}")

    # ---- Event matching (optionally scoped by detected_char for trainee) ----
    match_conf = float(config.get("text_match_confidence", 0.7))
    event_name, event_options = find_best_match(
        event_line,
        category,
        character_name=detected_char,
        confidence=match_conf,
    )

    if event_name and event_options:
        # Title omits character name by design
        overlay_lines: List[str] = [event_name]
        matched_skills: List[Tuple[str, Dict[str, Any]]] = []

        for option, effect in event_options.items():
            effect_lines = effect.split("\n")
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
