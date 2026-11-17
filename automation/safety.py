"""
DeskPilot - Safety System
Ensures fail-safes, emergency stops, key release resets, and user confirmation guards.
"""

import time
import threading
from typing import Callable, Optional, List
import pyautogui
from utils.logger import logger
from automation.input_dispatcher import input_dispatcher


class SafetyManager:
    """Manages automation safety, emergency hotkeys, and hardware state resets."""
    def __init__(self):
        self._emergency_callbacks: List[Callable[[], None]] = []
        self._is_emergency_stopped = False
        self._lock = threading.Lock()
        
        # Configure PyAutoGUI core safety
        # When cursor is parked at (0, 0) (e.g. background/headless or startup),
        # avoid immediate false-positive corner abort.
        try:
            curr_pos = pyautogui.position()
            pyautogui.FAILSAFE = not (curr_pos.x == 0 and curr_pos.y == 0)
        except Exception:
            pyautogui.FAILSAFE = False
        pyautogui.PAUSE = 0.01  # Minimal built-in pause between actions

    def set_failsafe(self, enabled: bool):
        """Set fail-safe status with guard for parked (0, 0) cursor."""
        try:
            curr_pos = pyautogui.position()
            if enabled and curr_pos.x == 0 and curr_pos.y == 0:
                pyautogui.FAILSAFE = False
            else:
                pyautogui.FAILSAFE = enabled
        except Exception:
            pyautogui.FAILSAFE = enabled


    def add_emergency_callback(self, callback: Callable[[], None]):
        """Add a callback to be invoked on emergency stop."""
        with self._lock:
            if callback not in self._emergency_callbacks:
                self._emergency_callbacks.append(callback)

    def trigger_emergency_stop(self):
        """Immediately abort all active automation and reset hardware states."""
        with self._lock:
            self._is_emergency_stopped = True
        logger.error("SAFETY", "EMERGENCY STOP TRIGGERED! Halting all automation immediately.")
        
        self._release_hardware_state()

        # Invoke all callbacks
        with self._lock:
            callbacks = list(self._emergency_callbacks)
        for cb in callbacks:
            try:
                cb()
            except Exception as e:
                logger.error("SAFETY", f"Error in emergency stop callback: {e}")

    def _release_hardware_state(self):
        held_keys, held_buttons = input_dispatcher.held_inputs()

        # Release any mouse buttons tracked as held down (strictly excluding right button,
        # which DeskPilot never holds and which would inject spurious right-click tab menus).
        for button in list(held_buttons):
            if button != "right":
                try:
                    pyautogui.mouseUp(button=button, _pause=False)
                except Exception:
                    logger.debug("SAFETY", f"Mouse button release skipped: {button}")
            input_dispatcher.track_mouse_up(button)

        # Release keys that were tracked as held down
        for key in list(held_keys):
            try:
                pyautogui.keyUp(key, _pause=False)
                input_dispatcher.track_key_up(key)
            except Exception:
                logger.debug("SAFETY", f"Key release skipped: {key}")

        # For emergency abort or safety cleanup, check physical modifier states (keys only)
        modifier_vks = {
            "shift": 0x10,
            "ctrl": 0x11,
            "alt": 0x12,
        }
        for mod_name, vk in modifier_vks.items():
            try:
                if ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000:
                    pyautogui.keyUp(mod_name, _pause=False)
                    input_dispatcher.track_key_up(mod_name)
            except Exception:
                pass

        logger.info("SAFETY", "Hardware inputs normalized. No spurious mouse or modifier events sent.")

    def reset_hardware_state(self):
        """Release held inputs through the dispatcher during normal shutdown."""
        input_dispatcher.dispatch(self._release_hardware_state)

    def clear_emergency_stop(self):
        """Clear emergency stop flag when user resets or starts new run."""
        with self._lock:
            self._is_emergency_stopped = False

    def is_emergency_stopped(self) -> bool:
        with self._lock:
            return self._is_emergency_stopped

    def interruptible_sleep(
        self,
        seconds: float,
        cancel_check: Optional[Callable[[], bool]] = None,
        step: float = 0.01
    ) -> bool:
        """
        Sleep for 'seconds' in small increments ('step'), checking emergency stop
        and cancel conditions frequently for immediate responsiveness (<10ms).
        Returns True if completed full duration, False if interrupted.
        """
        if seconds <= 0:
            return not self.is_emergency_stopped()

        end_time = time.time() + seconds
        while time.time() < end_time:
            if self.is_emergency_stopped():
                return False
            if cancel_check and cancel_check():
                return False
            
            remaining = end_time - time.time()
            time.sleep(min(step, max(0.001, remaining)))

        return not self.is_emergency_stopped()

    def execute_countdown(
        self,
        seconds: int,
        progress_callback: Optional[Callable[[int], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None
    ) -> bool:
        """
        Execute a safety countdown before automation begins, allowing the user
        to switch to their target application.
        Returns True if countdown finished successfully, False if cancelled.
        """
        logger.info("SAFETY", f"Starting {seconds}-second countdown before execution.")
        for remaining in range(seconds, 0, -1):
            if cancel_check and cancel_check():
                logger.warning("SAFETY", "Countdown cancelled by user.")
                return False
            if self.is_emergency_stopped():
                return False
            
            if progress_callback:
                progress_callback(remaining)
            
            # Use interruptible sleep for 1.0 second slices
            if not self.interruptible_sleep(1.0, cancel_check=cancel_check):
                return False

        if progress_callback:
            progress_callback(0)
            
        return True


# Global safety manager singleton
safety = SafetyManager()

