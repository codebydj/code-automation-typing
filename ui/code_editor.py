"""
DeskPilot - Code Typing Studio
Dedicated coding studio for streaming source code character-by-character
into external IDEs (VS Code, Notepad, JetBrains, browser editors) with
indentation preservation, countdown focusing, and live progress tracking.
"""

import time
import threading
from pathlib import Path
from tkinter import filedialog
import customtkinter as ctk
import pyperclip
from automation.keyboard_controller import keyboard_ctrl
from automation.safety import safety
from utils.logger import logger

SAMPLE_SNIPPETS = {
    "Python Function": (
        "def analyze_dataset(records: list[dict]) -> dict:\n"
        "    \"\"\"Analyze tabular records and return summary metrics.\"\"\"\n"
        "    if not records:\n"
        "        return {\"total\": 0, \"status\": \"empty\"}\n"
        "    \n"
        "    valid_entries = [r for r in records if r.get(\"active\", False)]\n"
        "    ratio = len(valid_entries) / len(records)\n"
        "    return {\n"
        "        \"total\": len(records),\n"
        "        \"active\": len(valid_entries),\n"
        "        \"activity_rate\": round(ratio, 4)\n"
        "    }\n"
    ),
    "JavaScript Async Fetch": (
        "async function fetchUserDashboard(userId) {\n"
        "    try {\n"
        "        const response = await fetch(`/api/v1/users/${userId}/metrics`);\n"
        "        if (!response.ok) {\n"
        "            throw new Error(`HTTP Error: ${response.status}`);\n"
        "        }\n"
        "        const data = await response.json();\n"
        "        console.log(\"Telemetry received:\", data);\n"
        "        return data;\n"
        "    } catch (err) {\n"
        "        console.error(\"Failed to load metrics:\", err.message);\n"
        "        return null;\n"
        "    }\n"
        "}\n"
    ),
    "SQL Analytical Query": (
        "SELECT \n"
        "    department_name,\n"
        "    COUNT(employee_id) AS total_headcount,\n"
        "    ROUND(AVG(salary), 2) AS average_salary,\n"
        "    MAX(hire_date) AS latest_hire\n"
        "FROM corporate_hr.employees\n"
        "WHERE active_status = 1\n"
        "GROUP BY department_name\n"
        "HAVING COUNT(employee_id) > 5\n"
        "ORDER BY average_salary DESC;\n"
    ),
    "HTML Component": (
        "<div class=\"metric-card elevated\">\n"
        "    <div class=\"card-header\">\n"
        "        <span class=\"status-dot online\"></span>\n"
        "        <h3>Automation Engine</h3>\n"
        "    </div>\n"
        "    <p class=\"description\">Real-time hardware synthetic events.</p>\n"
        "    <button class=\"btn-primary\" onclick=\"triggerRun()\">Execute</button>\n"
        "</div>\n"
    )
}


