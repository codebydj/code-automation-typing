"""
DeskPilot IDE - Center Code Editor Studio
Professional lightweight IDE editor with line numbers, syntax highlighting (Python,
JavaScript, HTML, CSS, SQL), indentation management, and target execution validation.
"""

import re
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional, Callable, Dict, Any
import customtkinter as ctk
from config import load_config, save_config

try:
    import pygments
    from pygments.lexers import (
        PythonLexer,
        JavascriptLexer,
        HtmlLexer,
        CssLexer,
        SqlLexer,
        TextLexer
    )
    from pygments.token import Token
    HAS_PYGMENTS = True
except ImportError:
    HAS_PYGMENTS = False

LEXER_MAP = {
    "Python": PythonLexer() if HAS_PYGMENTS else None,
    "JavaScript": JavascriptLexer() if HAS_PYGMENTS else None,
    "HTML": HtmlLexer() if HAS_PYGMENTS else None,
    "CSS": CssLexer() if HAS_PYGMENTS else None,
    "SQL": SqlLexer() if HAS_PYGMENTS else None,
    "Plain Text": TextLexer() if HAS_PYGMENTS else None,
}

SAMPLE_TEMPLATES = {
    "Python": (
        "# DeskPilot IDE - Python Automation Script\n"
        "def process_payload(items: list[dict], threshold: float = 0.75) -> dict:\n"
        "    \"\"\"Analyze and filter items above the score threshold.\"\"\"\n"
        "    results = {}\n"
        "    for item in items:\n"
        "        score = item.get(\"score\", 0.0)\n"
        "        if score >= threshold:\n"
        "            results[item[\"id\"]] = {\n"
        "                \"status\": \"VERIFIED\",\n"
        "                \"score\": round(score * 100, 2),\n"
        "                \"symbols\": \"{} [] () <> =+ -* &| !?\"\n"
        "            }\n"
        "    return results\n"
        "\n"
        "print(\"Automation ready!\")\n"
    ),
    "JavaScript": (
        "// DeskPilot IDE - JavaScript Async Automation\n"
        "async function fetchMetrics(endpoint, options = {}) {\n"
        "    console.log(`Connecting to ${endpoint}...`);\n"
        "    const response = await fetch(endpoint, {\n"
        "        method: 'POST',\n"
        "        headers: { 'Content-Type': 'application/json' },\n"
        "        body: JSON.stringify({ active: true, timestamp: Date.now() })\n"
        "    });\n"
        "    const data = await response.json();\n"
        "    return data.items.filter(item => item.score > 0.8);\n"
        "}\n"
    ),
    "HTML": (
        "<!DOCTYPE html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "    <meta charset=\"UTF-8\">\n"
        "    <title>DeskPilot IDE Automation</title>\n"
        "    <link rel=\"stylesheet\" href=\"style.css\">\n"
        "</head>\n"
        "<body>\n"
        "    <main class=\"container\">\n"
        "        <h1>Automated Form Submission</h1>\n"
        "        <input type=\"text\" id=\"username\" placeholder=\"Username\" />\n"
        "        <button type=\"submit\" id=\"btn-submit\">Save Data</button>\n"
        "    </main>\n"
        "</body>\n"
        "</html>\n"
    ),
    "CSS": (
        "/* DeskPilot IDE - Dark Studio Theme */\n"
        ":root {\n"
        "    --bg-primary: #1e1e1e;\n"
        "    --accent-color: #3b82f6;\n"
        "    --text-main: #d4d4d4;\n"
        "}\n"
        ".editor-container {\n"
        "    display: flex;\n"
        "    flex-direction: column;\n"
        "    padding: 1rem;\n"
        "    border-radius: 8px;\n"
        "    background-color: var(--bg-primary);\n"
        "}\n"
    ),
    "SQL": (
        "-- DeskPilot IDE - Analytical Automation Query\n"
        "SELECT \n"
        "    u.id,\n"
        "    u.username,\n"
        "    COUNT(a.id) AS total_actions,\n"
        "    ROUND(AVG(a.duration), 2) AS avg_duration\n"
        "FROM users u\n"
        "INNER JOIN audit_logs a ON u.id = a.user_id\n"
        "WHERE a.created_at >= NOW() - INTERVAL '7 DAYS'\n"
        "GROUP BY u.id, u.username\n"
        "HAVING COUNT(a.id) > 10\n"
        "ORDER BY total_actions DESC;\n"
    ),
    "Plain Text": (
        "DeskPilot IDE Automation Document\n"
        "1. Focus the target window.\n"
        "2. Stream this text at 3 characters per second.\n"
        "3. Preserve all tabs\tand special characters: [!] @ # $ % ^ & * ( )\n"
    )
}


class LineNumbersGutter(tk.Canvas):
    """Gutter canvas showing line numbers synchronized with the Text widget and active pointer."""
    def __init__(self, master, text_widget, **kwargs):
        super().__init__(master, width=46, bg="#1a1b22", bd=0, highlightthickness=0, **kwargs)
        self.text_widget = text_widget
        self.line_count = 1
        self.active_typing_line = None

    def redraw(self):
        """Redraw line numbers based on visible lines in text widget and draw typing pointer."""
        self.delete("all")
        i = self.text_widget.index("@0,0")
        while True:
            dline = self.text_widget.dlineinfo(i)
            if dline is None:
                break
            y = dline[1]
            linenum = str(i).split(".")[0]
            # If this is the active line being typed by automation, show glowing pointer!
            if self.active_typing_line is not None and str(self.active_typing_line) == linenum:
                self.create_text(
                    8, y + 2,
                    anchor="nw",
                    text="▶",
                    fill="#38bdf8",
                    font=("Consolas", 10, "bold")
                )
                self.create_text(
                    40, y + 2,
                    anchor="ne",
                    text=linenum,
                    fill="#38bdf8",
                    font=("Consolas", 11, "bold")
                )
            else:
                self.create_text(
                    40, y + 2,
                    anchor="ne",
                    text=linenum,
                    fill="#565969",
                    font=("Consolas", 11)
                )
            i = self.text_widget.index(f"{i}+1line")


