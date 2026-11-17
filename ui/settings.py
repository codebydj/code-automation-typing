"""
DeskPilot - Settings Panel
Manages persistent user configuration for typing micro-delays, mouse dynamics,
safety fail-safes, emergency stop hotkeys, and application appearance.
"""

from tkinter import messagebox
import math
import customtkinter as ctk
from config import load_config, save_config, DEFAULT_CONFIG
from automation.safety import safety
from automation.hotkey_manager import normalize_hotkey
from utils.logger import logger


class SettingsPanel(ctk.CTkFrame):
    """Configuration management panel."""

    def __init__(self, master, on_theme_change=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.on_theme_change = on_theme_change
        self.config_data = load_config()

        self._create_header()
        self._create_settings_body()
        self._create_footer_actions()

    def _create_header(self):
        hdr = ctk.CTkFrame(self, fg_color="#181920", corner_radius=10, border_width=1, border_color="#2b2d3c")
        hdr.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 10))
        hdr.grid_columnconfigure(0, weight=1)

        left = ctk.CTkFrame(hdr, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w", padx=16, pady=12)

        lbl_title = ctk.CTkLabel(
            left,
            text="⚙️ Application Configuration & Preferences",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color="#f3f4f6"
        )
        lbl_title.pack(anchor="w")

        lbl_sub = ctk.CTkLabel(
            left,
            text="Set typing cadence, action pauses, mouse controls, fail-safes, and hotkeys.",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#9ca3af"
        )
        lbl_sub.pack(anchor="w")

    def _create_settings_body(self):
        """Scrollable area containing categorized settings cards."""
        self.scroll_body = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            corner_radius=0
        )
        self.scroll_body.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 10))
        self.scroll_body.grid_columnconfigure((0, 1), weight=1)

        # Left Column: Keyboard & Mouse
        self._build_typing_card(col=0, row=0)
        self._build_mouse_card(col=0, row=1)

        # Right Column: Safety & Appearance
        self._build_safety_card(col=1, row=0)
        self._build_appearance_card(col=1, row=1)

        # Row 2 (Full Width): Global Hotkeys
        self._build_hotkeys_card(col=0, row=2)

    def _build_typing_card(self, col: int, row: int):
        card = ctk.CTkFrame(self.scroll_body, fg_color="#181920", corner_radius=10, border_width=1, border_color="#2b2d3c")
        card.grid(row=row, column=col, sticky="nsew", padx=(0, 8), pady=8)
        card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(card, text="⌨️ Natural Typing Engine & Rhythm", font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"), text_color="#f3f4f6").grid(row=0, column=0, columnspan=2, sticky="w", padx=14, pady=(12, 8))

        typing_cfg = self.config_data.get("typing", {})
        execution_cfg = self.config_data.get("execution", {})

        ctk.CTkLabel(card, text="Typing Speed (CPS, 1–30):").grid(row=1, column=0, sticky="w", padx=14, pady=4)
        self.ent_speed_cps = ctk.CTkEntry(card, width=90)
        self.ent_speed_cps.insert(0, str(typing_cfg.get("speed_cps", 3)))
        self.ent_speed_cps.grid(row=1, column=1, sticky="e", padx=14, pady=4)

        ctk.CTkLabel(card, text="Cadence Timing Mode:").grid(row=2, column=0, sticky="w", padx=14, pady=4)
        self.opt_timing_mode = ctk.CTkOptionMenu(card, values=["fixed", "variable"], width=110)
        self.opt_timing_mode.set(typing_cfg.get("timing_mode", "fixed"))
        self.opt_timing_mode.grid(row=2, column=1, sticky="e", padx=14, pady=4)

        ctk.CTkLabel(card, text="Punctuation Pause (ms):").grid(row=3, column=0, sticky="w", padx=14, pady=4)
        self.ent_punct_delay = ctk.CTkEntry(card, width=90)
        self.ent_punct_delay.insert(0, str(int(typing_cfg.get("punct_delay", 0.150) * 1000)))
        self.ent_punct_delay.grid(row=3, column=1, sticky="e", padx=14, pady=4)

        ctk.CTkLabel(card, text="Line-Ending Pause (ms):").grid(row=4, column=0, sticky="w", padx=14, pady=4)
        self.ent_newline_delay = ctk.CTkEntry(card, width=90)
        self.ent_newline_delay.insert(0, str(int(typing_cfg.get("newline_delay", 0.250) * 1000)))
        self.ent_newline_delay.grid(row=4, column=1, sticky="e", padx=14, pady=4)

        ctk.CTkLabel(card, text="Default Pause Between Tasks (ms):").grid(row=5, column=0, sticky="w", padx=14, pady=4)
        self.ent_action_pause_ms = ctk.CTkEntry(card, width=90)
        self.ent_action_pause_ms.insert(0, str(int(float(execution_cfg.get("default_action_pause", 0.1)) * 1000)))
        self.ent_action_pause_ms.grid(row=5, column=1, sticky="e", padx=14, pady=4)

        self.chk_numpad = ctk.CTkCheckBox(card, text="Use Number Pad for digits (Numpad 0–9)")
        if typing_cfg.get("use_numpad", False):
            self.chk_numpad.select()
        self.chk_numpad.grid(row=6, column=0, columnspan=2, sticky="w", padx=14, pady=(4, 2))

        self.chk_smart_indent = ctk.CTkCheckBox(card, text="Smart Indent Compensation (VS Code auto-indent fix)")
        if typing_cfg.get("smart_indent", True):
            self.chk_smart_indent.select()
        self.chk_smart_indent.grid(row=7, column=0, columnspan=2, sticky="w", padx=14, pady=(2, 14))

    def _build_mouse_card(self, col: int, row: int):
        card = ctk.CTkFrame(self.scroll_body, fg_color="#181920", corner_radius=10, border_width=1, border_color="#2b2d3c")
        card.grid(row=row, column=col, sticky="nsew", padx=(0, 8), pady=8)
        card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(card, text="🖱️ Mouse Kinematics & Line Interaction", font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"), text_color="#f3f4f6").grid(row=0, column=0, columnspan=2, sticky="w", padx=14, pady=(12, 8))

        mouse_cfg = self.config_data.get("mouse", {})
        line_cfg = mouse_cfg.get("line_interaction", {})

        ctk.CTkLabel(card, text="Movement Profile:").grid(row=1, column=0, sticky="w", padx=14, pady=4)
        self.opt_mouse_profile = ctk.CTkOptionMenu(card, values=["curved", "smooth", "direct"], width=110)
        self.opt_mouse_profile.set(mouse_cfg.get("movement_profile", "curved"))
        self.opt_mouse_profile.grid(row=1, column=1, sticky="e", padx=14, pady=4)

        ctk.CTkLabel(card, text="Default Move Duration (s):").grid(row=2, column=0, sticky="w", padx=14, pady=4)
        self.ent_move_dur = ctk.CTkEntry(card, width=90)
        self.ent_move_dur.insert(0, str(mouse_cfg.get("move_duration", 0.45)))
        self.ent_move_dur.grid(row=2, column=1, sticky="e", padx=14, pady=4)

        ctk.CTkLabel(card, text="Default Motion Easing:").grid(row=3, column=0, sticky="w", padx=14, pady=4)
        self.opt_easing = ctk.CTkOptionMenu(card, values=["easeInOutQuad", "easeOutQuad", "easeInQuad", "linear"], width=130)
        self.opt_easing.set(mouse_cfg.get("easing", "easeInOutQuad"))
        self.opt_easing.grid(row=3, column=1, sticky="e", padx=14, pady=4)

        ctk.CTkLabel(card, text="Line Interaction Interval (Min - Max):").grid(row=4, column=0, sticky="w", padx=14, pady=4)
        interval_box = ctk.CTkFrame(card, fg_color="transparent")
        interval_box.grid(row=4, column=1, sticky="e", padx=14, pady=4)
        self.ent_min_lines = ctk.CTkEntry(interval_box, width=38)
        self.ent_min_lines.insert(0, str(line_cfg.get("min_lines", 2)))
        self.ent_min_lines.pack(side="left", padx=1)
        ctk.CTkLabel(interval_box, text="-").pack(side="left", padx=1)
        self.ent_max_lines = ctk.CTkEntry(interval_box, width=38)
        self.ent_max_lines.insert(0, str(line_cfg.get("max_lines", 5)))
        self.ent_max_lines.pack(side="left", padx=1)

        ctk.CTkLabel(card, text="Line Safe Target (X, Y):").grid(row=5, column=0, sticky="w", padx=14, pady=4)
        coord_box = ctk.CTkFrame(card, fg_color="transparent")
        coord_box.grid(row=5, column=1, sticky="e", padx=14, pady=4)
        self.ent_line_target_x = ctk.CTkEntry(coord_box, width=48)
        self.ent_line_target_x.insert(0, str(line_cfg.get("target_x", 600)))
        self.ent_line_target_x.pack(side="left", padx=1)
        self.ent_line_target_y = ctk.CTkEntry(coord_box, width=48)
        self.ent_line_target_y.insert(0, str(line_cfg.get("target_y", 450)))
        self.ent_line_target_y.pack(side="left", padx=1)

        self.chk_line_mouse = ctk.CTkCheckBox(card, text="Enable Mouse Movement Between Lines")
        if line_cfg.get("enabled", False):
            self.chk_line_mouse.select()
        self.chk_line_mouse.grid(row=6, column=0, columnspan=2, sticky="w", padx=14, pady=(4, 2))

        self.chk_line_click = ctk.CTkCheckBox(card, text="Perform Safe Click on Line Interval")
        if line_cfg.get("click_enabled", False):
            self.chk_line_click.select()
        self.chk_line_click.grid(row=7, column=0, columnspan=2, sticky="w", padx=14, pady=(2, 14))

    def _build_safety_card(self, col: int, row: int):
        card = ctk.CTkFrame(self.scroll_body, fg_color="#181920", corner_radius=10, border_width=1, border_color="#2b2d3c")
        card.grid(row=row, column=col, sticky="nsew", padx=(8, 0), pady=8)
        card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(card, text="🛡️ Safety & Fail-Safes", font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"), text_color="#f3f4f6").grid(row=0, column=0, columnspan=2, sticky="w", padx=14, pady=(12, 8))

        safety_cfg = self.config_data.get("safety", {})

        ctk.CTkLabel(card, text="Emergency Stop Hotkey:").grid(row=1, column=0, sticky="w", padx=14, pady=4)
        self.ent_hotkey = ctk.CTkEntry(card, width=90)
        self.ent_hotkey.insert(0, str(safety_cfg.get("emergency_hotkey", "esc")))
        self.ent_hotkey.grid(row=1, column=1, sticky="e", padx=14, pady=4)

        ctk.CTkLabel(card, text="Focus Countdown (seconds):").grid(row=2, column=0, sticky="w", padx=14, pady=4)
        self.ent_cd_secs = ctk.CTkEntry(card, width=90)
        self.ent_cd_secs.insert(0, str(safety_cfg.get("countdown_seconds", 3)))
        self.ent_cd_secs.grid(row=2, column=1, sticky="e", padx=14, pady=4)

        self.chk_failsafe = ctk.CTkCheckBox(card, text="Enable PyAutoGUI Fail-Safe (Mouse to screen corner aborts)")
        if safety_cfg.get("failsafe", True):
            self.chk_failsafe.select()
        self.chk_failsafe.grid(row=3, column=0, columnspan=2, sticky="w", padx=14, pady=(6, 4))

        self.chk_confirm = ctk.CTkCheckBox(card, text="Require User Confirmation Dialog Before Execution")
        if safety_cfg.get("require_confirmation", True):
            self.chk_confirm.select()
        self.chk_confirm.grid(row=4, column=0, columnspan=2, sticky="w", padx=14, pady=(4, 14))

    def _build_appearance_card(self, col: int, row: int):
        card = ctk.CTkFrame(self.scroll_body, fg_color="#181920", corner_radius=10, border_width=1, border_color="#2b2d3c")
        card.grid(row=row, column=col, sticky="nsew", padx=(8, 0), pady=8)
        card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(card, text="🎨 UI Appearance", font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"), text_color="#f3f4f6").grid(row=0, column=0, columnspan=2, sticky="w", padx=14, pady=(12, 8))

        app_cfg = self.config_data.get("appearance", {})

        ctk.CTkLabel(card, text="Theme Mode:").grid(row=1, column=0, sticky="w", padx=14, pady=6)
        self.opt_theme = ctk.CTkOptionMenu(card, values=["Dark", "Light", "System"], width=130, command=self._on_theme_select)
        self.opt_theme.set(app_cfg.get("theme", "Dark"))
        self.opt_theme.grid(row=1, column=1, sticky="e", padx=14, pady=6)

        ctk.CTkLabel(card, text="Color Accent Theme:").grid(row=2, column=0, sticky="w", padx=14, pady=6)
        self.opt_color_theme = ctk.CTkOptionMenu(card, values=["blue", "green", "dark-blue"], width=130)
        self.opt_color_theme.set(app_cfg.get("color_theme", "blue"))
        self.opt_color_theme.grid(row=2, column=1, sticky="e", padx=14, pady=(6, 16))

    def _build_hotkeys_card(self, col: int, row: int):
        card = ctk.CTkFrame(self.scroll_body, fg_color="#181920", corner_radius=10, border_width=1, border_color="#2b2d3c")
        card.grid(row=row, column=col, columnspan=2, sticky="nsew", padx=0, pady=8)
        card.grid_columnconfigure((1, 3), weight=1)

        ctk.CTkLabel(
            card,
            text="⌨️ Global Hotkeys (Customizable Shortcuts)",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color="#f3f4f6"
        ).grid(row=0, column=0, columnspan=4, sticky="w", padx=14, pady=(12, 4))

        ctk.CTkLabel(
            card,
            text="Hotkeys trigger anywhere across Windows (VS Code, browser, etc.) even when DeskPilot is in background.",
            font=ctk.CTkFont(size=11),
            text_color="#9ca3af"
        ).grid(row=1, column=0, columnspan=4, sticky="w", padx=14, pady=(0, 10))

        hk_cfg = self.config_data.get("hotkeys", {})

        hk_fields = [
            ("▶ Start Automation:", "start", "ctrl+alt+f1"),
            ("⏸ Pause Automation:", "pause", "ctrl+alt+f2"),
            ("⏯ Resume Automation:", "resume", "ctrl+alt+f3"),
            ("⏹ Stop Automation:", "stop", "ctrl+alt+f4")
        ]

        self._hk_entries = {}
        for idx, (lbl1, k1, default) in enumerate(hk_fields):
            curr_row = idx + 2
            ctk.CTkLabel(
                card,
                text=lbl1,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color="#93c5fd"
            ).grid(row=curr_row, column=0, sticky="w", padx=(14, 6), pady=4)
            entry = ctk.CTkEntry(card, width=180)
            entry.insert(0, str(hk_cfg.get(k1, default)))
            entry.grid(row=curr_row, column=1, sticky="ew", padx=(0, 16), pady=4)
            self._hk_entries[k1] = entry

        lbl_hint = ctk.CTkLabel(
            card,
            text="Use Ctrl+Alt plus one key (for example Ctrl+Alt+F1). Ordinary editor shortcuts are reserved.",
            font=ctk.CTkFont(size=11),
            text_color="#f59e0b"
        )
        lbl_hint.grid(row=6, column=0, columnspan=2, sticky="w", padx=14, pady=(6, 12))

    def _create_footer_actions(self):
        footer = ctk.CTkFrame(self, fg_color="#181920", corner_radius=10, border_width=1, border_color="#2b2d3c")
        footer.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 16))
        footer.grid_columnconfigure(0, weight=1)

        self.lbl_save_status = ctk.CTkLabel(
            footer,
            text="Settings loaded from settings.json",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#9ca3af"
        )
        self.lbl_save_status.grid(row=0, column=0, sticky="w", padx=16, pady=12)

        btn_box = ctk.CTkFrame(footer, fg_color="transparent")
        btn_box.grid(row=0, column=1, sticky="e", padx=16, pady=12)

        btn_reset = ctk.CTkButton(
            btn_box,
            text="Reset Defaults",
            font=ctk.CTkFont(size=12),
            fg_color="#374151",
            hover_color="#4b5563",
            width=110,
            command=self._handle_reset_defaults
        )
        btn_reset.pack(side="left", padx=4)

        btn_save = ctk.CTkButton(
            btn_box,
            text="💾 Save Configuration",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color="#2563eb",
            hover_color="#3b82f6",
            width=150,
            command=self._handle_save_settings
        )
        btn_save.pack(side="left", padx=4)

    def _on_theme_select(self, theme: str):
        ctk.set_appearance_mode(theme)
        if self.on_theme_change:
            self.on_theme_change(theme)

    def _handle_save_settings(self):
        try:
            speed_cps = float(self.ent_speed_cps.get())
            if not math.isfinite(speed_cps) or not 1 <= speed_cps <= 30:
                raise ValueError("Typing speed must be between 1 and 30 characters per second.")
            action_pause = float(self.ent_action_pause_ms.get()) / 1000.0
            if not math.isfinite(action_pause) or action_pause < 0:
                raise ValueError("Default action pause must be a non-negative number of milliseconds.")

            new_config = load_config()
            new_config.update({
                "typing": {
                    "speed_cps": speed_cps,
                    "base_delay": 1.0 / speed_cps,
                    "timing_mode": self.opt_timing_mode.get(),
                    "use_numpad": bool(self.chk_numpad.get()),
                    "punct_delay": float(self.ent_punct_delay.get()) / 1000.0,
                    "newline_delay": float(self.ent_newline_delay.get()) / 1000.0,
                    "smart_indent": bool(self.chk_smart_indent.get())
                },
                "execution": {
                    "default_action_pause": action_pause
                },
                "mouse": {
                    "movement_profile": self.opt_mouse_profile.get(),
                    "move_duration": float(self.ent_move_dur.get()),
                    "easing": self.opt_easing.get(),
                    "click_delay": float(self.ent_click_delay.get()) / 1000.0,
                    "double_click_interval": 0.15,
                    "human_like": True,
                    "line_interaction": {
                        "enabled": bool(self.chk_line_mouse.get()),
                        "min_lines": int(self.ent_min_lines.get()),
                        "max_lines": int(self.ent_max_lines.get()),
                        "target_x": int(self.ent_line_target_x.get()),
                        "target_y": int(self.ent_line_target_y.get()),
                        "click_enabled": bool(self.chk_line_click.get())
                    }
                },
                "safety": {
                    "emergency_hotkey": self.ent_hotkey.get().strip().lower() or "ctrl+alt+esc",
                    "countdown_seconds": int(self.ent_cd_secs.get()),
                    "failsafe": bool(self.chk_failsafe.get()),
                    "require_confirmation": bool(self.chk_confirm.get()),
                    "beep_on_countdown": True
                },
                "hotkeys": {
                    k: self._hk_entries[k].get().strip().lower()
                    for k in getattr(self, "_hk_entries", {})
                },
                "appearance": {
                    "theme": self.opt_theme.get(),
                    "color_theme": self.opt_color_theme.get(),
                    "window_width": 1180,
                    "window_height": 780,
                    "min_width": 960,
                    "min_height": 640
                }
            })

            all_hotkeys = [
                new_config["safety"]["emergency_hotkey"],
                *new_config["hotkeys"].values()
            ]
            normalized = [normalize_hotkey(hotkey) for hotkey in all_hotkeys]
            if len(set(normalized)) != len(normalized):
                raise ValueError("Each global hotkey, including Emergency Stop, must be unique.")

            # Apply runtime updates
            safety.set_failsafe(new_config["safety"]["failsafe"])

            if save_config(new_config):
                self.config_data = new_config
                self.lbl_save_status.configure(text="✔ Configuration successfully saved and applied!", text_color="#10b981")
                logger.info("SETTINGS", "User updated and applied system preferences.")
                messagebox.showinfo("Settings Saved", "DeskPilot configuration successfully saved!", parent=self)
            else:
                self.lbl_save_status.configure(text="Failed to write settings.json", text_color="#ef4444")

        except Exception as e:
            messagebox.showerror("Error Saving Settings", f"Please check input values:\n{e}", parent=self)

    def _handle_reset_defaults(self):
        if messagebox.askyesno("Reset Configuration", "Reset all settings to factory defaults?", parent=self):
            save_config(DEFAULT_CONFIG)
            self.config_data = DEFAULT_CONFIG
            self.lbl_save_status.configure(text="Reset to default settings. Re-open panel to see values.", text_color="#f59e0b")

    @classmethod
    def open_settings_modal(cls, parent):
        """Open settings dialog as a clean modal top-level window."""
        win = ctk.CTkToplevel(parent)
        win.title("DeskPilot IDE Settings")
        win.geometry("780x620")
        win.minsize(650, 500)
        win.transient(parent)
        win.grab_set()

        panel = cls(win)
        panel.pack(fill="both", expand=True, padx=8, pady=8)
        win.wait_window()
