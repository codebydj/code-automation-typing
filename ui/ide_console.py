"""
DeskPilot IDE - Bottom Panel: Execution Console & Live Telemetry Inspector
Displays live automation telemetry (current task, character, speed, mouse pos, progress),
real-time audit logs, and diagnostic error reports.
"""

from typing import Dict, Any, Optional
import customtkinter as ctk
from utils.logger import logger, LogEntry

class IDEConsole(ctk.CTkFrame):
    """
    Bottom docked console in the IDE containing:
    1. Execution Status & Live Telemetry (speed, active character, progress bar, mouse pos)
    2. Real-Time Execution Log Stream
    3. Error & Diagnostic Suggestions Inspector
    """
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="#181920", corner_radius=8, border_width=1, border_color="#2b2d3c", **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._create_header()
        self._create_tabview()

        # Connect to logger
        logger.add_listener(self._on_log_entry)

    def _create_header(self):
        """Console top bar with title and quick actions."""
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=12, pady=(6, 2))
        hdr.grid_columnconfigure(0, weight=1)

        lbl = ctk.CTkLabel(
            hdr,
            text="💻 TERMINAL & TELEMETRY CONSOLE",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#9ca3af"
        )
        lbl.grid(row=0, column=0, sticky="w")

        # Status badge
        self.lbl_state_badge = ctk.CTkLabel(
            hdr,
            text="READY",
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            text_color="#10b981",
            fg_color="#064e3b",
            corner_radius=4,
            padx=8,
            pady=2
        )
        self.lbl_state_badge.grid(row=0, column=1, sticky="e")

    def _create_tabview(self):
        """Create tabview for Telemetry, Logs, and Error Inspector."""
        self.tabview = ctk.CTkTabview(
            self,
            fg_color="transparent",
            segmented_button_fg_color="#14151b",
            segmented_button_selected_color="#2563eb",
            segmented_button_selected_hover_color="#3b82f6"
        )
        self.tabview.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))

        # Tab 1: Execution Status & Telemetry
        self.tab_status = self.tabview.add("📊 Execution Status")
        self._build_telemetry_tab(self.tab_status)

        # Tab 2: Execution Logs
        self.tab_logs = self.tabview.add("📜 Logs")
        self._build_logs_tab(self.tab_logs)

        # Tab 3: Error Diagnostics
        self.tab_errors = self.tabview.add("⚠️ Diagnostics")
        self._build_errors_tab(self.tab_errors)

    def _build_telemetry_tab(self, parent):
        """Live dashboard showing all active execution metrics."""
        parent.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # Row 1: Key Metrics Cards
        # Card 1: Active Task
        c1 = ctk.CTkFrame(parent, fg_color="#14151b", corner_radius=6)
        c1.grid(row=0, column=0, padx=4, pady=4, sticky="nsew")
        ctk.CTkLabel(c1, text="Current Task", font=ctk.CTkFont(size=10), text_color="#9ca3af").pack(anchor="w", padx=8, pady=(6, 1))
        self.lbl_current_task = ctk.CTkLabel(
            c1,
            text="Idle / None",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#38bdf8",
            anchor="w"
        )
        self.lbl_current_task.pack(anchor="w", padx=8, pady=(0, 6))

        # Card 2: Active Character & Speed
        c2 = ctk.CTkFrame(parent, fg_color="#14151b", corner_radius=6)
        c2.grid(row=0, column=1, padx=4, pady=4, sticky="nsew")
        ctk.CTkLabel(c2, text="Typing Stream & Speed", font=ctk.CTkFont(size=10), text_color="#9ca3af").pack(anchor="w", padx=8, pady=(6, 1))
        
        row_c2 = ctk.CTkFrame(c2, fg_color="transparent")
        row_c2.pack(fill="x", padx=8, pady=(0, 6))
        
        self.lbl_active_char = ctk.CTkLabel(
            row_c2,
            text="'-'",
            font=ctk.CTkFont(family="Consolas", size=14, weight="bold"),
            text_color="#34d399",
            fg_color="#064e3b",
            corner_radius=4,
            padx=8,
            pady=2
        )
        self.lbl_active_char.pack(side="left")

        self.lbl_speed_val = ctk.CTkLabel(
            row_c2,
            text="3.0 chars/s (333ms)",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color="#10b981"
        )
        self.lbl_speed_val.pack(side="left", padx=8)

        # Card 3: Mouse & Keyboard Actions
        c3 = ctk.CTkFrame(parent, fg_color="#14151b", corner_radius=6)
        c3.grid(row=0, column=2, padx=4, pady=4, sticky="nsew")
        ctk.CTkLabel(c3, text="Mouse & Keyboard Action", font=ctk.CTkFont(size=10), text_color="#9ca3af").pack(anchor="w", padx=8, pady=(6, 1))
        self.lbl_hw_action = ctk.CTkLabel(
            c3,
            text="Keyboard: Idle • Mouse: (0, 0)",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color="#e5e7eb",
            anchor="w"
        )
        self.lbl_hw_action.pack(anchor="w", padx=8, pady=(0, 6))

        # Card 4: Task Progress
        c4 = ctk.CTkFrame(parent, fg_color="#14151b", corner_radius=6)
        c4.grid(row=0, column=3, padx=4, pady=4, sticky="nsew")
        ctk.CTkLabel(c4, text="Completed / Remaining", font=ctk.CTkFont(size=10), text_color="#9ca3af").pack(anchor="w", padx=8, pady=(6, 1))
        self.lbl_task_stats = ctk.CTkLabel(
            c4,
            text="0 Done • 0 Remaining",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#fbbf24",
            anchor="w"
        )
        self.lbl_task_stats.pack(anchor="w", padx=8, pady=(0, 6))

        # Row 2: Progress Bar and Stream Preview
        p_row = ctk.CTkFrame(parent, fg_color="#14151b", corner_radius=6)
        p_row.grid(row=1, column=0, columnspan=4, sticky="ew", padx=4, pady=(4, 2))
        p_row.grid_columnconfigure(0, weight=1)

        p_info = ctk.CTkFrame(p_row, fg_color="transparent")
        p_info.pack(fill="x", padx=8, pady=(6, 2))

        self.lbl_char_progress = ctk.CTkLabel(
            p_info,
            text="Progress: 0 / 0 characters (0%)",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#f3f4f6"
        )
        self.lbl_char_progress.pack(side="left")

        self.lbl_stream_snippet = ctk.CTkLabel(
            p_info,
            text="Active stream snippet will display here during automation...",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color="#9ca3af"
        )
        self.lbl_stream_snippet.pack(side="right")

        self.progress_bar = ctk.CTkProgressBar(p_row, height=8, progress_color="#10b981", fg_color="#374151")
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=8, pady=(0, 8))

    def _build_logs_tab(self, parent):
        """Real-time log console."""
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)

        # Toolbar
        tb = ctk.CTkFrame(parent, fg_color="transparent")
        tb.grid(row=0, column=0, sticky="ew", padx=4, pady=(2, 4))

        ctk.CTkButton(
            tb,
            text="Clear Logs",
            width=80,
            height=24,
            font=ctk.CTkFont(size=11),
            fg_color="#374151",
            hover_color="#4b5563",
            command=self._clear_logs
        ).pack(side="left")

        # Scrollable log text
        self.txt_logs = ctk.CTkTextbox(
            parent,
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="#14151b",
            text_color="#e5e7eb",
            wrap="word"
        )
        self.txt_logs.grid(row=1, column=0, sticky="nsew", padx=4, pady=2)

    def _build_errors_tab(self, parent):
        """Diagnostic error reporting tab."""
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(0, weight=1)

        self.txt_errors = ctk.CTkTextbox(
            parent,
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="#14151b",
            text_color="#f87171",
            wrap="word"
        )
        self.txt_errors.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self.txt_errors.insert("1.0", "No errors recorded. Automation systems healthy.\n")

    def _on_log_entry(self, entry: LogEntry):
        """Callback from logger listener."""
        line = entry.format_line() + "\n"
        self.after(0, lambda: self._append_log_line(line, entry))

    def _append_log_line(self, line: str, entry: LogEntry):
        self.txt_logs.insert("end", line)
        self.txt_logs.see("end")

        if entry.level == "ERROR":
            err_msg = f"[{entry.timestamp}] ERROR [{entry.category}]: {entry.message}\n"
            if entry.suggestion:
                err_msg += f"   💡 DIAGNOSTIC SUGGESTION: {entry.suggestion}\n"
            if entry.details:
                err_msg += f"   DETAILS: {entry.details}\n"
            err_msg += "-" * 70 + "\n"
            self.txt_errors.insert("end", err_msg)
            self.txt_errors.see("end")

    def _clear_logs(self):
        self.txt_logs.delete("1.0", "end")

    def update_telemetry(self, data: Dict[str, Any]):
        """Update live telemetry metrics safely from background automation threads."""
        def apply():
            if "state" in data:
                st = data["state"].upper()
                colors = {
                    "IDLE": ("#10b981", "#064e3b"),
                    "COUNTDOWN": ("#f59e0b", "#78350f"),
                    "RUNNING": ("#38bdf8", "#0369a1"),
                    "PAUSED": ("#fbbf24", "#78350f"),
                    "STOPPED": ("#9ca3af", "#374151"),
                    "EMERGENCY_STOPPED": ("#ef4444", "#7f1d1d")
                }
                fg, bg = colors.get(st, ("#38bdf8", "#0f2942"))
                self.lbl_state_badge.configure(text=st, text_color=fg, fg_color=bg)

            if "task_desc" in data:
                self.lbl_current_task.configure(text=str(data["task_desc"])[:35])

            if "char" in data:
                ch = data["char"]
                disp_ch = "\\n" if ch == "\n" else ("\\t" if ch == "\t" else (ch if ch != " " else "␣"))
                self.lbl_active_char.configure(text=f"'{disp_ch}'")

            if "speed" in data:
                self.lbl_speed_val.configure(text=str(data["speed"]))

            if "mouse_pos" in data:
                mx, my = data["mouse_pos"]
                self.lbl_hw_action.configure(text=f"Mouse: ({mx}, {my}) • Last Key: {data.get('last_key', 'None')}")

            if "tasks_done" in data and "tasks_remaining" in data:
                self.lbl_task_stats.configure(text=f"{data['tasks_done']} Done • {data['tasks_remaining']} Remaining")

            if "pct" in data:
                pct = float(data["pct"])
                self.progress_bar.set(pct / 100.0)
                curr = data.get("current_chars", 0)
                tot = data.get("total_chars", 0)
                self.lbl_char_progress.configure(text=f"Progress: {curr} / {tot} chars ({int(pct)}%)")

            if "snippet" in data:
                self.lbl_stream_snippet.configure(text=f"...{data['snippet']}...")

        self.after(0, apply)
