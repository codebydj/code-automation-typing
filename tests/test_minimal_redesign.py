"""
DeskPilot – Character Difficulty & Natural Input Behavior Upgrade Test Suite
Validates:
  1. Character-based typing speed (Easy, Medium, Difficult categories).
  2. Keyboard row difficulty mapping (Home, Upper, Bottom, Number rows).
  3. Dynamic delay calculation, CPS scaling (higher CPS -> shorter delay, lower CPS -> longer delay).
  4. Hard limits (delay never exceeds 3.5s, max configured speed 3.5 CPS).
  5. Natural typing rhythm (word spacing, punctuation pauses, newline pauses, bounded jitter).
  6. Varied mouse movement after every line (short/medium/long distance, directions, duration, safe bounds).
  7. Non-overlapping execution between keyboard and mouse.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from automation.timing_controller import timing_controller, CharacterDifficulty
from automation.character_mapper import character_mapper
from automation.keyboard_controller import keyboard_ctrl
from automation.mouse_controller import mouse_ctrl
from automation.safety import safety
from automation.hotkey_manager import normalize_hotkey, HotkeyManager
import main


class TestCharacterDifficultyAndNaturalBehavior(unittest.TestCase):
    """Test suite verifying character difficulty, timing controller, and natural input behavior."""

    def setUp(self):
        safety.clear_emergency_stop()

    def tearDown(self):
        safety.reset_hardware_state()

    # =========================================================================
    # 1. CHARACTER DIFFICULTY CATEGORIZATION & MULTIPLIERS
    # =========================================================================

    def test_character_difficulty_classification(self):
        """Verify easy, medium, and difficult character classifications."""
        # Easy characters: lowercase letters
        for ch in "asdfjkleotinrh":
            cat, mult, _ = timing_controller.classify_character(ch)
            self.assertEqual(cat, CharacterDifficulty.EASY, f"'{ch}' should be classified as EASY.")
            self.assertLessEqual(mult, 1.15, f"Easy character '{ch}' should have multiplier <= 1.15.")

        # Medium difficulty: uppercase letters, numbers, less frequent letters
        for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            cat, mult, _ = timing_controller.classify_character(ch)
            self.assertEqual(cat, CharacterDifficulty.MEDIUM, f"Uppercase '{ch}' should be MEDIUM.")
            self.assertGreaterEqual(mult, 1.50)

        for ch in "0123456789":
            cat, mult, _ = timing_controller.classify_character(ch)
            self.assertEqual(cat, CharacterDifficulty.MEDIUM, f"Number '{ch}' should be MEDIUM.")
            self.assertGreaterEqual(mult, 1.30)

        # Difficult characters: special symbols, brackets, layout-complex symbols
        for ch in "@#$%&*{}[]<>?~^_+|":
            cat, mult, _ = timing_controller.classify_character(ch)
            self.assertEqual(cat, CharacterDifficulty.DIFFICULT, f"Symbol '{ch}' should be DIFFICULT.")
            self.assertGreaterEqual(mult, 3.00, f"Special character '{ch}' must have high multiplier for human cadence.")

    def test_difficulty_hierarchy_delays(self):
        """Verify Easy delay < Medium delay < Difficult delay at the same CPS."""
        cps = 3.0
        # Easy: lowercase 'a' on home row
        delay_easy = timing_controller.get_character_delay("a", cps=cps, use_jitter=False)
        # Medium: uppercase 'A' (requires Shift) or digit '5'
        delay_medium_upper = timing_controller.get_character_delay("A", cps=cps, use_jitter=False)
        delay_medium_digit = timing_controller.get_character_delay("5", cps=cps, use_jitter=False)
        # Difficult: special symbols '{', '@', '#'
        delay_diff_brace = timing_controller.get_character_delay("{", cps=cps, use_jitter=False)
        delay_diff_at = timing_controller.get_character_delay("@", cps=cps, use_jitter=False)

        self.assertLess(delay_easy, delay_medium_upper, "Easy 'a' must be faster than uppercase 'A'.")
        self.assertLess(delay_easy, delay_medium_digit, "Easy 'a' must be faster than digit '5'.")
        self.assertLess(delay_medium_upper, delay_diff_brace, "Medium 'A' must be faster than difficult '{'.")
        self.assertLess(delay_medium_digit, delay_diff_at, "Medium '5' must be faster than difficult '@'.")

    def test_row_and_special_character_different_behaviors(self):
        """Verify distinct human typing behaviors for Middle/Home, Top, Bottom, and Special Characters."""
        cps = 3.0
        # Middle / Home row (fluid resting position)
        d_middle = timing_controller.get_character_delay("a", cps=cps, use_jitter=False)
        # Top row (upward reach)
        d_top = timing_controller.get_character_delay("e", cps=cps, use_jitter=False)
        # Bottom row (awkward downward curl)
        d_bottom = timing_controller.get_character_delay("c", cps=cps, use_jitter=False)
        # Number row
        d_number = timing_controller.get_character_delay("3", cps=cps, use_jitter=False)
        # Special characters (brackets, shifted symbols)
        d_bracket = timing_controller.get_character_delay("{", cps=cps, use_jitter=False)
        d_symbol = timing_controller.get_character_delay("@", cps=cps, use_jitter=False)

        # Clear hierarchy: Middle < Top < Bottom < Number < Special Bracket < Shifted Symbol
        self.assertLess(d_middle, d_top, "Middle/home row must type faster than top row.")
        self.assertLess(d_top, d_bottom, "Top row must type faster than bottom row.")
        self.assertLess(d_bottom, d_number, "Bottom row must type faster than top number row.")
        self.assertLess(d_number, d_bracket, "Number row must type faster than special bracket.")
        self.assertLess(d_bracket, d_symbol, "Brackets must type faster than complex shifted symbols.")

        # Ensure special characters are NOT typing fast (deliberate human pause >= 1.0s)
        self.assertGreaterEqual(d_bracket, 1.0, f"Special bracket '{{' delay ({d_bracket:.2f}s) must be deliberate.")
        self.assertGreaterEqual(d_symbol, 1.4, f"Special symbol '@' delay ({d_symbol:.2f}s) must be deliberate.")

    # =========================================================================
    # 2. KEYBOARD ROW DIFFICULTY
    # =========================================================================

    def test_keyboard_row_multipliers(self):
        """Verify physical row multipliers: Home row < Upper row < Bottom row < Number row."""
        # 'a' is home_row, 'q' is top_row, 'z' is bottom_row, '1' is number_row
        row_home = timing_controller.get_row_multiplier("a")
        row_top = timing_controller.get_row_multiplier("q")
        row_bottom = timing_controller.get_row_multiplier("z")
        row_number = timing_controller.get_row_multiplier("1")

        self.assertLess(row_home, row_top, "Home row should have lower physical effort than top row.")
        self.assertLess(row_top, row_bottom, "Top row should have lower effort than bottom row.")
        self.assertLess(row_bottom, row_number, "Bottom row should have lower effort than number row.")

    # =========================================================================
    # 3. CPS SCALING & HARD TIMING LIMITS
    # =========================================================================

    def test_cps_scaling_delays(self):
        """Verify that when CPS increases, delays decrease; when CPS decreases, delays increase."""
        test_chars = ["a", "M", "7", "{", "@", ";"]

        for ch in test_chars:
            with self.subTest(char=ch):
                delay_1_cps = timing_controller.get_character_delay(ch, cps=1.0, use_jitter=False)
                delay_2_cps = timing_controller.get_character_delay(ch, cps=2.0, use_jitter=False)
                delay_3_cps = timing_controller.get_character_delay(ch, cps=3.0, use_jitter=False)
                delay_35_cps = timing_controller.get_character_delay(ch, cps=3.5, use_jitter=False)

                # Strict monotonic decrease as CPS increases
                self.assertGreater(delay_1_cps, delay_2_cps, f"Delay at 1 CPS should be greater than 2 CPS for '{ch}'.")
                self.assertGreater(delay_2_cps, delay_3_cps, f"Delay at 2 CPS should be greater than 3 CPS for '{ch}'.")
                self.assertGreater(delay_3_cps, delay_35_cps, f"Delay at 3 CPS should be greater than 3.5 CPS for '{ch}'.")

    def test_maximum_character_delay_hard_limit(self):
        """Verify no character delay ever exceeds 3.5 seconds, even under lowest CPS and most complex symbol."""
        very_slow_cps = 0.5  # extreme slow edge case
        difficult_symbols = ["@", "#", "$", "%", "&", "*", "{", "}", "[", "]", "<", ">", "?"]

        for sym in difficult_symbols:
            delay = timing_controller.get_character_delay(sym, prev_ch=":", cps=very_slow_cps, use_jitter=True)
            self.assertLessEqual(delay, 3.5, f"Delay for '{sym}' ({delay:.3f}s) exceeded 3.5s hard limit!")

    # =========================================================================
    # 4. NATURAL TYPING RHYTHM
    # =========================================================================

    def test_word_spacing_and_punctuation_pauses(self):
        """Verify slight pauses after words and slightly longer pauses after punctuation."""
        cps = 3.0
        # Space after letter has extra word spacing delay
        delay_space_after_word = timing_controller.get_character_delay(" ", prev_ch="x", cps=cps, use_jitter=False)
        delay_space_after_space = timing_controller.get_character_delay(" ", prev_ch=" ", cps=cps, use_jitter=False)
        self.assertGreater(delay_space_after_word, delay_space_after_space, "Space after a word should include word pause.")

        # Punctuation pause: typing a character after a comma/period/colon takes longer
        delay_normal = timing_controller.get_character_delay("a", prev_ch="b", cps=cps, use_jitter=False)
        delay_after_comma = timing_controller.get_character_delay("a", prev_ch=",", cps=cps, use_jitter=False)
        delay_after_colon = timing_controller.get_character_delay("a", prev_ch=":", cps=cps, use_jitter=False)

        self.assertGreater(delay_after_comma, delay_normal, "Typing after comma should have natural punctuation pause.")
        self.assertGreater(delay_after_colon, delay_normal, "Typing after colon should have natural punctuation pause.")

    # =========================================================================
    # 5. VARIED MOUSE MOVEMENT AFTER EVERY LINE
    # =========================================================================

    def test_varied_mouse_movement_properties_and_safe_bounds(self):
        """Verify varied distances, directions, durations, and safe screen bounds across lines."""
        sw, sh = 1920, 1080
        steps = []
        for line_num in range(1, 15):
            curr_x = 900 + (line_num * 10)
            curr_y = 500 + (line_num * 10)
            step = timing_controller.generate_line_mouse_step(curr_x, curr_y, sw, sh)
            steps.append(step)

        # Check distances variation: must have varied lengths
        distances = [s["distance"] for s in steps]
        self.assertGreater(len(set(distances)), 1, "Distance should vary across lines.")

        # Check durations variation
        durations = [s["duration"] for s in steps]
        self.assertGreater(len(set(durations)), 1, "Duration should vary across lines.")

        # Check destinations: all must stay safely inside screen margins (never at corners or controls)
        for s in steps:
            tx, ty = s["target_x"], s["target_y"]
            self.assertGreater(tx, 100, "X coordinate too close to left border.")
            self.assertLess(tx, sw - 100, "X coordinate too close to right border.")
            self.assertGreater(ty, 80, "Y coordinate too close to top border / titlebar.")
            self.assertLess(ty, sh - 80, "Y coordinate too close to taskbar / bottom.")

    def test_natural_line_mouse_move_execution_completes_without_clicks(self):
        """Verify natural_line_mouse_move executes smoothly and all clicking methods are removed."""
        # 1. Verify non-movement mouse functions are removed from mouse_ctrl
        for fn in ["click", "right_click", "double_click", "triple_click", "scroll",
                   "mouse_down", "mouse_up", "drag_and_drop", "select_text_by_drag",
                   "select_word_at", "select_line_at", "deselect_text", "select_all"]:
            self.assertFalse(hasattr(mouse_ctrl, fn), f"'{fn}' must be removed from mouse_ctrl.")

        # 2. Verify natural_line_mouse_move completes without any OS click calls
        click_calls = []
        override_curved = {
            "target_x": 300,
            "target_y": 300,
            "duration": 0.25,
            "pre_pause": 0.0,
            "post_pause": 0.0,
            "profile": "curved"
        }
        with patch("pyautogui.click", side_effect=lambda *a, **k: click_calls.append(True)), \
             patch.object(mouse_ctrl, "human_move_to", return_value=True) as move_mock:
            ok = mouse_ctrl.natural_line_mouse_move(step_override=override_curved)
            self.assertTrue(ok)
            self.assertEqual(len(click_calls), 0, "No mouse clicks must be performed during line movement.")
            move_mock.assert_called_once_with(300, 300, duration=0.25)

    def test_line_mouse_moves_more_seconds_randomly(self):
        """Verify that line mouse movement takes more seconds randomly (1.0s to 3.2s) with human pauses."""
        sw, sh = 1920, 1080
        durations = []
        for _ in range(25):
            step = timing_controller.generate_line_mouse_step(500, 400, sw, sh)
            dur = step["duration"]
            durations.append(dur)
            self.assertGreaterEqual(dur, 1.0, f"Line mouse duration {dur:.2f}s must be at least 1.0s.")
            self.assertLessEqual(dur, 3.5, f"Line mouse duration {dur:.2f}s should stay bounded.")
            self.assertGreaterEqual(step["pre_pause"], 0.15, "Pre-pause must allow human hand transition.")
            self.assertGreaterEqual(step["post_pause"], 0.20, "Post-pause must allow keyboard repositions.")

        # Duration must vary randomly across calls
        self.assertGreater(len(set(round(d, 2) for d in durations)), 5, "Line mouse duration must vary randomly.")

    def test_reset_hardware_state_never_injects_unheld_right_mouse_up(self):
        """Verify safety.reset_hardware_state never sends mouseUp('right') if not held down."""
        mouse_up_calls = []
        with patch("automation.safety.pyautogui.mouseUp", side_effect=lambda *a, **k: mouse_up_calls.append(k.get("button") or (a[0] if a else None))):
            safety.reset_hardware_state()
        self.assertNotIn("right", mouse_up_calls, "reset_hardware_state must NEVER inject right-mouse-up when right button is not held down.")
        self.assertEqual(len(mouse_up_calls), 0, "No mouseUp events should be emitted when no mouse buttons are tracked.")

    # =========================================================================
    # 6. CENTRAL TIMING CONTROLLER INTEGRATION & SERIALIZATION
    # =========================================================================

    def test_typing_executes_with_character_difficulty_delays(self):
        """Verify keyboard_ctrl.type_text invokes timing_controller and preserves code exactly."""
        test_code = "def add(x: int) -> int:\n    return x + 1\n"
        delays_collected = []
        typed_chars = []

        def capture_sleep(sec, **kwargs):
            delays_collected.append(sec)
            return True

        with patch.object(keyboard_ctrl, "type_character", side_effect=lambda c, **kw: typed_chars.append(c) or True), \
             patch("automation.keyboard_controller.safety.interruptible_sleep", side_effect=capture_sleep):
            ok = keyboard_ctrl.type_text(
                test_code,
                speed_cps=3.0,
                use_difficulty=True,
                exact_speed=False
            )
            self.assertTrue(ok)

        # Code preserved 100%
        self.assertEqual("".join(typed_chars), test_code)
        # Delays occurred between characters and all delays are <= 3.5s
        self.assertGreater(len(delays_collected), 5)
        for d in delays_collected:
            self.assertLessEqual(d, 3.5)

    def test_line_mouse_callback_runs_after_each_line_and_resets_keys(self):
        """Verify line_mouse_callback is called after each completed newline."""
        multiline_code = "line_a = 1\nline_b = 2\nline_c = 3\n"
        completed_lines = []

        with patch.object(keyboard_ctrl, "type_character", return_value=True):
            ok = keyboard_ctrl.type_text(
                multiline_code,
                speed_cps=100.0,
                base_delay=0.001,
                line_mouse_callback=lambda ln: completed_lines.append(ln) or True
            )
            self.assertTrue(ok)
            self.assertEqual(completed_lines, [1, 2, 3], "Line callback must trigger after every completed line.")

    def test_sequence_executor_random_line_mouse_interval(self):
        """Verify that sequence_executor uses randomized 2-5 line interval for mouse movements."""
        from automation.sequence_executor import executor
        mouse_moves_triggered = []

        code_10_lines = "\n".join([f"line_{i} = {i}" for i in range(1, 12)]) + "\n"
        action = {
            "type": "type_code",
            "text": code_10_lines,
            "speed": 0.001,
            "line_mouse_enabled": True,
            "every_line": False,
            "min_lines": 2,
            "max_lines": 5,
            "natural_line_mouse": True,
        }

        with patch.object(keyboard_ctrl, "type_character", return_value=True), \
             patch("automation.keyboard_controller.safety.interruptible_sleep", return_value=True), \
             patch.object(mouse_ctrl, "natural_line_mouse_move", side_effect=lambda: mouse_moves_triggered.append(True) or True):
            executor._execute_single_action(action)

        # In 11 lines with interval between 2 and 5, mouse should trigger 2 to 5 times (NOT 11 times)
        self.assertGreaterEqual(len(mouse_moves_triggered), 2)
        self.assertLessEqual(len(mouse_moves_triggered), 6)

    # =========================================================================
    # 7. ESTIMATED TIME CALCULATION INTEGRATION
    # =========================================================================

    def test_sequence_estimate_calculation(self):
        """Verify timing_controller.calculate_sequence_estimate gives realistic time."""
        code = "print('Hello, World!')\n" * 5
        secs, time_str = timing_controller.calculate_sequence_estimate(code, cps=3.0, mouse_move_enabled=True)
        self.assertGreater(secs, 10)
        self.assertTrue(":" in time_str)
        h, m, s = map(int, time_str.split(":"))
        self.assertEqual(h * 3600 + m * 60 + s, secs)

    # =========================================================================
    # 8. TWO TYPING MODES: DIFFICULTY-BASED VS FIXED CPS
    # =========================================================================

    def test_two_typing_modes_difficulty_based_vs_fixed_cps(self):
        """Verify the two speed options: Difficulty-Based varies delay, Fixed CPS is constant."""
        sample = "abc {XYZ} 123"
        cps = 2.0  # base delay = 0.5s

        # Mode 1: Difficulty-Based (use_difficulty=True)
        diff_delays = []
        with patch.object(keyboard_ctrl, "type_character", return_value=True), \
             patch("automation.keyboard_controller.safety.interruptible_sleep", side_effect=lambda s, **k: diff_delays.append(round(s, 3)) or True):
            keyboard_ctrl.type_text(sample, speed_cps=cps, use_difficulty=True, exact_speed=False)

        # In difficulty-based mode, delay for '{' (difficult) should be greater than 'b' (easy)
        self.assertGreater(len(set(diff_delays)), 1, "Difficulty mode must produce varied delays across characters.")

        # Mode 2: Fixed CPS ("as usual", use_difficulty=False)
        fixed_delays = []
        with patch.object(keyboard_ctrl, "type_character", return_value=True), \
             patch("automation.keyboard_controller.safety.interruptible_sleep", side_effect=lambda s, **k: fixed_delays.append(round(s, 3)) or True):
            keyboard_ctrl.type_text(sample, speed_cps=cps, use_difficulty=False, exact_speed=True)

        # In fixed CPS mode, delays should be uniform at 1.0 / cps (0.500s)
        expected_delay = round(1.0 / cps, 3)
        for d in fixed_delays:
            self.assertEqual(d, expected_delay, f"Fixed CPS mode character delay {d} must match exact base delay {expected_delay}.")

    def test_right_mouse_button_never_emitted_even_if_tracked(self):
        """Verify safety.reset_hardware_state strictly suppresses right mouseUp under any circumstance."""
        from automation.input_dispatcher import input_dispatcher
        input_dispatcher.track_mouse_down("right")
        mouse_up_calls = []
        with patch("automation.safety.pyautogui.mouseUp", side_effect=lambda *a, **k: mouse_up_calls.append(k.get("button") or (a[0] if a else None))):
            safety.reset_hardware_state()
        self.assertNotIn("right", mouse_up_calls, "Right mouseUp must NEVER be sent to the OS.")
        self.assertNotIn("right", input_dispatcher.held_inputs()[1], "Right mouse state must be discarded.")

    def test_mode_estimate_and_main_task_configuration(self):
        """Verify sequence estimate and main task preparation respect Difficulty-Based vs Fixed CPS."""
        code = "@#$%&*{}[]" * 10
        cps = 3.0

        diff_secs, diff_str = timing_controller.calculate_sequence_estimate(code, cps=cps, use_difficulty=True)
        fixed_secs, fixed_str = timing_controller.calculate_sequence_estimate(code, cps=cps, use_difficulty=False)

        # For symbols, dynamic difficulty applies >=1.5x multiplier, making diff_secs > fixed_secs
        self.assertGreater(diff_secs, fixed_secs)
        self.assertTrue(":" in diff_str and ":" in fixed_str)


if __name__ == "__main__":
    unittest.main()
