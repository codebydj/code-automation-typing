"""
DeskPilot - Mouse Controller Module
Implements smooth, human-like mouse cursor movements only (Bézier curves,
eased movements, line-interval transitions).
All non-movement mouse operations (clicks, right-click, double-click,
drag-and-drop, and scrolling) are strictly removed to protect the target
editor from unwanted interactions, focus loss, or caret misplacement.
"""

import time
import math
import random
from typing import Tuple, Optional, Callable, Dict, Any
import pyautogui
from utils.logger import logger
from automation.safety import safety
from automation.input_dispatcher import serialized_input


class MouseController:
    """Automates mouse positioning and smooth human-like movement only."""

    EASING_MAP = {
        "easeInOutQuad": pyautogui.easeInOutQuad,
        "easeInQuad": pyautogui.easeInQuad,
        "easeOutQuad": pyautogui.easeOutQuad,
        "linear": pyautogui.linear,
    }

    def __init__(self):
        # Optional visual indicator callback: on_move(x, y), on_target_ping(x, y)
        self.on_cursor_ping: Optional[Callable[[int, int], None]] = None
        self.last_target_position: Tuple[int, int] = (0, 0)

    def get_position(self) -> Tuple[int, int]:
        """Return the current mouse coordinates (X, Y)."""
        try:
            pos = pyautogui.position()
            return int(pos.x), int(pos.y)
        except Exception:
            return 0, 0

    def get_screen_size(self) -> Tuple[int, int]:
        """Return the screen resolution (width, height)."""
        try:
            size = pyautogui.size()
            return int(size.width), int(size.height)
        except Exception:
            return 1920, 1080

    def is_within_screen_bounds(self, x: int, y: int) -> bool:
        """Validate if (x, y) resides inside the active display dimensions."""
        w, h = self.get_screen_size()
        return 0 <= x <= w and 0 <= y <= h

    @serialized_input
    def human_move_to(
        self,
        x: int,
        y: int,
        duration: Optional[float] = None
    ) -> bool:
        """
        Move the cursor to target (x, y) along a natural, curved trajectory using
        cubic Bézier paths, minimum-jerk acceleration/deceleration profiles,
        and subtle biological micro-tremor.
        """
        if safety.is_emergency_stopped():
            return False

        if not self.is_within_screen_bounds(x, y):
            w, h = self.get_screen_size()
            logger.error_detailed(
                "MOUSE",
                f"Target coordinates ({x}, {y}) are outside display bounds ({w}x{h}).",
                error_type="CoordinateOutOfBoundsError",
                action_type="human_move_to",
                action_params={"x": x, "y": y, "duration": duration},
                coordinates=(x, y),
                suggestion=f"Provide coordinates between (0, 0) and ({w}, {h})."
            )
            return False

        try:
            start_x, start_y = self.get_position()
            dist = math.hypot(x - start_x, y - start_y)
            w, h = self.get_screen_size()

            # If already at destination or negligible distance
            if dist < 2:
                pyautogui.moveTo(x, y)
                self.last_target_position = (x, y)
                if self.on_cursor_ping:
                    try:
                        self.on_cursor_ping(x, y)
                    except Exception:
                        pass
                return True

            # Calculate natural human duration if not explicitly specified
            if duration is None or duration <= 0:
                duration = max(0.25, min(1.3, 0.22 + (dist / 1400.0) * 0.45 + random.uniform(-0.04, 0.08)))

            logger.action("MOUSE", f"Human cursor moving ({start_x}, {start_y}) -> ({x}, {y}) [dist: {int(dist)}px, time: {duration:.2f}s]")

            # Compute cubic Bézier control points P1 & P2 with natural perpendicular arc deviation
            vec_x = x - start_x
            vec_y = y - start_y
            norm_x = -vec_y / dist
            norm_y = vec_x / dist

            # Natural wrist/arm curve deviation
            side = random.choice([-1, 1])
            dev_mag = random.uniform(0.08, 0.28) * dist  # wider arc range

            p1_x = start_x + 0.33 * vec_x + side * dev_mag * norm_x + random.uniform(-12, 12)
            p1_y = start_y + 0.33 * vec_y + side * dev_mag * norm_y + random.uniform(-12, 12)
            p2_x = start_x + 0.67 * vec_x + side * dev_mag * 0.75 * norm_x + random.uniform(-10, 10)
            p2_y = start_y + 0.67 * vec_y + side * dev_mag * 0.75 * norm_y + random.uniform(-10, 10)

            # Clamp control points within safe boundaries
            p1_x = max(10, min(w - 10, p1_x))
            p1_y = max(10, min(h - 10, p1_y))
            p2_x = max(10, min(w - 10, p2_x))
            p2_y = max(10, min(h - 10, p2_y))

            # Discretize path based on 60-90Hz refresh rate
            num_steps = max(18, int(duration * 90))
            step_delay = duration / num_steps

            for i in range(1, num_steps + 1):
                if safety.is_emergency_stopped():
                    safety.reset_hardware_state()
                    return False

                s = i / float(num_steps)
                # Minimum-jerk trajectory profile: 10*s^3 - 15*s^4 + 6*s^5 (zero jerk at endpoints)
                t = 10 * (s ** 3) - 15 * (s ** 4) + 6 * (s ** 5)

                # Cubic Bézier formula
                u = 1.0 - t
                bx = (u ** 3) * start_x + 3 * (u ** 2) * t * p1_x + 3 * u * (t ** 2) * p2_x + (t ** 3) * x
                by = (u ** 3) * start_y + 3 * (u ** 2) * t * p1_y + 3 * u * (t ** 2) * p2_y + (t ** 3) * y

                # Subtle mid-flight micro-tremor — stronger in the middle of the arc
                tremor_envelope = math.sin(s * math.pi)
                tremor_x = random.uniform(-1.2, 1.2) * tremor_envelope
                tremor_y = random.uniform(-1.2, 1.2) * tremor_envelope

                curr_x = int(round(bx + tremor_x))
                curr_y = int(round(by + tremor_y))

                # Safe clamp to avoid triggering (0,0) failsafe corner
                curr_x = max(5, min(w - 5, curr_x))
                curr_y = max(5, min(h - 5, curr_y))

                pyautogui.moveTo(curr_x, curr_y, _pause=False)

                # Variable step timing: speed up mid-arc, slow at start/end (like human wrist)
                speed_envelope = 0.5 + math.sin(s * math.pi) * 0.5  # peaks in middle
                step_jitter = random.uniform(-0.002, 0.002)
                actual_step_delay = max(0.001, step_delay / max(0.3, speed_envelope) + step_jitter)
                time.sleep(actual_step_delay)

            # Settle onto exact destination coordinate
            pyautogui.moveTo(x, y, _pause=False)
            self.last_target_position = (x, y)

            if self.on_cursor_ping:
                try:
                    self.on_cursor_ping(x, y)
                except Exception:
                    pass

            return True

        except pyautogui.FailSafeException:
            logger.error_detailed(
                "MOUSE",
                "Fail-safe triggered by mouse movement to screen corner.",
                error_type="FailSafeException",
                coordinates=(x, y),
                suggestion="Mouse reached screen corner. Emergency stop engaged."
            )
            safety.trigger_emergency_stop()
            return False
        except Exception as e:
            logger.error_detailed(
                "MOUSE",
                f"Error in human cursor movement to ({x}, {y}): {e}",
                error_type=type(e).__name__,
                coordinates=(x, y)
            )
            return False

    @serialized_input
    def human_move_random(
        self,
        min_duration: float = 0.4,
        max_duration: float = 1.6,
        min_length: int = 80,
        max_length: int = 480
    ) -> bool:
        """
        Move the cursor for a random time and random length in a deeply human way.
        Uses variable speed, multi-segment paths, and occasional overshoot/correction.
        Move only: does not click, drag, or trigger unwanted cursor operations.
        Safely stays away from screen corners and bounds.
        """
        if safety.is_emergency_stopped():
            return False

        curr_x, curr_y = self.get_position()
        w, h = self.get_screen_size()

        # Occasionally do a multi-segment move (humans rarely move in one straight arc)
        num_segments = random.choices([1, 2, 3], weights=[0.50, 0.35, 0.15])[0]

        for seg in range(num_segments):
            if safety.is_emergency_stopped():
                return False

            curr_x, curr_y = self.get_position()

            # Random length per segment; later segments are shorter (fatigue-like)
            seg_factor = 1.0 if seg == 0 else random.uniform(0.3, 0.6)
            length = random.uniform(min_length * seg_factor, max_length * seg_factor)

            # Random direction with slight bias toward interesting screen areas
            angle = random.uniform(0, 2 * math.pi)

            target_x = int(curr_x + length * math.cos(angle))
            target_y = int(curr_y + length * math.sin(angle))

            # Safe margins from screen corners and edges (keep away from top tabs)
            margin_x = max(120, min(180, w // 7))
            margin_y = max(140, min(220, h // 6))

            # If outside safe margins, steer naturally toward screen center
            if not (margin_x <= target_x <= w - margin_x and margin_y <= target_y <= h - margin_y):
                center_x = w // 2
                center_y = h // 2
                angle_to_center = math.atan2(center_y - curr_y, center_x - curr_x)
                angle = angle_to_center + random.uniform(-math.pi / 3, math.pi / 3)
                target_x = int(curr_x + length * math.cos(angle))
                target_y = int(curr_y + length * math.sin(angle))

            # Clamp safely
            target_x = max(margin_x, min(w - margin_x, target_x))
            target_y = max(margin_y, min(h - margin_y, target_y))

            # Random duration per segment – earlier segments faster, later slower
            seg_dur_range = (min_duration / num_segments, max_duration / num_segments)
            if min_duration >= 0.25:
                seg_dur_range = (max(0.25, seg_dur_range[0]), max(0.5, seg_dur_range[1]))
            duration = random.uniform(seg_dur_range[0], max(seg_dur_range[0], seg_dur_range[1]))

            logger.action(
                "MOUSE",
                f"Human cursor random motion [seg {seg+1}/{num_segments}]: ~{int(length)}px over {duration:.2f}s to ({target_x}, {target_y})"
            )

            ok = self.human_move_to(target_x, target_y, duration=duration)
            if not ok:
                return False

            # Between segments: tiny hesitation as if reconsidering direction
            if seg < num_segments - 1:
                pause = random.uniform(0.05, 0.25)
                time.sleep(pause)

        # Occasional micro-correction at the end (humans overshoot then nudge back)
        if random.random() < 0.30:
            fx, fy = self.get_position()
            nudge_x = fx + random.randint(-18, 18)
            nudge_y = fy + random.randint(-18, 18)
            nudge_x = max(10, min(w - 10, nudge_x))
            nudge_y = max(10, min(h - 10, nudge_y))
            self.human_move_to(nudge_x, nudge_y, duration=random.uniform(0.08, 0.22))

        return True

    @serialized_input
    def move_with_profile(
        self,
        x: int,
        y: int,
        profile: str = "curved",
        duration: Optional[float] = None,
        easing_name: str = "easeInOutQuad"
    ) -> bool:
        """
        Move the cursor using a configurable movement profile:
        - 'direct': straight-line predictable movement.
        - 'smooth': eased movement using configured acceleration/deceleration curves.
        - 'curved': natural curved demonstration movement using cubic Bézier paths.
        """
        profile = (profile or "curved").lower().strip()
        if profile in ("curved", "bezier", "demonstration"):
            return self.human_move_to(x, y, duration=duration)
        elif profile in ("smooth", "eased"):
            return self.move_to(x, y, duration=duration or 0.45, easing_name=easing_name, use_human_curves=False)
        elif profile in ("direct", "linear"):
            return self.move_to(x, y, duration=duration or 0.15, easing_name="linear", use_human_curves=False)
        else:
            # Default to curved demonstration
            return self.human_move_to(x, y, duration=duration)

    @serialized_input
    def natural_line_mouse_move(
        self,
        duration: Optional[float] = None,
        pause: Optional[float] = None,
        step_override: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Perform varied, smooth human-like mouse movement after a completed line of code.
        Variations include:
          - Movement length: short, medium, or long.
          - Direction: left, right, up, down, diagonal.
          - Speed/Duration: fast, medium, slow.
          - Path: curved Bézier trajectory or smooth easing.
          - Pauses before and after movement.
        Strictly guarantees:
          - Safely bounded away from screen corners, taskbar, destructive controls.
          - Does not click, does not steal focus, does not interfere with caret.
          - Completes 100% before returning.
        """
        if safety.is_emergency_stopped():
            return False

        from automation.timing_controller import timing_controller

        sw, sh = self.get_screen_size()
        curr_x, curr_y = self.get_position()

        step = step_override or timing_controller.generate_line_mouse_step(curr_x, curr_y, sw, sh)
        target_x = int(step["target_x"])
        target_y = int(step["target_y"])
        dur = float(duration if duration is not None else step["duration"])
        pre_p = float(step.get("pre_pause", 0.05)) if pause is None else 0.0
        post_p = float(pause if pause is not None else step.get("post_pause", 0.12))
        prof = str(step.get("profile", "curved"))

        # Pre-movement pause
        if pre_p > 0:
            if not safety.interruptible_sleep(pre_p):
                return False

        logger.action(
            "MOUSE",
            f"Line mouse movement [{step.get('length_category', 'med')}, {step.get('speed_category', 'med')}]: "
            f"({curr_x}, {curr_y}) -> ({target_x}, {target_y}) [{dur:.2f}s, {prof}]"
        )

        # Execute smooth move with chosen profile
        if prof == "curved":
            ok = self.human_move_to(target_x, target_y, duration=dur)
        else:
            ok = self.move_to(target_x, target_y, duration=dur, easing_name="easeInOutQuad", use_human_curves=False)

        # Post-movement pause
        if post_p > 0:
            safety.interruptible_sleep(post_p)

        return ok

    @serialized_input
    def move_to(
        self,
        x: int,
        y: int,
        duration: float = 0.45,
        easing_name: str = "easeInOutQuad",
        use_human_curves: bool = True
    ) -> bool:
        """
        Move the cursor to target (x, y) with human dynamics and bounds validation.
        """
        if safety.is_emergency_stopped():
            return False

        if not self.is_within_screen_bounds(x, y):
            w, h = self.get_screen_size()
            logger.error_detailed(
                "MOUSE",
                f"Target coordinates ({x}, {y}) are outside display bounds ({w}x{h}).",
                error_type="CoordinateOutOfBoundsError",
                action_type="move_to",
                action_params={"x": x, "y": y, "duration": duration},
                coordinates=(x, y),
                suggestion=f"Provide coordinates between (0, 0) and ({w}, {h})."
            )
            return False

        if use_human_curves:
            return self.human_move_to(x, y, duration=duration)

        try:
            easing = self.EASING_MAP.get(easing_name, pyautogui.easeInOutQuad)
            logger.action("MOUSE", f"Moving cursor to ({x}, {y}) over {duration:.2f}s")
            
            # Notify visual indicator if registered
            if self.on_cursor_ping:
                try:
                    self.on_cursor_ping(x, y)
                except Exception:
                    pass

            self.last_target_position = (x, y)
            pyautogui.moveTo(x, y, duration=duration, tween=easing)
            return True
        except pyautogui.FailSafeException:
            logger.error_detailed(
                "MOUSE",
                "Fail-safe triggered by mouse movement to screen corner.",
                error_type="FailSafeException",
                coordinates=(x, y),
                suggestion="Mouse reached (0, 0) screen corner. Emergency stop engaged."
            )
            safety.trigger_emergency_stop()
            return False
        except Exception as e:
            logger.error_detailed(
                "MOUSE",
                f"Error moving mouse to ({x}, {y}): {e}",
                error_type=type(e).__name__,
                coordinates=(x, y)
            )
            return False

    def __getattr__(self, name: str):
        if name in (
            "click", "right_click", "double_click", "triple_click",
            "scroll", "mouse_down", "mouse_up", "drag_and_drop",
            "select_text_by_drag", "select_word_at", "select_line_at",
            "deselect_text", "select_all"
        ):
            raise AttributeError(
                f"Mouse function '{name}' has been removed from DeskPilot. "
                "Only mouse cursor movement is supported."
            )
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")


# Singleton instance
mouse_ctrl = MouseController()
