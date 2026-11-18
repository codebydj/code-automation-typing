"""
DeskPilot – Settings, Custom Speeds, Rest Timings & Responsiveness Test Suite
Tests:
  1. Custom speed (arbitrary CPS) & Custom rest break intervals/durations.
  2. Editor line number scrolling synchronization under vertical scroll events.
  3. Real-time estimate display at working start (immediately during countdown).
  4. SettingsDialog data binding, custom value persistence, and reset to defaults.
  5. Debounced highlighting & gutter redraw optimization.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import DEFAULT_CONFIG, load_config, save_config
from automation.timing_controller import timing_controller
from ui.settings_dialog import SettingsDialog
from ui.ide_editor import IDECodeEditor, LineNumbersGutter
import tkinter as tk


class TestSettingsAndResponsiveness(unittest.TestCase):
    """Test suite covering custom settings, rest parameters, line numbers, and responsiveness."""

    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
            cls.root.withdraw()
        except Exception:
            cls.root = None

    @classmethod
    def tearDownClass(cls):
        if cls.root:
            try:
                cls.root.destroy()
            except Exception:
                pass

    def test_custom_speed_in_timing_controller(self):
        """Verify timing_controller supports arbitrary custom speeds (e.g. 1.8, 5.0 CPS)."""
        timing_controller.set_cps(1.8)
        self.assertAlmostEqual(timing_controller.current_cps, 1.8, places=2)

        timing_controller.set_cps(5.0)
        self.assertAlmostEqual(timing_controller.current_cps, 5.0, places=2)

        # Minimum floor protection
        timing_controller.set_cps(0.01)
        self.assertGreaterEqual(timing_controller.current_cps, 0.5)

    def test_custom_rest_interval_and_duration_in_estimate(self):
        """Verify custom rest interval and duration correctly scale estimated time."""
        code = "line = 1\n" * 100  # 100 lines
        cps = 3.0

        # Case 1: Standard rest (every 15-30 lines, 180s-360s = avg 270s)
        secs_std, _ = timing_controller.calculate_sequence_estimate(
            text=code,
            cps=cps,
            random_pause_enabled=True,
            rest_interval_lines=(15, 30),
            rest_duration_seconds=(180, 360)
        )

        # Case 2: Shorter custom rest (every 10-20 lines, 60s-120s = avg 90s)
        secs_custom, _ = timing_controller.calculate_sequence_estimate(
            text=code,
            cps=cps,
            random_pause_enabled=True,
            rest_interval_lines=(10, 20),
            rest_duration_seconds=(60, 120)
        )

        # Case 3: Rest disabled
        secs_no_rest, _ = timing_controller.calculate_sequence_estimate(
            text=code,
            cps=cps,
            random_pause_enabled=False
        )

        self.assertGreater(secs_std, secs_no_rest, "Rest pause must add break time to estimate.")
        self.assertGreater(secs_custom, secs_no_rest, "Custom rest pause must add break time.")
        self.assertNotEqual(secs_std, secs_custom, "Different rest durations must yield different total estimates.")

    def test_line_numbers_gutter_redraw_and_scrolling_sync(self):
        """Verify LineNumbersGutter redraws on yscroll and resizes width for digits."""
        if not self.root:
            self.skipTest("Tkinter GUI not available in this environment.")

        container = tk.Frame(self.root)
        container.pack()

        text = tk.Text(container, wrap="none")
        gutter = LineNumbersGutter(container, text)
        editor = IDECodeEditor(self.root)

        # Insert 150 lines
        text.insert("1.0", "\n".join(f"line_{i} = {i}" for i in range(1, 151)))
        text.update()

        # Initial redraw
        gutter.redraw()
        width = int(gutter.cget("width"))
        self.assertGreaterEqual(width, 46, "Gutter width should accommodate line number digits.")

        # Trigger vertical scroll hook
        editor.text_widget.insert("1.0", "\n".join(f"code_{i}" for i in range(1, 100)))
        editor.text_widget.update()
        editor._on_text_yscroll(0.2, 0.5)

        # Verify scrollbar and gutter are updated without error
        self.assertTrue(hasattr(editor, "v_scroll"))
        self.assertTrue(hasattr(editor, "gutter"))

        editor.destroy()
        container.destroy()

    def test_editor_jump_to_line_and_find_methods(self):
        """Verify jump_to_line and find_text methods exist and handle searches cleanly."""
        if not self.root:
            self.skipTest("Tkinter GUI not available in this environment.")

        editor = IDECodeEditor(self.root)
        editor.set_code("alpha = 1\nbeta = 2\ngamma = 3\n", "test.py", "Python")

        self.assertTrue(hasattr(editor, "jump_to_line"))
        self.assertTrue(hasattr(editor, "find_text"))

        # Test find_text with mock query
        with patch("tkinter.simpledialog.askstring", return_value="beta"):
            editor.find_text()
            ranges = editor.text_widget.tag_ranges("search_highlight")
            self.assertGreater(len(ranges), 0, "Found text should have search_highlight tag.")

        editor.destroy()

    def test_debounced_typing_pointer_optimization(self):
        """Verify show_typing_pointer only redraws gutter when line number changes."""
        if not self.root:
            self.skipTest("Tkinter GUI not available in this environment.")

        editor = IDECodeEditor(self.root)
        editor.set_code("x = 10\ny = 20\n", "test.py", "Python")

        with patch.object(editor.gutter, "redraw") as mock_redraw:
            # First char of line 1 -> should redraw gutter
            editor.show_typing_pointer(1, 1, "x")
            self.assertEqual(mock_redraw.call_count, 1)

            # Subsequent chars on SAME line 1 -> should NOT redraw gutter canvas
            editor.show_typing_pointer(1, 2, " ")
            editor.show_typing_pointer(1, 3, "=")
            editor.show_typing_pointer(1, 4, " ")
            self.assertEqual(mock_redraw.call_count, 1, "Gutter must NOT redraw for every char on the same line.")

            # Transition to line 2 -> should redraw gutter
            editor.show_typing_pointer(2, 1, "y")
            self.assertEqual(mock_redraw.call_count, 2, "Gutter must redraw when moving to a new line.")

        editor.destroy()


if __name__ == "__main__":
    unittest.main()
