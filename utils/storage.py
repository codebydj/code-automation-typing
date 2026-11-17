"""
DeskPilot - Storage Utility Module
Handles saving and loading automation sequences, configuration files, and log exports.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from config import SEQUENCES_DIR, CONFIG_FILE


def save_sequence_to_file(sequence_data: Dict[str, Any], filepath: Path) -> bool:
    """Save an automation sequence dictionary to a JSON file."""
    try:
        filepath = Path(filepath)
        if not filepath.suffix:
            filepath = filepath.with_suffix(".json")
            
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        sequence_data["updated_at"] = datetime.now().isoformat()
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(sequence_data, f, indent=4)
        return True
    except Exception as e:
        print(f"[Storage] Error saving sequence to {filepath}: {e}")
        return False


def load_sequence_from_file(filepath: Path) -> Optional[Dict[str, Any]]:
    """Load an automation sequence from a JSON file."""
    try:
        filepath = Path(filepath)
        if not filepath.exists():
            return None
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[Storage] Error loading sequence from {filepath}: {e}")
        return None


def list_saved_sequences() -> List[Dict[str, Any]]:
    """List all available sequence files in the sequences directory with metadata."""
    sequences = []
    if not SEQUENCES_DIR.exists():
        return sequences

    for p in sorted(SEQUENCES_DIR.glob("*.json")):
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
                sequences.append({
                    "name": data.get("name", p.stem),
                    "description": data.get("description", ""),
                    "actions_count": len(data.get("actions", [])),
                    "path": str(p),
                    "filename": p.name
                })
        except Exception:
            sequences.append({
                "name": p.stem,
                "description": "Corrupted or invalid file",
                "actions_count": 0,
                "path": str(p),
                "filename": p.name
            })
    return sequences


def export_logs_to_file(log_entries: List[Any], target_path: Path) -> bool:
    """Export log entries to a text file."""
    try:
        target_path = Path(target_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(f"=== DeskPilot Execution Log Export - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n\n")
            for entry in log_entries:
                f.write(entry.format_line() + "\n")
        return True
    except Exception as e:
        print(f"[Storage] Error exporting logs: {e}")
        return False


def create_sample_sequences_if_empty(force_update_defaults: bool = False):
    """Seed initial sample sequences to help users get started immediately."""
    SEQUENCES_DIR.mkdir(parents=True, exist_ok=True)
    
    samples = [
        {
            "filename": "demo_code_typing.json",
            "name": "Python Function Auto-Typer",
            "description": "Demonstrates human-style code typing, comment insertion, indentation, and natural human cursor movements.",
            "actions": [
                {
                    "type": "wait",
                    "seconds": 1.5,
                    "description": "Wait for user to switch into target editor window"
                },
                {
                    "type": "move_mouse",
                    "random_movement": True,
                    "min_duration": 0.4,
                    "max_duration": 0.9,
                    "min_length": 50,
                    "max_length": 180,
                    "description": "Human cursor movement for random time and length"
                },
                {
                    "type": "type_text",
                    "text": "# DeskPilot Automated Code Generation Demo\n",
                    "speed": 0.04,
                    "description": "Type header comment"
                },
                {
                    "type": "type_text",
                    "text": "def calculate_velocity(distance_km: float, time_hr: float) -> float:\n",
                    "speed": 0.04,
                    "description": "Type function signature"
                },
                {
                    "type": "move_mouse",
                    "random_movement": True,
                    "min_duration": 0.35,
                    "max_duration": 0.8,
                    "min_length": 40,
                    "max_length": 150,
                    "description": "Human cursor movement for random time and length"
                },
                {
                    "type": "type_text",
                    "text": "    \"\"\"Compute average velocity in kilometers per hour.\"\"\"\n",
                    "speed": 0.04,
                    "description": "Type docstring"
                },
                {
                    "type": "type_text",
                    "text": "    if time_hr <= 0:\n",
                    "speed": 0.04,
                    "description": "Type guard clause"
                },
                {
                    "type": "type_text",
                    "text": "        raise ValueError('Time must be greater than zero')\n",
                    "speed": 0.04,
                    "description": "Type exception raise"
                },
                {
                    "type": "type_text",
                    "text": "    return round(distance_km / time_hr, 2)\n",
                    "speed": 0.04,
                    "description": "Type return statement"
                },
                {
                    "type": "move_mouse",
                    "random_movement": True,
                    "min_duration": 0.4,
                    "max_duration": 1.0,
                    "min_length": 60,
                    "max_length": 200,
                    "description": "Human cursor movement for random time and length"
                }
            ]
        },
        {
            "filename": "demo_human_cursor_typing.json",
            "name": "Human Typing & Cursor Routine",
            "description": "Demonstrates human typing with natural cursor movements for random durations and lengths.",
            "actions": [
                {
                    "type": "wait",
                    "seconds": 1.5,
                    "description": "Prepare target text area"
                },
                {
                    "type": "move_mouse",
                    "random_movement": True,
                    "min_duration": 0.4,
                    "max_duration": 0.9,
                    "min_length": 50,
                    "max_length": 200,
                    "description": "Human cursor movement (random length and time)"
                },
                {
                    "type": "type_text",
                    "text": "DeskPilot simulates authentic human interaction.\nEvery keystroke and cursor movement feels natural and smooth.\n",
                    "speed": 0.04,
                    "description": "Type demonstration paragraph"
                },
                {
                    "type": "move_mouse",
                    "random_movement": True,
                    "min_duration": 0.5,
                    "max_duration": 1.1,
                    "min_length": 60,
                    "max_length": 220,
                    "description": "Human cursor movement (random length and time)"
                }
            ]
        }
    ]

    for sample in samples:
        target = SEQUENCES_DIR / sample["filename"]
        if not target.exists() or force_update_defaults:
            data = {
                "name": sample["name"],
                "description": sample["description"],
                "created_at": datetime.now().isoformat(),
                "actions": sample["actions"]
            }
            save_sequence_to_file(data, target)


# Ensure sample sequences exist without overwriting user-edited files.
create_sample_sequences_if_empty()
