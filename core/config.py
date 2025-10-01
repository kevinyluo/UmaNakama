import json
import os

CONFIG_FILE = "config.json"

default_config = {
    "region": {"x_offset": 596, "y_offset": 382, "width": 355, "height": 74},
    "overlay_position": {"x_offset": 1200, "y_offset": 400},
    "status_position": {"x_offset": 50, "y_offset": 50},
    "scan_speed": 0.5,
    "scanning_enabled": False,
    "text_match_confidence": 0.7,
    "debug_mode": False,
    "always_show_overlay": False,
    "hide_condition_viewer": False,
    "portrait_match_threshold": 0.70,  # for portrait auto-detect
}

def save_config(config: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

def load_config() -> dict:
    if not os.path.exists(CONFIG_FILE):
        save_config(default_config)
        return default_config.copy()

    cfg = default_config.copy()
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            loaded = json.load(f)

        # migrate x/y -> x_offset/y_offset if needed
        for key in ["region", "overlay_position", "status_position"]:
            if key in loaded and "x" in loaded[key]:
                loaded[key]["x_offset"] = loaded[key].pop("x")
                loaded[key]["y_offset"] = loaded[key].pop("y")

        for k, v in default_config.items():
            if k not in loaded:
                loaded[k] = v
        cfg.update(loaded)
        save_config(cfg)
    except Exception:
        save_config(default_config)
        return default_config.copy()
    return cfg
