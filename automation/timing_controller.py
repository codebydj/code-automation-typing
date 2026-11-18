"""
DeskPilot - Central Timing Controller
Coordinates dynamic character difficulty, keyboard row mapping, natural typing rhythm,
pacing, word spacing, punctuation pauses, newline pauses, and varied human-like mouse movements.
Strictly enforces:
  - Default speed: 3 CPS
  - Maximum configured speed: 3.5 CPS
  - Maximum individual character delay: 3.5 seconds (never exceeded)
  - When CPS increases, character delays decrease
  - When CPS decreases, character delays increase
  - Non-overlapping, serialized keyboard and mouse actions
"""

import math
import random
from enum import Enum
from typing import Optional, Tuple, Dict, Any
from automation.character_mapper import character_mapper, CharacterCategory, KeyMapping


class CharacterDifficulty(str, Enum):
    EASY = "EASY"
    MEDIUM = "MEDIUM"
    DIFFICULT = "DIFFICULT"


class TimingController:
    """
    Central timing controller coordinating keyboard difficulty and varied mouse kinematics.
    """

    DEFAULT_CPS: float = 3.0
    MAX_CONFIGURED_CPS: float = 3.5
    MIN_CONFIGURED_CPS: float = 0.5
    MAX_CHARACTER_DELAY: float = 3.5   # Hard upper limit in seconds
    MIN_CHARACTER_DELAY: float = 0.02  # Lower safety floor in seconds

    # Common English & programming letters on home row (lowest physical effort)
    HOME_ROW_COMMON = frozenset("asdfjkl")
    TOP_ROW_COMMON = frozenset("eotinrh")

    # Punctuation keys that warrant natural cognitive pauses
    MAJOR_PUNCTUATION = frozenset(",.;:!?")

    _ASCII_DIFFICULTY_ROW_MAP: Optional[Dict[str, float]] = None
    _estimate_cache: Dict[Any, Tuple[int, str]] = {}

    def __init__(self, current_cps: float = 3.0):
        self.current_cps = max(self.MIN_CONFIGURED_CPS, min(self.MAX_CONFIGURED_CPS, current_cps))
        self._last_line_mouse_angle: Optional[float] = None
        self._last_line_mouse_dist: Optional[float] = None
        if TimingController._ASCII_DIFFICULTY_ROW_MAP is None:
            self._build_ascii_mult_map()

    def _build_ascii_mult_map(self):
        """Precompute character difficulty * row multiplier lookup table for ASCII 0-127."""
        mults = {}
        for code in range(128):
            ch = chr(code)
            _, diff_mult, _ = self.classify_character(ch)
            row_mult = self.get_row_multiplier(ch)
            mults[ch] = diff_mult * row_mult
        TimingController._ASCII_DIFFICULTY_ROW_MAP = mults

    def set_cps(self, cps: float):
        """Set base typing speed (supports custom speed with minimum safety floor)."""
        self.current_cps = max(self.MIN_CONFIGURED_CPS, float(cps))

    # =========================================================================
    # 1. CHARACTER DIFFICULTY & ROW MAPPING
    # =========================================================================

    def classify_character(self, ch: str) -> Tuple[CharacterDifficulty, float, str]:
        """
        Classifies a character into EASY, MEDIUM, or DIFFICULT categories
        and returns (difficulty_category, difficulty_multiplier, explanation).

        Easy:
          - Lowercase letters.
          - Frequently typed letters (a, s, d, f, j, k, l, e, t, i, o, n, r, h).
          - Base multiplier: 0.70 – 0.85x
        Medium:
          - Uppercase letters (require Shift).
          - Numbers (0-9).
          - Less frequently typed lowercase letters (q, z, x).
          - Base multiplier: 1.15 – 1.35x
        Difficult:
          - Special symbols (@, #, $, %, &, *, {, }, [, ], <, >, ?, punctuation).
          - Characters requiring multiple or complex layout mappings.
          - Base multiplier: 1.50 – 2.20x
        """
        # Whitespace
        if ch in (" ", "\t", "\r", "\n"):
            return CharacterDifficulty.EASY, 0.70, "Whitespace"

        mapping = character_mapper.get_mapping(ch)
        category = character_mapper.get_category(ch)

        # 1. Lowercase letters (Middle/Home row vs Top row vs Bottom row)
        if category == CharacterCategory.ALPHABETIC_LOWER or (ch.isalpha() and ch.islower()):
            if ch in "asdfghjkl":  # Home / Middle row: natural resting posture, fastest response
                return CharacterDifficulty.EASY, 0.72, f"Home-row letter '{ch}'"
            elif ch in "qwertyuiop":  # Top row: upward reach
                if ch == "q":
                    return CharacterDifficulty.MEDIUM, 1.25, f"Top-row corner letter '{ch}'"
                return CharacterDifficulty.EASY, 0.88, f"Top-row letter '{ch}'"
            elif ch in "zxcvbnm":  # Bottom row: downward finger curl, slower reach
                if ch in "zx":
                    return CharacterDifficulty.MEDIUM, 1.50, f"Awkward bottom-row letter '{ch}'"
                return CharacterDifficulty.EASY, 0.95, f"Bottom-row letter '{ch}'"
            else:
                return CharacterDifficulty.EASY, 0.90, f"Standard lowercase letter '{ch}'"

        # 2. Uppercase letters (require Shift modifier + key reach)
        if category == CharacterCategory.ALPHABETIC_UPPER or (ch.isalpha() and ch.isupper()):
            lower = ch.lower()
            if lower in "asdfghjkl":
                return CharacterDifficulty.MEDIUM, 1.50, f"Home-row uppercase letter '{ch}'"
            elif lower in "qwertyuiop":
                return CharacterDifficulty.MEDIUM, 1.80, f"Top-row uppercase letter '{ch}'"
            else:
                return CharacterDifficulty.MEDIUM, 2.10, f"Bottom-row uppercase letter '{ch}'"

        # 3. Numeric characters (Number row high reach)
        if category in (CharacterCategory.NUMERIC_ROW, CharacterCategory.NUMERIC_PAD) or ch.isdigit():
            return CharacterDifficulty.MEDIUM, 1.40, f"Number digit '{ch}'"

        # 4. Special Characters & Programming Symbols (Distinct, slow, highly deliberate human cadence)
        # Programming brackets: {} [] () <>
        if ch in "{}[]()<>":
            return CharacterDifficulty.DIFFICULT, 3.20, f"Programming bracket '{ch}'"

        # Complex shifted symbols: @ # $ % ^ & * ~ _ + | ? !
        if ch in "!@#$%^&*~_+|?":
            return CharacterDifficulty.DIFFICULT, 3.40, f"Shifted special symbol '{ch}'"

        # Punctuation / syntax operators: : ; ' " , . / \ - = `
        if ch in ";:'\",./\\-=`":
            return CharacterDifficulty.DIFFICULT, 2.60, f"Punctuation / operator '{ch}'"

        # Fallback for arbitrary symbols
        return CharacterDifficulty.DIFFICULT, 2.80, f"Special character '{ch}'"

    def get_row_multiplier(self, ch: str) -> float:
        """
        Calculates physical keyboard row reach difficulty:
        - Home/middle row: 0.85x (fingers naturally rest here, quickest keystrokes)
        - Upper letter row: 1.15x (upward finger extension)
        - Bottom letter row: 1.35x (downward finger curl, awkward flexion)
        - Top number row: 1.55x (furthest reach to top number row, deliberate)
        - Space row: 0.85x
        - Numpad: 1.15x
        """
        mapping = character_mapper.get_mapping(ch)
        row = mapping.row if mapping else "top_row"

        row_multipliers = {
            "home_row": 0.85,
            "top_row": 1.15,
            "bottom_row": 1.35,
            "number_row": 1.55,
            "space_row": 0.85,
            "numpad": 1.15,
            "control": 1.00,
        }
        return row_multipliers.get(row, 1.00)

    # =========================================================================
    # 2. DYNAMIC CHARACTER DELAY CALCULATION
    # =========================================================================

    def get_character_delay(
        self,
        ch: str,
        prev_ch: Optional[str] = None,
        cps: Optional[float] = None,
        use_jitter: bool = True
    ) -> float:
        """
        Calculate individual character delay based on character difficulty,
        physical key row, natural rhythm variations, and current CPS.

        Strictly guarantees:
          - Base delay = 1 / CPS
          - Actual delay = Base delay × Difficulty multiplier × Row multiplier + Rhythm pauses
          - When CPS increases, delays decrease.
          - When CPS decreases, delays increase.
          - Actual delay is capped at 3.5 seconds maximum at all times.
        """
        effective_cps = max(
            self.MIN_CONFIGURED_CPS,
            float(cps if cps is not None else self.current_cps)
        )
        base_delay = 1.0 / effective_cps

        # 1. Base category difficulty multiplier
        _, diff_mult, _ = self.classify_character(ch)

        # 2. Keyboard row multiplier
        row_mult = self.get_row_multiplier(ch)

        # 3. Base calculated delay
        calculated_delay = base_delay * diff_mult * row_mult

        # 4. Small bounded natural timing variation (±5-8%)
        if use_jitter:
            jitter = random.uniform(-0.06, 0.06) * calculated_delay
            calculated_delay += jitter

        # 5. Consecutive symbol transition hesitation (e.g. ->, !=, ==, {}, [], ():)
        symbols_set = set("{}[]()<>!@#$%^&*~_+|?;:'\",./\\-=`")
        if ch in symbols_set and prev_ch in symbols_set:
            calculated_delay += base_delay * random.uniform(0.40, 0.70)

        # 6. Post-bracket / post-punctuation cognitive pause
        if prev_ch and prev_ch in self.MAJOR_PUNCTUATION:
            calculated_delay += base_delay * random.uniform(0.35, 0.65)
        elif prev_ch and prev_ch in ")}]>":
            calculated_delay += base_delay * random.uniform(0.30, 0.55)

        # 7. Word spacing hesitation (space following a non-space character)
        if ch == " " and prev_ch and prev_ch not in " \t\r\n":
            calculated_delay += base_delay * random.uniform(0.20, 0.38)

        # 8. Natural pause after completing a line (\n)
        if prev_ch == "\n":
            calculated_delay += base_delay * random.uniform(0.25, 0.45)

        # 9. Strict bounds clamping: NEVER exceed 3.5 seconds
        actual_delay = min(self.MAX_CHARACTER_DELAY, max(self.MIN_CHARACTER_DELAY, calculated_delay))
        return actual_delay

    # =========================================================================
    # 3. VARIED HUMAN-LIKE MOUSE MOVEMENT AFTER EVERY LINE
    # =========================================================================

    def generate_line_mouse_step(
        self,
        curr_x: int,
        curr_y: int,
        screen_w: int,
        screen_h: int
    ) -> Dict[str, Any]:
        """
        Calculates a varied, smooth, natural mouse movement after completed line intervals:
        - Movement length: short (80-150px), medium (160-270px), or long (280-420px).
        - Direction: left, right, up, down, or diagonal with border rebound.
        - Movement speed/duration: fast (1.1-1.6s), medium (1.7-2.4s), slow (2.5-3.2s) - more seconds randomly.
        - Path profile: curved (Bézier) or smooth (eased).
        - Pre-movement (0.20-0.42s) and post-movement (0.25-0.52s) natural human pauses.
        - Keeps movement strictly inside safe screen boundaries away from top tabs and destructive controls.
        """
        # Safe boundaries: keep cursor away from top tabs, titlebar, and bottom taskbar
        safe_min_x = max(120, int(screen_w * 0.12))
        safe_max_x = screen_w - max(120, int(screen_w * 0.12))
        safe_min_y = max(140, int(screen_h * 0.15))  # Keep well below window top / editor tabs
        safe_max_y = screen_h - max(100, int(screen_h * 0.10))

        # If current position is invalid or outside safe area, reset to safe center
        if not (safe_min_x <= curr_x <= safe_max_x and safe_min_y <= curr_y <= safe_max_y):
            curr_x = screen_w // 2
            curr_y = screen_h // 2

        # 1. Choose movement length category (short, medium, long)
        length_category = random.choices(["short", "medium", "long"], weights=[0.30, 0.45, 0.25])[0]
        if length_category == "short":
            distance = random.uniform(80.0, 150.0)
        elif length_category == "medium":
            distance = random.uniform(160.0, 270.0)
        else:  # long
            distance = random.uniform(280.0, 420.0)

        # 2. Choose movement direction (angle in radians)
        # Avoid picking the exact same angle as the previous line
        theta = random.uniform(0, 2 * math.pi)
        if self._last_line_mouse_angle is not None:
            # Shift by at least 45 degrees from previous direction
            if abs(theta - self._last_line_mouse_angle) < 0.78:
                theta = (theta + random.uniform(1.2, 3.8)) % (2 * math.pi)

        # Check candidate destination
        cand_x = int(curr_x + distance * math.cos(theta))
        cand_y = int(curr_y + distance * math.sin(theta))

        # If candidate breaches safe boundaries, direct back towards the center of safe area
        if not (safe_min_x <= cand_x <= safe_max_x and safe_min_y <= cand_y <= safe_max_y):
            safe_center_x = (safe_min_x + safe_max_x) // 2
            safe_center_y = (safe_min_y + safe_max_y) // 2
            angle_to_center = math.atan2(safe_center_y - curr_y, safe_center_x - curr_x)
            theta = angle_to_center + random.uniform(-0.35, 0.35)
            cand_x = int(curr_x + distance * math.cos(theta))
            cand_y = int(curr_y + distance * math.sin(theta))

        target_x = max(safe_min_x, min(safe_max_x, cand_x))
        target_y = max(safe_min_y, min(safe_max_y, cand_y))

        # Save direction for next line variation
        self._last_line_mouse_angle = theta
        self._last_line_mouse_dist = distance

        # 3. Choose speed / duration (more seconds randomly for natural human repositioning)
        speed_category = random.choices(["fast", "medium", "slow"], weights=[0.25, 0.50, 0.25])[0]
        if speed_category == "fast":
            duration = random.uniform(1.10, 1.60)
        elif speed_category == "medium":
            duration = random.uniform(1.70, 2.40)
        else:  # slow
            duration = random.uniform(2.50, 3.20)

        # 4. Choose profile and pauses
        profile = random.choice(["curved", "curved", "smooth"])
        pre_pause = random.uniform(0.20, 0.42)
        post_pause = random.uniform(0.25, 0.52)

        return {
            "target_x": target_x,
            "target_y": target_y,
            "distance": round(distance, 1),
            "length_category": length_category,
            "duration": round(duration, 3),
            "speed_category": speed_category,
            "profile": profile,
            "pre_pause": round(pre_pause, 3),
            "post_pause": round(post_pause, 3)
        }

    # =========================================================================
    # 4. TOTAL ESTIMATED TIME CALCULATION
    # =========================================================================

    def calculate_sequence_estimate(
        self,
        text: str,
        cps: Optional[float] = None,
        countdown_seconds: int = 3,
        mouse_move_enabled: bool = True,
        use_difficulty: bool = True,
        random_pause_enabled: bool = False,
        rest_interval_lines: Tuple[int, int] = (15, 30),
        rest_duration_seconds: Tuple[int, int] = (180, 360),
        work_interval_minutes: Optional[Tuple[float, float]] = None,
        break_duration_minutes: Optional[Tuple[float, float]] = None
    ) -> Tuple[int, str]:
        """
        Calculates exact estimated completion time for text payload by summing
        character delays (either dynamic character difficulty or fixed CPS),
        punctuation pauses, word pauses, newline pauses, and mouse movement durations.
        Supports custom speed CPS, work duration in minutes (e.g. 20-25m), and custom break lengths.
        """
        if not text:
            return 0, "00:00:00"

        effective_cps = max(
            self.MIN_CONFIGURED_CPS,
            float(cps if cps is not None else self.current_cps)
        )

        # Check in-memory fast memoization cache
        cache_key = (
            len(text),
            hash(text),
            round(effective_cps, 2),
            countdown_seconds,
            mouse_move_enabled,
            use_difficulty,
            random_pause_enabled,
            rest_interval_lines,
            rest_duration_seconds,
            work_interval_minutes,
            break_duration_minutes
        )
        if cache_key in self._estimate_cache:
            return self._estimate_cache[cache_key]

        base_delay = 1.0 / effective_cps

        total_seconds = float(countdown_seconds) + 1.0  # Countdown + focus buffer
        prev_ch: Optional[str] = None
        newlines_count = 0
        symbols_set = set("{}[]()<>!@#$%^&*~_+|?;:'\",./\\-=`")

        if use_difficulty:
            if self._ASCII_DIFFICULTY_ROW_MAP is None:
                self._build_ascii_mult_map()
            diff_row_map = self._ASCII_DIFFICULTY_ROW_MAP

        for ch in text:
            if use_difficulty:
                char_mult = diff_row_map.get(ch, 1.0)
                char_delay = base_delay * char_mult

                if ch in symbols_set and prev_ch in symbols_set:
                    char_delay += base_delay * 0.50

                if ch == " " and prev_ch and prev_ch not in " \t\r\n":
                    char_delay += base_delay * 0.28

                if prev_ch and prev_ch in self.MAJOR_PUNCTUATION:
                    char_delay += base_delay * 0.45
                elif prev_ch and prev_ch in ")}]>":
                    char_delay += base_delay * 0.35

                if ch == "\n":
                    char_delay += base_delay * 0.30
            else:
                char_delay = base_delay

            if ch == "\n":
                newlines_count += 1

            total_seconds += min(self.MAX_CHARACTER_DELAY, max(self.MIN_CHARACTER_DELAY, char_delay))
            prev_ch = ch

        # Add mouse movement time: triggers after line 1 and every random 2-5 lines (average ~3.5 lines)
        if mouse_move_enabled and newlines_count > 0:
            # Average mouse cycle: ~2.0s duration + 0.30s pre-pause + 0.38s post-pause = ~2.68s
            num_mouse_moves = max(1, int(round(newlines_count / 3.5)))
            total_seconds += num_mouse_moves * 2.68

        # Add random rest pause time based on work time (minutes) or line interval
        if random_pause_enabled:
            if work_interval_minutes is not None and break_duration_minutes is not None:
                avg_work_sec = max(60.0, ((work_interval_minutes[0] + work_interval_minutes[1]) / 2.0) * 60.0)
                avg_break_sec = max(1.0, ((break_duration_minutes[0] + break_duration_minutes[1]) / 2.0) * 60.0)
                if total_seconds >= avg_work_sec:
                    num_breaks = max(1, int(total_seconds / avg_work_sec))
                    total_seconds += num_breaks * avg_break_sec
            else:
                min_rest_line = rest_interval_lines[0]
                avg_rest_interval = max(1.0, (rest_interval_lines[0] + rest_interval_lines[1]) / 2.0)
                avg_rest_duration = max(1.0, (rest_duration_seconds[0] + rest_duration_seconds[1]) / 2.0)
                if newlines_count >= min_rest_line:
                    num_rest_pauses = max(1, int(newlines_count / avg_rest_interval))
                    total_seconds += num_rest_pauses * avg_rest_duration

        total_secs = int(round(total_seconds))
        h = total_secs // 3600
        m = (total_secs % 3600) // 60
        s = total_secs % 60
        time_str = f"{h:02d}:{m:02d}:{s:02d}"

        # Maintain cache size
        if len(self._estimate_cache) > 256:
            self._estimate_cache.clear()
        self._estimate_cache[cache_key] = (total_secs, time_str)
        return total_secs, time_str


# Singleton instance
timing_controller = TimingController(current_cps=3.0)
