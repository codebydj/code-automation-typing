"""
DeskPilot - Main Dashboard Panel
Displays live system metrics, execution controls, real-time visual mouse radar,
live typing character/line preview, progress indicator, and mini activity stream.
"""

import time
import threading
import customtkinter as ctk
from typing import Callable, Optional, Dict, Any
from automation.sequence_executor import executor, ExecutionState
from automation.mouse_controller import mouse_ctrl
from automation.safety import safety
from automation.notepad_verifier import run_notepad_verification
from ui.cursor_indicator import CursorRadarCanvas, DesktopSpotlight
from utils.logger import logger, LogEntry
from utils.storage import list_saved_sequences, load_sequence_from_file


class DashboardPanel(ctk.CTkFrame):
    """Modern, high-visibility dashboard panel with real-time hardware telemetry."""

    def __init__(self, master, navigate_callback: Optional[Callable[[str], None]] = None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.navigate_callback = navigate_callback
        
        # Grid layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)  # Activity feed expands

        # Build UI components
        self._create_header_banner()
        self._create_controls_bar()
        self._create_metric_cards()
        self._create_activity_feed()

        # Connect callbacks
        self._setup_executor_callbacks()
        logger.add_listener(self._on_log_entry)

        # Polling loop for live mouse coordinates
        self._update_mouse_telemetry()

    def _create_header_banner(self):
        """Top banner with title, subtitle, and dynamic status pill."""
        banner_frame = ctk.CTkFrame(self, fg_color="#181920", corner_radius=10, border_width=1, border_color="#2b2d3c")
        banner_frame.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 12))
        banner_frame.grid_columnconfigure(0, weight=1)

        # Left title section
        title_box = ctk.CTkFrame(banner_frame, fg_color="transparent")
        title_box.grid(row=0, column=0, sticky="w", padx=20, pady=14)

        title_lbl = ctk.CTkLabel(
            title_box,
            text="DeskPilot System Dashboard",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color="#f3f4f6"
        )
        title_lbl.pack(anchor="w")

        subtitle_lbl = ctk.CTkLabel(
            title_box,
            text="Autonomous human-style desktop automation engine • Press ESC anytime to abort",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color="#9ca3af"
        )
        subtitle_lbl.pack(anchor="w", pady=(2, 0))

        # Right status pill
        status_box = ctk.CTkFrame(banner_frame, fg_color="transparent")
        status_box.grid(row=0, column=1, sticky="e", padx=20, pady=14)

        self.status_pill = ctk.CTkLabel(
            status_box,
            text="● SYSTEM IDLE",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color="#10b981",
            fg_color="#064e3b",
            corner_radius=20,
            padx=16,
            pady=6
        )
        self.status_pill.pack()

    def _create_controls_bar(self):
        """Execution control buttons bar: Start, Pause, Resume, Stop, Notepad Test, Emergency Stop."""
        bar = ctk.CTkFrame(self, fg_color="#1f212a", corner_radius=10, border_width=1, border_color="#2b2d3c")
        bar.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 14))

        controls_layout = ctk.CTkFrame(bar, fg_color="transparent")
        controls_layout.pack(fill="x", padx=16, pady=12)

        # Start button
        self.btn_start = ctk.CTkButton(
            controls_layout,
            text="▶ Start Automation",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color="#059669",
            hover_color="#10b981",
            text_color="#ffffff",
            height=38,
            corner_radius=8,
            command=self._handle_start
        )
        self.btn_start.pack(side="left", padx=(0, 6))

        # Pause button
        self.btn_pause = ctk.CTkButton(
            controls_layout,
            text="⏸ Pause",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color="#d97706",
            hover_color="#f59e0b",
            text_color="#ffffff",
            height=38,
            corner_radius=8,
            command=self._handle_pause,
            state="disabled"
        )
        self.btn_pause.pack(side="left", padx=4)

        # Resume button
        self.btn_resume = ctk.CTkButton(
            controls_layout,
            text="⏯ Resume",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color="#2563eb",
            hover_color="#3b82f6",
            text_color="#ffffff",
            height=38,
            corner_radius=8,
            command=self._handle_resume,
            state="disabled"
        )
        self.btn_resume.pack(side="left", padx=4)

        # Stop button
        self.btn_stop = ctk.CTkButton(
            controls_layout,
            text="⏹ Stop",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color="#4b5563",
            hover_color="#6b7280",
            text_color="#ffffff",
            height=38,
            corner_radius=8,
            command=self._handle_stop,
            state="disabled"
        )
        self.btn_stop.pack(side="left", padx=4)

        # Notepad Real Test Button
        self.btn_notepad_test = ctk.CTkButton(
            controls_layout,
            text="🧪 Run Notepad Test Mode",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="#4f46e5",
            hover_color="#6366f1",
            text_color="#ffffff",
            height=38,
            corner_radius=8,
            command=self._handle_notepad_test
        )
        self.btn_notepad_test.pack(side="left", padx=(10, 4))

        # Emergency Stop button (prominent crimson alert style)
        self.btn_emergency = ctk.CTkButton(
            controls_layout,
            text="🛑 EMERGENCY STOP (ESC)",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color="#dc2626",
            hover_color="#ef4444",
            text_color="#ffffff",
            height=38,
            corner_radius=8,
            command=self._handle_emergency_stop
        )
        self.btn_emergency.pack(side="right", padx=(6, 0))

    def _create_metric_cards(self):
        """Four telemetry cards: Visual Mouse Position & Radar, Keyboard Telemetry, Progress, Completed Actions."""
        cards_grid = ctk.CTkFrame(self, fg_color="transparent")
        cards_grid.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 14))
        for col in range(4):
            cards_grid.grid_columnconfigure(col, weight=1, uniform="card")

        # Card 1: Mouse Coordinates & Live Visual Radar
        card_mouse = ctk.CTkFrame(cards_grid, fg_color="#181920", corner_radius=10, border_width=1, border_color="#2b2d3c")
        card_mouse.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=0)
        
        m_hdr = ctk.CTkFrame(card_mouse, fg_color="transparent")
        m_hdr.pack(fill="x", padx=12, pady=(10, 2))
        lbl_m_title = ctk.CTkLabel(m_hdr, text="📍 Mouse Telemetry", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color="#9ca3af")
        lbl_m_title.pack(side="left")

        btn_ping = ctk.CTkButton(
            m_hdr,
            text="Spotlight",
            font=ctk.CTkFont(size=10, weight="bold"),
            width=60,
            height=20,
            fg_color="#2563eb",
            hover_color="#3b82f6",
            command=self._handle_spotlight_ping
        )
        btn_ping.pack(side="right")
        
        self.val_mouse_pos = ctk.CTkLabel(card_mouse, text="X: 0   Y: 0", font=ctk.CTkFont(family="Consolas", size=16, weight="bold"), text_color="#38bdf8")
        self.val_mouse_pos.pack(anchor="w", padx=12, pady=(0, 2))

        # Embedded Visual Cursor Radar Canvas
        self.radar = CursorRadarCanvas(card_mouse, width=210, height=80)
        self.radar.pack(padx=8, pady=(0, 6))

        self.lbl_screen_res = ctk.CTkLabel(card_mouse, text="Screen: 1920x1080 px", font=ctk.CTkFont(family="Segoe UI", size=10), text_color="#6b7280")
        self.lbl_screen_res.pack(anchor="w", padx=12, pady=(0, 8))

        # Card 2: Current Keyboard Action & Live Character Preview
        card_kb = ctk.CTkFrame(cards_grid, fg_color="#181920", corner_radius=10, border_width=1, border_color="#2b2d3c")
        card_kb.grid(row=0, column=1, sticky="nsew", padx=4, pady=0)

        lbl_kb_title = ctk.CTkLabel(card_kb, text="⌨️ Live Typing Stream", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color="#9ca3af")
        lbl_kb_title.pack(anchor="w", padx=12, pady=(10, 2))

        self.val_kb_action = ctk.CTkLabel(card_kb, text="Idle (Keystrokes Ready)", font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), text_color="#a78bfa")
        self.val_kb_action.pack(anchor="w", padx=12, pady=(0, 2))

        # Character / Line Preview Box
        preview_box = ctk.CTkFrame(card_kb, fg_color="#121317", corner_radius=6, border_width=1, border_color="#2b2d3c")
        preview_box.pack(fill="x", padx=10, pady=(2, 6))

        p_row1 = ctk.CTkFrame(preview_box, fg_color="transparent")
        p_row1.pack(fill="x", padx=6, pady=(4, 2))

        ctk.CTkLabel(p_row1, text="Active Char:", font=ctk.CTkFont(size=10), text_color="#9ca3af").pack(side="left")
        self.lbl_active_char = ctk.CTkLabel(p_row1, text="'-'", font=ctk.CTkFont(family="Consolas", size=12, weight="bold"), text_color="#34d399", fg_color="#064e3b", corner_radius=4, padx=6)
        self.lbl_active_char.pack(side="left", padx=4)

        self.lbl_line_col = ctk.CTkLabel(p_row1, text="L: 1  C: 1", font=ctk.CTkFont(family="Consolas", size=10), text_color="#38bdf8")
        self.lbl_line_col.pack(side="right")

        self.lbl_stream_preview = ctk.CTkLabel(
            preview_box,
            text="Waiting for typing stream...",
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color="#9ca3af",
            anchor="w"
        )
        self.lbl_stream_preview.pack(fill="x", padx=6, pady=(0, 4))

        self.lbl_kb_cadence = ctk.CTkLabel(card_kb, text="Cadence: 0 WPM • 0 chars", font=ctk.CTkFont(family="Segoe UI", size=10), text_color="#6b7280")
        self.lbl_kb_cadence.pack(anchor="w", padx=12, pady=(0, 8))

        # Card 3: Execution Progress
        card_prog = ctk.CTkFrame(cards_grid, fg_color="#181920", corner_radius=10, border_width=1, border_color="#2b2d3c")
        card_prog.grid(row=0, column=2, sticky="nsew", padx=4, pady=0)

        lbl_prog_title = ctk.CTkLabel(card_prog, text="📈 Execution Progress", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color="#9ca3af")
        lbl_prog_title.pack(anchor="w", padx=12, pady=(10, 2))

        self.val_progress_text = ctk.CTkLabel(card_prog, text="0 / 0 steps (0%)", font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"), text_color="#34d399")
        self.val_progress_text.pack(anchor="w", padx=12, pady=(0, 4))

        self.progress_bar = ctk.CTkProgressBar(card_prog, height=8, corner_radius=4, progress_color="#10b981", fg_color="#374151")
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=12, pady=(4, 6))

        self.lbl_active_step_desc = ctk.CTkLabel(card_prog, text="Current Step: None", font=ctk.CTkFont(family="Segoe UI", size=10), text_color="#9ca3af", anchor="w")
        self.lbl_active_step_desc.pack(anchor="w", padx=12, pady=(0, 8))

        # Card 4: Total Actions Completed
        card_cnt = ctk.CTkFrame(cards_grid, fg_color="#181920", corner_radius=10, border_width=1, border_color="#2b2d3c")
        card_cnt.grid(row=0, column=3, sticky="nsew", padx=(6, 0), pady=0)

        lbl_cnt_title = ctk.CTkLabel(card_cnt, text="🔢 Actions Completed", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color="#9ca3af")
        lbl_cnt_title.pack(anchor="w", padx=12, pady=(10, 2))

        self.val_total_actions = ctk.CTkLabel(card_cnt, text="0", font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"), text_color="#fbbf24")
        self.val_total_actions.pack(anchor="w", padx=12, pady=(0, 2))

        self.lbl_completed_sub = ctk.CTkLabel(card_cnt, text="Session total executed", font=ctk.CTkFont(family="Segoe UI", size=11), text_color="#6b7280")
        self.lbl_completed_sub.pack(anchor="w", padx=12, pady=(0, 4))

        self.lbl_notepad_metric = ctk.CTkLabel(card_cnt, text="Notepad verification ready", font=ctk.CTkFont(family="Segoe UI", size=10), text_color="#10b981")
        self.lbl_notepad_metric.pack(anchor="w", padx=12, pady=(0, 8))

    def _create_activity_feed(self):
        """Live activity log feed with direct jump to Activity Monitor."""
        feed_container = ctk.CTkFrame(self, fg_color="#181920", corner_radius=10, border_width=1, border_color="#2b2d3c")
        feed_container.grid(row=3, column=0, sticky="nsew", padx=16, pady=(0, 16))
        feed_container.grid_rowconfigure(1, weight=1)
        feed_container.grid_columnconfigure(0, weight=1)

        # Header of activity box
        header_bar = ctk.CTkFrame(feed_container, fg_color="transparent")
        header_bar.grid(row=0, column=0, sticky="ew", padx=16, pady=(10, 6))
        header_bar.grid_columnconfigure(0, weight=1)

        lbl_feed_title = ctk.CTkLabel(
            header_bar,
            text="📜 Real-Time Execution Log Stream",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color="#e5e7eb"
        )
        lbl_feed_title.grid(row=0, column=0, sticky="w")

        btn_view_full = ctk.CTkButton(
            header_bar,
            text="Open Activity Monitor ➔",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#374151",
            hover_color="#4b5563",
            width=150,
            height=26,
            command=lambda: self.navigate_callback("Activity Monitor") if self.navigate_callback else None
        )
        btn_view_full.grid(row=0, column=1, sticky="e")

        # Scrollable textbox for log output
        self.log_textbox = ctk.CTkTextbox(
            feed_container,
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color="#e5e7eb",
            fg_color="#121317",
            corner_radius=6,
            wrap="none"
        )
        self.log_textbox.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 14))
        
        # Populate with existing logs
        for entry in logger.get_history()[-20:]:
            self.log_textbox.insert("end", entry.format_line() + "\n")
        self.log_textbox.see("end")

    def _setup_executor_callbacks(self):
        """Attach sequence executor events to update dashboard UI."""
        executor.on_status_change = self._on_executor_status_change
        executor.on_progress = self._on_executor_progress
        executor.on_action_start = self._on_executor_action_start
        executor.on_keyboard_action = self._on_keyboard_action_update
        executor.on_typing_telemetry = self._on_typing_telemetry_update
        executor.on_countdown = self._on_countdown_update
        executor.on_completed = self._on_completed_update

    def _update_mouse_telemetry(self):
        """Poll mouse coordinates every 50ms for smooth live tracking."""
        try:
            x, y = mouse_ctrl.get_position()
            self.val_mouse_pos.configure(text=f"X: {x:<5} Y: {y:<5}")
            
            if not hasattr(self, "_res_cached"):
                sw, sh = mouse_ctrl.get_screen_size()
                self.lbl_screen_res.configure(text=f"Screen: {sw}x{sh} px")
                self._res_cached = True
        except Exception:
            pass

        self.after(50, self._update_mouse_telemetry)

    def _handle_spotlight_ping(self):
        """Ping current mouse position with desktop spotlight overlay."""
        x, y = mouse_ctrl.get_position()
        DesktopSpotlight.ping(x, y)
        if hasattr(self, "radar"):
            self.radar.ping_target(x, y)

    def _on_log_entry(self, entry: LogEntry):
        """Thread-safe UI callback for incoming log items."""
        def append_log():
            try:
                self.log_textbox.insert("end", entry.format_line() + "\n")
                self.log_textbox.see("end")
            except Exception:
                pass
        self.after(0, append_log)

    def _on_executor_status_change(self, status: str):
        """Update status pill and button states when executor changes state."""
        def update_ui():
            if status == ExecutionState.RUNNING.value:
                self.status_pill.configure(text="● RUNNING", text_color="#10b981", fg_color="#064e3b")
                self.btn_start.configure(state="disabled")
                self.btn_pause.configure(state="normal")
                self.btn_resume.configure(state="disabled")
                self.btn_stop.configure(state="normal")
            elif status == ExecutionState.COUNTDOWN.value:
                self.status_pill.configure(text="● COUNTDOWN...", text_color="#f59e0b", fg_color="#78350f")
                self.btn_start.configure(state="disabled")
                self.btn_pause.configure(state="disabled")
                self.btn_resume.configure(state="disabled")
                self.btn_stop.configure(state="normal")
            elif status == ExecutionState.PAUSED.value:
                self.status_pill.configure(text="❚❚ PAUSED", text_color="#f59e0b", fg_color="#78350f")
                self.btn_start.configure(state="disabled")
                self.btn_pause.configure(state="disabled")
                self.btn_resume.configure(state="normal")
                self.btn_stop.configure(state="normal")
            elif status == ExecutionState.EMERGENCY_STOPPED.value:
                self.status_pill.configure(text="⚠ EMERGENCY STOPPED", text_color="#ef4444", fg_color="#7f1d1d")
                self.btn_start.configure(state="normal")
                self.btn_pause.configure(state="disabled")
                self.btn_resume.configure(state="disabled")
                self.btn_stop.configure(state="disabled")
            elif status == ExecutionState.COMPLETED.value:
                self.status_pill.configure(text="✔ COMPLETED", text_color="#34d399", fg_color="#064e3b")
                self.btn_start.configure(state="normal")
                self.btn_pause.configure(state="disabled")
                self.btn_resume.configure(state="disabled")
                self.btn_stop.configure(state="disabled")
            else:  # IDLE, STOPPED
                self.status_pill.configure(text="● SYSTEM IDLE", text_color="#9ca3af", fg_color="#262936")
                self.btn_start.configure(state="normal")
                self.btn_pause.configure(state="disabled")
                self.btn_resume.configure(state="disabled")
                self.btn_stop.configure(state="disabled")
        self.after(0, update_ui)

    def _on_executor_progress(self, current: int, total: int, pct: float):
        """Update progress bar and step counter."""
        def update_ui():
            self.progress_bar.set(pct / 100.0)
            self.val_progress_text.configure(text=f"{current} / {total} steps ({pct:.0f}%)")
        self.after(0, update_ui)

    def _on_executor_action_start(self, idx: int, action: Dict[str, Any]):
        def update_ui():
            desc = action.get("description", action.get("type", "Step"))
            self.lbl_active_step_desc.configure(text=f"Step {idx + 1}: {desc[:30]}")
        self.after(0, update_ui)

    def _on_keyboard_action_update(self, action_str: str):
        """Update the keyboard action indicator card."""
        def update_ui():
            self.val_kb_action.configure(text=action_str)
        self.after(0, update_ui)

    def _on_typing_telemetry_update(self, telemetry: Dict[str, Any]):
        """Live typing preview updater for character and line tracking."""
        def update_ui():
            ch = telemetry.get("char", "")
            disp_ch = "\\n" if ch == "\n" else ("\\t" if ch == "\t" else (ch if ch != " " else "␣"))
            line = telemetry.get("line", 1)
            col = telemetry.get("col", 1)
            wpm = telemetry.get("wpm", 0.0)
            total = telemetry.get("total", 0)
            idx = telemetry.get("index", 0)
            snippet = telemetry.get("preview_snippet", "").replace("\n", "↵ ").replace("\t", "⇥ ")

            self.lbl_active_char.configure(text=f"'{disp_ch}'")
            self.lbl_line_col.configure(text=f"L: {line}  C: {col}")
            self.lbl_stream_preview.configure(text=f"...{snippet}...")
            self.lbl_kb_cadence.configure(text=f"Cadence: {wpm} WPM • {idx}/{total} chars")
        self.after(0, update_ui)

    def _on_countdown_update(self, remaining: int):
        """Update keyboard action during countdown."""
        def update_ui():
            if remaining > 0:
                self.val_kb_action.configure(text=f"Starting in {remaining}s... Focus target window!")
            else:
                self.val_kb_action.configure(text="Executing actions...")
        self.after(0, update_ui)

    def _on_completed_update(self, total: int, elapsed: float):
        """Update completed count."""
        def update_ui():
            curr = int(self.val_total_actions.cget("text") or "0")
            self.val_total_actions.configure(text=str(curr + total))
            self.val_kb_action.configure(text=f"Done: {total} steps in {elapsed:.1f}s")
        self.after(0, update_ui)

    def _handle_start(self):
        """Start loaded sequence or prompt user."""
        saved = list_saved_sequences()
        if not saved:
            logger.warning("DASHBOARD", "No saved sequences found. Please create one in Sequence Builder.")
            if self.navigate_callback:
                self.navigate_callback("Sequence Builder")
            return

        seq_data = load_sequence_from_file(saved[0]["path"])
        if not seq_data or "actions" not in seq_data:
            logger.error("DASHBOARD", "Could not load sequence actions.")
            return

        logger.info("DASHBOARD", f"Starting sequence: '{seq_data.get('name', 'Sequence')}'")
        executor.start(seq_data["actions"], countdown_seconds=3)

    def _handle_pause(self):
        executor.pause()

    def _handle_resume(self):
        executor.resume()

    def _handle_stop(self):
        executor.stop()

    def _handle_emergency_stop(self):
        executor.emergency_stop()

    def _handle_notepad_test(self):
        """Execute real Windows Notepad automation verification in background thread."""
        self.btn_notepad_test.configure(state="disabled", text="Running Test in Notepad...")
        self.lbl_notepad_metric.configure(text="Testing in Notepad...", text_color="#f59e0b")

        def worker():
            try:
                report = run_notepad_verification(
                    progress_callback=lambda tel: self.after(0, lambda t=tel: self._on_typing_telemetry_update(t))
                )
                success = report.get("success", False)
                acc = report.get("accuracy_percentage", 0.0)
                time_sec = report.get("elapsed_seconds", 0.0)

                def update_done():
                    self.btn_notepad_test.configure(state="normal", text="🧪 Run Notepad Test Mode")
                    if success:
                        self.lbl_notepad_metric.configure(
                            text=f"✔ Notepad Test Passed: {acc}% in {time_sec}s",
                            text_color="#10b981"
                        )
                    else:
                        self.lbl_notepad_metric.configure(
                            text=f"⚠ Notepad Test: {acc}% match",
                            text_color="#ef4444"
                        )

                self.after(0, update_done)
            except Exception as e:
                self.after(0, lambda: self.btn_notepad_test.configure(state="normal", text="🧪 Run Notepad Test Mode"))
                self.after(0, lambda: self.lbl_notepad_metric.configure(text=f"Error: {e}", text_color="#ef4444"))

        threading.Thread(target=worker, daemon=True).start()
