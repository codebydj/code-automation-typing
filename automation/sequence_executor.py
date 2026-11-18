"""
DeskPilot - Action Sequence Executor
Threaded execution engine supporting start, pause, resume, stop, and emergency abort.
Features character-level pause/resume granularity and comprehensive action dispatching.
"""

import time
import math
import random
import threading
from enum import Enum
from typing import List, Dict, Any, Optional, Callable
from utils.logger import logger
from automation.safety import safety
from automation.keyboard_controller import keyboard_ctrl
from automation.mouse_controller import mouse_ctrl
from config import DEFAULT_CONFIG, load_config


class ExecutionState(str, Enum):
    IDLE = "IDLE"
    COUNTDOWN = "COUNTDOWN"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    REST_PAUSED = "REST_PAUSED"
    STOPPED = "STOPPED"
    EMERGENCY_STOPPED = "EMERGENCY_STOPPED"
    COMPLETED = "COMPLETED"


class SequenceExecutor:
    """Manages thread-safe automated execution of action lists."""

    def __init__(self):
        self._state = ExecutionState.IDLE
        self._current_sequence: List[Dict[str, Any]] = []
        self._current_index = 0
        self._total_actions = 0
        self._total_executed = 0
        self._loop_enabled = False
        self._loop_count = 0
        
        # Thread control primitives
        self._thread: Optional[threading.Thread] = None
        self._pause_event = threading.Event()
        self._pause_event.set()  # Set means NOT paused
        self._stop_event = threading.Event()
        self._skip_rest_event = threading.Event()
        self._lock = threading.RLock()

        # Listen for safety emergency stops
        safety.add_emergency_callback(self._on_safety_emergency_stop)

        # UI Callbacks
        self.on_status_change: Optional[Callable[[str], None]] = None
        self.on_progress: Optional[Callable[[int, int, float], None]] = None
        self.on_action_start: Optional[Callable[[int, Dict[str, Any]], None]] = None
        self.on_action_finish: Optional[Callable[[int, Dict[str, Any], bool], None]] = None
        self.on_keyboard_action: Optional[Callable[[str], None]] = None
        self.on_typing_telemetry: Optional[Callable[[Dict[str, Any]], None]] = None
        self.on_countdown: Optional[Callable[[int], None]] = None
        self.on_rest_pause_countdown: Optional[Callable[[int, int], None]] = None
        self.on_completed: Optional[Callable[[int, float], None]] = None

    @property
    def state(self) -> ExecutionState:
        with self._lock:
            return self._state

    def get_state(self) -> ExecutionState:
        """Return current execution state."""
        return self.state

    @property
    def current_index(self) -> int:
        return self._current_index

    @property
    def total_actions(self) -> int:
        return self._total_actions

    def _set_state(self, new_state: ExecutionState):
        with self._lock:
            self._state = new_state
            callback = self.on_status_change
        if callback:
            try:
                callback(new_state.value)
            except Exception as e:
                print(f"[Executor Status CB Error]: {e}")

    def _on_safety_emergency_stop(self):
        """Handler called when global emergency stop is triggered."""
        self._stop_event.set()
        self._pause_event.set()
        self._skip_rest_event.set()
        self._set_state(ExecutionState.EMERGENCY_STOPPED)

    def start(self, actions: List[Dict[str, Any]], countdown_seconds: int = 3, loop: bool = False) -> bool:
        """Start executing a sequence from the beginning."""
        if not actions:
            logger.warning("SEQUENCE", "Cannot start: action list is empty.")
            return False

        with self._lock:
            if self._worker_is_active():
                logger.warning("SEQUENCE", "Cannot start: an execution worker is still active.")
                return False

            safety.clear_emergency_stop()
            self._current_sequence = [dict(a) for a in actions]
            self._current_index = 0
            self._total_actions = len(actions)
            self._total_executed = 0
            self._loop_enabled = loop
            self._loop_count = 0
            self._stop_event.clear()
            self._skip_rest_event.clear()
            self._pause_event.set()

            self._thread = threading.Thread(
                target=self._run_sequence_worker,
                args=(countdown_seconds,),
                daemon=True,
                name="DeskPilot-ExecutorThread"
            )
            self._set_state(
                ExecutionState.COUNTDOWN if countdown_seconds > 0 else ExecutionState.RUNNING
            )
            self._thread.start()
        return True

    def _worker_is_active(self) -> bool:
        return bool(self._thread and self._thread.is_alive()) or self._state in (
            ExecutionState.RUNNING,
            ExecutionState.COUNTDOWN,
            ExecutionState.PAUSED,
            ExecutionState.REST_PAUSED
        )

    def pause(self) -> bool:
        """Pause execution at the current step or character."""
        with self._lock:
            if self._state != ExecutionState.RUNNING:
                return False
            self._pause_event.clear()
            self._set_state(ExecutionState.PAUSED)
        logger.info("SEQUENCE", f"Automation paused at step {self._current_index + 1}/{self._total_actions}.")
        return True

    def skip_rest_pause(self) -> bool:
        """Skip active 3–6 minute rest pause and immediately resume typing."""
        with self._lock:
            if self._state != ExecutionState.REST_PAUSED:
                return False
            self._skip_rest_event.set()
        logger.info("SEQUENCE", "Rest pause skipped by user; auto-resuming typing immediately.")
        return True

    def resume(self) -> bool:
        """Resume execution from the exact paused step, character, or rest pause."""
        with self._lock:
            if self._state == ExecutionState.REST_PAUSED:
                self._skip_rest_event.set()
                return True
            if self._state != ExecutionState.PAUSED:
                return False
            self._set_state(ExecutionState.RUNNING)
            self._pause_event.set()
        logger.info("SEQUENCE", f"Automation resumed at step {self._current_index + 1}/{self._total_actions}.")
        return True

    def stop(self) -> bool:
        """Gracefully stop automation."""
        with self._lock:
            if not self._worker_is_active():
                return False
            logger.info("SEQUENCE", "Stop requested by user.")
            self._stop_event.set()
            self._pause_event.set()
            self._skip_rest_event.set()
            self._set_state(ExecutionState.STOPPED)
        safety.reset_hardware_state()
        return True

    def emergency_stop(self):
        """Immediately abort all operations with emergency stop."""
        safety.trigger_emergency_stop()
        with self._lock:
            self._stop_event.set()
            self._pause_event.set()
            self._skip_rest_event.set()
            self._set_state(ExecutionState.EMERGENCY_STOPPED)

    def run_single_action(self, action: Dict[str, Any]) -> bool:
        """Execute a single task directly without running the entire sequence."""
        with self._lock:
            if self._worker_is_active():
                logger.warning("SEQUENCE", "Cannot run single action: another task is currently executing.")
                return False

            safety.clear_emergency_stop()
            self._stop_event.clear()
            self._pause_event.set()
            self._set_state(ExecutionState.RUNNING)

        def worker():
            try:
                success = self._execute_single_action(dict(action))
                if success:
                    logger.success("ACTION", f"Single task [{action.get('type')}] executed successfully.")
                else:
                    logger.warning("ACTION", f"Single task [{action.get('type')}] returned false.")
            except Exception as e:
                logger.error_detailed("ACTION", f"Error in single task: {e}", error_type=type(e).__name__)
            finally:
                safety.reset_hardware_state()
                if safety.is_emergency_stopped():
                    self._set_state(ExecutionState.EMERGENCY_STOPPED)
                elif self._stop_event.is_set():
                    self._set_state(ExecutionState.STOPPED)
                else:
                    self._set_state(ExecutionState.IDLE)

        with self._lock:
            self._thread = threading.Thread(
                target=worker,
                daemon=True,
                name="DeskPilot-SingleTaskWorker"
            )
            self._thread.start()
        return True

    def wait_for_idle(self, timeout: float = 2.0) -> bool:
        """Wait for the current execution worker to exit."""
        thread = self._thread
        if thread and thread is not threading.current_thread():
            thread.join(timeout=max(0.0, timeout))
        return not (thread and thread.is_alive())

    def _wait_interruptibly(self, seconds: float) -> bool:
        """Wait for a duration, preserving its remaining time across pause/resume."""
        remaining = max(0.0, seconds)
        while remaining > 0:
            if self._stop_event.is_set() or safety.is_emergency_stopped():
                return False
            if not self._pause_event.is_set():
                self._pause_event.wait()
                continue

            started = time.monotonic()
            completed = safety.interruptible_sleep(
                remaining,
                cancel_check=lambda: self._stop_event.is_set() or not self._pause_event.is_set()
            )
            remaining = max(0.0, remaining - (time.monotonic() - started))
            if self._stop_event.is_set() or safety.is_emergency_stopped():
                return False
            if completed:
                return True

        return not self._stop_event.is_set() and not safety.is_emergency_stopped()

    def focus_window_by_title(self, title_pattern: str) -> bool:
        """Focus a target window by partial title match, with Win32 foreground fallback."""
        if not title_pattern or title_pattern.lower() in ("active window / manual focus", "any window", "none"):
            return True
        try:
            import pygetwindow
            import ctypes
            normalized_title = title_pattern.strip().lower()
            if normalized_title in ("vs code", "vscode"):
                normalized_title = "visual studio code"
            matching = [
                window for window in pygetwindow.getAllWindows()
                if normalized_title in window.title.lower()
            ]
            if matching:
                target = matching[0]
                try:
                    target.activate()
                except Exception:
                    pass
                hwnd = getattr(target, "_hWnd", None)
                if hwnd:
                    ctypes.windll.user32.ShowWindow(hwnd, 9)
                    ctypes.windll.user32.BringWindowToTop(hwnd)
                    ctypes.windll.user32.SetForegroundWindow(hwnd)
                time.sleep(0.3)
                return True
            else:
                logger.warning("SEQUENCE", f"No window matching '{title_pattern}' found to focus.")
                return False
        except Exception as e:
            logger.warning("SEQUENCE", f"Could not focus window '{title_pattern}': {e}")
            return False

    def _run_sequence_worker(self, countdown_seconds: int):
        """Worker thread executing the countdown and action sequence."""
        start_time = time.time()
        execution_cfg = load_config().get("execution", {})
        try:
            default_action_pause = float(
                execution_cfg.get(
                    "default_action_pause",
                    DEFAULT_CONFIG["execution"]["default_action_pause"]
                )
            )
        except (TypeError, ValueError):
            default_action_pause = float(DEFAULT_CONFIG["execution"]["default_action_pause"])
            logger.warning("SEQUENCE", "Invalid default action pause; using the configured default.")
        if not math.isfinite(default_action_pause) or default_action_pause < 0:
            default_action_pause = float(DEFAULT_CONFIG["execution"]["default_action_pause"])
            logger.warning("SEQUENCE", "Invalid default action pause; using the configured default.")
        
        # Phase 1: Countdown
        if countdown_seconds > 0:
            self._set_state(ExecutionState.COUNTDOWN)
            countdown_ok = safety.execute_countdown(
                seconds=countdown_seconds,
                progress_callback=self.on_countdown,
                cancel_check=lambda: self._stop_event.is_set()
            )
            if not countdown_ok or self._stop_event.is_set() or safety.is_emergency_stopped():
                self._set_state(ExecutionState.STOPPED)
                return

        # Phase 2: Action Loop
        self._set_state(ExecutionState.RUNNING)
        logger.info("SEQUENCE", f"Starting sequence of {self._total_actions} actions (Continuous Loop={self._loop_enabled}).")

        while True:
            # Check stop condition
            if self._stop_event.is_set() or safety.is_emergency_stopped():
                break

            # Check pause condition
            if not self._pause_event.is_set():
                self._pause_event.wait()
                if self._stop_event.is_set() or safety.is_emergency_stopped():
                    break

            # If all actions in the current cycle completed
            if self._current_index >= self._total_actions:
                if self._loop_enabled and not self._stop_event.is_set() and not safety.is_emergency_stopped():
                    self._loop_count += 1
                    # Reset sequence index to 0 for next iteration
                    self._current_index = 0
                    continue
                else:
                    break

            action = self._current_sequence[self._current_index]
            step_num = self._current_index + 1
            
            # Check if task is enabled
            if not action.get("enabled", True):
                logger.info("SEQUENCE", f"Skipping disabled task {step_num}/{self._total_actions}: [{action.get('type')}]")
                self._current_index += 1
                continue
            
            # Progress update
            progress_pct = (self._current_index / self._total_actions) * 100
            if self.on_progress:
                self.on_progress(step_num, self._total_actions, progress_pct)

            if self.on_action_start:
                self.on_action_start(self._current_index, action)

            # Execute single action
            success = self._execute_single_action(action)

            # If paused during execution of action, wait before advancing index
            if not self._pause_event.is_set() and not self._stop_event.is_set() and not safety.is_emergency_stopped():
                self._pause_event.wait()
                if self._stop_event.is_set() or safety.is_emergency_stopped():
                    break

            if self.on_action_finish:
                self.on_action_finish(self._current_index, action, success)

            if not success and (self._stop_event.is_set() or safety.is_emergency_stopped()):
                break

            self._total_executed += 1
            
            # Delay after action if specified
            try:
                delay_after = float(action.get("delay_after", default_action_pause))
            except (TypeError, ValueError):
                logger.error("SEQUENCE", f"Invalid delay after action {step_num}: {action.get('delay_after')!r}.")
                self._stop_event.set()
                break
            if not math.isfinite(delay_after) or delay_after < 0:
                logger.error("SEQUENCE", f"Invalid delay after action {step_num}: {delay_after!r}.")
                self._stop_event.set()
                break
            if delay_after > 0 and not self._wait_interruptibly(delay_after):
                break

            # Advance step index only if action finished without mid-action pause
            if not action.get("_incomplete_pause", False):
                self._current_index += 1
            else:
                action["_incomplete_pause"] = False

        # Post-loop status determination
        elapsed = time.time() - start_time
        safety.reset_hardware_state()

        if self.on_keyboard_action:
            self.on_keyboard_action("None")

        if safety.is_emergency_stopped():
            self._set_state(ExecutionState.EMERGENCY_STOPPED)
            logger.error("SEQUENCE", "Sequence terminated by Emergency Stop.")
        elif self._stop_event.is_set():
            self._set_state(ExecutionState.STOPPED)
            logger.warning("SEQUENCE", f"Sequence stopped at step {self._current_index}/{self._total_actions}.")
        else:
            self._set_state(ExecutionState.COMPLETED)
            if self.on_progress:
                self.on_progress(self._total_actions, self._total_actions, 100.0)
            logger.success("SEQUENCE", f"Sequence completed successfully ({self._total_executed} actions in {elapsed:.2f}s).")
            if self.on_completed:
                self.on_completed(self._total_executed, elapsed)

    def _execute_single_action(self, action: Dict[str, Any]) -> bool:
        """Dispatch a single action based on its type."""
        action_type = action.get("type", "").lower()
        desc = action.get("description", action_type)
        logger.action("ACTION", f"Step {self._current_index + 1}: [{action_type.upper()}] - {desc}")

        try:
            if action_type in ["move_mouse", "human_move_mouse", "human_move", "move_with_profile"]:
                is_random = bool(action.get("random_movement", False) or action.get("random", False) or ("x" not in action and "y" not in action))
                if is_random:
                    min_dur = float(action.get("min_duration", 0.35))
                    max_dur = float(action.get("max_duration", 1.0))
                    min_len = int(action.get("min_length", 40))
                    max_len = int(action.get("max_length", 240))
                    return mouse_ctrl.human_move_random(min_duration=min_dur, max_duration=max_dur, min_length=min_len, max_length=max_len)
                else:
                    x = int(action.get("x", 0))
                    y = int(action.get("y", 0))
                    duration = float(action.get("duration", 0.45))
                    profile = str(action.get("profile", action.get("movement_profile", "curved")))
                    return mouse_ctrl.move_with_profile(x, y, profile=profile, duration=duration)

            elif action_type in [
                "click", "right_click", "double_click", "triple_click",
                "drag", "drag_and_drop", "select_text", "select_text_drag",
                "deselect_text", "select_all", "mouse_down", "mousedown",
                "mouse_up", "mouseup", "scroll"
            ]:
                logger.warning(
                    "ACTION",
                    f"Mouse action '{action_type}' is disabled and removed. DeskPilot only allows mouse cursor movement."
                )
                return True

            elif action_type == "select_arrows":
                direction = action.get("direction", "right")
                count = int(action.get("count", 1))
                mode = action.get("mode", "char")
                return keyboard_ctrl.select_by_arrows(direction=direction, count=count, mode=mode)

            elif action_type in ["type_text", "type_code"]:
                text = str(action.get("text", ""))
                speed = float(action.get("speed", 0.333))  # Default 333ms (~3 chars/sec)
                start_idx = action.get("_resume_char_index", 0)

                cfg = load_config()
                typing_cfg = cfg.get("typing", {})
                mouse_cfg = cfg.get("mouse", {})
                line_cfg = mouse_cfg.get("line_interaction", {})

                timing_mode = str(action.get("timing_mode", typing_cfg.get("timing_mode", "fixed")))
                exact_speed = bool(action.get("exact_speed", (timing_mode == "fixed")))
                use_numpad = bool(action.get("use_numpad", typing_cfg.get("use_numpad", False)))
                punct_delay = float(action.get("punct_delay", typing_cfg.get("punct_delay", 0.150)))
                newline_delay = float(action.get("newline_delay", typing_cfg.get("newline_delay", 0.250)))

                # Line-interval mouse interaction hook (enabled by default)
                line_interaction_enabled = bool(action.get("line_mouse_enabled", line_cfg.get("enabled", True)))
                line_mouse_cb = None

                if line_interaction_enabled:
                    natural_mode = bool(action.get("natural_line_mouse", True))
                    every_line = bool(action.get("every_line", False))
                    if every_line:
                        min_lines = 1
                        max_lines = 1
                    else:
                        min_lines = max(1, int(action.get("min_lines", line_cfg.get("min_lines", 2))))
                        max_lines = max(min_lines, int(action.get("max_lines", line_cfg.get("max_lines", 5))))

                    target_x = int(action.get("mouse_target_x", line_cfg.get("target_x", 600)))
                    target_y = int(action.get("mouse_target_y", line_cfg.get("target_y", 450)))
                    m_profile = str(action.get("movement_profile", mouse_cfg.get("movement_profile", "curved")))
                    target_win = action.get("target_window", None)

                    lines_counter = [0]
                    interval = [random.randint(min_lines, max_lines) if min_lines < max_lines else min_lines]
                    total_doc_lines = text.count("\n") + 1

                    def on_line_completed(completed_line_num: int):
                        if self._stop_event.is_set() or safety.is_emergency_stopped():
                            return
                        lines_counter[0] += 1
                        is_single_line_doc = (total_doc_lines <= 1)
                        if lines_counter[0] >= interval[0] or (is_single_line_doc and completed_line_num == 1):
                            lines_counter[0] = 0
                            interval[0] = random.randint(min_lines, max_lines) if min_lines < max_lines else min_lines

                            # 1. Finish keyboard action & release all held keys
                            safety.reset_hardware_state()

                            # 2. Smoothly move cursor naturally with varied kinematics (move only, no clicks)
                            if self.on_keyboard_action:
                                self.on_keyboard_action(f"Moving mouse naturally after Line {completed_line_num}...")

                            if natural_mode:
                                mouse_ctrl.natural_line_mouse_move()
                            else:
                                logger.action(
                                    "SEQUENCE",
                                    f"Line interval reached ({completed_line_num} lines). Moving mouse to ({target_x}, {target_y}) [profile: {m_profile}]."
                                )
                                mouse_ctrl.move_with_profile(target_x, target_y, profile=m_profile)
                                if target_win:
                                    self.focus_window_by_title(target_win)

                            # 3. Release any inputs before continuing typing next line
                            safety.reset_hardware_state()

                    line_mouse_cb = on_line_completed

                # Random Rest Pause Hook (3 to 6 minutes human break between random line intervals with auto-resume)
                rand_pause_cfg = cfg.get("random_pause", {})
                rest_pause_enabled = bool(action.get("random_pause_enabled", rand_pause_cfg.get("enabled", True)))
                rest_pause_cb = None

                if rest_pause_enabled:
                    rp_min_lines = max(1, int(action.get("random_pause_min_lines", rand_pause_cfg.get("min_interval_lines", 15))))
                    rp_max_lines = max(rp_min_lines, int(action.get("random_pause_max_lines", rand_pause_cfg.get("max_interval_lines", 30))))
                    rp_min_secs = max(1, int(action.get("random_pause_min_seconds", rand_pause_cfg.get("min_duration_seconds", 180))))
                    rp_max_secs = max(rp_min_secs, int(action.get("random_pause_max_seconds", rand_pause_cfg.get("max_duration_seconds", 360))))
                    target_win = action.get("target_window", None)

                    rp_lines_counter = [0]
                    rp_interval = [random.randint(rp_min_lines, rp_max_lines)]

                    def on_rest_pause_completed(completed_line_num: int):
                        if self._stop_event.is_set() or safety.is_emergency_stopped():
                            return
                        rp_lines_counter[0] += 1
                        if rp_lines_counter[0] >= rp_interval[0]:
                            rp_lines_counter[0] = 0
                            rp_interval[0] = random.randint(rp_min_lines, rp_max_lines)

                            # 1. Release all hardware keys & mouse states completely
                            safety.reset_hardware_state()

                            # 2. Determine random pause duration (3 to 6 minutes: 180s - 360s)
                            pause_duration = random.randint(rp_min_secs, rp_max_secs)
                            logger.action(
                                "SEQUENCE",
                                f"Random Rest Pause triggered after Line {completed_line_num} "
                                f"for {pause_duration}s ({pause_duration // 60}m {pause_duration % 60}s). "
                                f"All hardware released; auto-resuming when timer reaches 0."
                            )

                            self._skip_rest_event.clear()
                            self._set_state(ExecutionState.REST_PAUSED)

                            try:
                                for remaining in range(pause_duration, 0, -1):
                                    if self._stop_event.is_set() or safety.is_emergency_stopped():
                                        break
                                    if self._skip_rest_event.is_set():
                                        logger.info("SEQUENCE", "Rest pause skipped by user.")
                                        break

                                    mm = remaining // 60
                                    ss = remaining % 60
                                    msg = f"Rest Pause: auto-resuming in {mm:02d}:{ss:02d} (Line {completed_line_num})"
                                    if self.on_keyboard_action:
                                        self.on_keyboard_action(msg)
                                    if self.on_rest_pause_countdown:
                                        self.on_rest_pause_countdown(remaining, pause_duration)

                                    safety.interruptible_sleep(
                                        1.0,
                                        cancel_check=lambda: self._stop_event.is_set() or safety.is_emergency_stopped() or self._skip_rest_event.is_set()
                                    )
                            finally:
                                self._skip_rest_event.clear()
                                safety.reset_hardware_state()

                            if self._stop_event.is_set() or safety.is_emergency_stopped():
                                return

                            # 3. Auto-resume: transition back to RUNNING and re-focus target window
                            logger.info("SEQUENCE", f"Rest Pause finished. Auto-resuming typing at Line {completed_line_num + 1}...")
                            self._set_state(ExecutionState.RUNNING)
                            if target_win:
                                self.focus_window_by_title(target_win)
                                time.sleep(0.4)

                    rest_pause_cb = on_rest_pause_completed

                def char_telemetry_cb(telemetry: Dict[str, Any]):
                    if isinstance(telemetry, dict):
                        ch = telemetry.get("char", "")
                        disp_char = repr(ch)[1:-1]
                        line = telemetry.get("line", 1)
                        idx = telemetry.get("index", 1)
                        tot = telemetry.get("total", len(text))
                        if self.on_keyboard_action:
                            self.on_keyboard_action(f"Typing '{disp_char}' (L{line}, {idx}/{tot})")
                        if self.on_typing_telemetry:
                            self.on_typing_telemetry(telemetry)
                        action["_resume_char_index"] = idx

                raw_diff = action.get("use_difficulty")
                if raw_diff is not None:
                    use_diff = bool(raw_diff)
                else:
                    use_diff = not (timing_mode == "fixed" or exact_speed)
                success = keyboard_ctrl.type_text(
                    text=text,
                    speed_cps=round(1.0 / max(0.001, speed), 2),
                    timing_mode=timing_mode,
                    exact_speed=exact_speed and not use_diff,
                    base_delay=None if use_diff else speed,
                    use_difficulty=use_diff,
                    punct_delay=punct_delay,
                    newline_delay=newline_delay,
                    use_numpad=use_numpad,
                    line_mouse_callback=line_mouse_cb,
                    rest_pause_callback=rest_pause_cb,
                    start_index=start_idx,
                    smart_indent=bool(action.get("smart_indent", typing_cfg.get("smart_indent", False))),
                    tab_width=action.get("tab_width"),
                    progress_callback=char_telemetry_cb,
                    pause_event=self._pause_event,
                    stop_event=self._stop_event
                )

                if success:
                    action.pop("_resume_char_index", None)
                    action["_incomplete_pause"] = False
                elif not self._pause_event.is_set():
                    # Paused mid-string: stay on this step to resume remaining chars
                    action["_incomplete_pause"] = True

                return success

            elif action_type == "navigate_arrows":
                direction = action.get("direction", "right")
                count = int(action.get("count", 1))
                mode = action.get("mode", "char")
                return keyboard_ctrl.navigate_by_arrows(direction=direction, count=count, mode=mode)

            elif action_type == "copy":
                return keyboard_ctrl.copy()

            elif action_type == "paste":
                return keyboard_ctrl.paste()

            elif action_type == "cut":
                return keyboard_ctrl.cut()

            elif action_type == "undo":
                return keyboard_ctrl.undo()

            elif action_type == "save":
                return keyboard_ctrl.save()

            elif action_type == "hotkey":
                keys = str(action.get("keys", ""))
                if self.on_keyboard_action:
                    self.on_keyboard_action(f"Hotkey: {keys.upper()}")
                return keyboard_ctrl.press_hotkey(keys)

            elif action_type == "press_key":
                key = str(action.get("key", "enter"))
                presses = int(action.get("presses", 1))
                if self.on_keyboard_action:
                    self.on_keyboard_action(f"Key: {key.upper()} x{presses}")
                return keyboard_ctrl.press_key(key, presses=presses)

            elif action_type == "key_down":
                return keyboard_ctrl.key_down(str(action.get("key", "shift")))

            elif action_type == "key_up":
                return keyboard_ctrl.key_up(str(action.get("key", "shift")))

            elif action_type == "focus_window":
                title_pattern = str(action.get("title", ""))
                return self.focus_window_by_title(title_pattern)

            elif action_type == "wait":
                seconds = float(action.get("seconds", 1.0))
                logger.action("ACTION", f"Waiting for {seconds:.2f} seconds...")
                return self._wait_interruptibly(seconds)

            else:
                logger.warning("ACTION", f"Unknown action type: '{action_type}'. Skipping.")
                return True

        except Exception as e:
            logger.error_detailed(
                "ACTION",
                f"Execution error in step {self._current_index + 1} ({action_type}): {e}",
                error_type=type(e).__name__,
                action_type=action_type,
                action_params=action
            )
            return False


# Global executor instance
executor = SequenceExecutor()
