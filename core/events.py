"""
Event loading and fuzzy matching.

Responsibilities
- Load global category event files (e.g., `trainee_events.json`, `support_events.json`)
  and the preferred per-character map `trainee_events_by_character.json` (with a legacy fallback).
- Given OCR’d event text, choose the best candidate using `difflib.get_close_matches`,
  optionally restricting candidates to a detected character to reduce collisions.
- Apply special handling for known ambiguous phrases (e.g., “inspiration”, “summer camp”)
  by raising the cutoff to reduce false positives.

Notes
- Keys in `trainee_events_by_character.json` must match the portrait filenames you save.
  Keep names consistent (including spaces/punctuation).
- If per-character data is missing for a detected character, the matcher gracefully
  falls back to the global file for that category.
"""

import os
import json
import difflib
from typing import Dict, Tuple, Optional

# Cache per (base_dir, filenames) tuple so alternate paths don’t collide
_events_by_char_cache: Dict[Tuple[str, Tuple[str, ...]], dict] = {}


def load_events_by_char(
    base_dir: str = "events",
    filenames: Tuple[str, ...] = ("trainee_events_by_character.json", "trainee_by_character.json"),
) -> dict:
    """
    Load per-character trainee events (prefers the new filename, falls back to legacy).

    Expected structure
    - { "Character Name": { "Event Name": { "Top": "...", "Bot": "..." }, ... }, ... }

    Used by
    - `find_best_match()` when a detected character name is available.

    Args
    - base_dir: Directory containing event JSON files.
    - filenames: Candidate file names to try in order.

    Returns
    - dict: Mapping character_name -> events_map (or {} if no file found).
    """
    cache_key = (base_dir, filenames)
    if cache_key in _events_by_char_cache:
        return _events_by_char_cache[cache_key]

    for fname in filenames:
        path = os.path.join(base_dir, fname)
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                _events_by_char_cache[cache_key] = data
                print(f"[events] loaded {os.path.basename(path)} ({len(data)} trainees)")
                return data
            except Exception as e:
                print(f"[events] error loading {path}: {e}")

    _events_by_char_cache[cache_key] = {}
    print("[events] no trainee-by-character file found; will fall back to global list.")
    return {}


def load_events(category: str, base_dir: str = "events") -> dict:
    """
    Load a global events file for a category, e.g. 'trainee_events.json' or 'support_events.json'.

    What it does
    - Reads `{base_dir}/{category}_events.json` (UTF-8) and returns a dict mapping:
      event_name -> { option_label -> effect_text }.

    Used by
    - `find_best_match()` as fallback when per-character data isn’t present.

    Args
    - category: "trainee" or "support".
    - base_dir: Directory containing event JSON files.

    Returns
    - dict: Event data or {} on error.
    """
    filename = os.path.join(base_dir, f"{category}_events.json")
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {filename}: {e}")
        return {}


def find_best_match(
    event_line: str,
    category: str,
    character_name: Optional[str] = None,
    confidence: float = 0.7,
    base_dir: str = "events",
) -> Tuple[Optional[str], Optional[dict]]:
    """
    Fuzzy-match the OCR'd event title to known events, optionally scoped by character.

    Flow
    - If `category == "trainee"` and `character_name` has a matching entry in
      `load_events_by_char()`, only those events are used as candidates.
      Otherwise falls back to global `load_events(category)`.
    - Uses `difflib.get_close_matches(..., n=1, cutoff=confidence)` to select the best event.
    - For ambiguous phrases ("inspiration", "summer camp"), a higher cutoff is applied.

    Used by
    - main.py right after OCR (and optional portrait detection).

    Args
    - event_line: The second OCR line containing the event name.
    - category: "trainee" or "support".
    - character_name: Exact key from per-character JSON (raw name), or None.
    - confidence: Base fuzzy-match cutoff in [0..1].
    - base_dir: Events folder.

    Returns
    - (event_name, event_map): event_name or None, and its option/effects dict or None.
    """
    if not event_line or len(event_line) < 4:
        return None, None

    # Build candidate map
    if category == "trainee":
        candidates_map = None
        by_char = load_events_by_char(base_dir=base_dir)
        if character_name:
            # Try exact + stripped variants
            candidates_map = by_char.get(character_name) or by_char.get(character_name.strip())
            if candidates_map:
                print(f"[events] matching within {character_name} ({len(candidates_map)} events)")
        if candidates_map is None:
            candidates_map = load_events("trainee", base_dir=base_dir)
    else:
        candidates_map = load_events(category, base_dir=base_dir)

    if not candidates_map:
        return None, None

    candidates = list(candidates_map.keys())

    # Raise cutoff for ambiguous phrases
    cutoff = confidence
    if any(s in event_line.lower() for s in ("inspiration", "summer camp")):
        cutoff = max(cutoff, 0.95)

    matches = difflib.get_close_matches(event_line, candidates, n=1, cutoff=cutoff)
    if matches:
        name = matches[0]
        return name, candidates_map[name]
    return None, None
