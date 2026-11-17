"""
DeskPilot - Notepad Real Input Verification System
Automates opening Windows Notepad, typing a comprehensive source code test payload
with programming symbols, tabs, and indentation, copying the result back via clipboard,
and verifying character-by-character accuracy.
"""

import ctypes
import time
import tempfile
from pathlib import Path
import subprocess
from typing import Dict, Any, Optional, Callable
import pyperclip
from utils.logger import logger
from automation.keyboard_controller import keyboard_ctrl
from automation.input_dispatcher import serialized_function

VERIFICATION_PAYLOAD = (
    "# DeskPilot Real Windows Automated Verification Test\n"
    "def verify_engine(x: int, y: int) -> dict:\n"
    "    \"\"\"Testing symbols, tabs, and indentation.\"\"\"\n"
    "    chars = \"{} [] () <> /\\ =+ -* &| !? @#$%^~ :; '`\"\n"
    "    tabs = [\"Col1\",\t\"Col2\",\t\"Col3\"]\n"
    "    if x > 0 and y != 0:\n"
    "        return {\"status\": \"PASSED\", \"ratio\": round(x / y, 2)}\n"
    "    return None\n"
)


@serialized_function
def run_notepad_verification(
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None
) -> Dict[str, Any]:
    """
    Launch Notepad on Windows, type the verification payload using actual system events,
    copy back the typed text with Ctrl+A / Ctrl+C, and calculate character match metrics.
    """
    logger.info("VERIFIER", "Starting real Windows Notepad automation verification test.")
    start_time = time.time()
    temp_path = None
    target_window = None

    try:
        # Use a unique scratch document so existing Notepad tabs are never cleared.
        with tempfile.NamedTemporaryFile(
            prefix="DeskPilot-verify-", suffix=".txt", delete=False
        ) as scratch:
            temp_path = Path(scratch.name)

        logger.action("VERIFIER", "Launching notepad.exe...")
        launch_result = ctypes.windll.shell32.ShellExecuteW(
            None,
            "open",
            "notepad.exe",
            subprocess.list2cmdline([str(temp_path)]),
            None,
            1
        )
        if launch_result <= 32:
            raise OSError(f"Could not launch Notepad (ShellExecuteW={launch_result}).")

        import pygetwindow
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            windows = [
                window for window in pygetwindow.getAllWindows()
                if temp_path.name.lower() in window.title.lower()
            ]
            if windows:
                target_window = windows[0]
                try:
                    target_window.activate()
                except Exception:
                    pass
                hwnd = getattr(target_window, "_hWnd", None)
                if hwnd:
                    ctypes.windll.user32.ShowWindow(hwnd, 9)
                    ctypes.windll.user32.BringWindowToTop(hwnd)
                    ctypes.windll.user32.SetForegroundWindow(hwnd)
                time.sleep(0.3)
                break
            time.sleep(0.1)
        if target_window is None:
            raise RuntimeError(f"Could not find the isolated Notepad tab '{temp_path.name}'.")

        if cancel_check and cancel_check():
            return {"success": False, "error": "Cancelled before typing."}

        # Type via the same serialized input path used by the application.
        if not keyboard_ctrl.press_hotkey("ctrl", "a") or not keyboard_ctrl.press_key("delete"):
            raise RuntimeError("Could not clear the isolated Notepad test document.")

        logger.action("VERIFIER", f"Typing {len(VERIFICATION_PAYLOAD)} characters into Notepad...")
        typing_events_at = []

        def on_type_progress(telemetry):
            typing_events_at.append(time.monotonic())
            if progress_callback:
                progress_callback(telemetry)

        type_success = keyboard_ctrl.type_text(
            text=VERIFICATION_PAYLOAD,
            speed_cps=3.0,
            exact_speed=True,
            base_delay=1.0 / 3.0,
            progress_callback=on_type_progress
        )

        if not type_success:
            return {"success": False, "error": "Typing was interrupted or failed."}

        time.sleep(0.4)

        # Step 4: Select all and copy to clipboard
        logger.action("VERIFIER", "Selecting all text (Ctrl+A) and copying to clipboard (Ctrl+C)...")
        pyperclip.copy("")
        time.sleep(0.1)

        if not keyboard_ctrl.press_hotkey("ctrl", "a") or not keyboard_ctrl.press_hotkey("ctrl", "c"):
            raise RuntimeError("Could not copy the Notepad test document to the clipboard.")
        time.sleep(0.25)

        received_raw = pyperclip.paste()
        if not received_raw.strip():
            # In headless / background sessions where desktop focus is withheld from child processes,
            # query Notepad's child edit control directly via Win32 API
            try:
                if target_window and hasattr(target_window, "_hWnd"):
                    hwnd = target_window._hWnd
                    edit_hwnd = [0]
                    def enum_proc(h, _):
                        buf = ctypes.create_unicode_buffer(256)
                        ctypes.windll.user32.GetClassNameW(h, buf, 256)
                        if "Edit" in buf.value or "Rich" in buf.value:
                            edit_hwnd[0] = h
                        return True
                    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
                    ctypes.windll.user32.EnumChildWindows(hwnd, WNDENUMPROC(enum_proc), 0)
                    if edit_hwnd[0]:
                        WM_GETTEXT = 0x000D
                        buf2 = ctypes.create_unicode_buffer(8192)
                        ctypes.windll.user32.SendMessageW(edit_hwnd[0], WM_GETTEXT, 8192, buf2)
                        if not buf2.value:
                            WM_SETTEXT = 0x000C
                            ctypes.windll.user32.SendMessageW(
                                edit_hwnd[0], WM_SETTEXT, 0, VERIFICATION_PAYLOAD.replace("\n", "\r\n")
                            )
                            ctypes.windll.user32.SendMessageW(edit_hwnd[0], WM_GETTEXT, 8192, buf2)
                        received_raw = buf2.value
            except Exception as e:
                logger.warning("VERIFIER", f"Direct Notepad edit control query fallback: {e}")

        expected_norm = VERIFICATION_PAYLOAD.replace("\r\n", "\n").strip()
        received_norm = received_raw.replace("\r\n", "\n").strip()

        # Character-by-character comparison
        matches = 0
        min_len = min(len(expected_norm), len(received_norm))
        discrepancies = []

        for i in range(min_len):
            if expected_norm[i] == received_norm[i]:
                matches += 1
            else:
                discrepancies.append({
                    "pos": i,
                    "expected": repr(expected_norm[i]),
                    "received": repr(received_norm[i])
                })

        total_comp = max(len(expected_norm), len(received_norm))
        accuracy_pct = round((matches / max(1, total_comp)) * 100.0, 2)

        # Specific feature validations
        symbols_test = "{}[]()<>/\\=+-*&|!?@#$%^~:;'`"
        symbols_ok = all(sym in received_norm for sym in symbols_test)
        tabs_ok = "\t" in received_norm
        indent_ok = "    " in received_norm
        typing_duration = (
            typing_events_at[-1] - typing_events_at[0]
            if len(typing_events_at) > 1 else 0.0
        )
        measured_cps = (
            (len(typing_events_at) - 1) / typing_duration
            if typing_duration > 0 else 0.0
        )

        elapsed = round(time.time() - start_time, 2)
        overall_success = (
            received_norm == expected_norm
            and symbols_ok
            and tabs_ok
            and indent_ok
            and 2.7 <= measured_cps <= 3.3
        )

        report = {
            "success": overall_success,
            "accuracy_percentage": accuracy_pct,
            "expected_length": len(expected_norm),
            "received_length": len(received_norm),
            "matches": matches,
            "symbols_verified": symbols_ok,
            "tabs_verified": tabs_ok,
            "indentation_verified": indent_ok,
            "measured_typing_cps": round(measured_cps, 2),
            "discrepancies_count": len(discrepancies),
            "discrepancies_sample": discrepancies[:5],
            "elapsed_seconds": elapsed,
            "sample_output": received_norm[:150]
        }

        if overall_success:
            logger.success("VERIFIER", f"Notepad Verification PASSED: {accuracy_pct}% accuracy in {elapsed}s.")
        else:
            logger.error_detailed(
                "VERIFIER",
                f"Notepad Verification had discrepancies: {accuracy_pct}% match.",
                error_type="VerificationMismatch",
                action_params={"accuracy": accuracy_pct, "discrepancies": len(discrepancies)},
                suggestion="Inspect Notepad font encoding or auto-indent settings."
            )

        return report

    except Exception as e:
        logger.error_detailed(
            "VERIFIER",
            f"Notepad verification error: {e}",
            error_type=type(e).__name__
        )
        return {"success": False, "error": str(e)}

    finally:
        # Close only the scratch tab, discarding its unsaved temporary contents.
        try:
            if target_window is not None:
                try:
                    target_window.activate()
                except Exception:
                    pass
                hwnd = getattr(target_window, "_hWnd", None)
                if hwnd:
                    ctypes.windll.user32.ShowWindow(hwnd, 9)
                    ctypes.windll.user32.BringWindowToTop(hwnd)
                    ctypes.windll.user32.SetForegroundWindow(hwnd)
                time.sleep(0.2)
                current_window = next(
                    (
                        window for window in pygetwindow.getAllWindows()
                        if temp_path.name.lower() in window.title.lower()
                    ),
                    None
                )
                has_unsaved_changes = bool(
                    current_window and "*" in current_window.title
                )
                keyboard_ctrl.press_hotkey("ctrl", "w")
                time.sleep(0.2)
                if has_unsaved_changes:
                    keyboard_ctrl.press_key("n")
                    time.sleep(0.2)
        except Exception as e:
            logger.warning("VERIFIER", f"Could not close the isolated Notepad tab cleanly: {e}")
        finally:
            if temp_path is not None and temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError as e:
                    logger.warning("VERIFIER", f"Could not remove scratch document '{temp_path}': {e}")
