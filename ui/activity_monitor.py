"""
DeskPilot - Activity Monitor Panel
Live streaming audit trail displaying timestamps, categories, execution parameters,
and error telemetry. Clearly identifies all operations as automated events.
"""

from pathlib import Path
from tkinter import filedialog, messagebox
import customtkinter as ctk
from utils.logger import logger, LogEntry
from utils.storage import export_logs_to_file
from automation.sequence_executor import executor, ExecutionState


class ActivityMonitorPanel(ctk.CTkFrame):
    """Real-time automation audit monitor and log filtering console."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self.current_filter = "ALL"
        self.search_term = ""
        self.auto_scroll_enabled = True

        self._create_header()
        self._create_filter_toolbar()
        self._create_log_console()
        self._create_footer_status()

        # Connect log listener
        logger.add_listener(self._on_log_entry)
        executor.on_status_change = self._on_executor_status_change

        # Initial populate
        self._reload_logs()

    def _create_header(self):
        """Top banner with active indicator and export/clear controls."""
        hdr = ctk.CTkFrame(self, fg_color="#181920", corner_radius=10, border_width=1, border_color="#2b2d3c")
        hdr.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 10))
        hdr.grid_columnconfigure(0, weight=1)

        left = ctk.CTkFrame(hdr, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w", padx=16, pady=12)

        lbl_title = ctk.CTkLabel(
            left,
            text="📜 Live Activity & Audit Monitor",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color="#f3f4f6"
        )
        lbl_title.pack(anchor="w")

        lbl_sub = ctk.CTkLabel(
            left,
            text="Complete telemetry trail of automated hardware events, keystrokes, and diagnostics.",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#9ca3af"
        )
        lbl_sub.pack(anchor="w")

        # Right status indicator
        right = ctk.CTkFrame(hdr, fg_color="transparent")
        right.grid(row=0, column=1, sticky="e", padx=16, pady=12)

        self.lbl_auto_banner = ctk.CTkLabel(
            right,
            text="● AUTOMATION IDLE",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#10b981",
            fg_color="#064e3b",
            corner_radius=16,
            padx=14,
            pady=5
        )
        self.lbl_auto_banner.pack()

    def _create_filter_toolbar(self):
        """Toolbar with filter chips, search input, auto-scroll, clear, and export buttons."""
        tb = ctk.CTkFrame(self, fg_color="#1f212a", corner_radius=10, border_width=1, border_color="#2b2d3c")
        tb.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 10))
        tb.grid_columnconfigure(6, weight=1)

        # Filter Category Buttons
        self.filter_buttons = {}
        categories = [("ALL", "All Events"), ("KEYBOARD", "Keyboard"), ("MOUSE", "Mouse"), ("ACTION", "Actions"), ("SAFETY", "Safety & Errors")]

        for idx, (cat_key, cat_label) in enumerate(categories):
            btn = ctk.CTkButton(
                tb,
                text=cat_label,
                font=ctk.CTkFont(size=11, weight="bold"),
                fg_color="#2563eb" if cat_key == "ALL" else "#374151",
                hover_color="#3b82f6",
                height=28,
                width=80 if cat_key == "ALL" else 95,
                corner_radius=6,
                command=lambda k=cat_key: self._set_filter(k)
            )
            btn.grid(row=0, column=idx, padx=4, pady=8)
            self.filter_buttons[cat_key] = btn

        # Search field
        self.ent_search = ctk.CTkEntry(
            tb,
            placeholder_text="Search logs...",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            height=28,
            width=160
        )
        self.ent_search.grid(row=0, column=5, padx=8, pady=8)
        self.ent_search.bind("<KeyRelease>", self._on_search_change)

        # Right side action buttons: Auto-scroll, Export, Clear
        actions_box = ctk.CTkFrame(tb, fg_color="transparent")
        actions_box.grid(row=0, column=6, sticky="e", padx=(0, 12), pady=8)

        self.chk_autoscroll = ctk.CTkCheckBox(
            actions_box,
            text="Auto-scroll",
            font=ctk.CTkFont(size=12),
            command=self._on_autoscroll_toggle
        )
        self.chk_autoscroll.select()
        self.chk_autoscroll.pack(side="left", padx=6)

        btn_test_np = ctk.CTkButton(
            actions_box,
            text="🧪 Notepad Test",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#4f46e5",
            hover_color="#6366f1",
            width=110,
            height=28,
            command=self._handle_run_notepad_test
        )
        btn_test_np.pack(side="left", padx=4)

        btn_export = ctk.CTkButton(
            actions_box,
            text="💾 Export Log",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#374151",
            hover_color="#4b5563",
            width=90,
            height=28,
            command=self._handle_export_log
        )
        btn_export.pack(side="left", padx=4)


        btn_clear = ctk.CTkButton(
            actions_box,
            text="Clear",
            font=ctk.CTkFont(size=11),
            fg_color="#374151",
            hover_color="#4b5563",
            width=65,
            height=28,
            command=self._handle_clear
        )
        btn_clear.pack(side="left", padx=4)

    def _create_log_console(self):
        """High-contrast monospace console log display."""
        console_frame = ctk.CTkFrame(self, fg_color="#181920", corner_radius=10, border_width=1, border_color="#2b2d3c")
        console_frame.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 10))
        console_frame.grid_rowconfigure(0, weight=1)
        console_frame.grid_columnconfigure(0, weight=1)

        self.txt_console = ctk.CTkTextbox(
            console_frame,
            font=ctk.CTkFont(family="Consolas", size=12),
            text_color="#f3f4f6",
            fg_color="#0e1015",
            corner_radius=8,
            wrap="none"
        )
        self.txt_console.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

    def _create_footer_status(self):
        """Footer showing entry count and auto-tag legend."""
        footer = ctk.CTkFrame(self, fg_color="#181920", corner_radius=10, border_width=1, border_color="#2b2d3c")
        footer.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 16))
        footer.grid_columnconfigure(0, weight=1)

        self.lbl_stats = ctk.CTkLabel(
            footer,
            text="Showing 0 entries",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#9ca3af"
        )
        self.lbl_stats.grid(row=0, column=0, sticky="w", padx=16, pady=8)

        legend = ctk.CTkLabel(
            footer,
            text="[KEYBOARD] Keystrokes  •  [MOUSE] Coordinates & Clicks  •  [ACTION] Steps  •  [SAFETY] Guards",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#6b7280"
        )
        legend.grid(row=0, column=1, sticky="e", padx=16, pady=8)

    def _on_log_entry(self, entry: LogEntry):
        """Handle incoming log stream."""
        def append():
            if self._matches_filter(entry):
                self.txt_console.insert("end", entry.format_line() + "\n")
                if self.auto_scroll_enabled:
                    self.txt_console.see("end")
            self._update_stats_label()
        self.after(0, append)

    def _matches_filter(self, entry: LogEntry) -> bool:
        if self.current_filter != "ALL":
            if self.current_filter == "SAFETY":
                if entry.category not in ["SAFETY", "ERROR", "WARN"]:
                    return False
            elif entry.category != self.current_filter:
                return False

        if self.search_term:
            if self.search_term.lower() not in entry.message.lower():
                return False
        return True

    def _reload_logs(self):
        """Re-filter and reload console view."""
        self.txt_console.delete("1.0", "end")
        count = 0
        for entry in logger.get_history():
            if self._matches_filter(entry):
                self.txt_console.insert("end", entry.format_line() + "\n")
                count += 1
        if self.auto_scroll_enabled:
            self.txt_console.see("end")
        self.lbl_stats.configure(text=f"Showing {count} log entries (Filter: {self.current_filter})")

    def _set_filter(self, category: str):
        self.current_filter = category
        for cat_key, btn in self.filter_buttons.items():
            btn.configure(fg_color="#2563eb" if cat_key == category else "#374151")
        self._reload_logs()

    def _on_search_change(self, event=None):
        self.search_term = self.ent_search.get().strip()
        self._reload_logs()

    def _on_autoscroll_toggle(self):
        self.auto_scroll_enabled = bool(self.chk_autoscroll.get())
        if self.auto_scroll_enabled:
            self.txt_console.see("end")

    def _update_stats_label(self):
        total = len(logger.get_history())
        self.lbl_stats.configure(text=f"Showing recent entries ({total} total in session) • Filter: {self.current_filter}")

    def _handle_clear(self):
        logger.clear()
        self._reload_logs()

    def _handle_export_log(self):
        entries = logger.get_history()
        if not entries:
            messagebox.showinfo("Export Logs", "No logs recorded in this session.", parent=self)
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            initialfile="deskpilot_audit_log.txt",
            filetypes=[("Text Logs", "*.txt"), ("Log Files", "*.log"), ("All Files", "*.*")]
        )
        if file_path:
            if export_logs_to_file(entries, Path(file_path)):
                messagebox.showinfo("Export Successful", f"Log export saved to:\n{Path(file_path).name}", parent=self)

    def _handle_run_notepad_test(self):
        """Execute real Windows Notepad automation verification test."""
        from automation.notepad_verifier import run_notepad_verification
        import threading
        
        logger.info("SYSTEM", "User triggered Notepad automation verification test.")
        
        def worker():
            report = run_notepad_verification()
            success = report.get("success", False)
            acc = report.get("accuracy_percentage", 0.0)
            if success:
                self.after(0, lambda: messagebox.showinfo(
                    "Notepad Test Passed",
                    f"Notepad automation verification succeeded!\n\n"
                    f"• Accuracy: {acc}%\n"
                    f"• Expected Length: {report.get('expected_length')} chars\n"
                    f"• Received Length: {report.get('received_length')} chars\n"
                    f"• Symbols Verified: {report.get('symbols_verified')}\n"
                    f"• Tabs Verified: {report.get('tabs_verified')}\n"
                    f"• Indent Verified: {report.get('indentation_verified')}\n"
                    f"• Elapsed Time: {report.get('elapsed_seconds')}s",
                    parent=self
                ))
            else:
                self.after(0, lambda: messagebox.showwarning(
                    "Notepad Test Notice",
                    f"Notepad verification test finished with notes:\n\n"
                    f"• Accuracy: {acc}%\n"
                    f"• Discrepancies: {report.get('discrepancies_count')}\n"
                    f"• Error: {report.get('error', 'None')}",
                    parent=self
                ))

        threading.Thread(target=worker, daemon=True).start()


    def _on_executor_status_change(self, status: str):
        """Update top active indicator banner."""
        def update():
            if status == ExecutionState.RUNNING.value:
                self.lbl_auto_banner.configure(
                    text="● AUTOMATION ACTIVE (RUNNING)",
                    text_color="#10b981",
                    fg_color="#064e3b"
                )
            elif status == ExecutionState.COUNTDOWN.value:
                self.lbl_auto_banner.configure(
                    text="● AUTOMATION COUNTDOWN...",
                    text_color="#f59e0b",
                    fg_color="#78350f"
                )
            elif status == ExecutionState.PAUSED.value:
                self.lbl_auto_banner.configure(
                    text="❚❚ AUTOMATION PAUSED",
                    text_color="#f59e0b",
                    fg_color="#78350f"
                )
            elif status == ExecutionState.EMERGENCY_STOPPED.value:
                self.lbl_auto_banner.configure(
                    text="⚠ EMERGENCY STOPPED",
                    text_color="#ef4444",
                    fg_color="#7f1d1d"
                )
            else:
                self.lbl_auto_banner.configure(
                    text="● AUTOMATION IDLE",
                    text_color="#9ca3af",
                    fg_color="#262936"
                )
        self.after(0, update)
