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

# Core IDE Editor & Dialogs
from ui.ide_editor import IDECodeEditor
from ui.settings_dialog import SettingsDialog


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
        self._cached_est_remaining: str = "00:00:00"
        self._last_estimate_calc_time: float = 0.0

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

        # UI action pump (60 FPS smooth responsive polling)
        self._ui_drain_after_id = self.after(16, self._drain_ui_actions)

        # Clean shutdown protocol
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        logger.info("SYSTEM", f"DeskPilot v{APP_VERSION} initialized. Default typing speed: 3 chars/sec.")

    # =========================================================================
    # 1. TOP TOOLBAR WITH FLEX WRAP
    # =========================================================================

    def _is_difficulty_mode(self) -> bool:
        """Check if character difficulty-based typing mode is selected."""
        if not hasattr(self, "opt_mode") or self.opt_mode is None:
            return True
        mode_str = str(self.opt_mode.get()).lower()
        return "diff" in mode_str

    def _create_top_toolbar(self):
        """Build the streamlined, flex-wrapping top toolbar with zero-lag controls."""
        self.toolbar = ctk.CTkFrame(
            self,
            corner_radius=0,
            fg_color="#111319",
            border_width=1,
            border_color="#202330"
        )
        self.toolbar.grid(row=0, column=0, sticky="ew")

        # Decks for true responsive flex-wrapping
        self.brand_deck = ctk.CTkFrame(self.toolbar, fg_color="transparent")
        self.file_deck = ctk.CTkFrame(self.toolbar, fg_color="transparent")
        self.checkpoint_deck = ctk.CTkFrame(self.toolbar, fg_color="transparent")
        self.exec_deck = ctk.CTkFrame(self.toolbar, fg_color="transparent")
        self.util_deck = ctk.CTkFrame(self.toolbar, fg_color="transparent")
        self.selectors_deck = ctk.CTkFrame(self.toolbar, fg_color="transparent")
        self.right_deck = self.selectors_deck  # Full backward compatibility

        # --- 1. Brand Deck ---
        lbl_logo = ctk.CTkLabel(
            self.brand_deck,
            text="⚡ DeskPilot",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#f8fafc"
        )
        lbl_logo.pack(side="left", padx=(4, 6), pady=4)

        # --- 2. File Deck ---
        self.btn_new = ctk.CTkButton(
            self.file_deck,
            text="📄 New",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            fg_color="#1e2230",
            hover_color="#2d3348",
            text_color="#e2e8f0",
            cursor="hand2",
            width=44,
            height=26,
            corner_radius=4,
            command=self._handle_new_file
        )
        self.btn_new.pack(side="left", padx=1)

        self.btn_open = ctk.CTkButton(
            self.file_deck,
            text="📂 Open",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            fg_color="#1e2230",
            hover_color="#2d3348",
            text_color="#e2e8f0",
            cursor="hand2",
            width=46,
            height=26,
            corner_radius=4,
            command=self._handle_open_file
        )
        self.btn_open.pack(side="left", padx=1)

        self.btn_save = ctk.CTkButton(
            self.file_deck,
            text="💾 Save",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            fg_color="#1e2230",
            hover_color="#2d3348",
            text_color="#e2e8f0",
            cursor="hand2",
            width=46,
            height=26,
            corner_radius=4,
            command=self._handle_save_file
        )
        self.btn_save.pack(side="left", padx=1)

        # --- 3. Checkpoint & Estimate Deck ---
        self.btn_checkpoint = ctk.CTkButton(
            self.checkpoint_deck,
            text="🔖 Mark",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color="#1e293b",
            hover_color="#334155",
            text_color="#cbd5e1",
            cursor="hand2",
            width=60,
            height=26,
            corner_radius=4,
            command=self._handle_checkpoint
        )
        self.btn_checkpoint.pack(side="left", padx=(1, 0))

        self.btn_clear_checkpoint = ctk.CTkButton(
            self.checkpoint_deck,
            text="✖",
            font=ctk.CTkFont(size=9, weight="bold"),
            fg_color="#7f1d1d",
            hover_color="#991b1b",
            text_color="#fca5a5",
            cursor="hand2",
            width=18,
            height=26,
            corner_radius=3,
            command=self._clear_checkpoint
        )

        self.btn_est_time = ctk.CTkButton(
            self.checkpoint_deck,
            text="⏱ 00:00:00",
            font=ctk.CTkFont(family="Consolas", size=10, weight="bold"),
            fg_color="#064e3b",
            hover_color="#047857",
            text_color="#34d399",
            cursor="hand2",
            width=74,
            height=26,
            corner_radius=4,
            command=self._handle_calc_time
        )
        self.btn_est_time.pack(side="left", padx=1)

        # --- 4. Execution Deck ---
        self.btn_start = ctk.CTkButton(
            self.exec_deck,
            text="▶ Start",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            width=54,
            height=26,
            fg_color="#059669",
            hover_color="#10b981",
            cursor="hand2",
            corner_radius=4,
            command=self._handle_start_automation
        )
        self.btn_start.pack(side="left", padx=1)

        self.btn_pause = ctk.CTkButton(
            self.exec_deck,
            text="⏸ Pause",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            width=54,
            height=26,
            fg_color="#b45309",
            hover_color="#d97706",
            cursor="hand2",
            state="disabled",
            corner_radius=4,
            command=self._handle_pause_automation
        )
        self.btn_pause.pack(side="left", padx=1)

        self.btn_resume = ctk.CTkButton(
            self.exec_deck,
            text="⏯ Resume",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            width=58,
            height=26,
            fg_color="#1d4ed8",
            hover_color="#2563eb",
            cursor="hand2",
            state="disabled",
            corner_radius=4,
            command=self._handle_resume_automation
        )
        self.btn_resume.pack(side="left", padx=1)

        self.btn_stop = ctk.CTkButton(
            self.exec_deck,
            text="⏹ Stop",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            width=50,
            height=26,
            fg_color="#374151",
            hover_color="#b91c1c",
            cursor="hand2",
            state="disabled",
            corner_radius=4,
            command=self._handle_stop_automation
        )
        self.btn_stop.pack(side="left", padx=1)

        # --- 5. Utilities Deck ---
        self.btn_rest_pause = ctk.CTkButton(
            self.util_deck,
            text="☕ Rest: ON" if self._random_pause_enabled else "☕ Rest: OFF",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            width=68,
            height=26,
            fg_color="#065f46" if self._random_pause_enabled else "#1f2937",
            hover_color="#047857" if self._random_pause_enabled else "#374151",
            text_color="#6ee7b7" if self._random_pause_enabled else "#9ca3af",
            cursor="hand2",
            corner_radius=4,
            command=self._handle_toggle_rest_pause
        )
        self.btn_rest_pause.pack(side="left", padx=1)

        self.btn_settings = ctk.CTkButton(
            self.util_deck,
            text="⚙️ Settings",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            width=68,
            height=26,
            fg_color="#1e2230",
            hover_color="#2d3348",
            text_color="#e2e8f0",
            cursor="hand2",
            corner_radius=4,
            command=self._handle_open_settings
        )
        self.btn_settings.pack(side="left", padx=1)

        # --- 6. Selectors Deck ---
        ctk.CTkLabel(self.selectors_deck, text="Target:", font=ctk.CTkFont(size=10), text_color="#94a3b8").pack(side="left", padx=(2, 1))
        self.opt_target = ctk.CTkOptionMenu(
            self.selectors_deck,
            values=["VS Code", "Notepad", "Active Win"],
            width=84,
            height=26,
            font=ctk.CTkFont(size=10)
        )
        self.opt_target.set("VS Code")
        self.opt_target.pack(side="left", padx=(1, 4))

        ctk.CTkLabel(self.selectors_deck, text="Mode:", font=ctk.CTkFont(size=10), text_color="#94a3b8").pack(side="left", padx=(2, 1))
        self.opt_mode = ctk.CTkOptionMenu(
            self.selectors_deck,
            values=["Difficulty", "Fixed CPS"],
            width=88,
            height=26,
            font=ctk.CTkFont(size=10),
            command=self._on_mode_changed
        )
        cfg_mode = str(self.config_data.get("typing", {}).get("timing_mode", "difficulty")).lower()
        init_mode = "Fixed CPS" if cfg_mode == "fixed" else "Difficulty"
        self.opt_mode.set(init_mode)
        self.opt_mode.pack(side="left", padx=(1, 4))

        ctk.CTkLabel(self.selectors_deck, text="Speed:", font=ctk.CTkFont(size=10), text_color="#94a3b8").pack(side="left", padx=(2, 1))
        self.opt_speed = ctk.CTkOptionMenu(
            self.selectors_deck,
            values=["3 CPS", "1 CPS", "1.5 CPS", "2 CPS", "2.5 CPS", "3.5 CPS", "5 CPS", "Custom..."],
            width=68,
            height=26,
            font=ctk.CTkFont(size=10),
            command=self._on_speed_changed
        )
        curr_speed = float(self.config_data.get("typing", {}).get("speed_cps", 3.0))
        speed_txt = f"{int(curr_speed)} CPS" if curr_speed.is_integer() else f"{curr_speed:.1f} CPS"
        curr_vals = list(self.opt_speed.cget("values"))
        if speed_txt not in curr_vals:
            curr_vals.insert(0, speed_txt)
            self.opt_speed.configure(values=curr_vals)
        self.opt_speed.set(speed_txt)
        self.opt_speed.pack(side="left", padx=(1, 2))

        # Initial responsive reflow and window configure listener
        self._navbar_reflow_timer = None
        self._reflow_navbar()
        self.bind("<Configure>", self._on_window_configure)

    def _on_window_configure(self, event):
        """Debounced window configure event to trigger responsive navbar flex wrapping."""
        if event.widget == self:
            if self._navbar_reflow_timer:
                self.after_cancel(self._navbar_reflow_timer)
            self._navbar_reflow_timer = self.after(30, self._reflow_navbar)

    def _reflow_navbar(self, event=None):
        """Flex-wrap toolbar decks into rows dynamically based on available width."""
        if not hasattr(self, "toolbar") or not self.toolbar.winfo_exists():
            return
        w = self.winfo_width()
        if w <= 10:
            w = 1180

        decks = [
            self.brand_deck,
            self.file_deck,
            self.checkpoint_deck,
            self.exec_deck,
            self.util_deck,
            self.selectors_deck
        ]

        for d in decks:
            d.grid_forget()

        row = 0
        col = 0
        cur_w = 0
        for d in decks:
            dw = d.winfo_reqwidth() + 6
            if cur_w + dw > (w - 16) and cur_w > 0:
                row += 1
                col = 0
                cur_w = 0
            d.grid(row=row, column=col, padx=(2, 4), pady=2, sticky="w")
            col += 1
            cur_w += dw

        num_rows = row + 1
        new_h = max(42, num_rows * 36 + 6)
        self.toolbar.configure(height=new_h)

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
            rem_str = getattr(self, "_cached_est_remaining", "00:00:00")
            self._ui_actions.put(lambda: (
                self.lbl_sb_status.configure(
                    text=f"● Countdown: {secs}s (Switch to target window)",
                    text_color="#f59e0b"
                ),
                self.lbl_sb_time.configure(
                    text=f"Est. Remaining: {rem_str} • Elapsed: 00:00:00"
                )
            ))

        def on_progress(current_step, total_steps, pct):
            pass

        def on_typing_telemetry(tel):
            if isinstance(tel, dict):
                idx = tel.get("index", 0)
                tot = tel.get("total", getattr(self, "_cached_total_chars", 1))
                ln = tel.get("line", 1)
                col = tel.get("col", 1)
                ch = tel.get("char", "")
                pct = tel.get("pct", 0.0)

                self._last_typed_index = idx
                self._last_typed_line = ln

                # Ultra-fast O(1) remaining time calculation - zero cross-thread GUI calls
                tot_chars = getattr(self, "_cached_total_chars", tot)
                tot_seconds = getattr(self, "_cached_total_seconds", 0)
                remaining_fraction = max(0.0, 1.0 - (idx / max(1, tot_chars)))
                rem_seconds = int(tot_seconds * remaining_fraction)
                rem_h = rem_seconds // 3600
                rem_m = (rem_seconds % 3600) // 60
                rem_s = rem_seconds % 60
                rem_str = f"{rem_h:02d}:{rem_m:02d}:{rem_s:02d}"

                # Calculate elapsed time
                elapsed_sec = int(max(0, time.monotonic() - getattr(self, "_typing_start_time", time.monotonic())))
                el_h = elapsed_sec // 3600
                el_m = (elapsed_sec % 3600) // 60
                el_s = elapsed_sec % 60
                el_str = f"{el_h:02d}:{el_m:02d}:{el_s:02d}"

                cat = tel.get("category", "")
                self._ui_actions.put(lambda: self._update_live_telemetry(ln, idx, tot, pct, rem_str, el_str, ch, col, cat))

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

    def _update_live_telemetry(self, line: int, char_idx: int, total_chars: int, pct: float, rem_time: str, el_time: str, ch: str, col: int, cat: str = ""):
        """Update live status bar numbers, character difficulty HUD, and editor pointer."""
        tot_lines = getattr(self, "_cached_total_lines", 0)
        if tot_lines <= 0:
            tot_lines = self.panel_editor.get_code().count("\n") + 1
        self.lbl_sb_lines.configure(text=f"Line: {line} / {tot_lines}")
        self.lbl_sb_progress.configure(text=f"Progress: {pct:.1f}% ({char_idx} / {total_chars} chars)")
        self.lbl_sb_time.configure(text=f"Est. Remaining: {rem_time} • Elapsed: {el_time}")
        if self._is_difficulty_mode() and cat and executor.get_state() == ExecutionState.RUNNING:
            disp_c = repr(ch)[1:-1] if ch else ""
            self.lbl_sb_status.configure(text=f"● Typing '{disp_c}' [{cat}]", text_color="#38bdf8")
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
            if self.config_data.get("safety", {}).get("beep_on_countdown", True):
                threading.Thread(target=self._play_chime, args=("rest",), daemon=True).start()

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
                if self.config_data.get("safety", {}).get("beep_on_countdown", True):
                    threading.Thread(target=self._play_chime, args=("complete",), daemon=True).start()
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
        """Parse typing speed in characters per second from toolbar selector."""
        try:
            val = float(self.opt_speed.get().split()[0])
            return max(0.2, val)
        except Exception:
            return float(self.config_data.get("typing", {}).get("speed_cps", 3.0))

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
        countdown = 3

        # Prepare sequential task list (direct typing, no invasive window manipulation)
        tasks = []

        # Checkpoint resume logic
        start_char_idx = 0
        if self.checkpoint_char_index is not None and self.checkpoint_char_index > 0:
            start_char_idx = self.checkpoint_char_index
            logger.info("SYSTEM", f"Resuming automation from checkpoint at char {start_char_idx} (Line {self.checkpoint_line}).")

        # Code typing task (strictly character typing only, natural mouse after every line)
        is_difficulty = self._is_difficulty_mode()
        rp_cfg = self.config_data.get("random_pause", {})
        rp_work_min = float(rp_cfg.get("work_min_minutes", 20.0))
        rp_work_max = float(rp_cfg.get("work_max_minutes", 25.0))
        rp_brk_min = float(rp_cfg.get("break_min_minutes", 3.0))
        rp_brk_max = float(rp_cfg.get("break_max_minutes", 5.0))
        rp_min_l = int(rp_cfg.get("min_interval_lines", 15))
        rp_max_l = int(rp_cfg.get("max_interval_lines", 30))
        rp_min_s = int(round(rp_brk_min * 60))
        rp_max_s = max(rp_min_s, int(round(rp_brk_max * 60)))

        mouse_cfg = self.config_data.get("mouse", {})
        line_mouse_cfg = mouse_cfg.get("line_interaction", {})
        m_enabled = bool(line_mouse_cfg.get("enabled", True))
        m_min_l = int(line_mouse_cfg.get("min_lines", 2))
        m_max_l = int(line_mouse_cfg.get("max_lines", 5))

        tasks.append({
            "type": "type_code",
            "text": code,
            "_resume_char_index": start_char_idx,
            "speed": 1.0 / speed_cps,
            "timing_mode": "difficulty" if is_difficulty else "fixed",
            "use_difficulty": is_difficulty,
            "exact_speed": not is_difficulty,
            "tab_width": getattr(self.panel_editor, "indent_width", 4),
            "line_mouse_enabled": m_enabled,
            "every_line": False,
            "min_lines": m_min_l,
            "max_lines": m_max_l,
            "natural_line_mouse": True,
            "random_pause_enabled": self._random_pause_enabled,
            "work_min_minutes": rp_work_min,
            "work_max_minutes": rp_work_max,
            "break_min_minutes": rp_brk_min,
            "break_max_minutes": rp_brk_max,
            "random_pause_min_lines": rp_min_l,
            "random_pause_max_lines": rp_max_l,
            "random_pause_min_seconds": rp_min_s,
            "random_pause_max_seconds": rp_max_s,
            "smart_indent": False,
            "target_window": target_app,
            "description": f"Type code ({'Difficulty-Based' if is_difficulty else 'Fixed CPS'} at {speed_cps:.1f} CPS, {len(code)} chars)"
        })

        self._typing_start_time = time.monotonic()
        self._last_typed_index = start_char_idx
        self._last_typed_line = self.checkpoint_line or 1

        # Calculate and show remaining time immediately at working start
        from automation.timing_controller import timing_controller
        remaining_code = code[start_char_idx:]
        tot_chars = len(code)
        tot_lines = code.count("\n") + 1
        curr_line = self.checkpoint_line or 1
        self._cached_total_lines = tot_lines

        tot_secs, est_str = timing_controller.calculate_sequence_estimate(
            text=remaining_code,
            cps=speed_cps,
            countdown_seconds=countdown,
            mouse_move_enabled=m_enabled,
            use_difficulty=is_difficulty,
            random_pause_enabled=self._random_pause_enabled,
            work_interval_minutes=(rp_work_min, rp_work_max),
            break_duration_minutes=(rp_brk_min, rp_brk_max),
            rest_interval_lines=(rp_min_l, rp_max_l),
            rest_duration_seconds=(rp_min_s, rp_max_s)
        )
        self._cached_est_remaining = est_str
        self._last_estimate_calc_time = time.monotonic()
        self._cached_total_chars = tot_chars
        self._cached_total_seconds = tot_secs

        # Display remaining time immediately at working start
        self.lbl_sb_time.configure(text=f"Est. Remaining: {est_str} • Elapsed: 00:00:00")
        self.lbl_sb_lines.configure(text=f"Line: {curr_line} / {tot_lines}")
        self.lbl_sb_progress.configure(text=f"Progress: 0.0% ({start_char_idx} / {tot_chars} chars)")

        # Instant visual feedback on Start button
        self._update_ui_state(ExecutionState.COUNTDOWN if countdown > 0 else ExecutionState.RUNNING)
        self.update_idletasks()

        logger.info("SYSTEM", f"Starting code typing automation targeting '{target_app}' at {speed_cps:.1f} CPS.")
        if not executor.start(tasks, countdown_seconds=countdown, loop=False):
            logger.warning("SYSTEM", "Execution worker already active; start rejected.")

    def _handle_pause_automation(self):
        """Temporarily pause typing at the current character boundary with instant feedback."""
        self.btn_pause.configure(state="disabled", fg_color="#374151")
        self.btn_resume.configure(state="normal", text="⏯ Resume", fg_color="#2563eb")
        self.lbl_sb_status.configure(
            text=f"● Automation Paused at Line {self._last_typed_line}",
            text_color="#fbbf24"
        )
        self.update_idletasks()
        executor.pause()

    def _handle_resume_automation(self):
        """Resume typing from the exact paused character position or skip rest pause with instant feedback."""
        self.btn_resume.configure(state="disabled", text="⏯ Resume", fg_color="#1e3a8a")
        self.btn_pause.configure(state="normal", fg_color="#b45309")
        self.lbl_sb_status.configure(text="● Typing...", text_color="#38bdf8")
        self.update_idletasks()
        if executor.get_state() == ExecutionState.REST_PAUSED:
            executor.skip_rest_pause()
        else:
            executor.resume()

    def _handle_toggle_rest_pause(self):
        """Toggle random rest pause on or off with instant UI update."""
        self._random_pause_enabled = not self._random_pause_enabled
        if self._random_pause_enabled:
            self.btn_rest_pause.configure(
                text="☕ Rest: ON",
                fg_color="#065f46",
                hover_color="#047857",
                text_color="#6ee7b7"
            )
            logger.info("SYSTEM", "Random Rest Pause enabled (human breaks between random line intervals).")
        else:
            self.btn_rest_pause.configure(
                text="☕ Rest: OFF",
                fg_color="#1f2937",
                hover_color="#374151",
                text_color="#9ca3af"
            )
            logger.info("SYSTEM", "Random Rest Pause disabled.")
        self.update_idletasks()
        self._update_estimated_time()

    def _handle_stop_automation(self):
        """Cancel automation and release all held hardware keys/buttons with instant feedback."""
        self._update_ui_state(ExecutionState.STOPPED)
        self.update_idletasks()
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

        # Update toolbar button concisely
        self.btn_checkpoint.configure(
            text=f"🔖 Mark: L{self.checkpoint_line}",
            fg_color="#312e81",
            hover_color="#3730a3",
            text_color="#c7d2fe"
        )
        self.btn_clear_checkpoint.pack(side="left", padx=(2, 0))

        self.lbl_sb_status.configure(
            text=f"● Checkpoint set at Line {self.checkpoint_line} (Char {self.checkpoint_char_index})",
            text_color="#a5b4fc"
        )
        self.update_idletasks()
        logger.info("SYSTEM", f"Checkpoint set at line {self.checkpoint_line}, character {self.checkpoint_char_index}.")

    def _clear_checkpoint(self):
        """Clear active checkpoint and reset Mark button to beginning."""
        self.checkpoint_char_index = None
        self.checkpoint_line = None
        self.btn_checkpoint.configure(
            text="🔖 Mark",
            fg_color="#1e293b",
            hover_color="#334155",
            text_color="#cbd5e1"
        )
        self.btn_clear_checkpoint.pack_forget()
        self.lbl_sb_status.configure(text="● Checkpoint cleared", text_color="#94a3b8")
        self.update_idletasks()
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

    def _handle_open_settings(self):
        """Open the modern Preferences & Settings dialog (Ctrl+,)."""
        SettingsDialog(self, on_save_callback=self._on_settings_saved)

    def _on_settings_saved(self, new_config: dict):
        """Callback when settings are saved in SettingsDialog."""
        self.config_data = new_config
        self._random_pause_enabled = bool(new_config.get("random_pause", {}).get("enabled", True))
        if self._random_pause_enabled:
            self.btn_rest_pause.configure(
                text="☕ Rest: ON",
                fg_color="#065f46",
                hover_color="#047857",
                text_color="#6ee7b7"
            )
        else:
            self.btn_rest_pause.configure(
                text="☕ Rest: OFF",
                fg_color="#1f2937",
                hover_color="#374151",
                text_color="#9ca3af"
            )

        # Update speed optionmenu
        speed_val = float(new_config.get("typing", {}).get("speed_cps", 3.0))
        speed_txt = f"{int(speed_val)} CPS" if speed_val.is_integer() else f"{speed_val:.1f} CPS"
        curr_vals = list(self.opt_speed.cget("values"))
        if speed_txt not in curr_vals:
            curr_vals.insert(0, speed_txt)
            self.opt_speed.configure(values=curr_vals)
        self.opt_speed.set(speed_txt)

        # Update mode optionmenu
        mode_val = str(new_config.get("typing", {}).get("timing_mode", "difficulty")).lower()
        self.opt_mode.set("Difficulty" if "diff" in mode_val else "Fixed CPS")

        # Update editor indent
        indent_val = int(new_config.get("editor", {}).get("indent_width", 4))
        self.panel_editor.indent_width = indent_val
        if hasattr(self.panel_editor, "lbl_encoding"):
            self.panel_editor.lbl_encoding.configure(text=f"UTF-8 • Spaces: {indent_val}")

        # Update failsafe
        safety.set_failsafe(bool(new_config.get("safety", {}).get("failsafe", True)))

        self._update_estimated_time()
        logger.info("SETTINGS", f"Applied updated settings: Speed {speed_val} CPS, Rest Pause {'ON' if self._random_pause_enabled else 'OFF'}.")

    def _play_chime(self, chime_type: str = "complete"):
        """Play non-blocking Windows notification chime."""
        try:
            import winsound
            if chime_type == "complete":
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            else:
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except Exception:
            pass

    def _on_speed_changed(self, val: str):
        """Update estimates and editor target config when speed changes."""
        if val == "Custom...":
            from tkinter import simpledialog
            try:
                curr = self._get_current_speed_cps()
                custom_val = simpledialog.askfloat(
                    "Custom Typing Speed",
                    "Enter custom typing speed in Characters Per Second (CPS):\n(e.g., 1.8, 3.2, 5.0)",
                    initialvalue=curr,
                    minvalue=0.2,
                    maxvalue=20.0,
                    parent=self
                )
                if custom_val is not None:
                    txt = f"{int(custom_val)} CPS" if custom_val.is_integer() else f"{custom_val:.1f} CPS"
                    curr_vals = list(self.opt_speed.cget("values"))
                    if txt not in curr_vals:
                        curr_vals.insert(0, txt)
                        self.opt_speed.configure(values=curr_vals)
                    self.opt_speed.set(txt)
                    self.config_data.setdefault("typing", {})["speed_cps"] = custom_val
                    save_config(self.config_data)
                else:
                    curr_speed = float(self.config_data.get("typing", {}).get("speed_cps", 3.0))
                    self.opt_speed.set(f"{curr_speed:.1f} CPS")
            except Exception:
                pass
        else:
            try:
                cps = float(val.split()[0])
                self.config_data.setdefault("typing", {})["speed_cps"] = cps
                save_config(self.config_data)
            except Exception:
                pass

        if not hasattr(self, "panel_editor"):
            return
        speed_cps = self._get_current_speed_cps()
        self.panel_editor._speed_cps = speed_cps
        self._update_estimated_time()

    def _on_mode_changed(self, mode_val: str):
        """Update typing difficulty mode and recalculate estimated time."""
        is_diff = self._is_difficulty_mode()
        if hasattr(self, "panel_editor"):
            self.panel_editor._use_difficulty = is_diff
        self._update_estimated_time()
        logger.info("UI", f"Typing mode set to: {'Difficulty-Based' if is_diff else 'Fixed CPS'}")

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
        is_difficulty = self._is_difficulty_mode()

        self.panel_editor._speed_cps = speed_cps
        self.panel_editor._line_mouse_enabled = True
        self.panel_editor._use_difficulty = is_difficulty

        rp_cfg = self.config_data.get("random_pause", {})
        rp_work_min = float(rp_cfg.get("work_min_minutes", 20.0))
        rp_work_max = float(rp_cfg.get("work_max_minutes", 25.0))
        rp_brk_min = float(rp_cfg.get("break_min_minutes", 3.0))
        rp_brk_max = float(rp_cfg.get("break_max_minutes", 5.0))
        rest_interval = (int(rp_cfg.get("min_interval_lines", 15)), int(rp_cfg.get("max_interval_lines", 30)))
        rest_duration = (int(rp_cfg.get("min_duration_seconds", 180)), int(rp_cfg.get("max_duration_seconds", 360)))

        from automation.timing_controller import timing_controller
        _, est_time_str = timing_controller.calculate_sequence_estimate(
            text=code,
            cps=speed_cps,
            countdown_seconds=3,
            mouse_move_enabled=True,
            use_difficulty=is_difficulty,
            random_pause_enabled=getattr(self, "_random_pause_enabled", False),
            work_interval_minutes=(rp_work_min, rp_work_max),
            break_duration_minutes=(rp_brk_min, rp_brk_max),
            rest_interval_lines=rest_interval,
            rest_duration_seconds=rest_duration
        )
        self.btn_est_time.configure(text=f"⏱ {est_time_str}")

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
        self.bind("<Control-comma>", lambda _e: self._handle_open_settings())

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
            self._ui_drain_after_id = self.after(16, self._drain_ui_actions)

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

    def destroy(self):
        self._closing = True
        for timer_attr in ("_ui_drain_after_id", "_navbar_reflow_timer"):
            tid = getattr(self, timer_attr, None)
            if tid:
                try:
                    self.after_cancel(tid)
                except Exception:
                    pass
        super().destroy()

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
