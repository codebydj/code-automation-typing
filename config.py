"""
DeskPilot - Configuration Module
Manages default settings, paths, and persistent user configuration.
"""

import os
import json
import copy
from pathlib import Path

# Application Metadata
APP_NAME = "DeskPilot"
APP_SUBTITLE = "Human-Style Desktop Automation Tool"
APP_VERSION = "1.0.0"

# Directories
BASE_DIR = Path(__file__).resolve().parent
SEQUENCES_DIR = BASE_DIR / "sequences"
LOGS_DIR = BASE_DIR / "logs"
CONFIG_FILE = BASE_DIR / "settings.json"

# Ensure runtime directories exist
SEQUENCES_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Default Settings
DEFAULT_CONFIG = {
    # Keyboard & Typing Settings (Default: 3 CPS with Dynamic Character Difficulty)
    "typing": {
        "speed_cps": 3,               # 0.5–3.5 characters per second (Default: 3 CPS)
        "timing_mode": "difficulty",  # "difficulty" (character difficulty & row scaling) or "fixed" (constant CPS)
        "use_numpad": False,          # Use numeric keypad for numbers 0-9
        "punct_delay": 0.150,         # Pause after punctuation (comma, semicolon, period) in variable mode
        "newline_delay": 0.250,       # Pause at line endings in variable mode
        "base_delay": 0.333,          # Average delay between characters in seconds (~3 chars/sec)
        "smart_indent": False,        # Keep exact source code indentation; no destructive backspacing
    },

    # Random Rest Pause (3–6 minutes human rest between random line intervals with auto-resume)
    "random_pause": {
        "enabled": True,              # Random human rest pause option
        "min_interval_lines": 15,     # Minimum completed lines before rest pause
        "max_interval_lines": 30,     # Maximum completed lines before rest pause
        "min_duration_seconds": 180,  # 3 minutes (180s)
        "max_duration_seconds": 360,  # 6 minutes (360s)
    },

    # Sequence timing
    "execution": {
        "default_action_pause": 0.1
    },
    
    # Mouse Settings (Movement only - clicking, dragging, and scrolling are removed)
    "mouse": {
        "movement_profile": "curved", # "curved", "smooth", "direct"
        "move_duration": 0.45,        # Default duration for smooth cursor movement
        "easing": "easeInOutQuad",    # PyAutoGUI easing function name
        "human_like": True,
        # Line-interval mouse interaction between lines (Move only, no clicks)
        "line_interaction": {
            "enabled": True,          # Automatically enabled by default
            "min_lines": 2,           # Minimum lines between mouse actions (random 2-5 lines)
            "max_lines": 5,           # Maximum lines between mouse actions (random 2-5 lines)
            "target_x": 600,          # Configured safe coordinate X
            "target_y": 450,          # Configured safe coordinate Y
        }
    },
    
    # Safety Settings
    "safety": {
        "failsafe": True,             # PyAutoGUI fail-safe: move mouse to corner to abort
        "countdown_seconds": 3,       # Countdown delay before automation begins
        "require_confirmation": True, # Ask confirmation dialog before executing sequence
        "emergency_hotkey": "ctrl+alt+esc",
        "beep_on_countdown": True     # Play system beep during countdown
    },
    
    # Global Hotkeys Settings
    "hotkeys": {
        "start": "ctrl+alt+f1",
        "pause": "ctrl+alt+f2",
        "resume": "ctrl+alt+f3",
        "stop": "ctrl+alt+f4"
    },

    # Code editor settings
    "editor": {
        "indent_width": 4
    },

    # Resizable IDE workspace panel widths
    "layout": {
        "explorer_width": 190,
        "quickinput_width": 330
    },
    
    # UI & Appearance
    "appearance": {
        "theme": "Dark",              # "Dark", "Light", "System"
        "color_theme": "blue",        # "blue", "green", "dark-blue"
        "window_width": 1180,
        "window_height": 780,
        "min_width": 960,
        "min_height": 640
    }
}


def load_config() -> dict:
    """Load configuration from JSON file or return default configuration."""
    if not CONFIG_FILE.exists():
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            user_config = json.load(f)
            # Deep merge with defaults in case new keys were added
            merged = copy.deepcopy(DEFAULT_CONFIG)
            for section, values in user_config.items():
                if section in merged and isinstance(values, dict):
                    merged[section].update(values)
                else:
                    merged[section] = values
            return merged
    except Exception as e:
        print(f"[Config] Error loading settings: {e}. Using defaults.")
        return copy.deepcopy(DEFAULT_CONFIG)


def save_config(config: dict) -> bool:
    """Save configuration dictionary to settings.json."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
        return True
    except Exception as e:
        print(f"[Config] Error saving settings: {e}")
        return False
