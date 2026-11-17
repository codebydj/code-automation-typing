"""
DeskPilot - Keyboard Controller Panel
Interactive workbench for human-style text typing, character-level pause/resume,
live character/line preview telemetry, keyboard selection tools, and shortcuts.
"""

import time
import threading
import customtkinter as ctk
from typing import Optional, Dict, Any
from automation.keyboard_controller import keyboard_ctrl
from automation.safety import safety
from utils.logger import logger


class KeyboardPanel(ctk.CTkFrame):
    """Modern keyboard automation control center."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._typing_stop_event = threading.Event()
        self._typing_pause_event = threading.Event()
        self._typing_pause_event.set()
        self._is_active = False

        # Left Column: Letter-by-letter Typing Tester & Live Preview
        self._create_typing_tester(col=0)

        # Right Column: Shortcut Pad & Text Selection Suite
        self._create_shortcuts_and_selection(col=1)

    def _create_typing_tester(self, col: int):
        """Card for typing text with human micro-delays and character-level pause/resume."""
        container = ctk.CTkFrame(self, fg_color="#181920", corner_radius=10, border_width=1, border_color="#2b2d3c")
        container.grid(row=0, column=col, sticky="nsew", padx=(16, 8), pady=16)
        container.grid_rowconfigure(2, weight=1)
        container.grid_columnconfigure(0, weight=1)

        # Header
        hdr = ctk.CTkFrame(container, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 6))
        
        lbl_title = ctk.CTkLabel(
            hdr,
            text="✍️ Human Typing & Live Preview",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color="#f3f4f6"
        )
        lbl_title.pack(anchor="w")

        lbl_desc = ctk.CTkLabel(
            hdr,
            text="Types text character-by-character with micro-jitter and character-level pause.",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#9ca3af"
        )
        lbl_desc.pack(anchor="w")

        # Controls & Speed Settings
        settings_box = ctk.CTkFrame(container, fg_color="#1f212a", corner_radius=8)
        settings_box.grid(row=1, column=0, sticky="ew", padx=16, pady=6)
        settings_box.grid_columnconfigure((0, 1, 2), weight=1)

        # Speed slider
        lbl_speed = ctk.CTkLabel(settings_box, text="Base Speed (Delay):", font=ctk.CTkFont(size=12, weight="bold"), text_color="#d1d5db")
        lbl_speed.grid(row=0, column=0, sticky="w", padx=12, pady=(8, 2))
        
        self.lbl_speed_val = ctk.CTkLabel(settings_box, text="333 ms / char (~3.0 chars/s)", font=ctk.CTkFont(size=12), text_color="#38bdf8")
        self.lbl_speed_val.grid(row=0, column=1, sticky="e", padx=12, pady=(8, 2))

        self.slider_speed = ctk.CTkSlider(
            settings_box,
            from_=50,
            to=800,
            number_of_steps=75,
            command=self._on_speed_slider_change
        )
        self.slider_speed.set(333)
        self.slider_speed.grid(row=1, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 6))

        # Countdown selector
        lbl_cd = ctk.CTkLabel(settings_box, text="Focus Countdown:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#d1d5db")
        lbl_cd.grid(row=0, column=2, sticky="w", padx=12, pady=(8, 2))

        self.opt_countdown = ctk.CTkOptionMenu(
            settings_box,
            values=["1 second", "2 seconds", "3 seconds", "5 seconds", "No countdown"],
            width=120,
            height=26
        )
        self.opt_countdown.set("3 seconds")
        self.opt_countdown.grid(row=1, column=2, sticky="ew", padx=12, pady=(0, 6))

        # Multiline text input
        input_hdr = ctk.CTkFrame(container, fg_color="transparent")
        input_hdr.grid(row=2, column=0, sticky="ew", padx=16, pady=(2, 2))
        ctk.CTkLabel(input_hdr, text="Text Payload (Symbols & Indent Preserved):", font=ctk.CTkFont(size=12, weight="bold"), text_color="#d1d5db").pack(side="left")
        
        btn_sample = ctk.CTkButton(
            input_hdr,
            text="Load Symbols Sample",
            font=ctk.CTkFont(size=11),
            width=130,
            height=22,
            fg_color="#374151",
            hover_color="#4b5563",
            command=self._load_sample_text
        )
        btn_sample.pack(side="right")

        self.txt_payload = ctk.CTkTextbox(
            container,
            font=ctk.CTkFont(family="Consolas", size=12),
            fg_color="#121317",
            text_color="#e5e7eb",
            corner_radius=6,
            wrap="word",
            height=120
        )
        self.txt_payload.grid(row=3, column=0, sticky="nsew", padx=16, pady=4)
        container.grid_rowconfigure(3, weight=1)
        
        self.txt_payload.insert("1.0", (
            "DeskPilot Real Keystroke Test\n"
            "Symbols: {} [] () <> /\\ =+ -* &| !? @#$%^~ :; \"' `_\n"
            "Tabs:\t[Col1]\t[Col2]\t[Col3]\n"
            "    def calculate_metrics():\n"
            "        return True\n"
        ))

        # Live Character & Line Telemetry Box
        preview_card = ctk.CTkFrame(container, fg_color="#121317", corner_radius=8, border_width=1, border_color="#2b2d3c")
        preview_card.grid(row=4, column=0, sticky="ew", padx=16, pady=(4, 6))

        row_stat = ctk.CTkFrame(preview_card, fg_color="transparent")
        row_stat.pack(fill="x", padx=10, pady=(6, 2))

        ctk.CTkLabel(row_stat, text="Current Char:", font=ctk.CTkFont(size=11), text_color="#9ca3af").pack(side="left")
        self.lbl_curr_char = ctk.CTkLabel(
            row_stat,
            text="'-'",
            font=ctk.CTkFont(family="Consolas", size=13, weight="bold"),
            text_color="#34d399",
            fg_color="#064e3b",
            corner_radius=4,
            padx=8,
            pady=2
        )
        self.lbl_curr_char.pack(side="left", padx=6)

        self.lbl_telemetry_pos = ctk.CTkLabel(
            row_stat,
            text="Line: 1  Col: 1  •  0 WPM",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color="#38bdf8"
        )
        self.lbl_telemetry_pos.pack(side="right")

        self.lbl_stream_snippet = ctk.CTkLabel(
            preview_card,
            text="Typing stream will preview active characters here...",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color="#9ca3af",
            anchor="w"
        )
        self.lbl_stream_snippet.pack(fill="x", padx=10, pady=(2, 6))

        # Progress bar
        self.typing_progress_bar = ctk.CTkProgressBar(container, height=6, progress_color="#10b981", fg_color="#374151")
        self.typing_progress_bar.set(0)
        self.typing_progress_bar.grid(row=5, column=0, sticky="ew", padx=16, pady=(0, 6))

        # Bottom buttons with Pause/Resume
        btn_row = ctk.CTkFrame(container, fg_color="transparent")
        btn_row.grid(row=6, column=0, sticky="ew", padx=16, pady=(0, 14))

        self.btn_start_type = ctk.CTkButton(
            btn_row,
            text="▶ Start Typing",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color="#059669",
            hover_color="#10b981",
            height=34,
            command=self._handle_start_typing
        )
        self.btn_start_type.pack(side="left", expand=True, fill="x", padx=(0, 4))

        self.btn_pause_type = ctk.CTkButton(
            btn_row,
            text="⏸ Pause",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="#d97706",
            hover_color="#f59e0b",
            height=34,
            width=80,
            command=self._handle_pause_toggle,
            state="disabled"
        )
        self.btn_pause_type.pack(side="left", padx=4)

        self.btn_stop_type = ctk.CTkButton(
            btn_row,
            text="⏹ Cancel",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="#4b5563",
            hover_color="#6b7280",
            height=34,
            width=80,
            command=self._handle_stop_typing,
            state="disabled"
        )
        self.btn_stop_type.pack(side="right")

    def _create_shortcuts_and_selection(self, col: int):
        """Card for keyboard selection tools, shortcuts, and custom hotkey runner."""
        container = ctk.CTkFrame(self, fg_color="#181920", corner_radius=10, border_width=1, border_color="#2b2d3c")
        container.grid(row=0, column=col, sticky="nsew", padx=(8, 16), pady=16)
        container.grid_columnconfigure(0, weight=1)

        # Header
        hdr = ctk.CTkFrame(container, fg_color="transparent")
        hdr.pack(fill="x", padx=16, pady=(14, 6))
        
        lbl_title = ctk.CTkLabel(
            hdr,
            text="🔤 Selection Tool & Shortcuts",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color="#f3f4f6"
        )
        lbl_title.pack(anchor="w")

        lbl_desc = ctk.CTkLabel(
            hdr,
            text="Keyboard text selection using Shift+Arrow, Ctrl+Shift+Arrow, and Ctrl+A.",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#9ca3af"
        )
        lbl_desc.pack(anchor="w")

        # Dedicated Keyboard Selection Suite
        sel_box = ctk.CTkFrame(container, fg_color="#1f212a", corner_radius=8)
        sel_box.pack(fill="x", padx=16, pady=4)
        sel_box.grid_columnconfigure((0, 1, 2, 3), weight=1)

        ctk.CTkLabel(sel_box, text="Keyboard Text Selection Suite:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#38bdf8").grid(row=0, column=0, columnspan=4, sticky="w", padx=10, pady=(8, 4))

        sel_buttons = [
            ("Shift+Left", "Char ←", "left", "char"),
            ("Shift+Right", "Char →", "right", "char"),
            ("Shift+Up", "Line ↑", "up", "char"),
            ("Shift+Down", "Line ↓", "down", "char"),
            ("Ctrl+Shift+←", "Word ←", "left", "word"),
            ("Ctrl+Shift+→", "Word →", "right", "word"),
            ("Shift+Home", "Line Start", "home", "line"),
            ("Shift+End", "Line End", "end", "line"),
        ]

        r, c = 1, 0
        for label, desc, dir_key, mode in sel_buttons:
            btn = ctk.CTkButton(
                sel_box,
                text=f"{label}\n({desc})",
                font=ctk.CTkFont(size=10, weight="bold"),
                fg_color="#2b2d3c",
                hover_color="#2563eb",
                height=38,
                command=lambda d=dir_key, m=mode: self._trigger_arrow_select(d, m)
            )
            btn.grid(row=r, column=c, padx=3, pady=3, sticky="ew")
            c += 1
            if c >= 4:
                c = 0
                r += 1

        ctk.CTkLabel(sel_box, text="Triggers with 1.5s countdown so you can focus text.", font=ctk.CTkFont(size=10), text_color="#9ca3af").grid(row=r, column=0, columnspan=4, sticky="w", padx=10, pady=(2, 6))

        # Standard Shortcuts Grid
        shortcuts_box = ctk.CTkFrame(container, fg_color="#1f212a", corner_radius=8)
        shortcuts_box.pack(fill="x", padx=16, pady=4)
        for i in range(3):
            shortcuts_box.grid_columnconfigure(i, weight=1)

        ctk.CTkLabel(shortcuts_box, text="Standard Shortcuts:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#d1d5db").grid(row=0, column=0, columnspan=3, sticky="w", padx=10, pady=(8, 4))

        quick_shortcuts = [
            ("Ctrl+A", "Select All", "ctrl+a"),
            ("Ctrl+C", "Copy", "ctrl+c"),
            ("Ctrl+V", "Paste", "ctrl+v"),
            ("Ctrl+X", "Cut", "ctrl+x"),
            ("Ctrl+Z", "Undo", "ctrl+z"),
            ("Ctrl+S", "Save File", "ctrl+s"),
            ("Tab", "Indent", "tab"),
            ("Enter", "Newline", "enter"),
            ("Backspace", "Delete Prev", "backspace"),
        ]

        sr, sc = 1, 0
        for label, tooltip, key_combo in quick_shortcuts:
            btn = ctk.CTkButton(
                shortcuts_box,
                text=f"{label} ({tooltip})",
                font=ctk.CTkFont(size=11, weight="bold"),
                fg_color="#2b2d3c",
                hover_color="#3b82f6",
                height=32,
                corner_radius=6,
                command=lambda k=key_combo: self._trigger_quick_shortcut(k)
            )
            btn.grid(row=sr, column=sc, padx=3, pady=3, sticky="ew")
            sc += 1
            if sc >= 3:
                sc = 0
                sr += 1

        # Custom Hotkey Runner
        custom_box = ctk.CTkFrame(container, fg_color="#1f212a", corner_radius=8)
        custom_box.pack(fill="x", padx=16, pady=(4, 12))
        custom_box.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(custom_box, text="🎯 Custom Hotkey Runner:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#d1d5db").grid(row=0, column=0, sticky="w", padx=10, pady=(6, 2))

        input_row = ctk.CTkFrame(custom_box, fg_color="transparent")
        input_row.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 6))
        input_row.grid_columnconfigure(0, weight=1)

        self.ent_custom_hotkey = ctk.CTkEntry(
            input_row,
            placeholder_text="e.g. alt+tab, win+r, ctrl+shift+esc",
            font=ctk.CTkFont(family="Consolas", size=12),
            height=30
        )
        self.ent_custom_hotkey.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        btn_run_custom = ctk.CTkButton(
            input_row,
            text="Execute (2s)",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#2563eb",
            hover_color="#3b82f6",
            height=30,
            command=self._handle_run_custom_hotkey
        )
        btn_run_custom.grid(row=0, column=1)

        self.lbl_feedback = ctk.CTkLabel(
            custom_box,
            text="Ready to trigger shortcuts.",
            font=ctk.CTkFont(size=10),
            text_color="#9ca3af"
        )
        self.lbl_feedback.grid(row=2, column=0, sticky="w", padx=10, pady=(0, 6))

    def _on_speed_slider_change(self, value):
        ms = int(value)
        rate = round(1000.0 / max(1, ms), 1)
        self.lbl_speed_val.configure(text=f"{ms} ms / char (~{rate} chars/s)")

    def _load_sample_text(self):
        sample = (
            "DeskPilot Real Keystroke Test\n"
            "Symbols: {} [] () <> /\\ =+ -* &| !? @#$%^~ :; \"' `_\n"
            "Tabs:\t[Col1]\t[Col2]\t[Col3]\n"
            "    def calculate_metrics():\n"
            "        return True\n"
        )
        self.txt_payload.delete("1.0", "end")
        self.txt_payload.insert("1.0", sample)

    def _handle_start_typing(self):
        text = self.txt_payload.get("1.0", "end-1c")
        if not text:
            return

        cd_map = {"1 second": 1, "2 seconds": 2, "3 seconds": 3, "5 seconds": 5, "No countdown": 0}
        countdown = cd_map.get(self.opt_countdown.get(), 3)
        base_delay = self.slider_speed.get() / 1000.0

        self._typing_stop_event.clear()
        self._typing_pause_event.set()
        self.btn_start_type.configure(state="disabled")
        self.btn_pause_type.configure(state="normal", text="⏸ Pause", fg_color="#d97706")
        self.btn_stop_type.configure(state="normal")
        self.typing_progress_bar.set(0)

        threading.Thread(
            target=self._typing_worker,
            args=(text, countdown, base_delay),
            daemon=True
        ).start()

    def _typing_worker(self, text: str, countdown: int, base_delay: float):
        try:
            if countdown > 0:
                for rem in range(countdown, 0, -1):
                    if self._typing_stop_event.is_set():
                        self.after(0, lambda: self.lbl_stream_snippet.configure(text="Typing cancelled.", text_color="#ef4444"))
                        return
                    self.after(0, lambda r=rem: self.lbl_stream_snippet.configure(
                        text=f"SWITCH FOCUS TO TARGET APP! Typing in {r}s...",
                        text_color="#f59e0b"
                    ))
                    time.sleep(1.0)

            def telemetry_cb(tel: Dict[str, Any]):
                self.after(0, lambda t=tel: self._update_telemetry_ui(t))

            success = keyboard_ctrl.type_text(
                text=text,
                base_delay=base_delay,
                progress_callback=telemetry_cb,
                pause_event=self._typing_pause_event,
                stop_event=self._typing_stop_event
            )

            if success:
                self.after(0, lambda: self.lbl_stream_snippet.configure(text="✔ Typing completed successfully!", text_color="#34d399"))
            else:
                self.after(0, lambda: self.lbl_stream_snippet.configure(text="Typing stopped or interrupted.", text_color="#f59e0b"))

        except Exception as e:
            self.after(0, lambda: self.lbl_stream_snippet.configure(text=f"Error: {e}", text_color="#ef4444"))
        finally:
            self.after(0, lambda: self.btn_start_type.configure(state="normal"))
            self.after(0, lambda: self.btn_pause_type.configure(state="disabled", text="⏸ Pause", fg_color="#d97706"))
            self.after(0, lambda: self.btn_stop_type.configure(state="disabled"))

    def _update_telemetry_ui(self, tel: Dict[str, Any]):
        ch = tel.get("char", "")
        disp_ch = "\\n" if ch == "\n" else ("\\t" if ch == "\t" else (ch if ch != " " else "␣"))
        line = tel.get("line", 1)
        col = tel.get("col", 1)
        wpm = tel.get("wpm", 0.0)
        pct = tel.get("pct", 0.0) / 100.0
        snippet = tel.get("preview_snippet", "").replace("\n", "↵ ").replace("\t", "⇥ ")

        self.lbl_curr_char.configure(text=f"'{disp_ch}'")
        self.lbl_telemetry_pos.configure(text=f"Line: {line}  Col: {col}  •  {wpm} WPM")
        self.lbl_stream_snippet.configure(text=f"...{snippet}...", text_color="#e5e7eb")
        self.typing_progress_bar.set(pct)

    def _handle_pause_toggle(self):
        if self._typing_pause_event.is_set():
            self._typing_pause_event.clear()
            self.btn_pause_type.configure(text="⏯ Resume", fg_color="#2563eb")
            self.lbl_stream_snippet.configure(text="Typing paused at character level. Click Resume to continue.", text_color="#f59e0b")
        else:
            self._typing_pause_event.set()
            self.btn_pause_type.configure(text="⏸ Pause", fg_color="#d97706")
            self.lbl_stream_snippet.configure(text="Resuming typing...", text_color="#10b981")

    def _handle_stop_typing(self):
        self._typing_stop_event.set()
        self._typing_pause_event.set()

    def _trigger_arrow_select(self, direction: str, mode: str):
        self.lbl_feedback.configure(
            text=f"Selecting Shift+{direction.upper()} ({mode}) in 1.5s... Focus target text!",
            text_color="#f59e0b"
        )
        def worker():
            time.sleep(1.5)
            success = keyboard_ctrl.select_by_arrows(direction=direction, count=1, mode=mode)
            color = "#10b981" if success else "#ef4444"
            msg = f"Executed selection Shift+{direction.upper()}" if success else "Selection failed"
            self.after(0, lambda: self.lbl_feedback.configure(text=msg, text_color=color))
        threading.Thread(target=worker, daemon=True).start()

    def _trigger_quick_shortcut(self, key_combo: str):
        self.lbl_feedback.configure(
            text=f"Preparing {key_combo.upper()}... Switch to target window! (1.5s)",
            text_color="#f59e0b"
        )
        def run_shortcut():
            time.sleep(1.5)
            keyboard_ctrl.press_hotkey(key_combo)
            self.after(0, lambda: self.lbl_feedback.configure(
                text=f"Executed shortcut: {key_combo.upper()}",
                text_color="#10b981"
            ))
        threading.Thread(target=run_shortcut, daemon=True).start()

    def _handle_run_custom_hotkey(self):
        combo = self.ent_custom_hotkey.get().strip()
        if not combo:
            return
        self.lbl_feedback.configure(
            text=f"Executing [{combo.upper()}] in 2.0s... Switch to target window!",
            text_color="#f59e0b"
        )
        def worker():
            time.sleep(2.0)
            success = keyboard_ctrl.press_hotkey(combo)
            color = "#10b981" if success else "#ef4444"
            status_text = f"Executed [{combo.upper()}]" if success else f"Failed to execute [{combo.upper()}]"
            self.after(0, lambda: self.lbl_feedback.configure(text=status_text, text_color=color))
        threading.Thread(target=worker, daemon=True).start()
