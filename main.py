"""
DeskPilot – Minimal Code Typing Automation Redesign
A streamlined, lightweight desktop automation application with a single code editor
and basic controls to type the entered code into the selected target application
using exact character-by-character typing and natural human-like mouse movement.
"""

import sys
import time
import math
import queue
import threading
import tkinter as tk
from pathlib import Path
from typing import Optional, Any, Callable, Dict, Tuple
from tkinter import filedialog, messagebox
import customtkinter as ctk

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import load_config, save_config, APP_VERSION, SEQUENCES_DIR
from utils.logger import logger
from utils.storage import create_sample_sequences_if_empty
from automation.safety import safety
from automation.sequence_executor import executor, ExecutionState
from automation.keyboard_controller import keyboard_ctrl
from automation.mouse_controller import mouse_ctrl
from automation.hotkey_manager import HotkeyManager
from automation.input_dispatcher import input_dispatcher

# Core IDE Editor
from ui.ide_editor import IDECodeEditor


class DeskPilotApp(ctk.CTk):
    """
    DeskPilot Minimal Code Typing Automation Application.
    Provides:
      - Top Toolbar: New, Open, Save (F9), Checkpoint (F10), Estimated Time,
        Start (F5), Pause (F6), Resume (F7), Stop (F8), Target App, Speed, and Mouse Move.
      - Main Workspace: One large code editor occupying almost the entire window.
      - Bottom Status Bar: Execution status, Line number, Progress, and Remaining time.
    """

    def __init__(self):
        super().__init__()

        # Load persistent configuration
        self.config_data = load_config()
        self._ui_actions: queue.Queue = queue.Queue()
        self._closing = False
        self.hotkey_manager = HotkeyManager()

        # Appearance configuration
        app_cfg = self.config_data.get("appearance", {})
        ctk.set_appearance_mode(app_cfg.get("theme", "Dark"))
        ctk.set_default_color_theme(app_cfg.get("color_theme", "blue"))

        # Window properties
        self.title("DeskPilot – Minimal Code Typing Automation")
        width = max(1120, app_cfg.get("window_width", 1180))
        height = max(700, app_cfg.get("window_height", 740))
        self.geometry(f"{width}x{height}")
        self.minsize(860, 540)

        # Safety setup
        safety_cfg = self.config_data.get("safety", {})
        safety.set_failsafe(safety_cfg.get("failsafe", True))

        # Checkpoint state
        self.checkpoint_char_index: Optional[int] = None
        self.checkpoint_line: Optional[int] = None

        # Live telemetry tracking
        self._typing_start_time: float = 0.0
        self._last_typed_index: int = 0
        self._last_typed_line: int = 1
        self._total_chars: int = 0
        self._total_lines: int = 1

        # Random rest pause option (3–6 minutes human break)
        self._random_pause_enabled: bool = bool(self.config_data.get("random_pause", {}).get("enabled", True))

        # Seed sample sequences if needed
        create_sample_sequences_if_empty()

        # Grid configuration:
        # Row 0: Top Toolbar (weight 0)
        # Row 1: Code Editor Workspace (weight 1 - occupies almost entire window)
        # Row 2: Bottom Status Bar (weight 0)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)
        self.grid_columnconfigure(0, weight=1)

        # Construct UI
        self._create_top_toolbar()
        self._create_main_workspace()
        self._create_status_bar()

        # Wire up executor callbacks
        self._setup_executor_listeners()

        # Load user's given code from sequences/demo if present
        user_demo_file = SEQUENCES_DIR / "demo"
        if user_demo_file.is_file():
            try:
                user_code = user_demo_file.read_text(encoding="utf-8")
                self.panel_editor.set_code(user_code, "demo.py", "Python")
                logger.info("SYSTEM", f"Loaded code from {user_demo_file.name} ({len(user_code)} chars).")
            except Exception as e:
                logger.warning("SYSTEM", f"Could not auto-load sequences/demo: {e}")

        # Update initial estimated time
        self._update_estimated_time()

        # Register hotkeys (F5–F10 + global/window bindings)
        self._register_global_hotkeys()
        self._bind_local_hotkeys()

        # UI action pump
        self._ui_drain_after_id = self.after(30, self._drain_ui_actions)

        # Clean shutdown protocol
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        logger.info("SYSTEM", f"DeskPilot v{APP_VERSION} initialized. Default typing speed: 3 chars/sec.")

    # =========================================================================
    # 1. TOP TOOLBAR
    # =========================================================================

    def _create_top_toolbar(self):
        """Build the top toolbar with ONLY the essential controls requested."""
        self.toolbar = ctk.CTkFrame(
            self,
            height=46,
            corner_radius=0,
            fg_color="#111319",
            border_width=1,
            border_color="#202330"
        )
        self.toolbar.grid(row=0, column=0, sticky="ew")
        self.toolbar.grid_propagate(False)

        # Brand Badge
        brand_frame = ctk.CTkFrame(self.toolbar, fg_color="transparent")
        brand_frame.pack(side="left", padx=(10, 6), pady=6)

        lbl_logo = ctk.CTkLabel(
            brand_frame,
            text="⚡ DeskPilot",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color="#f8fafc"
        )
        lbl_logo.pack(side="left")

        # Separator
        ctk.CTkFrame(self.toolbar, width=1, height=22, fg_color="#262a3b").pack(side="left", padx=4)

        # File Controls: New, Open, Save (F9)
        self.btn_new = ctk.CTkButton(
            self.toolbar,
            text="📄 New",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#1e2230",
            hover_color="#2d3348",
            text_color="#e2e8f0",
            width=56,
            height=28,
            corner_radius=5,
            command=self._handle_new_file
        )
        self.btn_new.pack(side="left", padx=2)

        self.btn_open = ctk.CTkButton(
            self.toolbar,
            text="📂 Open",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#1e2230",
            hover_color="#2d3348",
            text_color="#e2e8f0",
            width=58,
            height=28,
            corner_radius=5,
            command=self._handle_open_file
        )
        self.btn_open.pack(side="left", padx=2)

        self.btn_save = ctk.CTkButton(
            self.toolbar,
            text="💾 Save (F9)",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#1e2230",
            hover_color="#2d3348",
            text_color="#e2e8f0",
            width=76,
            height=28,
            corner_radius=5,
            command=self._handle_save_file
        )
        self.btn_save.pack(side="left", padx=2)

        # Separator
        ctk.CTkFrame(self.toolbar, width=1, height=22, fg_color="#262a3b").pack(side="left", padx=4)

        # Checkpoint Control (F10)
        self.checkpoint_frame = ctk.CTkFrame(self.toolbar, fg_color="transparent")
        self.checkpoint_frame.pack(side="left", padx=2)

        self.btn_checkpoint = ctk.CTkButton(
            self.checkpoint_frame,
            text="🔖 Checkpoint (F10)",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="#1e293b",
            hover_color="#334155",
            text_color="#cbd5e1",
            height=28,
            corner_radius=5,
            command=self._handle_checkpoint
        )
        self.btn_checkpoint.pack(side="left")

        self.btn_clear_checkpoint = ctk.CTkButton(
            self.checkpoint_frame,
            text="✖",
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color="#7f1d1d",
            hover_color="#991b1b",
            text_color="#fca5a5",
            width=20,
            height=28,
            corner_radius=4,
            command=self._clear_checkpoint
        )
        # Not packed until checkpoint is set

        # Estimated Time Button / Display
        self.btn_est_time = ctk.CTkButton(
            self.toolbar,
            text="⏱ Est. Time: 00:00:00",
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            fg_color="#064e3b",
            hover_color="#047857",
            text_color="#34d399",
            height=28,
            corner_radius=5,
            command=self._handle_calc_time
        )
        self.btn_est_time.pack(side="left", padx=4)

        # Separator
        ctk.CTkFrame(self.toolbar, width=1, height=22, fg_color="#262a3b").pack(side="left", padx=4)

        # Execution Controls: Start (F5), Pause (F6), Resume (F7), Stop (F8)
        self.btn_start = ctk.CTkButton(
            self.toolbar,
            text="▶ Start (F5)",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            width=80,
            height=28,
            fg_color="#059669",
            hover_color="#10b981",
            corner_radius=5,
            command=self._handle_start_automation
        )
        self.btn_start.pack(side="left", padx=2)

        self.btn_pause = ctk.CTkButton(
            self.toolbar,
            text="⏸ Pause (F6)",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            width=78,
            height=28,
            fg_color="#b45309",
            hover_color="#d97706",
            state="disabled",
            corner_radius=5,
            command=self._handle_pause_automation
        )
        self.btn_pause.pack(side="left", padx=2)

        self.btn_resume = ctk.CTkButton(
            self.toolbar,
            text="⏯ Resume (F7)",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            width=84,
            height=28,
            fg_color="#1d4ed8",
            hover_color="#2563eb",
            state="disabled",
            corner_radius=5,
            command=self._handle_resume_automation
        )
        self.btn_resume.pack(side="left", padx=2)

        self.btn_stop = ctk.CTkButton(
            self.toolbar,
            text="⏹ Stop (F8)",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            width=76,
            height=28,
            fg_color="#374151",
            hover_color="#b91c1c",
            state="disabled",
            corner_radius=5,
            command=self._handle_stop_automation
        )
        self.btn_stop.pack(side="left", padx=2)

        # Separator
        ctk.CTkFrame(self.toolbar, width=1, height=22, fg_color="#262a3b").pack(side="left", padx=4)

        # Random Rest Pause (3–6 minutes human break) Toggle
        self.btn_rest_pause = ctk.CTkButton(
            self.toolbar,
            text="☕ Rest: ON" if self._random_pause_enabled else "☕ Rest: OFF",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            width=86,
            height=28,
            fg_color="#065f46" if self._random_pause_enabled else "#1f2937",
            hover_color="#047857" if self._random_pause_enabled else "#374151",
            text_color="#6ee7b7" if self._random_pause_enabled else "#9ca3af",
            corner_radius=5,
            command=self._handle_toggle_rest_pause
        )
        self.btn_rest_pause.pack(side="left", padx=2)

        # Right side: Simple Target selector, Mode selector, and Speed selector
        right_deck = ctk.CTkFrame(self.toolbar, fg_color="transparent")
        right_deck.pack(side="right", padx=(4, 10), pady=6)

        # Speed selector (default: 3 CPS, max: 3.5 CPS)
        self.opt_speed = ctk.CTkOptionMenu(
            right_deck,
            values=["3 CPS", "1 CPS", "1.5 CPS", "2 CPS", "2.5 CPS", "3.5 CPS"],
            width=84,
            height=26,
            font=ctk.CTkFont(size=11),
            command=self._on_speed_changed
        )
        curr_speed = float(self.config_data.get("typing", {}).get("speed_cps", 3.0))
        curr_speed = min(3.5, max(0.5, curr_speed))
        self.opt_speed.set(f"{int(curr_speed)} CPS" if curr_speed.is_integer() else f"{curr_speed} CPS")
        self.opt_speed.pack(side="right", padx=4)

        ctk.CTkLabel(right_deck, text="Speed:", font=ctk.CTkFont(size=11), text_color="#94a3b8").pack(side="right", padx=(4, 1))

        # Mode selector: Difficulty-Based vs Fixed CPS ("CPS as usual")
        self.opt_mode = ctk.CTkOptionMenu(
            right_deck,
            values=["Difficulty-Based", "Fixed CPS"],
            width=132,
            height=26,
            font=ctk.CTkFont(size=11),
            command=self._on_mode_changed
        )
        cfg_mode = str(self.config_data.get("typing", {}).get("timing_mode", "difficulty")).lower()
        init_mode = "Fixed CPS" if cfg_mode == "fixed" else "Difficulty-Based"
        self.opt_mode.set(init_mode)
        self.opt_mode.pack(side="right", padx=4)

        ctk.CTkLabel(right_deck, text="Mode:", font=ctk.CTkFont(size=11), text_color="#94a3b8").pack(side="right", padx=(4, 1))

        # Target app selector
        self.opt_target = ctk.CTkOptionMenu(
            right_deck,
            values=["VS Code", "Notepad", "Active Window / Manual Focus"],
            width=140,
            height=26,
            font=ctk.CTkFont(size=11)
        )
        self.opt_target.set("VS Code")
        self.opt_target.pack(side="right", padx=4)

        ctk.CTkLabel(right_deck, text="Target:", font=ctk.CTkFont(size=11), text_color="#94a3b8").pack(side="right", padx=(4, 1))

    # =========================================================================
    # 2. MAIN WORKSPACE (ONE LARGE CODE EDITOR)
    # =========================================================================

    def _create_main_workspace(self):
        """Create the central code editor workspace occupying almost the entire window."""
        self.panel_editor = IDECodeEditor(
            self,
            on_code_changed=self._on_editor_code_changed
        )
        self.panel_editor.grid(row=1, column=0, sticky="nsew", padx=6, pady=4)

    # =========================================================================
    # 3. BOTTOM STATUS BAR
    # =========================================================================

    def _create_status_bar(self):
        """Construct the minimal 4-segment application status bar."""
        self.statusbar = ctk.CTkFrame(
            self,
            height=26,
            corner_radius=0,
            fg_color="#0c0e14",
            border_width=1,
            border_color="#1c1f2b"
        )
        self.statusbar.grid(row=2, column=0, sticky="ew")
        self.statusbar.grid_propagate(False)

        # Segment 1: Current execution status
        self.lbl_sb_status = ctk.CTkLabel(
            self.statusbar,
            text="● Ready to Automate",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#34d399"
        )
        self.lbl_sb_status.pack(side="left", padx=12)

        # Segment 2: Current line / total lines
        self.lbl_sb_lines = ctk.CTkLabel(
            self.statusbar,
            text="Line: 1 / 1",
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color="#94a3b8"
        )
        self.lbl_sb_lines.pack(side="left", padx=14)

        # Segment 3: Typing progress percentage and char count
        self.lbl_sb_progress = ctk.CTkLabel(
            self.statusbar,
            text="Progress: 0.0% (0 / 0 chars)",
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color="#38bdf8"
        )
        self.lbl_sb_progress.pack(side="left", padx=14)

        # Segment 4: Estimated remaining time & elapsed time
        self.lbl_sb_time = ctk.CTkLabel(
            self.statusbar,
            text="Est. Remaining: 00:00:00 • Elapsed: 00:00:00",
            font=ctk.CTkFont(family="Consolas", size=10, weight="bold"),
            text_color="#f1f5f9"
        )
        self.lbl_sb_time.pack(side="right", padx=12)

    # =========================================================================
    # 4. EXECUTOR TELEMETRY & LISTENERS
    # =========================================================================

    def _setup_executor_listeners(self):
        """Wire execution engine events to thread-safe UI updates."""
        def on_state(state):
            try:
                state_enum = ExecutionState(state)
            except ValueError:
                state_enum = ExecutionState.IDLE
            self._ui_actions.put(lambda: self._update_ui_state(state_enum))

        def on_countdown(secs):
            self._ui_actions.put(lambda: self.lbl_sb_status.configure(
                text=f"● Countdown: {secs}s (Switch to target window)",
                text_color="#f59e0b"
            ))

        def on_progress(current_step, total_steps, pct):
            pass

        def on_typing_telemetry(tel):
            if isinstance(tel, dict):
                idx = tel.get("index", 0)
                tot = tel.get("total", 0)
                ln = tel.get("line", 1)
                col = tel.get("col", 1)
                ch = tel.get("char", "")
                pct = tel.get("pct", 0.0)

                self._last_typed_index = idx
                self._last_typed_line = ln

                # Calculate remaining time using selected mode (Difficulty-Based vs Fixed CPS)
                code = self.panel_editor.get_code()
                speed_cps = self._get_current_speed_cps()
                is_difficulty = getattr(self, "opt_mode", None) is None or self.opt_mode.get() == "Difficulty-Based"
                from automation.timing_controller import timing_controller
                rem_seconds, rem_str = timing_controller.calculate_sequence_estimate(
                    text=code[idx:],
                    cps=speed_cps,
                    countdown_seconds=0,
                    mouse_move_enabled=True,
                    use_difficulty=is_difficulty,
                    random_pause_enabled=getattr(self, "_random_pause_enabled", False)
                )

                # Calculate elapsed time
                elapsed_sec = int(max(0, time.monotonic() - getattr(self, "_typing_start_time", time.monotonic())))
                el_h = elapsed_sec // 3600
                el_m = (elapsed_sec % 3600) // 60
                el_s = elapsed_sec % 60
                el_str = f"{el_h:02d}:{el_m:02d}:{el_s:02d}"

                self._ui_actions.put(lambda: self._update_live_telemetry(ln, idx, tot, pct, rem_str, el_str, ch, col))

        def on_action_start(idx, action):
            pass

        def on_completed(total_actions, elapsed_time):
            pass

        def on_kb_action(act_text):
            if act_text and "Moving mouse" in act_text:
                self._ui_actions.put(lambda: self.lbl_sb_status.configure(
                    text=f"● {act_text}",
                    text_color="#c084fc"
                ))
            elif act_text and "Rest Pause" in act_text:
                self._ui_actions.put(lambda: self.lbl_sb_status.configure(
                    text=f"● {act_text} • [F7 to Skip]",
                    text_color="#f59e0b"
                ))

        def on_rest_pause_countdown(rem_secs, tot_secs):
            mm = rem_secs // 60
            ss = rem_secs % 60
            self._ui_actions.put(lambda: self.lbl_sb_status.configure(
                text=f"● Rest Pause: auto-resuming in {mm:02d}:{ss:02d}... [F7 to Skip]",
                text_color="#f59e0b"
            ))

        executor.on_status_change = on_state
        executor.on_countdown = on_countdown
        executor.on_progress = on_progress
        executor.on_typing_telemetry = on_typing_telemetry
        executor.on_action_start = on_action_start
        executor.on_completed = on_completed
        executor.on_keyboard_action = on_kb_action
        executor.on_rest_pause_countdown = on_rest_pause_countdown

    def _update_live_telemetry(self, line: int, char_idx: int, total_chars: int, pct: float, rem_time: str, el_time: str, ch: str, col: int):
        """Update live status bar numbers and editor pointer."""
        code = self.panel_editor.get_code()
        total_lines = code.count("\n") + 1
        self.lbl_sb_lines.configure(text=f"Line: {line} / {total_lines}")
        self.lbl_sb_progress.configure(text=f"Progress: {pct:.1f}% ({char_idx} / {total_chars} chars)")
        self.lbl_sb_time.configure(text=f"Est. Remaining: {rem_time} • Elapsed: {el_time}")
        self.panel_editor.show_typing_pointer(line, col, ch)

    def _update_ui_state(self, state: ExecutionState):
        """Synchronize toolbar buttons and status text based on execution state."""
        if state == ExecutionState.RUNNING:
            self.btn_start.configure(state="disabled", fg_color="#1f2937")
            self.btn_pause.configure(state="normal", fg_color="#b45309")
            self.btn_resume.configure(state="disabled", text="⏯ Resume (F7)", fg_color="#1e3a8a")
            self.btn_stop.configure(state="normal", fg_color="#b91c1c", hover_color="#dc2626")
            self.lbl_sb_status.configure(text="● Typing...", text_color="#38bdf8")

        elif state == ExecutionState.REST_PAUSED:
            self.btn_start.configure(state="disabled", fg_color="#1f2937")
            self.btn_pause.configure(state="disabled", fg_color="#b45309")
            self.btn_resume.configure(state="normal", text="⏯ Skip Rest (F7)", fg_color="#2563eb", hover_color="#1d4ed8")
            self.btn_stop.configure(state="normal", fg_color="#b91c1c", hover_color="#dc2626")
            self.lbl_sb_status.configure(
                text="● Rest Pause: auto-resuming in 3–6 min... [F7 to Skip]",
                text_color="#f59e0b"
            )

        elif state == ExecutionState.COUNTDOWN:
            self.btn_start.configure(state="disabled", fg_color="#1f2937")
            self.btn_pause.configure(state="disabled", fg_color="#b45309")
            self.btn_resume.configure(state="disabled", text="⏯ Resume (F7)", fg_color="#1e3a8a")
            self.btn_stop.configure(state="normal", fg_color="#b91c1c")

        elif state == ExecutionState.PAUSED:
            self.btn_start.configure(state="disabled", fg_color="#1f2937")
            self.btn_pause.configure(state="disabled", fg_color="#b45309")
            self.btn_resume.configure(state="normal", text="⏯ Resume (F7)", fg_color="#2563eb")
            self.btn_stop.configure(state="normal", fg_color="#b91c1c")
            self.lbl_sb_status.configure(
                text=f"● Automation Paused at Line {self._last_typed_line}",
                text_color="#fbbf24"
            )

        else:  # IDLE, STOPPED, COMPLETED, EMERGENCY_STOPPED
            self.btn_start.configure(state="normal", fg_color="#059669")
            self.btn_pause.configure(state="disabled", fg_color="#374151")
            self.btn_resume.configure(state="disabled", text="⏯ Resume (F7)", fg_color="#374151")
            self.btn_stop.configure(state="disabled", fg_color="#374151")

            self.panel_editor.clear_typing_pointer()

            if state == ExecutionState.COMPLETED:
                self.lbl_sb_status.configure(text="● Completed Successfully", text_color="#34d399")
                code = self.panel_editor.get_code()
                tot_chars = len(code)
                tot_lines = code.count("\n") + 1
                self.lbl_sb_lines.configure(text=f"Line: {tot_lines} / {tot_lines}")
                self.lbl_sb_progress.configure(text=f"Progress: 100.0% ({tot_chars} / {tot_chars} chars)")
                # Clear checkpoint upon full completion
                self._clear_checkpoint()
            elif state == ExecutionState.EMERGENCY_STOPPED:
                self.lbl_sb_status.configure(text="● EMERGENCY STOP (Inputs Released)", text_color="#ef4444")
            elif state == ExecutionState.STOPPED:
                self.lbl_sb_status.configure(text="● Stopped", text_color="#94a3b8")
            else:
                self.lbl_sb_status.configure(text="● Ready to Automate", text_color="#34d399")

    # =========================================================================
    # 5. AUTOMATION CONTROLS (START, PAUSE, RESUME, STOP, CHECKPOINT)
    # =========================================================================

    def _get_current_speed_cps(self) -> float:
        """Parse typing speed in characters per second from toolbar selector (max 3.5 CPS)."""
        try:
            val = float(self.opt_speed.get().split()[0])
            return min(3.5, max(0.5, val))
        except Exception:
            return 3.0

    def _handle_start_automation(self):
        """
        Validate editor code, build sequential typing task, focus target application,
        and start automated execution with dynamic character difficulty and mouse movements.
        """
        code = self.panel_editor.get_code()
        if not code or not code.strip():
            messagebox.showwarning("Empty Code Editor", "Please enter or paste code into the editor before starting.", parent=self)
            return

        target_app = self.opt_target.get()
        speed_cps = self._get_current_speed_cps()
        countdown = 3 if target_app.lower() != "active window / manual focus" else 3

        # Prepare sequential task list
        tasks = []

        # Focus target window if specified
        if target_app and target_app.lower() not in ("active window / manual focus", "any window", "none"):
            tasks.append({
                "type": "focus_window",
                "title": target_app,
                "description": f"Focus target window: {target_app}"
            })

        tasks.append({
            "type": "wait",
            "seconds": 1.0,
            "description": "Wait for target window to settle"
        })

        # Checkpoint resume logic
        start_char_idx = 0
        if self.checkpoint_char_index is not None and self.checkpoint_char_index > 0:
            start_char_idx = self.checkpoint_char_index
            logger.info("SYSTEM", f"Resuming automation from checkpoint at char {start_char_idx} (Line {self.checkpoint_line}).")

        # Code typing task (strictly character typing only, natural mouse after every line)
        is_difficulty = getattr(self, "opt_mode", None) is None or self.opt_mode.get() == "Difficulty-Based"
        tasks.append({
            "type": "type_code",
            "text": code,
            "_resume_char_index": start_char_idx,
            "speed": 1.0 / speed_cps,
            "timing_mode": "difficulty" if is_difficulty else "fixed",
            "use_difficulty": is_difficulty,
            "exact_speed": not is_difficulty,
            "tab_width": getattr(self.panel_editor, "indent_width", 4),
            "line_mouse_enabled": True,
            "every_line": False,
            "min_lines": 2,
            "max_lines": 5,
            "natural_line_mouse": True,
            "random_pause_enabled": self._random_pause_enabled,
            "random_pause_min_lines": 15,
            "random_pause_max_lines": 30,
            "random_pause_min_seconds": 180,
            "random_pause_max_seconds": 360,
            "smart_indent": False,
            "target_window": target_app,
            "description": f"Type code ({'Difficulty-Based' if is_difficulty else 'Fixed CPS'} at {speed_cps:.1f} CPS, {len(code)} chars)"
        })

        self._typing_start_time = time.monotonic()
        self._last_typed_index = start_char_idx
        self._last_typed_line = self.checkpoint_line or 1

        logger.info("SYSTEM", f"Starting code typing automation targeting '{target_app}' at {speed_cps:.1f} CPS.")
        if not executor.start(tasks, countdown_seconds=countdown, loop=False):
            logger.warning("SYSTEM", "Execution worker already active; start rejected.")

    def _handle_pause_automation(self):
        """Temporarily pause typing at the current character boundary."""
        executor.pause()

    def _handle_resume_automation(self):
        """Resume typing from the exact paused character position or skip rest pause."""
        if executor.get_state() == ExecutionState.REST_PAUSED:
            executor.skip_rest_pause()
        else:
            executor.resume()

    def _handle_toggle_rest_pause(self):
        """Toggle random 3–6 minute rest pause on or off."""
        self._random_pause_enabled = not self._random_pause_enabled
        if self._random_pause_enabled:
            self.btn_rest_pause.configure(
                text="☕ Rest: ON",
                fg_color="#065f46",
                hover_color="#047857",
                text_color="#6ee7b7"
            )
            logger.info("SYSTEM", "Random Rest Pause enabled (3–6 minute human breaks between random 15–30 lines).")
        else:
            self.btn_rest_pause.configure(
                text="☕ Rest: OFF",
                fg_color="#1f2937",
                hover_color="#374151",
                text_color="#9ca3af"
            )
            logger.info("SYSTEM", "Random Rest Pause disabled.")
        self._update_estimated_time()

    def _handle_stop_automation(self):
        """Cancel automation and release all held hardware keys/buttons."""
        executor.stop()

    def _handle_emergency_stop(self):
        """Immediate hardware abort."""
        executor.emergency_stop()

    def _handle_checkpoint(self):
        """
        Record the current execution or cursor position as a safe recovery checkpoint.
        When started, execution will resume from here without duplicating prior text.
        """
        if executor.get_state() in (ExecutionState.RUNNING, ExecutionState.PAUSED):
            self.checkpoint_char_index = self._last_typed_index
            self.checkpoint_line = self._last_typed_line
        else:
            self.checkpoint_char_index = self.panel_editor.get_cursor_char_offset()
            self.checkpoint_line = self.panel_editor.get_cursor_line()

        # Update toolbar button
        self.btn_checkpoint.configure(
            text=f"🔖 Checkpoint: Ln {self.checkpoint_line} (Char {self.checkpoint_char_index})",
            fg_color="#312e81",
            hover_color="#3730a3",
            text_color="#c7d2fe"
        )
        self.btn_clear_checkpoint.pack(side="left", padx=(2, 0))

        self.lbl_sb_status.configure(
            text=f"● Checkpoint set at Line {self.checkpoint_line} (Char {self.checkpoint_char_index})",
            text_color="#a5b4fc"
        )
        logger.info("SYSTEM", f"Checkpoint set at line {self.checkpoint_line}, character {self.checkpoint_char_index}.")

    def _clear_checkpoint(self):
        """Clear active checkpoint and reset Start button to beginning."""
        self.checkpoint_char_index = None
        self.checkpoint_line = None
        self.btn_checkpoint.configure(
            text="🔖 Checkpoint (F10)",
            fg_color="#1e293b",
            hover_color="#334155",
            text_color="#cbd5e1"
        )
        self.btn_clear_checkpoint.pack_forget()
        self.lbl_sb_status.configure(text="● Checkpoint cleared", text_color="#94a3b8")
        logger.info("SYSTEM", "Checkpoint cleared.")

    # =========================================================================
    # 6. FILE OPERATIONS & ESTIMATE CALCULATION
    # =========================================================================

    def _handle_new_file(self):
        """Reset editor, checkpoint, and estimates."""
        self._clear_checkpoint()
        self.panel_editor.set_code("", "untitled.py", "Python")
        self._update_estimated_time()
        self.lbl_sb_status.configure(text="● Ready to Automate", text_color="#34d399")

    def _handle_open_file(self):
        """Open source code file into editor."""
        file_path = filedialog.askopenfilename(
            title="Open Script File",
            filetypes=[
                ("Source Code", "*.py;*.js;*.html;*.css;*.sql;*.txt"),
                ("Python Files", "*.py"),
                ("JavaScript Files", "*.js"),
                ("All Files", "*.*")
            ],
            parent=self
        )
        if file_path:
            p = Path(file_path)
            try:
                content = p.read_text(encoding="utf-8", errors="replace")
                ext = p.suffix.lower()
                lang_map = {".py": "Python", ".js": "JavaScript", ".html": "HTML", ".css": "CSS", ".sql": "SQL"}
                lang = lang_map.get(ext, "Plain Text")
                self._clear_checkpoint()
                self.panel_editor.set_code(content, p.name, lang)
                self._update_estimated_time()
                logger.info("SYSTEM", f"Opened file: {p.name}")
            except Exception as e:
                messagebox.showerror("File Error", f"Could not read file: {e}", parent=self)

    def _handle_save_file(self):
        """Save editor code to file."""
        file_path = filedialog.asksaveasfilename(
            title="Save Script File",
            initialfile=self.panel_editor.current_filename,
            filetypes=[
                ("Python Files", "*.py"),
                ("JavaScript Files", "*.js"),
                ("Text Files", "*.txt"),
                ("All Files", "*.*")
            ],
            parent=self
        )
        if file_path:
            p = Path(file_path)
            try:
                p.write_text(self.panel_editor.get_code(), encoding="utf-8")
                self.panel_editor.current_filename = p.name
                self.panel_editor.lbl_tab.configure(text=f"📄 {p.name}")
                logger.info("SYSTEM", f"Saved file: {p.name}")
            except Exception as e:
                messagebox.showerror("File Error", f"Could not save file: {e}", parent=self)

    def _handle_calc_time(self):
        """Show full estimated time breakdown dialog."""
        self.panel_editor.calculate_estimated_time(show_dialog=True)

    def _on_editor_code_changed(self, code: str):
        """Update line counts and estimated time when editor text is edited."""
        if not hasattr(self, "panel_editor"):
            return
        self._update_estimated_time()

    def _on_speed_changed(self, _val: str):
        """Update estimates and editor target config when speed changes."""
        if not hasattr(self, "panel_editor"):
            return
        speed_cps = self._get_current_speed_cps()
        self.panel_editor._speed_cps = speed_cps
        self._update_estimated_time()

    def _on_mode_changed(self, mode_val: str):
        """Update typing difficulty mode and recalculate estimated time."""
        is_diff = (mode_val == "Difficulty-Based")
        if hasattr(self, "panel_editor"):
            self.panel_editor._use_difficulty = is_diff
        self._update_estimated_time()
        logger.info("UI", f"Typing mode set to: {mode_val}")

    def _on_mouse_move_toggled(self):
        """Compatibility hook for mouse move toggle."""
        if not hasattr(self, "panel_editor"):
            return
        self.panel_editor._line_mouse_enabled = True
        self._update_estimated_time()

    def _update_estimated_time(self):
        """Recalculate and update the estimated time badge and status bar stats."""
        if not hasattr(self, "panel_editor"):
            return
        code = self.panel_editor.get_code()
        chars = len(code)
        newlines = code.count("\n")
        lines = newlines + 1 if code else 0
        speed_cps = self._get_current_speed_cps()
        is_difficulty = getattr(self, "opt_mode", None) is None or self.opt_mode.get() == "Difficulty-Based"

        self.panel_editor._speed_cps = speed_cps
        self.panel_editor._line_mouse_enabled = True
        self.panel_editor._use_difficulty = is_difficulty

        from automation.timing_controller import timing_controller
        _, est_time_str = timing_controller.calculate_sequence_estimate(
            text=code,
            cps=speed_cps,
            countdown_seconds=3,
            mouse_move_enabled=True,
            use_difficulty=is_difficulty,
            random_pause_enabled=getattr(self, "_random_pause_enabled", False)
        )
        self.btn_est_time.configure(text=f"⏱ Est. Time: {est_time_str}")

        if executor.get_state() in (ExecutionState.IDLE, ExecutionState.STOPPED):
            self.lbl_sb_lines.configure(text=f"Line: 1 / {max(1, lines)}")
            self.lbl_sb_progress.configure(text=f"Progress: 0.0% (0 / {chars} chars)")
            self.lbl_sb_time.configure(text=f"Est. Total: {est_time_str} • Elapsed: 00:00:00")

    # =========================================================================
    # 7. HOTKEYS (F5–F10 + GLOBAL/WINDOW HOOKS)
    # =========================================================================

    def _register_global_hotkeys(self):
        """Register low-level global hotkeys that ignore injected events and do not conflict with VS Code."""
        bindings = [
            ("f5", lambda: self._queue_command("start")),
            ("f6", lambda: self._queue_command("pause")),
            ("f7", lambda: self._queue_command("resume")),
            ("f8", lambda: self._queue_command("stop")),
            ("f9", lambda: self._queue_command("save")),
            ("f10", lambda: self._queue_command("checkpoint")),
            (
                self.config_data.get("safety", {}).get("emergency_hotkey", "ctrl+alt+esc"),
                safety.trigger_emergency_stop
            )
        ]
        self.hotkey_manager.configure(bindings)

    def _bind_local_hotkeys(self):
        """Bind window-level hotkeys for when DeskPilot has focus."""
        self.bind("<F5>", lambda _e: self._handle_start_automation())
        self.bind("<F6>", lambda _e: self._handle_pause_automation())
        self.bind("<F7>", lambda _e: self._handle_resume_automation())
        self.bind("<F8>", lambda _e: self._handle_stop_automation())
        self.bind("<F9>", lambda _e: self._handle_save_file())
        self.bind("<F10>", lambda _e: self._handle_checkpoint())

    def _queue_command(self, cmd: str):
        self._ui_actions.put(cmd)

    def _drain_ui_actions(self):
        """Process queued thread-safe UI actions."""
        while True:
            try:
                action = self._ui_actions.get_nowait()
            except queue.Empty:
                break
            try:
                if action == "start":
                    self._handle_start_automation()
                elif action == "pause":
                    self._handle_pause_automation()
                elif action == "resume":
                    self._handle_resume_automation()
                elif action == "stop":
                    self._handle_stop_automation()
                elif action == "save":
                    self._handle_save_file()
                elif action == "checkpoint":
                    self._handle_checkpoint()
                elif callable(action):
                    action()
            except Exception as exc:
                logger.error_detailed("UI", f"Queued UI action failed: {exc}", error_type=type(exc).__name__)

        if not self._closing and self.winfo_exists():
            self._ui_drain_after_id = self.after(30, self._drain_ui_actions)

    # =========================================================================
    # 8. BACKWARD-COMPATIBILITY METHODS (UNIT TEST COMPATIBILITY)
    # =========================================================================

    def _format_hotkey_hint(self) -> str:
        """Format active hotkey bindings string for test compatibility."""
        hotkeys = self.config_data.get("hotkeys", {})
        actions = [
            ("start", "Start", "f5"),
            ("pause", "Pause", "f6"),
            ("resume", "Resume", "f7"),
            ("stop", "Stop", "f8")
        ]
        chords = [
            (str(hotkeys.get(key, default)).upper().split("+"), label)
            for key, label, default in actions
        ]
        shared_prefix = [parts[:-1] for parts, _ in chords]
        if all(prefix == shared_prefix[0] for prefix in shared_prefix) and shared_prefix[0]:
            prefix = "+".join(shared_prefix[0])
            bindings = " • ".join(
                f"{parts[-1]} {label}" for parts, label in chords
            )
            return f"Hotkeys: {prefix}+{bindings}"
        return "Hotkeys: " + " • ".join(
            f"{'+'.join(parts)} {label}" for parts, label in chords
        )

    def _save_workspace_sizes(self, _event=None):
        """Persist layout sizing if panes exist (compatibility with test suite)."""
        if not hasattr(self, "workspace_panes"):
            return
        if _event is not None and _event.widget is not self.workspace_panes:
            return
        try:
            explorer_width = self.panel_explorer.winfo_width()
            quickinput_width = self.workspace_quickinput.winfo_width()
            if explorer_width <= 1 or quickinput_width <= 1:
                return
            config_data = load_config()
            config_data.setdefault("layout", {}).update({
                "explorer_width": explorer_width,
                "quickinput_width": quickinput_width
            })
            save_config(config_data)
        except Exception:
            pass

    def _run_input_task(self, label: str, operation: Callable[[], Any]):
        """Run single input operation in background worker (compatibility)."""
        def worker():
            try:
                succeeded = operation()
            except Exception as exc:
                logger.error_detailed("INPUT", f"{label} failed: {exc}", error_type=type(exc).__name__)
                return
            message = f"{label} {'completed' if succeeded else 'failed'}"
            self._ui_actions.put(lambda: self.lbl_sb_status.configure(text=message))

        threading.Thread(target=worker, daemon=True, name="DeskPilot-QuickInput").start()

    def _handle_quick_key(self):
        """Handle quick keyboard send (compatibility)."""
        if executor.get_state() in (
            ExecutionState.RUNNING,
            ExecutionState.COUNTDOWN,
            ExecutionState.PAUSED
        ):
            if hasattr(self, "lbl_sb_status"):
                self.lbl_sb_status.configure(
                    text="Quick keyboard shortcuts are disabled during automation."
                )
            return
        if not hasattr(self, "ent_quick_key"):
            return
        keys = self.ent_quick_key.get().strip()
        if not keys:
            return
        if "+" in keys:
            operation = lambda: keyboard_ctrl.press_hotkey(keys)
        else:
            operation = lambda: keyboard_ctrl.press_key(keys)
        self._run_input_task(f"Keyboard {keys.upper()}", operation)

    # =========================================================================
    # 9. SHUTDOWN & CLEANUP
    # =========================================================================

    def _on_close(self):
        """Clean shutdown releasing hotkeys, workers, and hardware states."""
        self._closing = True
        after_id = getattr(self, "_ui_drain_after_id", None)
        if after_id:
            try:
                self.after_cancel(after_id)
            except tk.TclError:
                pass
        try:
            self.hotkey_manager.unregister()
            executor.stop()
            executor.wait_for_idle(timeout=2.0)
            safety.reset_hardware_state()
            if not input_dispatcher.shutdown(timeout=2.0):
                logger.warning("SYSTEM", "Input dispatcher did not stop before UI shutdown.")
        except Exception as e:
            logger.error_detailed("SYSTEM", f"Shutdown error: {e}", error_type=type(e).__name__)
        self.destroy()


def main():
    app = DeskPilotApp()
    app.mainloop()


if __name__ == "__main__":
    main()