class CodeEditorPanel(ctk.CTkFrame):
    """Studio for staging and human-typing code into external editors."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._typing_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()

        self._create_header_bar()
        self._create_controls_bar()
        self._create_editor_area()
        self._create_progress_footer()

    def _create_header_bar(self):
        """Header with title, description, and snippet loader."""
        hdr = ctk.CTkFrame(self, fg_color="#181920", corner_radius=10, border_width=1, border_color="#2b2d3c")
        hdr.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 10))
        hdr.grid_columnconfigure(0, weight=1)

        left_box = ctk.CTkFrame(hdr, fg_color="transparent")
        left_box.grid(row=0, column=0, sticky="w", padx=16, pady=12)

        lbl_title = ctk.CTkLabel(
            left_box,
            text="💻 Code Typing Studio",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color="#f3f4f6"
        )
        lbl_title.pack(anchor="w")

        lbl_sub = ctk.CTkLabel(
            left_box,
            text="Stage code, select target countdown, and stream keystrokes into VS Code / Notepad with natural cadence.",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#9ca3af"
        )
        lbl_sub.pack(anchor="w")

        # Right actions: Snippet template menu & Import
        right_box = ctk.CTkFrame(hdr, fg_color="transparent")
        right_box.grid(row=0, column=1, sticky="e", padx=16, pady=12)

        ctk.CTkLabel(right_box, text="Load Template:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#d1d5db").pack(side="left", padx=(0, 6))

        self.opt_snippet = ctk.CTkOptionMenu(
            right_box,
            values=list(SAMPLE_SNIPPETS.keys()),
            width=170,
            command=self._handle_snippet_select
        )
        self.opt_snippet.set("Python Function")
        self.opt_snippet.pack(side="left", padx=4)

        btn_import = ctk.CTkButton(
            right_box,
            text="📂 Open File",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#374151",
            hover_color="#4b5563",
            width=100,
            command=self._handle_import_file
        )
        btn_import.pack(side="left", padx=4)

        btn_paste = ctk.CTkButton(
            right_box,
            text="📋 Paste",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#374151",
            hover_color="#4b5563",
            width=80,
            command=self._handle_paste_clipboard
        )
        btn_paste.pack(side="left", padx=4)

    def _create_controls_bar(self):
        """Studio control settings: speed, focus countdown, action triggers."""
        bar = ctk.CTkFrame(self, fg_color="#1f212a", corner_radius=10, border_width=1, border_color="#2b2d3c")
        bar.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 10))
        bar.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # Focus countdown
        cd_box = ctk.CTkFrame(bar, fg_color="transparent")
        cd_box.grid(row=0, column=0, sticky="w", padx=16, pady=10)
        ctk.CTkLabel(cd_box, text="Focus Switch Delay:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#d1d5db").pack(anchor="w")
        self.opt_countdown = ctk.CTkOptionMenu(
            cd_box,
            values=["3 seconds", "5 seconds", "8 seconds", "10 seconds", "1 second"],
            width=130,
            height=28
        )
        self.opt_countdown.set("5 seconds")
        self.opt_countdown.pack(anchor="w", pady=(2, 0))

        # Speed slider
        speed_box = ctk.CTkFrame(bar, fg_color="transparent")
        speed_box.grid(row=0, column=1, sticky="ew", padx=12, pady=10)
        
        lbl_sp_hdr = ctk.CTkFrame(speed_box, fg_color="transparent")
        lbl_sp_hdr.pack(fill="x")
        ctk.CTkLabel(lbl_sp_hdr, text="Typing Speed:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#d1d5db").pack(side="left")
        self.lbl_speed_val = ctk.CTkLabel(lbl_sp_hdr, text="333 ms / char (~3.0 chars/s)", font=ctk.CTkFont(size=12), text_color="#38bdf8")
        self.lbl_speed_val.pack(side="right")

        self.slider_speed = ctk.CTkSlider(
            speed_box,
            from_=50,
            to=800,
            number_of_steps=75,
            command=lambda v: self.lbl_speed_val.configure(text=f"{int(v)} ms / char (~{round(1000.0/max(1, int(v)), 1)} chars/s)")
        )
        self.slider_speed.set(333)
        self.slider_speed.pack(fill="x", pady=(4, 0))

        # Execution buttons
        btn_box = ctk.CTkFrame(bar, fg_color="transparent")
        btn_box.grid(row=0, column=2, columnspan=2, sticky="e", padx=16, pady=10)

        self.btn_start = ctk.CTkButton(
            btn_box,
            text="▶ Start Typing to Focused Window",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color="#059669",
            hover_color="#10b981",
            height=36,
            command=self._handle_start_typing
        )
        self.btn_start.pack(side="left", padx=4)

        self.btn_pause = ctk.CTkButton(
            btn_box,
            text="⏸ Pause",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color="#d97706",
            hover_color="#f59e0b",
            height=36,
            width=85,
            command=self._handle_pause,
            state="disabled"
        )
        self.btn_pause.pack(side="left", padx=4)

        self.btn_cancel = ctk.CTkButton(
            btn_box,
            text="⏹ Cancel",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color="#4b5563",
            hover_color="#6b7280",
            height=36,
            width=85,
            command=self._handle_cancel,
            state="disabled"
        )
        self.btn_cancel.pack(side="left", padx=4)

    def _create_editor_area(self):
        """Full-height code editor textbox."""
        editor_frame = ctk.CTkFrame(self, fg_color="#181920", corner_radius=10, border_width=1, border_color="#2b2d3c")
        editor_frame.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 10))
        editor_frame.grid_rowconfigure(0, weight=1)
        editor_frame.grid_columnconfigure(0, weight=1)

        self.txt_code = ctk.CTkTextbox(
            editor_frame,
            font=ctk.CTkFont(family="Consolas", size=13),
            fg_color="#0e1015",
            text_color="#e5e7eb",
            corner_radius=8,
            wrap="none",
            undo=True
        )
        self.txt_code.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        # Insert initial snippet
        self.txt_code.insert("1.0", SAMPLE_SNIPPETS["Python Function"])

    def _create_progress_footer(self):
        """Status text, live telemetry stream, and animated progress bar."""
        footer = ctk.CTkFrame(self, fg_color="#181920", corner_radius=10, border_width=1, border_color="#2b2d3c")
        footer.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 16))
        footer.grid_columnconfigure(0, weight=1)

        # Status text row
        status_row = ctk.CTkFrame(footer, fg_color="transparent")
        status_row.grid(row=0, column=0, sticky="ew", padx=16, pady=(8, 2))
        status_row.grid_columnconfigure(0, weight=1)

        self.lbl_status = ctk.CTkLabel(
            status_row,
            text="Ready. Select countdown duration, click Start, and switch to your target code editor window.",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#9ca3af"
        )
        self.lbl_status.grid(row=0, column=0, sticky="w")

        self.lbl_char_count = ctk.CTkLabel(
            status_row,
            text="0 / 0 chars (0%)",
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
            text_color="#38bdf8"
        )
        self.lbl_char_count.grid(row=0, column=1, sticky="e")

        # Telemetry preview strip
        telem_strip = ctk.CTkFrame(footer, fg_color="#121317", corner_radius=6, border_width=1, border_color="#2b2d3c")
        telem_strip.grid(row=1, column=0, sticky="ew", padx=14, pady=4)

        ctk.CTkLabel(telem_strip, text="Active Char:", font=ctk.CTkFont(size=10), text_color="#9ca3af").pack(side="left", padx=(8, 2))
        self.lbl_active_char = ctk.CTkLabel(
            telem_strip,
            text="'-'",
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
            text_color="#34d399",
            fg_color="#064e3b",
            corner_radius=4,
            padx=6
        )
        self.lbl_active_char.pack(side="left", padx=4)

        self.lbl_line_col = ctk.CTkLabel(telem_strip, text="L: 1  C: 1", font=ctk.CTkFont(family="Consolas", size=10), text_color="#38bdf8")
        self.lbl_line_col.pack(side="left", padx=8)

        self.lbl_stream_preview = ctk.CTkLabel(
            telem_strip,
            text="Ready to stream code...",
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color="#9ca3af"
        )
        self.lbl_stream_preview.pack(side="left", padx=8)

        self.lbl_wpm = ctk.CTkLabel(telem_strip, text="0.0 WPM", font=ctk.CTkFont(family="Consolas", size=10, weight="bold"), text_color="#fbbf24")
        self.lbl_wpm.pack(side="right", padx=8)

        # Progress bar
        self.code_progress_bar = ctk.CTkProgressBar(footer, height=6, progress_color="#10b981", fg_color="#374151")
        self.code_progress_bar.set(0)
        self.code_progress_bar.grid(row=2, column=0, sticky="ew", padx=14, pady=(2, 10))


    def _handle_snippet_select(self, choice: str):
        snippet = SAMPLE_SNIPPETS.get(choice, "")
        if snippet:
            self.txt_code.delete("1.0", "end")
            self.txt_code.insert("1.0", snippet)
            self.lbl_status.configure(text=f"Loaded template '{choice}'. Ready to type.", text_color="#10b981")

    def _handle_import_file(self):
        """Open file dialog to load source code."""
        file_path = filedialog.askopenfilename(
            title="Import Source Code File",
            filetypes=[
                ("Source Files", "*.py;*.js;*.ts;*.html;*.css;*.json;*.sql;*.txt;*.cpp;*.c;*.java;*.rs;*.go"),
                ("All Files", "*.*")
            ]
        )
        if file_path:
            try:
                content = Path(file_path).read_text(encoding="utf-8")
                self.txt_code.delete("1.0", "end")
                self.txt_code.insert("1.0", content)
                self.lbl_status.configure(text=f"Imported: {Path(file_path).name} ({len(content)} chars)", text_color="#10b981")
            except Exception as e:
                self.lbl_status.configure(text=f"Error reading file: {e}", text_color="#ef4444")

    def _handle_paste_clipboard(self):
        try:
            content = pyperclip.paste()
            if content:
                self.txt_code.delete("1.0", "end")
                self.txt_code.insert("1.0", content)
                self.lbl_status.configure(text=f"Pasted {len(content)} characters from clipboard.", text_color="#10b981")
        except Exception as e:
            self.lbl_status.configure(text=f"Clipboard error: {e}", text_color="#ef4444")

    def _handle_start_typing(self):
        code = self.txt_code.get("1.0", "end-1c")
        if not code:
            self.lbl_status.configure(text="Editor is empty! Paste or import code first.", text_color="#f59e0b")
            return

        cd_map = {
            "1 second": 1,
            "3 seconds": 3,
            "5 seconds": 5,
            "8 seconds": 8,
            "10 seconds": 10
        }
        countdown = cd_map.get(self.opt_countdown.get(), 5)
        base_delay = self.slider_speed.get() / 1000.0

        self._stop_event.clear()
        self._pause_event.set()
        self.btn_start.configure(state="disabled")
        self.btn_pause.configure(state="normal", text="⏸ Pause")
        self.btn_cancel.configure(state="normal")
        self.code_progress_bar.set(0)

        self._typing_thread = threading.Thread(
            target=self._code_worker,
            args=(code, countdown, base_delay),
            daemon=True
        )
        self._typing_thread.start()

    def _code_worker(self, code: str, countdown: int, base_delay: float):
        total_len = len(code)
        try:
            # Countdown
            for remaining in range(countdown, 0, -1):
                if self._stop_event.is_set():
                    self._set_ui_status("Typing aborted during countdown.", "#ef4444")
                    return
                self._set_ui_status(f"SWITCH TO TARGET CODE EDITOR! Typing starts in {remaining}s...", "#f59e0b")
                time.sleep(1.0)

            self._set_ui_status("Typing code into target editor...", "#10b981")

            def progress_cb(telemetry):
                if isinstance(telemetry, dict):
                    ch = telemetry.get("char", "")
                    disp_ch = "\\n" if ch == "\n" else ("\\t" if ch == "\t" else (ch if ch != " " else "␣"))
                    line = telemetry.get("line", 1)
                    col = telemetry.get("col", 1)
                    wpm = telemetry.get("wpm", 0.0)
                    pct = telemetry.get("pct", 0.0) / 100.0
                    current = telemetry.get("index", 0)
                    total = telemetry.get("total", total_len)
                    snip = telemetry.get("preview_snippet", "").replace("\n", "↵ ").replace("\t", "⇥ ")

                    self.after(0, lambda: self.code_progress_bar.set(pct))
                    self.after(0, lambda: self.lbl_char_count.configure(text=f"{current} / {total} chars ({int(pct*100)}%)"))
                    self.after(0, lambda: self.lbl_active_char.configure(text=f"'{disp_ch}'"))
                    self.after(0, lambda: self.lbl_line_col.configure(text=f"L: {line}  C: {col}"))
                    self.after(0, lambda: self.lbl_stream_preview.configure(text=f"...{snip}..."))
                    self.after(0, lambda: self.lbl_wpm.configure(text=f"{wpm} WPM"))
                    self.after(0, lambda: self.lbl_status.configure(
                        text=f"Streaming code • Line {line} • Char '{disp_ch}' ({wpm} WPM)",
                        text_color="#10b981"
                    ))
                else:
                    pass

            success = keyboard_ctrl.type_text(
                text=code,
                base_delay=base_delay,
                progress_callback=progress_cb,
                pause_event=self._pause_event,
                stop_event=self._stop_event
            )


            if success:
                self._set_ui_status(f"Code streaming finished! {total_len} characters written.", "#34d399")
            else:
                self._set_ui_status("Code typing stopped.", "#f59e0b")

        except Exception as e:
            self._set_ui_status(f"Error during code typing: {e}", "#ef4444")
        finally:
            self.after(0, lambda: self.btn_start.configure(state="normal"))
            self.after(0, lambda: self.btn_pause.configure(state="disabled"))
            self.after(0, lambda: self.btn_cancel.configure(state="disabled"))

    def _set_ui_status(self, text: str, color: str):
        self.after(0, lambda: self.lbl_status.configure(text=text, text_color=color))

    def _handle_pause(self):
        if self._pause_event.is_set():
            self._pause_event.clear()
            self.btn_pause.configure(text="⏯ Resume", fg_color="#2563eb", hover_color="#3b82f6")
            self._set_ui_status("Code typing paused. Click Resume to continue.", "#f59e0b")
        else:
            self._pause_event.set()
            self.btn_pause.configure(text="⏸ Pause", fg_color="#d97706", hover_color="#f59e0b")
            self._set_ui_status("Resuming code typing...", "#10b981")

    def _handle_cancel(self):
        self._stop_event.set()
        self._pause_event.set()
        self._set_ui_status("Cancelling...", "#f59e0b")
