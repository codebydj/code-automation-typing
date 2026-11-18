"""
DeskPilot - Keyboard Controller Module
Provides fixed-cadence letter-by-letter typing, programming symbol preservation,
and standard shortcut execution with character-level pause/resume.
"""

import time
import math
import random
import threading
from typing import Callable, Optional, List, Dict, Any, Union
import pyautogui
import pyperclip
import keyboard
from utils.logger import logger
from automation.safety import safety
from automation.input_dispatcher import input_dispatcher, serialized_input
from automation.character_mapper import character_mapper, CharacterCategory, KeyMapping


class KeyboardController:
    """Automates keyboard typing, shortcuts, and key combinations."""

    # Map of supported standard shortcuts
    STANDARD_SHORTCUTS = {
        "ctrl+a": ("ctrl", "a"),
        "ctrl+c": ("ctrl", "c"),
        "ctrl+v": ("ctrl", "v"),
        "ctrl+x": ("ctrl", "x"),
        "ctrl+z": ("ctrl", "z"),
        "ctrl+s": ("ctrl", "s"),
        "home": ("home",),
        "end": ("end",),
        "shift+left": ("shift", "left"),
        "shift+right": ("shift", "right"),
        "shift+up": ("shift", "up"),
        "shift+down": ("shift", "down"),
        "ctrl+left": ("ctrl", "left"),
        "ctrl+right": ("ctrl", "right"),
        "ctrl+shift+left": ("ctrl", "shift", "left"),
        "ctrl+shift+right": ("ctrl", "shift", "right"),
        "shift+home": ("shift", "home"),
        "shift+end": ("shift", "end"),
        "backspace": ("backspace",),
        "delete": ("delete",),
        "enter": ("enter",),
        "tab": ("tab",),
        "esc": ("esc",),
    }

    def __init__(self):
        self._is_typing = False
        self.last_char_index = 0
        self.last_total_chars = 0
        self.current_state: Dict[str, Any] = {
            "is_typing": False,
            "char_index": 0,
            "total_chars": 0,
            "current_char": "",
            "line": 1,
            "col": 1,
            "wpm": 0.0,
            "is_paused": False
        }

    @serialized_input
    def type_character(self, ch: str, tab_width: Optional[int] = None, use_numpad: bool = False) -> bool:
        """
        Type a single character using exact character-aware system keyboard events.
        Identifies physical key mapping, required modifier keys (Shift), category,
        and ensures modifier keys are always released.
        Never uses clipboard paste as a replacement for character typing.
        """
        try:
            if ch == "\n":
                pyautogui.press("enter")
            elif ch == "\t":
                if tab_width is None:
                    pyautogui.press("tab")
                else:
                    if not 1 <= tab_width <= 8:
                        raise ValueError("Tab width must be between 1 and 8 spaces.")
                    for _ in range(tab_width):
                        pyautogui.press("space")
            elif ch == " ":
                pyautogui.press("space")
            else:
                character_mapper.use_numpad = use_numpad
                mapping = character_mapper.get_mapping(ch)
                if mapping:
                    held_mods = []
                    try:
                        for mod in mapping.modifiers:
                            pyautogui.keyDown(mod)
                            input_dispatcher.track_key_down(mod)
                            held_mods.append(mod)
                        pyautogui.press(mapping.primary_key)
                    finally:
                        # Guarantee modifier keys are always released
                        for mod in reversed(held_mods):
                            try:
                                pyautogui.keyUp(mod)
                                input_dispatcher.track_key_up(mod)
                            except Exception:
                                pass
                else:
                    # Direct SendInput unicode for special unicode not in standard layout
                    try:
                        keyboard.write(ch)
                    except Exception:
                        pyautogui.write(ch)
            return True
        except pyautogui.FailSafeException:
            safety.trigger_emergency_stop()
            logger.error_detailed(
                "KEYBOARD",
                "PyAutoGUI FailSafe triggered while typing character.",
                error_type="FailSafeException",
                action_type="type_character",
                action_params={"char": repr(ch)},
                suggestion="Mouse was moved to screen corner. Clear corner or adjust failsafe in Settings."
            )
            return False
        except Exception as e:
            logger.error_detailed(
                "KEYBOARD",
                f"Failed to type character {repr(ch)}: {e}",
                error_type=type(e).__name__,
                action_type="type_character",
                action_params={"char": repr(ch)},
                suggestion="Verify the target window accepts keyboard input and has focus."
            )
            return False

    def _clear_current_line_auto_indent(self) -> bool:
        """Remove IDE-inserted indentation without selecting prior lines."""
        original_clipboard = pyperclip.paste()
        marker = f"__deskpilot_indent_{time.monotonic_ns()}__"
        try:
            pyperclip.copy(marker)
            pyautogui.hotkey("shift", "home")
            pyautogui.hotkey("ctrl", "c")
            selected = pyperclip.paste()
            if selected != marker and selected and all(char in " \t" for char in selected):
                pyautogui.press("backspace")
            else:
                pyautogui.press("right")

            auto_indent = 0
            while True:
                pyautogui.hotkey("shift", "left")
                pyautogui.hotkey("ctrl", "c")
                selected = pyperclip.paste()
                if selected == marker or not selected or not all(char in " \t" for char in selected):
                    pyautogui.press("right")
                    break
                auto_indent = len(selected)

            if auto_indent:
                for _ in range(auto_indent):
                    pyautogui.hotkey("shift", "left")
                pyautogui.press("backspace")
            return True
        finally:
            pyperclip.copy(original_clipboard)

    @serialized_input
    def type_text(
        self,
        text: str,
        speed_cps: float = 3.0,
        timing_mode: str = "fixed",
        exact_speed: bool = True,
        use_jitter: bool = False,
        base_delay: Optional[float] = None,
        min_delay: float = 0.280,
        max_delay: float = 0.380,
        punct_delay: float = 0.150,
        newline_delay: float = 0.250,
        use_numpad: bool = False,
        line_mouse_callback: Optional[Callable[[int], bool]] = None,
        start_index: int = 0,
        cursor_movement_on_newline: bool = False,
        smart_indent: bool = False,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        pause_event: Optional[threading.Event] = None,
        stop_event: Optional[threading.Event] = None,
        tab_width: Optional[int] = None,
        use_difficulty: Optional[bool] = None
    ) -> bool:
        """
        Type multiline text at a configurable cadence (Fixed 3 CPS average or
        Variable demonstration timing) with character-level pause/resume,
        exact source code preservation, and line-interval mouse coordination.
        """
        if not text:
            return True

        # Clear residual emergency stop flag when starting fresh typing session
        if start_index == 0:
            safety.clear_emergency_stop()

        total_chars = len(text)
        self.last_total_chars = total_chars

        if not math.isfinite(speed_cps) or speed_cps <= 0:
            logger.error("KEYBOARD", f"Invalid typing speed: {speed_cps!r} characters per second.")
            return False
        if base_delay is not None and (not math.isfinite(base_delay) or base_delay < 0):
            logger.error("KEYBOARD", f"Invalid per-character delay: {base_delay!r} seconds.")
            return False

        per_char_delay = base_delay if base_delay is not None else (1.0 / speed_cps)
        self._is_typing = True
        start_time = time.monotonic()
        next_char_deadline = start_time
        typed_count = 0

        # Calculate initial line and col up to start_index
        prefix = text[:start_index]
        current_line = prefix.count("\n") + 1
        last_nl = prefix.rfind("\n")
        current_col = len(prefix) - last_nl if last_nl != -1 else len(prefix) + 1

        is_fixed_mode = (timing_mode == "fixed") or exact_speed
        if use_difficulty is None:
            use_difficulty = (base_delay is None) and not is_fixed_mode

        from automation.timing_controller import timing_controller
        effective_cps = min(timing_controller.MAX_CONFIGURED_CPS, max(0.5, speed_cps))
        if not use_difficulty and base_delay is None:
            base_delay = 1.0 / effective_cps

        logger.action(
            "KEYBOARD",
            f"Starting typing ({total_chars} chars, CPS={effective_cps:.1f}, "
            f"difficulty_mode={'ACTIVE' if use_difficulty else 'FIXED'}, start_idx={start_index + 1})."
        )

        try:
            for idx in range(start_index, total_chars):
                ch = text[idx]
                human_idx = idx + 1
                self.last_char_index = human_idx

                # Check for stop or emergency stop
                if (stop_event and stop_event.is_set()) or safety.is_emergency_stopped():
                    logger.warning("KEYBOARD", f"Typing aborted at character {human_idx}/{total_chars}.")
                    self._update_state(False, human_idx, total_chars, ch, current_line, current_col, 0.0, False)
                    return False

                # Character-level pause handling: pause immediately before typing next char
                if pause_event and not pause_event.is_set():
                    disp_ch = "\\n" if ch == "\n" else ("\\t" if ch == "\t" else ch)
                    logger.info(
                        "KEYBOARD",
                        f"Typing paused at char {human_idx}/{total_chars} ('{disp_ch}', line {current_line}, col {current_col})."
                    )
                    # Guarantee all modifier keys released during pause
                    safety.reset_hardware_state()
                    self._update_state(True, human_idx, total_chars, ch, current_line, current_col, 0.0, is_paused=True)
                    
                    pause_event.wait()
                    if (stop_event and stop_event.is_set()) or safety.is_emergency_stopped():
                        return False
                    next_char_deadline = time.monotonic()
                    logger.info("KEYBOARD", f"Typing resumed from char {human_idx}/{total_chars}.")

                # Emit actual keystroke event
                if use_numpad:
                    success = self.type_character(ch, tab_width=tab_width, use_numpad=True)
                else:
                    success = self.type_character(ch, tab_width=tab_width)
                if not success:
                    return False

                typed_count += 1
                
                # Update line and column; cursor movement is a separate sequence action.
                if ch == "\n":
                    if smart_indent:
                        self._clear_current_line_auto_indent()
                    current_line += 1
                    current_col = 1

                    # Trigger line-interval mouse interaction if configured
                    if line_mouse_callback:
                        safety.reset_hardware_state()
                        try:
                            line_mouse_callback(current_line - 1)
                        except Exception as cb_err:
                            logger.warning("KEYBOARD", f"Line mouse callback error: {cb_err}")
                        if (stop_event and stop_event.is_set()) or safety.is_emergency_stopped():
                            return False
                        next_char_deadline = time.monotonic()
                else:
                    current_col += 1 if ch != "\t" else 4

                # Compute telemetry metrics
                elapsed = max(0.001, time.monotonic() - start_time)
                wpm = round((typed_count / 5.0) / (elapsed / 60.0), 1)
                measured_cps = round(typed_count / elapsed, 2)
                ch_cat = character_mapper.get_category(ch).value

                # Generate preview snippet
                snip_start = max(0, idx - 15)
                snip_end = min(total_chars, idx + 20)
                preview_snippet = text[snip_start:snip_end]

                telemetry = {
                    "index": human_idx,
                    "total": total_chars,
                    "char": ch,
                    "category": ch_cat,
                    "line": current_line,
                    "col": current_col,
                    "pct": round((human_idx / total_chars) * 100, 1),
                    "wpm": wpm,
                    "measured_cps": measured_cps,
                    "preview_snippet": preview_snippet,
                    "chars_remaining": total_chars - human_idx,
                    "elapsed": round(elapsed, 2)
                }

                self._update_state(True, human_idx, total_chars, ch, current_line, current_col, wpm, False)

                # Report progress
                if progress_callback:
                    try:
                        progress_callback(telemetry)
                    except TypeError:
                        try:
                            progress_callback(human_idx, total_chars, ch, current_line)
                        except Exception:
                            pass

                if idx + 1 < total_chars:
                    next_ch = text[idx + 1]

                    if not use_difficulty:
                        # Fixed CPS mode ("as usual"): each character delay is exactly the calibrated CPS base delay
                        delay = base_delay if base_delay is not None else (1.0 / effective_cps)
                    else:
                        # Dynamic Character Difficulty & Natural Rhythm via Central Timing Controller
                        delay = timing_controller.get_character_delay(
                            ch=next_ch,
                            prev_ch=ch,
                            cps=effective_cps,
                            use_jitter=use_jitter
                        )

                    sleep_completed = safety.interruptible_sleep(
                        delay,
                        cancel_check=lambda: (stop_event and stop_event.is_set()) or (pause_event and not pause_event.is_set())
                    )
                    if not sleep_completed and safety.is_emergency_stopped():
                        logger.warning("KEYBOARD", f"Typing immediately stopped by Emergency Stop at char {human_idx}.")
                        return False

            logger.success("KEYBOARD", f"Completed typing {total_chars} characters.")
            self._update_state(False, total_chars, total_chars, "", current_line, current_col, 0.0, False)
            return True

        except pyautogui.FailSafeException:
            logger.error_detailed(
                "KEYBOARD",
                "Fail-safe triggered during typing.",
                error_type="FailSafeException",
                suggestion="Moving mouse to corner aborted typing. Clear mouse corner to avoid triggers."
            )
            safety.trigger_emergency_stop()
            return False
        except Exception as e:
            logger.error_detailed(
                "KEYBOARD",
                f"Unexpected error during typing: {e}",
                error_type=type(e).__name__,
                suggestion="Ensure active focused window can accept text inputs."
            )
            return False
        finally:
            self._is_typing = False
            safety.reset_hardware_state()

    def _update_state(self, is_typing, idx, total, ch, line, col, wpm, is_paused):
        self.current_state = {
            "is_typing": is_typing,
            "char_index": idx,
            "total_chars": total,
            "current_char": ch,
            "line": line,
            "col": col,
            "wpm": wpm,
            "is_paused": is_paused
        }

    @serialized_input
    def press_hotkey(self, *keys: str) -> bool:
        """Execute a keyboard shortcut (e.g., 'ctrl', 's')."""
        try:
            expanded_keys: List[str] = []
            for k in keys:
                for part in k.lower().replace(" ", "").split("+"):
                    expanded_keys.append(part)

            logger.action("KEYBOARD", f"Executing shortcut: {' + '.join(expanded_keys).upper()}")
            pyautogui.hotkey(*expanded_keys)
            return True
        except pyautogui.FailSafeException:
            safety.trigger_emergency_stop()
            return False
        except Exception as e:
            logger.error_detailed(
                "KEYBOARD",
                f"Error executing hotkey {keys}: {e}",
                error_type=type(e).__name__,
                action_type="hotkey",
                action_params={"keys": keys},
                suggestion="Check if specified key names exist and are valid in PyAutoGUI."
            )
            return False

    @serialized_input
    def press_key(self, key: str, presses: int = 1, interval: float = 0.05) -> bool:
        """Press a specific key one or multiple times."""
        try:
            key = key.lower().strip()
            logger.action("KEYBOARD", f"Pressing key [{key.upper()}] x{presses}")
            pyautogui.press(key, presses=presses, interval=interval)
            return True
        except pyautogui.FailSafeException:
            safety.trigger_emergency_stop()
            return False
        except Exception as e:
            logger.error_detailed(
                "KEYBOARD", f"Error pressing key {key}: {e}", error_type=type(e).__name__,
                action_type="press_key", action_params={"key": key, "presses": presses},
                suggestion="Verify the key name is valid."
            )
            return False

    @serialized_input
    def key_down(self, key: str) -> bool:
        """Hold a key down until a matching key_up action is executed."""
        try:
            normalized = key.lower().strip()
            pyautogui.keyDown(normalized)
            input_dispatcher.track_key_down(normalized)
            return True
        except Exception as e:
            logger.error_detailed("KEYBOARD", f"Could not hold key {key}: {e}", error_type=type(e).__name__)
            return False

    @serialized_input
    def key_up(self, key: str) -> bool:
        """Release a previously held key."""
        try:
            normalized = key.lower().strip()
            pyautogui.keyUp(normalized)
            input_dispatcher.track_key_up(normalized)
            return True
        except Exception as e:
            logger.error_detailed("KEYBOARD", f"Could not release key {key}: {e}", error_type=type(e).__name__)
            return False
    @serialized_input
    def select_by_arrows(self, direction: str = "right", count: int = 1, mode: str = "char") -> bool:
        """
        Programmatic text selection using keyboard Shift+Arrow keys.
        
        Args:
            direction: 'left', 'right', 'up', 'down', 'home', 'end'
            count: Number of times to press the navigation key
            mode: 'char' (Shift+Arrow), 'word' (Ctrl+Shift+Arrow), 'line' (Shift+Home/End)
        """
        try:
            direction = direction.lower().strip()
            logger.action("KEYBOARD", f"Selecting text via Shift+{direction.upper()} (mode: {mode}, count: {count})")

            for _ in range(max(1, count)):
                if safety.is_emergency_stopped():
                    return False

                if mode == "word" and direction in ["left", "right"]:
                    pyautogui.hotkey("ctrl", "shift", direction)
                elif mode == "line" and direction in ["home", "end"]:
                    pyautogui.hotkey("shift", direction)
                else:
                    pyautogui.hotkey("shift", direction)

                time.sleep(0.04)

            return True
        except Exception as e:
            logger.error_detailed(
                "KEYBOARD",
                f"Failed to execute arrow text selection: {e}",
                error_type=type(e).__name__,
                action_type="select_arrows",
                action_params={"direction": direction, "count": count, "mode": mode}
            )
            return False

    @serialized_input
    def select_all(self) -> bool:
        """Select all text in focused window using Ctrl+A."""
        logger.action("KEYBOARD", "Selecting all text via Ctrl+A")
        return self.press_hotkey("ctrl", "a")

    @serialized_input
    def copy(self) -> bool:
        """Copy selected text using Ctrl+C."""
        logger.action("KEYBOARD", "Copying selection via Ctrl+C")
        return self.press_hotkey("ctrl", "c")

    @serialized_input
    def paste(self) -> bool:
        """Paste clipboard content using Ctrl+V."""
        logger.action("KEYBOARD", "Pasting via Ctrl+V")
        return self.press_hotkey("ctrl", "v")

    @serialized_input
    def cut(self) -> bool:
        """Cut selected text using Ctrl+X."""
        logger.action("KEYBOARD", "Cutting selection via Ctrl+X")
        return self.press_hotkey("ctrl", "x")

    @serialized_input
    def undo(self) -> bool:
        """Undo last action using Ctrl+Z."""
        logger.action("KEYBOARD", "Undo via Ctrl+Z")
        return self.press_hotkey("ctrl", "z")

    @serialized_input
    def save(self) -> bool:
        """Save file in focused window using Ctrl+S."""
        logger.action("KEYBOARD", "Saving file via Ctrl+S")
        return self.press_hotkey("ctrl", "s")

    @serialized_input
    def navigate_by_arrows(self, direction: str = "right", count: int = 1, mode: str = "char") -> bool:
        """
        Keyboard navigation using arrows, Ctrl+Arrows, Home, End.
        Args:
            direction: 'left', 'right', 'up', 'down', 'home', 'end'
            count: Number of times to press the key
            mode: 'char' (single step), 'word' (Ctrl+Arrow), 'line' (Home/End)
        """
        try:
            direction = direction.lower().strip()
            logger.action("KEYBOARD", f"Navigating cursor via {direction.upper()} (mode: {mode}, count: {count})")
            for _ in range(max(1, count)):
                if safety.is_emergency_stopped():
                    return False
                if mode == "word" and direction in ["left", "right"]:
                    pyautogui.hotkey("ctrl", direction)
                elif mode == "line" and direction in ["home", "end"]:
                    pyautogui.press(direction)
                else:
                    pyautogui.press(direction)
                time.sleep(0.03)
            return True
        except Exception as e:
            logger.error_detailed(
                "KEYBOARD",
                f"Failed arrow navigation: {e}",
                error_type=type(e).__name__,
                action_type="navigate_arrows",
                action_params={"direction": direction, "count": count, "mode": mode}
            )
            return False


# Singleton instance
keyboard_ctrl = KeyboardController()
