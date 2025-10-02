"""
Configuration utilities.

Responsibilities
- Load and save `config.json`, merging safely with `default_config` while preserving
  user changes and back-filling new fields. Legacy keys (x/y) are upgraded to offsets.
- Resolve on-screen coordinates with awareness of the “Umamusume” window when present
  (positions are saved as offsets, then translated to absolute pixels at runtime).
- Provide a single source of truth for overlay positions, scan speed, thresholds,
  and toggles used across modules.

Notes
- Single-process file access is assumed; avoid concurrent writers.
- Always treat the stored rect as the *full* selector; subregions are derived elsewhere.
"""

from typing import Dict, Any
import json
import os

CONFIG_FILE = "config.json"
default_config: Dict[str, Any] = {
    "region": {"x_offset": 596, "y_offset": 382, "width": 355, "height": 74},
    "overlay_position": {"x_offset": 1200, "y_offset": 400},
    "status_position": {"x_offset": 50, "y_offset": 50},
    "scan_speed": 0.5,
    "scanning_enabled": False,
    "text_match_confidence": 0.7,
    "debug_mode": False,
    "always_show_overlay": False,
    "hide_condition_viewer": False,
    "portrait_match_threshold": 0.70,
}

def load_config(
    config_file: str = CONFIG_FILE,
    defaults: Dict[str, Any] = default_config
) -> Dict[str, Any]:
    """
    Load the app config from disk, merge with defaults, and normalize legacy keys.

    Args
    - config_file: Path to the config JSON. Defaults to module constant.
    - defaults: Default schema. Not mutated.

    Returns
    - dict: Merged, normalized runtime config.
    """
    if not os.path.exists(config_file):
        save_config(defaults, config_file)
        return defaults.copy()

    cfg = defaults.copy()
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            loaded = json.load(f)

        # Back-compat on x/y keys → x_offset/y_offset
        for key in ("region", "overlay_position", "status_position"):
            if key in loaded and isinstance(loaded[key], dict) and "x" in loaded[key]:
                loaded[key]["x_offset"] = loaded[key].pop("x")
                loaded[key]["y_offset"] = loaded[key].pop("y")

        # Backfill any new defaults
        for k, v in defaults.items():
            if k not in loaded:
                loaded[k] = v

        cfg.update(loaded)
        # Write back normalized shape so the file stays modern
        save_config(cfg, config_file)
    except Exception:
        # On read/parse error, reset to defaults
        save_config(defaults, config_file)
        return defaults.copy()

    return cfg

def save_config(
    config: Dict[str, Any],
    config_file: str = CONFIG_FILE
) -> None:
    """
    Persist the in-memory configuration as pretty JSON.

    Args
    - config: The full configuration dict to save.
    - config_file: Path to the config JSON. Defaults to module constant.
    """
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
