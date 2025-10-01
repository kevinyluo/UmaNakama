import json
import os
import difflib

_events_cache = {}
_events_by_char_cache = None

def _load_json(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def load_events(category: str):
    global _events_cache
    if category in _events_cache:
        return _events_cache[category]
    path = os.path.join("events", f"{category}_events.json")
    data = _load_json(path) or {}
    _events_cache[category] = data
    return data

def load_events_by_char():
    global _events_by_char_cache
    if _events_by_char_cache is not None:
        return _events_by_char_cache
    path = os.path.join("events", "trainee_by_character.json")
    _events_by_char_cache = _load_json(path) or {}
    return _events_by_char_cache

def find_best_match(event_line: str, category: str, confidence: float, character_name: str | None = None):
    if len(event_line or "") < 4:
        return None, None

    candidates_map = None
    if category == "trainee":
        by_char = load_events_by_char()
        if character_name and character_name in by_char and isinstance(by_char[character_name], dict):
            candidates_map = by_char[character_name]

    if candidates_map is None:
        candidates_map = load_events(category)

    candidates = list(candidates_map.keys())
    matches = difflib.get_close_matches(event_line, candidates, n=1, cutoff=confidence)
    if matches:
        key = matches[0]
        return key, candidates_map[key]
    return None, None
