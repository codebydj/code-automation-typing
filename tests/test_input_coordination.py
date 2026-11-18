import threading
import time
import unittest
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import main
from automation.hotkey_manager import HotkeyManager, normalize_hotkey
from automation.input_dispatcher import input_dispatcher
from automation.keyboard_controller import keyboard_ctrl
from automation.safety import safety
from automation.sequence_executor import ExecutionState, SequenceExecutor
from config import DEFAULT_CONFIG


class TestInputCoordination(unittest.TestCase):
    def test_hotkeys_reserve_standard_editor_shortcuts(self):
        self.assertEqual(normalize_hotkey("Ctrl+Alt+F1"), ("alt", "ctrl", "f1"))
        for shortcut in ("ctrl+s", "ctrl+z", "ctrl+c", "ctrl+v", "ctrl+a", "ctrl+1", "esc"):
            with self.subTest(shortcut=shortcut):
                with self.assertRaises(ValueError):
                    normalize_hotkey(shortcut)

    def test_hotkey_hook_ignores_injected_events_and_passes_through_physical_chords(self):
        manager = HotkeyManager()
        triggered = []
        chord = normalize_hotkey("ctrl+alt+f1")
        manager._callbacks[chord] = lambda: triggered.append(True)
        manager._key_sets[chord] = set(chord)

        manager._handle_hook_event(0xA2, 0x0100, manager._LLKHF_INJECTED)
        manager._handle_hook_event(0xA4, 0x0100, manager._LLKHF_INJECTED)
        manager._handle_hook_event(0x70, 0x0100, manager._LLKHF_INJECTED)
        self.assertEqual(triggered, [])

        manager._handle_hook_event(0xA2, 0x0100, 0)
        manager._handle_hook_event(0xA4, 0x0100, 0)
        manager._handle_hook_event(0x70, 0x0100, 0)
        self.assertEqual(triggered, [True])

        manager._handle_hook_event(0x70, 0x0101, 0)
        manager._handle_hook_event(0xA4, 0x0101, 0)
        manager._handle_hook_event(0xA2, 0x0101, 0)
        manager._handle_hook_event(0x11, 0x0100, 0)
        manager._handle_hook_event(0x12, 0x0100, 0)
        manager._handle_hook_event(0x70, 0x0100, 0)
        self.assertEqual(triggered, [True, True])

    def test_dispatcher_serializes_concurrent_input_tasks(self):
        state_lock = threading.Lock()
        active = 0
        max_active = 0

        def operation():
            nonlocal active, max_active
            with state_lock:
                active += 1
                max_active = max(max_active, active)
            time.sleep(0.02)
            with state_lock:
                active -= 1

        threads = [
            threading.Thread(target=lambda: input_dispatcher.dispatch(operation))
            for _ in range(6)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=2.0)

        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(max_active, 1)

    def test_typing_keeps_other_automation_input_queued_until_complete(self):
        char_started = threading.Event()
        allow_typing_to_finish = threading.Event()
        queued_operation_ran = threading.Event()
        typing_result = []

        def block_character(_char, **_kwargs):
            char_started.set()
            return allow_typing_to_finish.wait(timeout=2)

        def type_text():
            typing_result.append(keyboard_ctrl.type_text("A", base_delay=0))

        typing_thread = threading.Thread(target=type_text)
        input_thread = threading.Thread(
            target=lambda: input_dispatcher.dispatch(queued_operation_ran.set)
        )
        with patch.object(keyboard_ctrl, "type_character", side_effect=block_character), \
             patch("automation.keyboard_controller.safety.interruptible_sleep", return_value=True):
            typing_thread.start()
            self.assertTrue(char_started.wait(timeout=1))
            input_thread.start()
            try:
                self.assertFalse(queued_operation_ran.wait(timeout=0.05))
            finally:
                allow_typing_to_finish.set()
            typing_thread.join(timeout=2)
            input_thread.join(timeout=2)

        self.assertEqual(typing_result, [True])
        self.assertTrue(queued_operation_ran.is_set())

    def test_explicit_key_down_and_up_update_held_input_tracking(self):
        with patch("automation.keyboard_controller.pyautogui.keyDown"), \
             patch("automation.keyboard_controller.pyautogui.keyUp"):
            self.assertTrue(keyboard_ctrl.key_down("shift"))
            self.assertIn("shift", input_dispatcher.held_inputs()[0])
            self.assertTrue(keyboard_ctrl.key_up("shift"))
            self.assertNotIn("shift", input_dispatcher.held_inputs()[0])

    def test_newline_does_not_backspace_when_editor_has_no_auto_indent(self):
        with patch("automation.keyboard_controller.pyautogui.press") as press:
            self.assertTrue(keyboard_ctrl.type_character("\n"))
        press.assert_called_once_with("enter")

    def test_tab_width_expands_to_configured_spaces(self):
        with patch("automation.keyboard_controller.pyautogui.press") as press:
            self.assertTrue(keyboard_ctrl.type_character("\t", tab_width=3))
        self.assertEqual(
            [call.args[0] for call in press.call_args_list],
            ["space", "space", "space"]
        )

    def test_type_text_passes_tab_width_to_character_dispatch(self):
        with patch.object(keyboard_ctrl, "type_character", return_value=True) as type_character:
            self.assertTrue(keyboard_ctrl.type_text("\t", base_delay=0, tab_width=2))
        type_character.assert_called_once_with("\t", tab_width=2)

    def test_fixed_typing_uses_same_character_interval_for_symbols(self):
        delays = []
        with patch.object(keyboard_ctrl, "type_character", return_value=True), \
             patch(
                 "automation.keyboard_controller.safety.interruptible_sleep",
                 side_effect=lambda delay, **_kwargs: delays.append(delay) or True
             ):
            self.assertTrue(keyboard_ctrl.type_text(
                "a!",
                speed_cps=5,
                base_delay=0.2,
                exact_speed=False
            ))
        self.assertEqual(len(delays), 1)
        self.assertAlmostEqual(delays[0], 0.2, delta=0.01)

    def test_newline_never_moves_cursor_during_typing(self):
        with patch.object(keyboard_ctrl, "type_character", return_value=True), \
             patch(
                 "automation.mouse_controller.mouse_ctrl.human_move_random",
                 return_value=True
             ) as cursor_move, \
             patch("automation.keyboard_controller.safety.interruptible_sleep", return_value=True):
            self.assertTrue(keyboard_ctrl.type_text(
                "\n",
                base_delay=0.1,
                cursor_movement_on_newline=True
            ))
        cursor_move.assert_not_called()

    def test_default_rate_and_action_pause_are_predictable(self):
        self.assertEqual(DEFAULT_CONFIG["typing"]["speed_cps"], 3)
        self.assertEqual(DEFAULT_CONFIG["execution"]["default_action_pause"], 0.1)

    def test_action_pause_preserves_remaining_time_across_resume(self):
        executor = SequenceExecutor()
        calls = []

        def interrupt_once(seconds, **_kwargs):
            calls.append(seconds)
            if len(calls) == 1:
                executor._pause_event.clear()
                threading.Timer(0.02, executor._pause_event.set).start()
                return False
            return True

        with patch("automation.sequence_executor.safety.interruptible_sleep", side_effect=interrupt_once):
            self.assertTrue(executor._wait_interruptibly(0.2))
        self.assertEqual(len(calls), 2)
        self.assertGreaterEqual(calls[1], 0.19)

    def test_stop_cleanup_releases_tracked_keys_and_mouse_buttons(self):
        input_dispatcher.track_key_down("shift")
        input_dispatcher.track_mouse_down("left")
        with patch("automation.safety.pyautogui.keyUp") as key_up, \
             patch("automation.safety.pyautogui.mouseUp") as mouse_up:
            safety.reset_hardware_state()
        key_up.assert_any_call("shift", _pause=False)
        mouse_up.assert_any_call(button="left", _pause=False)
        self.assertNotIn("shift", input_dispatcher.held_inputs()[0])
        self.assertNotIn("left", input_dispatcher.held_inputs()[1])

    def test_workspace_resize_persists_explorer_and_quickinput_widths(self):
        app = SimpleNamespace(
            workspace_panes=object(),
            panel_explorer=SimpleNamespace(winfo_width=lambda: 245),
            workspace_quickinput=SimpleNamespace(winfo_width=lambda: 360)
        )
        with patch.object(main, "load_config", return_value={"layout": {}}), \
             patch.object(main, "save_config", return_value=True) as save:
            main.DeskPilotApp._save_workspace_sizes(app)
        save.assert_called_once_with({
            "layout": {
                "explorer_width": 245,
                "quickinput_width": 360
            }
        })

    def test_hotkey_hint_matches_active_bindings(self):
        app = SimpleNamespace(config_data={
            "hotkeys": {
                "start": "ctrl+alt+f1",
                "pause": "ctrl+alt+f2",
                "resume": "ctrl+alt+f3",
                "stop": "ctrl+alt+f4"
            }
        })
        hint = main.DeskPilotApp._format_hotkey_hint(app)
        self.assertEqual(hint, "Hotkeys: CTRL+ALT+F1 Start • F2 Pause • F3 Resume • F4 Stop")

    def test_quick_keyboard_shortcuts_are_rejected_during_automation(self):
        status_messages = []
        app = SimpleNamespace(
            ent_quick_key=SimpleNamespace(get=lambda: "ctrl+a"),
            lbl_sb_status=SimpleNamespace(
                configure=lambda **kwargs: status_messages.append(kwargs["text"])
            )
        )
        with patch("main.executor.get_state", return_value=ExecutionState.RUNNING), \
             patch.object(main.DeskPilotApp, "_run_input_task") as run_input:
            main.DeskPilotApp._handle_quick_key(app)
        run_input.assert_not_called()
        self.assertTrue(status_messages)

    def test_smart_indent_cleanup_never_deletes_a_line_break(self):
        with patch("automation.keyboard_controller.time.monotonic_ns", return_value=123), \
             patch(
            "automation.keyboard_controller.pyperclip.paste",
            side_effect=("existing clipboard", "__deskpilot_indent_123__", "\n")
        ), patch("automation.keyboard_controller.pyperclip.copy"), \
             patch("automation.keyboard_controller.pyautogui.press") as press, \
             patch("automation.keyboard_controller.pyautogui.hotkey") as hotkey:
            self.assertTrue(keyboard_ctrl._clear_current_line_auto_indent())
        self.assertFalse(any(call.args == ("backspace",) for call in press.call_args_list))
        hotkey.assert_any_call("shift", "home")

    def test_smart_indent_cleanup_removes_editor_inserted_spaces(self):
        with patch(
            "automation.keyboard_controller.pyperclip.paste",
            side_effect=("existing clipboard", "    ", "\n")
        ), patch("automation.keyboard_controller.pyperclip.copy"), \
             patch("automation.keyboard_controller.pyautogui.press") as press, \
             patch("automation.keyboard_controller.pyautogui.hotkey") as hotkey:
            self.assertTrue(keyboard_ctrl._clear_current_line_auto_indent())
        press.assert_any_call("backspace")
        hotkey.assert_any_call("shift", "home")

    def test_smart_indent_cleanup_removes_actual_indent_when_source_indent_is_zero(self):
        with patch(
            "automation.keyboard_controller.pyperclip.paste",
            side_effect=("existing clipboard", "    ", "\n    ")
        ), patch("automation.keyboard_controller.pyperclip.copy"), \
             patch("automation.keyboard_controller.pyautogui.press") as press, \
             patch("automation.keyboard_controller.pyautogui.hotkey") as hotkey:
            self.assertTrue(keyboard_ctrl._clear_current_line_auto_indent())
        press.assert_any_call("backspace")
        hotkey.assert_any_call("shift", "home")

    def test_smart_indent_cleanup_removes_actual_indent_when_source_indent_differs(self):
        with patch("automation.keyboard_controller.time.monotonic_ns", return_value=123), \
             patch(
            "automation.keyboard_controller.pyperclip.paste",
            side_effect=("existing clipboard", "__deskpilot_indent_123__", " ", "  ", "   ", "    ", "\n    ")
        ), patch("automation.keyboard_controller.pyperclip.copy"), \
             patch("automation.keyboard_controller.pyautogui.press") as press, \
             patch("automation.keyboard_controller.pyautogui.hotkey") as hotkey:
            self.assertTrue(keyboard_ctrl._clear_current_line_auto_indent())
        press.assert_any_call("backspace")
        self.assertEqual(
            sum(call.args == ("shift", "left") for call in hotkey.call_args_list),
            9
        )

    def test_smart_indent_cleanup_runs_after_newline_with_no_source_indent(self):
        with patch.object(keyboard_ctrl, "type_character", return_value=True), \
             patch.object(keyboard_ctrl, "_clear_current_line_auto_indent") as clear_indent:
            self.assertTrue(keyboard_ctrl.type_text("\n", base_delay=0, smart_indent=True))
        clear_indent.assert_called_once_with()

    def test_sequence_executor_uses_configured_smart_indent_by_default(self):
        executor = SequenceExecutor()
        with patch(
            "automation.sequence_executor.load_config",
            return_value={"typing": {"smart_indent": True}, "mouse": {"line_interaction": {"enabled": False}}}
        ), patch.object(keyboard_ctrl, "type_text", return_value=True) as type_text:
            executor._execute_single_action({
                "type": "type_text",
                "text": "line\n",
                "line_mouse_enabled": False
            })
        self.assertTrue(type_text.call_args.kwargs["smart_indent"])

    def test_vs_code_target_matches_full_window_title(self):
        class FakeWindow:
            title = "script.py - Visual Studio Code"

            def __init__(self):
                self.activated = False

            def activate(self):
                self.activated = True

        window = FakeWindow()
        fake_module = SimpleNamespace(getAllWindows=lambda: [window])
        executor = SequenceExecutor()
        with patch.dict(sys.modules, {"pygetwindow": fake_module}), \
             patch("automation.sequence_executor.time.sleep"):
            self.assertTrue(executor._execute_single_action({
                "type": "focus_window",
                "title": "VS Code"
            }))
        self.assertTrue(window.activated)

    def test_executor_rejects_starts_while_paused_worker_is_alive(self):
        executor = SequenceExecutor()
        self.assertTrue(executor.start([{"type": "wait", "seconds": 0.3}], countdown_seconds=0))
        deadline = time.monotonic() + 1.0
        while executor.get_state() != ExecutionState.RUNNING and time.monotonic() < deadline:
            time.sleep(0.005)

        self.assertTrue(executor.pause())
        self.assertFalse(executor.start([{"type": "wait", "seconds": 0.01}], countdown_seconds=0))
        self.assertFalse(executor.run_single_action({"type": "wait", "seconds": 0.01}))
        self.assertTrue(executor.stop())
        self.assertTrue(executor.wait_for_idle(timeout=2.0))


if __name__ == "__main__":
    unittest.main()
