"""
DeskPilot IDE - Standalone Given Code Demo Runner
Executes automation for the given code (from sequences/demo or specified file)
at a fixed typing cadence, with optional continuous looping until stopped.
"""

import sys
import time
import argparse
from pathlib import Path
from typing import Optional, Tuple

from config import SEQUENCES_DIR
from utils.logger import logger
from automation.safety import safety
from automation.sequence_executor import executor
from automation.mouse_controller import mouse_ctrl
from automation.keyboard_controller import keyboard_ctrl

DEFAULT_FALLBACK_CODE = '''# DeskPilot Automation Demo
def main():
    print("DeskPilot Human Automation Active")

if __name__ == "__main__":
    main()
'''


def get_given_code(cli_args: Optional[list] = None) -> Tuple[str, str]:
    """
    Retrieve the given code payload to automate.
    Priority:
      1. Explicit command line file argument if specified
      2. sequences/demo file (primary user code file)
      3. Default fallback code
    Returns (code_payload, source_description)
    """
    # 1. Check if a specific file path was passed in cli_args or sys.argv
    target_path = None
    args_to_check = cli_args if cli_args is not None else []
    # If run directly as script (not in unit test), also check sys.argv
    if cli_args is None and len(sys.argv) > 1 and "demo.py" in sys.argv[0]:
        args_to_check = sys.argv[1:]

    for arg in args_to_check:
        if arg and not arg.startswith("-"):
            candidate = Path(arg)
            if candidate.is_file():
                target_path = candidate
                break

    if target_path and target_path.is_file():
        try:
            content = target_path.read_text(encoding="utf-8", errors="replace")
            return content, f"cli_arg: {target_path}"
        except Exception as e:
            logger.warning("DEMO", f"Failed to read file '{target_path}': {e}")

    # 2. Check primary sequences/demo
    demo_file = SEQUENCES_DIR / "demo"
    if not demo_file.is_file():
        demo_file = Path("sequences/demo")

    if demo_file.is_file():
        try:
            content = demo_file.read_text(encoding="utf-8", errors="replace")
            if content.strip():
                return content, f"sequences/demo ({len(content)} chars)"
        except Exception as e:
            logger.warning("DEMO", f"Failed to read sequences/demo: {e}")

    # 3. Fallback
    return DEFAULT_FALLBACK_CODE, "default_fallback"


def run_standalone_demo(loop: bool = False, target_file: Optional[str] = None):
    """Run standalone demonstration of the given code automation."""
    payload, source = get_given_code([target_file] if target_file else None)
    logger.info("DEMO", f"Loaded code from {source} ({len(payload)} chars). Continuous loop: {loop}")

    # Keep cursor movement under explicit user control.
    tasks = [
        {
            "type": "wait",
            "seconds": 1.0,
            "description": "Wait for target window focus"
        },
        {
            "type": "type_code",
            "text": payload,
            "speed": 0.333,
            "description": f"Type given code ({len(payload)} chars)"
        }
    ]

    print(f"\n[DeskPilot] Starting automation for {source} in 3 seconds... Press ESC anytime to abort.")
    success = executor.start(tasks, countdown_seconds=3, loop=loop)
    if not success:
        print("[DeskPilot] Failed to start executor.")
        return

    try:
        while executor.get_state() in [executor.state.RUNNING, executor.state.COUNTDOWN, executor.state.PAUSED]:
            time.sleep(0.2)
    except KeyboardInterrupt:
        executor.stop()
        print("\n[DeskPilot] Stopped by KeyboardInterrupt.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DeskPilot Given Code Automation Runner")
    parser.add_argument("file", nargs="?", default=None, help="Optional path to source code file")
    parser.add_argument("--loop", action="store_true", help="Loop continuously until ESC or stop")
    parsed_args = parser.parse_args()

    run_standalone_demo(loop=parsed_args.loop, target_file=parsed_args.file)