class IDECodeEditor(ctk.CTkFrame):
    """
    Center IDE panel providing professional code editing, syntax coloring,
    line numbering, and target application focus controls.
    """
    def __init__(self, master, on_code_changed: Optional[Callable[[str], None]] = None, **kwargs):
        super().__init__(master, fg_color="#14151b", corner_radius=8, border_width=1, border_color="#2b2d3c", **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.on_code_changed = on_code_changed
        self.current_filename = "untitled.py"
        self.current_language = "Python"
        self._target_app = "VS Code"
        self._countdown_seconds = 3
        self._speed_cps = 3.0
        self._line_mouse_enabled = False
        editor_config = load_config().get("editor", {})
        try:
            self.indent_width = int(editor_config.get("indent_width", 4))
        except (TypeError, ValueError):
            self.indent_width = 4
        if self.indent_width not in (2, 4, 8):
            self.indent_width = 4

        self._create_editor_header()
        self._create_code_area()
        self._create_editor_footer()

        # Load initial sample
        self.set_code(SAMPLE_TEMPLATES["Python"], "main.py", "Python")

    def _create_editor_header(self):
        """Top tab strip of the editor with language and templates."""
        hdr = ctk.CTkFrame(self, fg_color="#181920", height=32, corner_radius=6)
        hdr.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 2))
        hdr.grid_columnconfigure(1, weight=1)

        # Tab badge
        self.lbl_tab = ctk.CTkLabel(
            hdr,
            text="📄 untitled.py",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#38bdf8",
            fg_color="#0f2942",
            corner_radius=4,
            width=150,
            padx=8,
            pady=2
        )
        self.lbl_tab.grid(row=0, column=0, sticky="w", padx=6, pady=2)

        # Right side: Language picker and Template loader
        r_box = ctk.CTkFrame(hdr, fg_color="transparent")
        r_box.grid(row=0, column=2, sticky="e", padx=6, pady=2)

        ctk.CTkLabel(r_box, text="Syntax:", font=ctk.CTkFont(size=11), text_color="#9ca3af").pack(side="left", padx=(0, 3))
        self.opt_lang = ctk.CTkOptionMenu(
            r_box,
            values=["Python", "JavaScript", "HTML", "CSS", "SQL", "Plain Text"],
            width=100,
            height=24,
            command=self._on_language_change
        )
        self.opt_lang.set("Python")
        self.opt_lang.pack(side="left", padx=3)

        ctk.CTkLabel(r_box, text="Template:", font=ctk.CTkFont(size=11), text_color="#9ca3af").pack(side="left", padx=(6, 3))
        self.opt_template = ctk.CTkOptionMenu(
            r_box,
            values=list(SAMPLE_TEMPLATES.keys()),
            width=105,
            height=24,
            command=self._on_template_select
        )
        self.opt_template.set("Python")
        self.opt_template.pack(side="left", padx=3)

        ctk.CTkLabel(r_box, text="Indent:", font=ctk.CTkFont(size=11), text_color="#9ca3af").pack(
            side="left", padx=(6, 3)
        )
        self.opt_indent_width = ctk.CTkOptionMenu(
            r_box,
            values=["2", "4", "8"],
            width=58,
            height=24,
            command=self._on_indent_width_change
        )
        self.opt_indent_width.set(str(self.indent_width))
        self.opt_indent_width.pack(side="left", padx=3)

    def _create_target_config_bar(self):
        """Target application confirmation bar with countdown & focus settings."""
        bar = ctk.CTkFrame(self, fg_color="#1a1c24", height=32, corner_radius=6)
        bar.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 2))
        bar.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            bar,
            text="🎯 Target:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#f3f4f6"
        ).pack(side="left", padx=(8, 4), pady=3)

        self.opt_target = ctk.CTkOptionMenu(
            bar,
            values=["VS Code", "Active Window / Manual Focus", "Notepad", "Any Window"],
            width=175,
            height=24
        )
        self.opt_target.set("VS Code")
        self.opt_target.pack(side="left", padx=3, pady=3)

        ctk.CTkLabel(
            bar,
            text="Delay:",
            font=ctk.CTkFont(size=11),
            text_color="#9ca3af"
        ).pack(side="left", padx=(8, 3), pady=3)

        self.opt_countdown = ctk.CTkOptionMenu(
            bar,
            values=["3 seconds", "5 seconds", "2 seconds", "1 second", "No countdown"],
            width=110,
            height=24
        )
        self.opt_countdown.set("3 seconds")
        self.opt_countdown.pack(side="left", padx=3, pady=3)

        # Speed indicator badge
        self.lbl_speed_badge = ctk.CTkLabel(
            bar,
            text="⚡ 3 chars/sec (333ms)",
            font=ctk.CTkFont(family="Consolas", size=10, weight="bold"),
            text_color="#10b981",
            fg_color="#064e3b",
            corner_radius=4,
            padx=6,
            pady=2
        )
        self.lbl_speed_badge.pack(side="right", padx=8, pady=3)

    def _create_compact_engine_bar(self):
        """Compact configuration section for Keyboard engine & Mouse line interaction."""
        cfg = load_config()
        typing_cfg = cfg.get("typing", {})
        mouse_cfg = cfg.get("mouse", {})
        line_cfg = mouse_cfg.get("line_interaction", {})

        eng_frame = ctk.CTkFrame(self, fg_color="#181a22", corner_radius=6, border_width=1, border_color="#2b2d3c")
        eng_frame.grid(row=2, column=0, sticky="ew", padx=6, pady=(0, 2))
        eng_frame.grid_columnconfigure(6, weight=1)

        # Row 0: Keyboard Controls
        ctk.CTkLabel(
            eng_frame, text="⌨️ Keyboard:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#38bdf8"
        ).grid(row=0, column=0, sticky="w", padx=(8, 4), pady=(3, 2))

        self.opt_timing_mode = ctk.CTkOptionMenu(
            eng_frame,
            values=["Fixed (3 CPS)", "Variable Demo"],
            width=110,
            height=22,
            font=ctk.CTkFont(size=11),
            command=self._on_timing_mode_changed
        )
        self.opt_timing_mode.set("Fixed (3 CPS)" if typing_cfg.get("timing_mode", "fixed") == "fixed" else "Variable Demo")
        self.opt_timing_mode.grid(row=0, column=1, padx=2, pady=(3, 2))

        self.opt_engine_speed = ctk.CTkOptionMenu(
            eng_frame,
            values=["3 CPS", "1 CPS", "2 CPS", "4 CPS", "5 CPS", "8 CPS", "10 CPS"],
            width=78,
            height=22,
            font=ctk.CTkFont(size=11),
            command=self._on_speed_changed
        )
        curr_speed = typing_cfg.get("speed_cps", 3)
        self.opt_engine_speed.set(f"{curr_speed} CPS")
        self.opt_engine_speed.grid(row=0, column=2, padx=2, pady=(3, 2))

        self.chk_numpad = ctk.CTkCheckBox(
            eng_frame,
            text="Numpad",
            font=ctk.CTkFont(size=11),
            checkbox_width=16,
            checkbox_height=16
        )
        if typing_cfg.get("use_numpad", False):
            self.chk_numpad.select()
        self.chk_numpad.grid(row=0, column=3, padx=4, pady=(3, 2))

        ctk.CTkLabel(eng_frame, text="Punct:", font=ctk.CTkFont(size=10), text_color="#9ca3af").grid(row=0, column=4, sticky="e", padx=(4, 1), pady=(3, 2))
        self.ent_punct_pause = ctk.CTkEntry(eng_frame, width=38, height=22, font=ctk.CTkFont(size=10))
        self.ent_punct_pause.insert(0, str(int(typing_cfg.get("punct_delay", 0.150) * 1000)))
        self.ent_punct_pause.grid(row=0, column=5, sticky="w", padx=1, pady=(3, 2))

        ctk.CTkLabel(eng_frame, text="LineEnd:", font=ctk.CTkFont(size=10), text_color="#9ca3af").grid(row=0, column=6, sticky="e", padx=(4, 1), pady=(3, 2))
        self.ent_line_pause = ctk.CTkEntry(eng_frame, width=38, height=22, font=ctk.CTkFont(size=10))
        self.ent_line_pause.insert(0, str(int(typing_cfg.get("newline_delay", 0.250) * 1000)))
        self.ent_line_pause.grid(row=0, column=7, sticky="w", padx=1, pady=(3, 2))

        self.btn_preview_sequence = ctk.CTkButton(
            eng_frame,
            text="👁 Preview Sequence",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#1e3a8a",
            hover_color="#2563eb",
            text_color="#93c5fd",
            height=22,
            width=125,
            command=self.show_sequence_preview
        )
        self.btn_preview_sequence.grid(row=0, column=8, padx=(6, 6), pady=(3, 2))

        # Row 1: Mouse Controls
        ctk.CTkLabel(
            eng_frame, text="🖱️ Mouse:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#38bdf8"
        ).grid(row=1, column=0, sticky="w", padx=(8, 4), pady=(2, 3))

        self.chk_line_mouse = ctk.CTkCheckBox(
            eng_frame,
            text="Between Lines",
            font=ctk.CTkFont(size=11),
            checkbox_width=16,
            checkbox_height=16
        )
        if line_cfg.get("enabled", False):
            self.chk_line_mouse.select()
        self.chk_line_mouse.grid(row=1, column=1, sticky="w", padx=2, pady=(2, 3))

        int_box = ctk.CTkFrame(eng_frame, fg_color="transparent")
        int_box.grid(row=1, column=2, sticky="w", padx=1, pady=(2, 3))
        ctk.CTkLabel(int_box, text="Lines:", font=ctk.CTkFont(size=10), text_color="#9ca3af").pack(side="left", padx=(0, 1))
        self.ent_min_lines = ctk.CTkEntry(int_box, width=24, height=22, font=ctk.CTkFont(size=10))
        self.ent_min_lines.insert(0, str(line_cfg.get("min_lines", 2)))
        self.ent_min_lines.pack(side="left", padx=1)
        ctk.CTkLabel(int_box, text="-", font=ctk.CTkFont(size=10), text_color="#9ca3af").pack(side="left")
        self.ent_max_lines = ctk.CTkEntry(int_box, width=24, height=22, font=ctk.CTkFont(size=10))
        self.ent_max_lines.insert(0, str(line_cfg.get("max_lines", 5)))
        self.ent_max_lines.pack(side="left", padx=1)

        self.opt_mouse_profile = ctk.CTkOptionMenu(
            eng_frame,
            values=["Curved (Bézier)", "Smooth (Eased)", "Direct (Linear)"],
            width=105,
            height=22,
            font=ctk.CTkFont(size=11)
        )
        prof_val = line_cfg.get("movement_profile", mouse_cfg.get("movement_profile", "curved"))
        if "direct" in prof_val:
            self.opt_mouse_profile.set("Direct (Linear)")
        elif "smooth" in prof_val or "eased" in prof_val:
            self.opt_mouse_profile.set("Smooth (Eased)")
        else:
            self.opt_mouse_profile.set("Curved (Bézier)")
        self.opt_mouse_profile.grid(row=1, column=3, padx=2, pady=(2, 3))

        coord_box = ctk.CTkFrame(eng_frame, fg_color="transparent")
        coord_box.grid(row=1, column=4, columnspan=3, sticky="w", padx=1, pady=(2, 3))
        ctk.CTkLabel(coord_box, text="Target:", font=ctk.CTkFont(size=10), text_color="#9ca3af").pack(side="left", padx=(0, 1))
        self.ent_target_x = ctk.CTkEntry(coord_box, width=36, height=22, font=ctk.CTkFont(size=10))
        self.ent_target_x.insert(0, str(line_cfg.get("target_x", 600)))
        self.ent_target_x.pack(side="left", padx=1)
        self.ent_target_y = ctk.CTkEntry(coord_box, width=36, height=22, font=ctk.CTkFont(size=10))
        self.ent_target_y.insert(0, str(line_cfg.get("target_y", 450)))
        self.ent_target_y.pack(side="left", padx=1)

        btn_pick = ctk.CTkButton(
            coord_box,
            text="🎯 Pick",
            width=42,
            height=22,
            font=ctk.CTkFont(size=10),
            fg_color="#334155",
            hover_color="#475569",
            command=self._on_pick_cursor_coordinates
        )
        btn_pick.pack(side="left", padx=(2, 1))

        self.chk_mouse_click = ctk.CTkCheckBox(
            eng_frame,
            text="Click Safe Point",
            font=ctk.CTkFont(size=11),
            checkbox_width=16,
            checkbox_height=16
        )
        if line_cfg.get("click_enabled", False):
            self.chk_mouse_click.select()
        self.chk_mouse_click.grid(row=1, column=7, columnspan=2, sticky="w", padx=4, pady=(2, 3))

    def _on_timing_mode_changed(self, mode: str):
        if mode.startswith("Fixed"):
            self.lbl_speed_badge.configure(text="⚡ 3 chars/sec (333ms)", fg_color="#064e3b", text_color="#10b981")
        else:
            self.lbl_speed_badge.configure(text="🎭 Variable Demo Mode", fg_color="#1e3a8a", text_color="#93c5fd")
        self.calculate_estimated_time(show_dialog=False)

    def _on_speed_changed(self, speed_str: str):
        cps = speed_str.split()[0]
        try:
            ms = int(1000.0 / float(cps))
            self.lbl_speed_badge.configure(text=f"⚡ {cps} chars/sec ({ms}ms)")
        except Exception:
            pass
        self.calculate_estimated_time(show_dialog=False)

    def _on_pick_cursor_coordinates(self):
        try:
            from automation.mouse_controller import mouse_ctrl
            x, y = mouse_ctrl.get_position()
            self.ent_target_x.delete(0, tk.END)
            self.ent_target_x.insert(0, str(x))
            self.ent_target_y.delete(0, tk.END)
            self.ent_target_y.insert(0, str(y))
        except Exception:
            pass

    def _create_code_area(self):
        """Create code area with line numbers gutter and monospace editor."""
        code_container = tk.Frame(self, bg="#14151b", bd=0)
        code_container.grid(row=1, column=0, sticky="nsew", padx=8, pady=2)
        code_container.grid_columnconfigure(1, weight=1)
        code_container.grid_rowconfigure(0, weight=1)

        # Gutter
        self.text_widget = tk.Text(
            code_container,
            wrap="none",
            undo=True,
            font=("Consolas", 12),
            bg="#14151b",
            fg="#e5e7eb",
            insertbackground="#38bdf8",
            selectbackground="#264f78",
            selectforeground="#ffffff",
            bd=0,
            padx=8,
            pady=6
        )

        self.gutter = LineNumbersGutter(code_container, self.text_widget)
        self.gutter.grid(row=0, column=0, sticky="ns")

        # Scrollbars
        v_scroll = ttk.Scrollbar(code_container, orient="vertical", command=self._on_v_scroll)
        v_scroll.grid(row=0, column=2, sticky="ns")
        h_scroll = ttk.Scrollbar(code_container, orient="horizontal", command=self.text_widget.xview)
        h_scroll.grid(row=1, column=1, sticky="ew")

        self.text_widget.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
        self.text_widget.grid(row=0, column=1, sticky="nsew")

        # Configure syntax tags
        self._setup_syntax_tags()

        # Bind events
        self.text_widget.bind("<KeyRelease>", self._on_text_modified)
        self.text_widget.bind("<ButtonRelease>", self._on_cursor_moved)
        self.text_widget.bind("<Tab>", self._handle_tab)
        self.text_widget.bind("<Shift-Tab>", self._handle_shift_tab)
        self.text_widget.bind("<Return>", self._handle_return)
        self.text_widget.bind("<Control-a>", self._handle_select_all)
        self.text_widget.bind("<Control-A>", self._handle_select_all)

    def _on_v_scroll(self, *args):
        self.text_widget.yview(*args)
        self.gutter.redraw()

    def _setup_syntax_tags(self):
        """Define colors for syntax tokens and live typing pointer."""
        self.text_widget.tag_configure("token_keyword", foreground="#c084fc", font=("Consolas", 12, "bold"))
        self.text_widget.tag_configure("token_name_func", foreground="#60a5fa", font=("Consolas", 12, "bold"))
        self.text_widget.tag_configure("token_name_class", foreground="#38bdf8", font=("Consolas", 12, "bold"))
        self.text_widget.tag_configure("token_string", foreground="#34d399")
        self.text_widget.tag_configure("token_comment", foreground="#6b7280", font=("Consolas", 12, "italic"))
        self.text_widget.tag_configure("token_number", foreground="#fbbf24")
        self.text_widget.tag_configure("token_operator", foreground="#f472b6")
        self.text_widget.tag_configure("token_builtin", foreground="#2dd4bf")

        # Live typing pointer tags
        self.text_widget.tag_configure("typing_line", background="#1e293b")
        self.text_widget.tag_configure("typing_cursor", background="#2563eb", foreground="#ffffff")
        self.text_widget.tag_raise("typing_line")
        self.text_widget.tag_raise("typing_cursor")

    def _create_editor_footer(self):
        """Bottom status strip showing cursor position, statistics, live pointer, and estimated completion time."""
        ftr = ctk.CTkFrame(self, fg_color="#181920", height=24, corner_radius=4)
        ftr.grid(row=2, column=0, sticky="ew", padx=6, pady=(2, 4))

        self.lbl_pos = ctk.CTkLabel(
            ftr,
            text="Ln 1, Col 1",
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color="#9ca3af"
        )
        self.lbl_pos.pack(side="left", padx=6)

        self.lbl_stats = ctk.CTkLabel(
            ftr,
            text="0 chars • 1 line",
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color="#9ca3af"
        )
        self.lbl_stats.pack(side="left", padx=6)

        self.lbl_current_line = ctk.CTkLabel(
            ftr,
            text="▶ Pointer: Idle",
            font=ctk.CTkFont(family="Consolas", size=10, weight="bold"),
            text_color="#38bdf8"
        )
        self.lbl_current_line.pack(side="left", padx=8)

        # Right side: Encoding, Time badge, and Calculate button
        self.lbl_encoding = ctk.CTkLabel(
            ftr,
            text=f"UTF-8 • Spaces: {self.indent_width}",
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color="#64748b"
        )
        self.lbl_encoding.pack(side="right", padx=6)

        self.lbl_est_time = ctk.CTkLabel(
            ftr,
            text="⏱ Est. Time: 00:00:00",
            font=ctk.CTkFont(family="Consolas", size=10, weight="bold"),
            fg_color="#064e3b",
            text_color="#34d399",
            corner_radius=4,
            padx=6,
            pady=1
        )
        self.lbl_est_time.pack(side="right", padx=4)

        self.btn_calc_time = ctk.CTkButton(
            ftr,
            text="⏱ Calculate Time",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color="#1e293b",
            hover_color="#334155",
            text_color="#38bdf8",
            width=105,
            height=20,
            corner_radius=4,
            command=lambda: self.calculate_estimated_time(show_dialog=True)
        )
        self.btn_calc_time.pack(side="right", padx=4)

    def _on_text_modified(self, event=None):
        self.gutter.redraw()
        self._update_cursor_info()
        self.apply_syntax_highlighting()
        if self.on_code_changed:
            self.on_code_changed(self.get_code())

    def _on_cursor_moved(self, event=None):
        self._update_cursor_info()

    def _update_cursor_info(self):
        cursor_pos = self.text_widget.index(tk.INSERT)
        line, col = cursor_pos.split(".")
        code = self.get_code()
        chars = len(code)
        lines = code.count("\n") + 1
        self.lbl_pos.configure(text=f"Ln {line}, Col {int(col) + 1}")
        self.lbl_stats.configure(text=f"{chars} chars • {lines} lines")
        # Automatically update the estimated completion time in HH:MM:SS
        self.calculate_estimated_time(show_dialog=False)

    def calculate_estimated_time(self, show_dialog: bool = False) -> str:
        """
        Calculate realistic estimated time (HH:MM:SS) to type the code using
        the central timing controller, character difficulty, and line mouse movement.
        """
        code = self.get_code()
        if not code or not code.strip():
            time_str = "00:00:00"
            if hasattr(self, "lbl_est_time"):
                self.lbl_est_time.configure(text=f"⏱ Est. Time: {time_str}")
            return time_str

        from automation.timing_controller import timing_controller

        target_cfg = self.get_target_config()
        speed_cps = float(target_cfg.get("speed_cps", getattr(self, "_speed_cps", 3.0)))
        countdown = int(target_cfg.get("countdown_seconds", getattr(self, "_countdown_seconds", 3)))
        mouse_enabled = bool(target_cfg.get("line_mouse_enabled", getattr(self, "_line_mouse_enabled", True)))
        use_diff = getattr(self, "_use_difficulty", True)
        rand_pause_enabled = bool(target_cfg.get("random_pause_enabled", getattr(self, "_random_pause_enabled", True)))

        total_seconds, time_str = timing_controller.calculate_sequence_estimate(
            text=code,
            cps=speed_cps,
            countdown_seconds=countdown,
            mouse_move_enabled=mouse_enabled,
            use_difficulty=use_diff,
            random_pause_enabled=rand_pause_enabled
        )

        if hasattr(self, "lbl_est_time"):
            self.lbl_est_time.configure(text=f"⏱ Est. Time: {time_str}")

        if show_dialog:
            try:
                from tkinter import messagebox
                chars = len(code)
                lines = code.count("\n") + 1
                mode_desc = "Dynamic Character Difficulty" if use_diff else "Fixed CPS (Steady)"
                msg = (
                    f"Code Statistics & Estimated Completion Time:\n\n"
                    f"• Total Characters: {chars}\n"
                    f"• Total Lines: {lines}\n"
                    f"• Mode: {mode_desc}\n"
                    f"• Base Speed: {speed_cps:.1f} CPS\n"
                    f"• Mouse Movement After Lines: {'Enabled' if mouse_enabled else 'Disabled'}\n"
                    f"• Startup Countdown: {countdown} seconds\n\n"
                    f"⏱ Estimated Total Time: {time_str} ({total_seconds} seconds)"
                )
                messagebox.showinfo("Estimated Completion Time", msg, parent=self)
            except Exception:
                pass

        return time_str

    def _handle_tab(self, event):
        """Insert the selected number of spaces for consistent code indentation."""
        self.text_widget.insert(tk.INSERT, self._indent_unit())
        self._on_text_modified()
        return "break"

    def _indent_unit(self) -> str:
        return " " * self.indent_width

    def _on_indent_width_change(self, value: str):
        self.indent_width = int(value)
        config_data = load_config()
        config_data.setdefault("editor", {})["indent_width"] = self.indent_width
        if not save_config(config_data):
            messagebox.showerror("Settings Error", "Could not save the editor indentation width.", parent=self)
        self.lbl_encoding.configure(text=f"UTF-8 • Spaces: {self.indent_width}")

    def _handle_shift_tab(self, event):
        """Dedent current line or selection."""
        # Simple dedent of current line
        line = self.text_widget.index(tk.INSERT).split(".")[0]
        line_start = f"{line}.0"
        content = self.text_widget.get(line_start, f"{line}.end")
        leading_spaces = len(content) - len(content.lstrip(" "))
        spaces_to_remove = min(self.indent_width, leading_spaces)
        if spaces_to_remove:
            self.text_widget.delete(line_start, f"{line}.{spaces_to_remove}")
        self._on_text_modified()
        return "break"

    def _handle_return(self, event):
        """Auto-indent on enter key."""
        curr_line = self.text_widget.get("insert linestart", "insert")
        indent = re.match(r"^(\s*)", curr_line).group(1)
        # Extra indent after colon in Python
        if curr_line.strip().endswith(":"):
            indent += self._indent_unit()
        self.text_widget.insert(tk.INSERT, "\n" + indent)
        self.text_widget.see(tk.INSERT)
        self._on_text_modified()
        return "break"

    def _handle_select_all(self, event):
        self.text_widget.tag_add("sel", "1.0", "end")
        return "break"

    def _on_language_change(self, choice: str):
        self.current_language = choice
        ext_map = {"Python": ".py", "JavaScript": ".js", "HTML": ".html", "CSS": ".css", "SQL": ".sql", "Plain Text": ".txt"}
        base = self.current_filename.rsplit(".", 1)[0]
        self.current_filename = base + ext_map.get(choice, ".txt")
        self.lbl_tab.configure(text=f"📄 {self.current_filename}")
        self.apply_syntax_highlighting()

    def _on_template_select(self, choice: str):
        if choice in SAMPLE_TEMPLATES:
            self.set_code(SAMPLE_TEMPLATES[choice], f"sample_{choice.lower().replace(' ', '_')}.py", choice)

    def apply_syntax_highlighting(self):
        """Apply syntax highlighting tags using pygments if available."""
        if not HAS_PYGMENTS:
            return

        lexer = LEXER_MAP.get(self.current_language)
        if not lexer:
            return

        code = self.get_code()
        # Remove existing tokens
        for tag in ["token_keyword", "token_name_func", "token_name_class", "token_string",
                    "token_comment", "token_number", "token_operator", "token_builtin"]:
            self.text_widget.tag_remove(tag, "1.0", "end")

        try:
            tokens = list(pygments.lex(code, lexer))
            index = "1.0"
            for ttype, value in tokens:
                end_index = self.text_widget.index(f"{index}+{len(value)}c")
                tag_name = None
                if ttype in Token.Keyword:
                    tag_name = "token_keyword"
                elif ttype in Token.Name.Function:
                    tag_name = "token_name_func"
                elif ttype in Token.Name.Class:
                    tag_name = "token_name_class"
                elif ttype in Token.Name.Builtin:
                    tag_name = "token_builtin"
                elif ttype in Token.Literal.String:
                    tag_name = "token_string"
                elif ttype in Token.Comment:
                    tag_name = "token_comment"
                elif ttype in Token.Literal.Number:
                    tag_name = "token_number"
                elif ttype in Token.Operator:
                    tag_name = "token_operator"

                if tag_name:
                    self.text_widget.tag_add(tag_name, index, end_index)
                index = end_index
        except Exception:
            pass

    def get_code(self) -> str:
        """Get the current editor text content."""
        return self.text_widget.get("1.0", "end-1c")

    def set_code(self, code: str, filename: Optional[str] = None, language: Optional[str] = None):
        """Set the editor text content and update highlighting."""
        self.text_widget.delete("1.0", "end")
        self.text_widget.insert("1.0", code)
        if filename:
            self.current_filename = filename
            self.lbl_tab.configure(text=f"📄 {filename}")
        if language:
            self.current_language = language
            self.opt_lang.set(language)
            self.opt_template.set(language)
        self.gutter.redraw()
        self._update_cursor_info()
        self.apply_syntax_highlighting()
        self.clear_typing_pointer()
        if self.on_code_changed:
            self.on_code_changed(code)

    def show_typing_pointer(self, line_num: int, col_num: int, char: str = ""):
        """Highlight current line and character pointer where typing is actively occurring."""
        try:
            self.gutter.active_typing_line = line_num
            self.gutter.redraw()

            # Remove previous typing highlights
            self.text_widget.tag_remove("typing_line", "1.0", "end")
            self.text_widget.tag_remove("typing_cursor", "1.0", "end")

            # Highlight current line
            line_start = f"{line_num}.0"
            line_end = f"{line_num}.end"
            self.text_widget.tag_add("typing_line", line_start, line_end)

            # Highlight exact character
            c_idx = max(0, col_num - 1)
            char_pos = f"{line_num}.{c_idx}"
            char_end = f"{line_num}.{c_idx + 1}"
            self.text_widget.tag_add("typing_cursor", char_pos, char_end)

            # Auto-scroll so current line is visible in editor
            self.text_widget.see(f"{line_num}.0")

            disp_char = repr(char)[1:-1] if char else " "
            self.lbl_current_line.configure(
                text=f"▶ Typing: Ln {line_num}, Col {col_num} ('{disp_char}')",
                text_color="#38bdf8"
            )
        except Exception:
            pass

    def clear_typing_pointer(self):
        """Clear typing line/cursor pointer when automation stops or is idle."""
        try:
            if hasattr(self, "gutter"):
                self.gutter.active_typing_line = None
                self.gutter.redraw()
            if hasattr(self, "text_widget"):
                self.text_widget.tag_remove("typing_line", "1.0", "end")
                self.text_widget.tag_remove("typing_cursor", "1.0", "end")
            if hasattr(self, "lbl_current_line"):
                self.lbl_current_line.configure(text="▶ Pointer: Idle", text_color="#9ca3af")
        except Exception:
            pass

    def get_cursor_line(self) -> int:
        """Return the 1-based line number of the text insertion cursor."""
        try:
            return int(self.text_widget.index(tk.INSERT).split(".")[0])
        except Exception:
            return 1

    def get_cursor_char_offset(self) -> int:
        """Return the 0-based character offset of the text insertion cursor."""
        try:
            idx = self.text_widget.index(tk.INSERT)
            return len(self.text_widget.get("1.0", idx))
        except Exception:
            return 0

    def clear_typing_pointer(self):
        """Reset live cursor tags, line gutter pointer, and idle status."""
        try:
            self.text_widget.tag_remove("typing_line", "1.0", "end")
            self.text_widget.tag_remove("typing_cursor", "1.0", "end")
            self.gutter.active_typing_line = None
            self.gutter.redraw()
            if hasattr(self, "lbl_current_line"):
                self.lbl_current_line.configure(text="▶ Pointer: Idle", text_color="#38bdf8")
        except Exception:
            pass

    def update_live_typing(self, char: str, line_num: int, col_num: int, text_so_far: str = ""):
        """Update the live typing label with the current character being typed."""
        self.show_typing_pointer(line_num, col_num, char)

    def get_target_config(self) -> Dict[str, Any]:
        """Return configured target app, typing cadence, and mouse coordination parameters."""
        cd_map = {
            "3 seconds": 3,
            "5 seconds": 5,
            "2 seconds": 2,
            "1 second": 1,
            "No countdown": 0
        }

        target_app = (
            self.opt_target.get()
            if hasattr(self, "opt_target")
            else getattr(self, "_target_app", "VS Code")
        )
        countdown_seconds = (
            cd_map.get(self.opt_countdown.get(), 3)
            if hasattr(self, "opt_countdown")
            else getattr(self, "_countdown_seconds", 3)
        )

        # Parse speed from dropdown (e.g. "3 CPS" -> 3.0)
        speed_cps = getattr(self, "_speed_cps", 3.0)
        if hasattr(self, "opt_engine_speed"):
            try:
                speed_cps = float(self.opt_engine_speed.get().split()[0])
            except (ValueError, IndexError):
                speed_cps = 3.0

        is_fixed = True
        if hasattr(self, "opt_timing_mode"):
            is_fixed = self.opt_timing_mode.get().startswith("Fixed")
        timing_mode = "fixed" if is_fixed else "variable"

        use_numpad = False
        if hasattr(self, "chk_numpad"):
            use_numpad = bool(self.chk_numpad.get())

        punct_delay = 0.150
        if hasattr(self, "ent_punct_pause"):
            try:
                punct_delay = max(0.0, float(self.ent_punct_pause.get()) / 1000.0)
            except ValueError:
                punct_delay = 0.150

        newline_delay = 0.250
        if hasattr(self, "ent_line_pause"):
            try:
                newline_delay = max(0.0, float(self.ent_line_pause.get()) / 1000.0)
            except ValueError:
                newline_delay = 0.250

        line_mouse_enabled = getattr(self, "_line_mouse_enabled", False)
        if hasattr(self, "chk_line_mouse"):
            line_mouse_enabled = bool(self.chk_line_mouse.get())

        min_lines, max_lines = 1, 1
        if hasattr(self, "ent_min_lines") and hasattr(self, "ent_max_lines"):
            try:
                min_lines = max(1, int(self.ent_min_lines.get()))
                max_lines = max(min_lines, int(self.ent_max_lines.get()))
            except ValueError:
                min_lines, max_lines = 1, 1

        movement_profile = "curved"
        if hasattr(self, "opt_mouse_profile"):
            prof = self.opt_mouse_profile.get().lower()
            if "direct" in prof:
                movement_profile = "direct"
            elif "smooth" in prof or "eased" in prof:
                movement_profile = "smooth"
            else:
                movement_profile = "curved"

        mouse_x, mouse_y = 600, 450
        if hasattr(self, "ent_target_x") and hasattr(self, "ent_target_y"):
            try:
                mouse_x = int(self.ent_target_x.get())
                mouse_y = int(self.ent_target_y.get())
            except ValueError:
                mouse_x, mouse_y = 600, 450

        click_enabled = False
        if hasattr(self, "chk_mouse_click"):
            click_enabled = bool(self.chk_mouse_click.get())

        return {
            "target_app": target_app,
            "countdown_seconds": countdown_seconds,
            "speed_cps": speed_cps,
            "exact_speed": is_fixed,
            "timing_mode": timing_mode,
            "use_numpad": use_numpad,
            "punct_delay": punct_delay,
            "newline_delay": newline_delay,
            "line_mouse_enabled": line_mouse_enabled,
            "min_lines": min_lines,
            "max_lines": max_lines,
            "movement_profile": movement_profile,
            "mouse_target_x": mouse_x,
            "mouse_target_y": mouse_y,
            "mouse_click_enabled": click_enabled,
            "indent_width": self.indent_width
        }

    def show_sequence_preview(self):
        """Display an action sequence preview modal before starting automation."""
        cfg = self.get_target_config()
        code = self.get_code()
        chars = len(code)
        lines = code.count("\n") + 1
        non_empty_lines = len([l for l in code.split("\n") if l.strip()])

        # Tally character categories
        from automation.character_mapper import character_mapper, CharacterCategory
        cat_counts: Dict[str, int] = {}
        for ch in code:
            cat = character_mapper.get_category(ch)
            cat_counts[cat.value] = cat_counts.get(cat.value, 0) + 1

        speed_cps = cfg["speed_cps"]
        timing_mode = cfg["timing_mode"]
        est_seconds = chars / max(0.1, speed_cps)
        if timing_mode == "variable":
            est_seconds *= 1.25
        est_mins = int(est_seconds // 60)
        est_secs = int(est_seconds % 60)
        time_display = f"{est_mins:02d}:{est_secs:02d}"

        # Create modal window
        win = ctk.CTkToplevel(self)
        win.title("DeskPilot – Action Sequence Preview")
        win.geometry("580x560")
        win.resizable(False, False)
        win.transient(self.winfo_toplevel())

        # Header
        hdr = ctk.CTkFrame(win, fg_color="#181a24", corner_radius=8)
        hdr.pack(fill="x", padx=14, pady=(14, 8))
        ctk.CTkLabel(
            hdr,
            text="👁 Configured Action Sequence Preview",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color="#38bdf8"
        ).pack(anchor="w", padx=12, pady=(10, 2))
        ctk.CTkLabel(
            hdr,
            text="Review typing parameters, character breakdown, and mouse actions before execution.",
            font=ctk.CTkFont(size=11),
            text_color="#9ca3af"
        ).pack(anchor="w", padx=12, pady=(0, 10))

        # Body container
        body = ctk.CTkScrollableFrame(win, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=14, pady=4)

        # Card 1: Target & General Specs
        c1 = ctk.CTkFrame(body, fg_color="#181920", corner_radius=8, border_width=1, border_color="#2b2d3c")
        c1.pack(fill="x", pady=4)
        ctk.CTkLabel(c1, text="🎯 Execution Target & Cadence", font=ctk.CTkFont(size=12, weight="bold"), text_color="#f3f4f6").pack(anchor="w", padx=10, pady=(8, 4))
        
        info_txt = (
            f"• Target Window: {cfg['target_app']}\n"
            f"• Countdown Delay: {cfg['countdown_seconds']} seconds\n"
            f"• Total Payload: {chars} characters across {lines} lines ({non_empty_lines} non-empty)\n"
            f"• Typing Cadence: {speed_cps:.1f} CPS ({int(1000/speed_cps)}ms/char) • Mode: {timing_mode.upper()}\n"
            f"• Estimated Duration: ~{time_display} (MM:SS)"
        )
        ctk.CTkLabel(c1, text=info_txt, font=ctk.CTkFont(family="Consolas", size=11), text_color="#cbd5e1", justify="left").pack(anchor="w", padx=14, pady=(0, 8))

        # Card 2: Character Categories
        c2 = ctk.CTkFrame(body, fg_color="#181920", corner_radius=8, border_width=1, border_color="#2b2d3c")
        c2.pack(fill="x", pady=4)
        ctk.CTkLabel(c2, text="🔤 Character Category Distribution", font=ctk.CTkFont(size=12, weight="bold"), text_color="#f3f4f6").pack(anchor="w", padx=10, pady=(8, 4))

        cat_txt = (
            f"• Lowercase Alphabetic: {cat_counts.get(CharacterCategory.ALPHABETIC_LOWER.value, 0)}\n"
            f"• Uppercase Alphabetic (Shift handled): {cat_counts.get(CharacterCategory.ALPHABETIC_UPPER.value, 0)}\n"
            f"• Numeric Digits (Numpad={'Yes' if cfg['use_numpad'] else 'No'}): {cat_counts.get(CharacterCategory.NUMERIC_ROW.value, 0) + cat_counts.get(CharacterCategory.NUMERIC_PAD.value, 0)}\n"
            f"• Programming Symbols & Operators: {cat_counts.get(CharacterCategory.SPECIAL_SYMBOL.value, 0)}\n"
            f"• Whitespace & Indentation: {cat_counts.get(CharacterCategory.WHITESPACE.value, 0)}\n"
            f"• Newlines: {cat_counts.get(CharacterCategory.NEWLINE.value, 0)}"
        )
        ctk.CTkLabel(c2, text=cat_txt, font=ctk.CTkFont(family="Consolas", size=11), text_color="#cbd5e1", justify="left").pack(anchor="w", padx=14, pady=(0, 8))

        # Card 3: Mouse Line Interaction
        c3 = ctk.CTkFrame(body, fg_color="#181920", corner_radius=8, border_width=1, border_color="#2b2d3c")
        c3.pack(fill="x", pady=4)
        ctk.CTkLabel(c3, text="🖱️ Line-Interval Mouse Interactivity", font=ctk.CTkFont(size=12, weight="bold"), text_color="#f3f4f6").pack(anchor="w", padx=10, pady=(8, 4))

        if cfg["line_mouse_enabled"]:
            mouse_txt = (
                f"• Status: ENABLED (triggers every {cfg['min_lines']} to {cfg['max_lines']} lines)\n"
                f"• Safe Target Coordinate: ({cfg['mouse_target_x']}, {cfg['mouse_target_y']})\n"
                f"• Kinematic Profile: {cfg['movement_profile'].capitalize()}\n"
                f"• Safe Click Action: {'Enabled' if cfg['mouse_click_enabled'] else 'Disabled (move only)'}\n"
                f"• Focus Recovery: Editor focus restored automatically after mouse move"
            )
        else:
            mouse_txt = "• Status: DISABLED (continuous uninterrupted typing)"
        ctk.CTkLabel(c3, text=mouse_txt, font=ctk.CTkFont(family="Consolas", size=11), text_color="#cbd5e1", justify="left").pack(anchor="w", padx=14, pady=(0, 8))

        # Footer button
        btn_close = ctk.CTkButton(
            win,
            text="Close Preview",
            fg_color="#334155",
            hover_color="#475569",
            command=win.destroy
        )
        btn_close.pack(pady=(6, 12))
