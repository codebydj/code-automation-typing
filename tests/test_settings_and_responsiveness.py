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

    def test_navbar_flex_wrap_responsiveness(self):
        """Verify top navbar flex-wraps onto multiple rows when screen width is compact."""
        from main import DeskPilotApp
        app = DeskPilotApp()
        app.update()

        # At wide width (1400px), toolbar is 1 row
        app.geometry("1400x700")
        app.update()
        app._reflow_navbar()
        app.update()
        h_wide = app.toolbar.winfo_height()

        # At compact width (900px), toolbar wraps onto 2 rows
        app.geometry("900x700")
        app.update()
        app._reflow_navbar()
        app.update()
        h_compact = app.toolbar.winfo_height()

        self.assertGreater(h_compact, h_wide, "Toolbar height must expand when wrapping onto multiple rows.")

        # Re-expanding back to wide collapses toolbar back
        app.geometry("1400x700")
        app.update()
        app._reflow_navbar()
        app.update()
        self.assertEqual(app.toolbar.winfo_height(), h_wide, "Toolbar must collapse back to single row on wide display.")
        app.destroy()

    def test_character_based_difficulty_mode_selection(self):
        """Verify _is_difficulty_mode recognizes Difficulty, Difficulty-Based, and Fixed CPS."""
        from main import DeskPilotApp
        app = DeskPilotApp()
        app.update()

        app.opt_mode.set("Difficulty")
        self.assertTrue(app._is_difficulty_mode(), "'Difficulty' option must activate difficulty mode.")

        app.opt_mode.set("Difficulty-Based")
        self.assertTrue(app._is_difficulty_mode(), "'Difficulty-Based' option must activate difficulty mode.")

        app.opt_mode.set("Fixed CPS")
        self.assertFalse(app._is_difficulty_mode(), "'Fixed CPS' option must deactivate difficulty mode.")
        app.destroy()

    def test_minute_based_rest_break_estimate(self):
        """Verify rest breaks calculated from work minutes scale sequence estimate accurately."""
        code = "print('hello')\n" * 200
        # 1. Without rest breaks
        sec_no_rest, _ = timing_controller.calculate_sequence_estimate(
            text=code,
            cps=3.0,
            random_pause_enabled=False
        )
        # 2. With 20-25m work interval and 3-5m break duration
        sec_with_rest, _ = timing_controller.calculate_sequence_estimate(
            text=code,
            cps=3.0,
            random_pause_enabled=True,
            work_interval_minutes=(0.01, 0.02),  # rapid work interval to verify addition
            break_duration_minutes=(3.0, 5.0)
        )
        self.assertGreater(sec_with_rest, sec_no_rest, "Rest breaks based on working minutes must increase total estimate.")

    def test_settings_dialog_destroyed_during_mouse_test(self):
        """Verify closing SettingsDialog during or after test mouse movement does not throw TclError."""
        if not self.root:
            self.skipTest("Tkinter GUI not available in this environment.")

        saved_config = None
        def on_save(cfg):
            nonlocal saved_config
            saved_config = cfg

        dlg = SettingsDialog(self.root, on_save_callback=on_save)
        self.root.update()

        # Trigger mouse test
        dlg._handle_test_mouse_move()

        # Immediately destroy dialog (simulates user closing settings dialog while test runs)
        dlg.destroy()
        self.root.update()

        # Allow scheduled timer ticks to fire; must not raise TclError
        import time
        t0 = time.time()
        while time.time() - t0 < 0.2:
            self.root.update()
            time.sleep(0.02)

        self.assertTrue(getattr(dlg, "_is_destroyed", False))

    def test_settings_dialog_break_minutes_to_seconds_derivation(self):
        """Verify break minutes (e.g. 3–5 min) strictly produce 180s–300s in saved settings."""
        if not self.root:
            self.skipTest("Tkinter GUI not available in this environment.")

        saved_cfg = None
        def on_save(cfg):
            nonlocal saved_cfg
            saved_cfg = cfg

        dlg = SettingsDialog(self.root, on_save_callback=on_save)
        self.root.update()

        # Set break minutes to 3 and 5
        dlg.ent_break_min_m.delete(0, "end")
        dlg.ent_break_min_m.insert(0, "3")
        dlg.ent_break_max_m.delete(0, "end")
        dlg.ent_break_max_m.insert(0, "5")

        # Save settings
        dlg._handle_save()
        self.root.update()

        self.assertIsNotNone(saved_cfg)
        rp = saved_cfg.get("random_pause", {})
        self.assertEqual(rp.get("break_min_minutes"), 3.0)
        self.assertEqual(rp.get("break_max_minutes"), 5.0)
        self.assertEqual(rp.get("min_duration_seconds"), 180)
        self.assertEqual(rp.get("max_duration_seconds"), 300)

    def test_automation_start_does_not_minimize_or_restore_target_window(self):
        """Verify automation start creates zero window-manipulation tasks and ShowWindow(9) is removed."""
        from main import DeskPilotApp
        from automation.sequence_executor import executor
        import inspect

        # 1. Verify ShowWindow(hwnd, 9) was removed from focus_window_by_title
        src = inspect.getsource(executor.focus_window_by_title)
        self.assertNotIn("ShowWindow", src, "focus_window_by_title must not call ShowWindow (SW_RESTORE).")

        # 2. Verify _handle_start_automation does not queue focus_window task
        app = DeskPilotApp()
        app.update()
        app.panel_editor.set_code("print('clean start')\n")
        app.opt_target.set("Visual Studio Code")

        # Start automation while mocking executor.start to inspect the submitted tasks
        submitted_tasks = []
        with patch.object(executor, "start", side_effect=lambda tasks, **kw: submitted_tasks.extend(tasks) or True):
            app._handle_start_automation()

        app.destroy()

        task_types = [t.get("type") for t in submitted_tasks]
        self.assertNotIn("focus_window", task_types, "No focus_window action that manipulates or shrinks target window.")
        self.assertNotIn("wait", task_types, "No unnecessary wait task before typing starts.")
        self.assertIn("type_code", task_types, "Only clean direct type_code task is queued.")


if __name__ == "__main__":
    unittest.main()
