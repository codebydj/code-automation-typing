"""
DeskPilot - Modern Settings Dialog
Provides an intuitive, clean interface to configure:
  - Custom typing speed (CPS) & cadence mode (Difficulty-Based vs Fixed CPS)
  - Custom human rest breaks (interval lines, duration min/max seconds)
  - Natural mouse movement between lines (interval, profile, target coordinates)
  - General options (countdown, indentation, sound alert, auto-scroll)
"""

import time
import threading
import tkinter as tk
from typing import Dict, Any, Callable, Optional
import customtkinter as ctk
import pyautogui

from config import DEFAULT_CONFIG, load_config, save_config
from utils.logger import logger


class SettingsDialog(ctk.CTkToplevel):
    """
    Settings dialog allowing user to customize typing speed, difficulty cadence,
    human rest break intervals, mouse movement, and editor preferences.
    """

    def __init__(self, parent, on_save_callback: Optional[Callable[[Dict[str, Any]], None]] = None):
        super().__init__(parent)

        self.title("DeskPilot – Settings & Custom Preferences")
        self.geometry("640x680")
        self.minsize(580, 560)
        self.transient(parent)
        self.grab_set()

        self.on_save_callback = on_save_callback
        self.config_data = load_config()

        # Build UI layout
        self._create_header()
        self._create_tabs_body()
        self._create_footer_actions()

        # Center dialog relative to parent
        self._center_window(parent)

    def _center_window(self, parent):
        try:
            self.update_idletasks()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            w = self.winfo_width()
            h = self.winfo_height()
            x = px + max(0, (pw - w) // 2)
            y = py + max(0, (ph - h) // 2)
            self.geometry(f"+{x}+{y}")
        except Exception:
            pass

    def _create_header(self):
        """Top title banner."""
        hdr = ctk.CTkFrame(self, fg_color="#111319", height=54, corner_radius=0)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        title_lbl = ctk.CTkLabel(
            hdr,
            text="⚙️ Preferences & Automation Settings",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color="#f8fafc"
        )
        title_lbl.pack(side="left", padx=16, pady=12)

        sub_lbl = ctk.CTkLabel(
            hdr,
            text="Customize speed, rest breaks, mouse movement & general behavior",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#94a3b8"
        )
        sub_lbl.pack(side="right", padx=16, pady=12)

    def _create_tabs_body(self):
        """Tabbed view for settings categories."""
        self.tabview = ctk.CTkTabview(self, fg_color="#181a24")
        self.tabview.pack(fill="both", expand=True, padx=12, pady=8)

        tab_speed = self.tabview.add("⚡ Speed & Cadence")
        tab_rest = self.tabview.add("☕ Rest Breaks")
        tab_mouse = self.tabview.add("🖱️ Mouse Movement")
        tab_general = self.tabview.add("🛠️ General & Editor")

        self._build_speed_tab(tab_speed)
        self._build_rest_tab(tab_rest)
        self._build_mouse_tab(tab_mouse)
        self._build_general_tab(tab_general)

    # -------------------------------------------------------------------------
    # TAB 1: SPEED & CADENCE
    # -------------------------------------------------------------------------
    def _build_speed_tab(self, tab):
        typing_cfg = self.config_data.get("typing", {})

        # Speed Card
        c1 = ctk.CTkFrame(tab, fg_color="#13141c", corner_radius=8, border_width=1, border_color="#272a38")
        c1.pack(fill="x", padx=10, pady=6)

        ctk.CTkLabel(
            c1,
            text="Typing Speed (Characters Per Second)",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#38bdf8"
        ).pack(anchor="w", padx=12, pady=(10, 2))

        ctk.CTkLabel(
            c1,
            text="Set exact or custom typing rate. Default is 3.0 CPS. Supports any custom speed.",
            font=ctk.CTkFont(size=11),
            text_color="#94a3b8"
        ).pack(anchor="w", padx=12, pady=(0, 6))

        speed_row = ctk.CTkFrame(c1, fg_color="transparent")
        speed_row.pack(fill="x", padx=12, pady=(0, 10))

        current_speed = float(typing_cfg.get("speed_cps", 3.0))

        self.slider_speed = ctk.CTkSlider(
            speed_row,
            from_=0.5,
            to=10.0,
            number_of_steps=95,
            command=self._on_slider_speed_change
        )
        self.slider_speed.set(min(10.0, max(0.5, current_speed)))
        self.slider_speed.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.ent_speed = ctk.CTkEntry(speed_row, width=70, font=ctk.CTkFont(size=12, weight="bold"))
        self.ent_speed.insert(0, f"{current_speed:.1f}")
        self.ent_speed.pack(side="left")
        self.ent_speed.bind("<KeyRelease>", self._on_entry_speed_change)

        ctk.CTkLabel(speed_row, text="CPS", font=ctk.CTkFont(size=11), text_color="#cbd5e1").pack(side="left", padx=4)

        # Quick preset pills
        presets_row = ctk.CTkFrame(c1, fg_color="transparent")
        presets_row.pack(fill="x", padx=12, pady=(0, 10))
        ctk.CTkLabel(presets_row, text="Presets:", font=ctk.CTkFont(size=10), text_color="#64748b").pack(side="left", padx=(0, 6))
        for p in [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 5.0]:
            btn = ctk.CTkButton(
                presets_row,
                text=f"{p} CPS",
                width=52,
                height=22,
                font=ctk.CTkFont(size=10),
                fg_color="#1e2230",
                hover_color="#2d3348",
                command=lambda val=p: self._set_speed_value(val)
            )
            btn.pack(side="left", padx=2)

        # Cadence Mode Card
        c2 = ctk.CTkFrame(tab, fg_color="#13141c", corner_radius=8, border_width=1, border_color="#272a38")
        c2.pack(fill="x", padx=10, pady=6)

        ctk.CTkLabel(
            c2,
            text="Timing Cadence Mode",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#38bdf8"
        ).pack(anchor="w", padx=12, pady=(10, 2))

        self.mode_var = tk.StringVar(
            value="Difficulty-Based" if typing_cfg.get("timing_mode", "difficulty") == "difficulty" else "Fixed CPS"
        )

        rb1 = ctk.CTkRadioButton(
            c2,
            text="Dynamic Character Difficulty (Natural human pacing, symbol & row effort)",
            variable=self.mode_var,
            value="Difficulty-Based"
        )
        rb1.pack(anchor="w", padx=14, pady=4)

        rb2 = ctk.CTkRadioButton(
            c2,
            text="Fixed CPS (Metronomic steady pace, exact character delay = 1 / CPS)",
            variable=self.mode_var,
            value="Fixed CPS"
        )
        rb2.pack(anchor="w", padx=14, pady=(2, 10))

        # Punctuation & Newline Delays Card
        c3 = ctk.CTkFrame(tab, fg_color="#13141c", corner_radius=8, border_width=1, border_color="#272a38")
        c3.pack(fill="x", padx=10, pady=6)

        ctk.CTkLabel(
            c3,
            text="Fine Delays (Punctuation & Newline Pauses)",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#38bdf8"
        ).pack(anchor="w", padx=12, pady=(10, 2))

        delays_row = ctk.CTkFrame(c3, fg_color="transparent")
        delays_row.pack(fill="x", padx=12, pady=(4, 10))

        ctk.CTkLabel(delays_row, text="Punctuation Pause:", font=ctk.CTkFont(size=11), text_color="#cbd5e1").pack(side="left")
        self.ent_punct = ctk.CTkEntry(delays_row, width=54)
        self.ent_punct.insert(0, str(int(float(typing_cfg.get("punct_delay", 0.150)) * 1000)))
        self.ent_punct.pack(side="left", padx=(4, 14))
        ctk.CTkLabel(delays_row, text="ms", font=ctk.CTkFont(size=10), text_color="#64748b").pack(side="left", padx=(0, 16))

        ctk.CTkLabel(delays_row, text="Newline Pause:", font=ctk.CTkFont(size=11), text_color="#cbd5e1").pack(side="left")
        self.ent_newline = ctk.CTkEntry(delays_row, width=54)
        self.ent_newline.insert(0, str(int(float(typing_cfg.get("newline_delay", 0.250)) * 1000)))
        self.ent_newline.pack(side="left", padx=(4, 4))
        ctk.CTkLabel(delays_row, text="ms", font=ctk.CTkFont(size=10), text_color="#64748b").pack(side="left")

    def _on_slider_speed_change(self, val):
        self.ent_speed.delete(0, "end")
        self.ent_speed.insert(0, f"{float(val):.1f}")

    def _on_entry_speed_change(self, _event=None):
        try:
            val = float(self.ent_speed.get().strip())
            if 0.5 <= val <= 10.0:
                self.slider_speed.set(val)
        except ValueError:
            pass

    def _set_speed_value(self, val: float):
        self.slider_speed.set(val)
        self.ent_speed.delete(0, "end")
        self.ent_speed.insert(0, f"{val:.1f}")

    # -------------------------------------------------------------------------
    # TAB 2: REST BREAKS
    # -------------------------------------------------------------------------
    def _build_rest_tab(self, tab):
        rp_cfg = self.config_data.get("random_pause", {})

        c1 = ctk.CTkFrame(tab, fg_color="#13141c", corner_radius=8, border_width=1, border_color="#272a38")
        c1.pack(fill="x", padx=10, pady=6)

        self.chk_rest_enabled = ctk.CTkCheckBox(
            c1,
            text="Enable Human Rest Breaks (Auto-pauses keyboard & mouse, then auto-resumes)",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#f8fafc"
        )
        self.chk_rest_enabled.select() if rp_cfg.get("enabled", True) else self.chk_rest_enabled.deselect()
        self.chk_rest_enabled.pack(anchor="w", padx=12, pady=10)

        # Interval settings
        c2 = ctk.CTkFrame(tab, fg_color="#13141c", corner_radius=8, border_width=1, border_color="#272a38")
        c2.pack(fill="x", padx=10, pady=6)

        ctk.CTkLabel(
            c2,
            text="Rest Interval (Lines between rest breaks)",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#38bdf8"
        ).pack(anchor="w", padx=12, pady=(10, 2))

        ctk.CTkLabel(
            c2,
            text="DeskPilot picks a random line count within this range before triggering each break.",
            font=ctk.CTkFont(size=11),
            text_color="#94a3b8"
        ).pack(anchor="w", padx=12, pady=(0, 6))

        i_row = ctk.CTkFrame(c2, fg_color="transparent")
        i_row.pack(fill="x", padx=12, pady=(2, 10))

        ctk.CTkLabel(i_row, text="Min Lines:", font=ctk.CTkFont(size=11), text_color="#cbd5e1").pack(side="left")
        self.ent_rp_min_lines = ctk.CTkEntry(i_row, width=54)
        self.ent_rp_min_lines.insert(0, str(rp_cfg.get("min_interval_lines", 15)))
        self.ent_rp_min_lines.pack(side="left", padx=(4, 16))

        ctk.CTkLabel(i_row, text="Max Lines:", font=ctk.CTkFont(size=11), text_color="#cbd5e1").pack(side="left")
        self.ent_rp_max_lines = ctk.CTkEntry(i_row, width=54)
        self.ent_rp_max_lines.insert(0, str(rp_cfg.get("max_interval_lines", 30)))
        self.ent_rp_max_lines.pack(side="left", padx=(4, 10))

        # Duration settings
        c3 = ctk.CTkFrame(tab, fg_color="#13141c", corner_radius=8, border_width=1, border_color="#272a38")
        c3.pack(fill="x", padx=10, pady=6)

        ctk.CTkLabel(
            c3,
            text="Rest Break Duration (Break length)",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#38bdf8"
        ).pack(anchor="w", padx=12, pady=(10, 2))

        ctk.CTkLabel(
            c3,
            text="Duration in seconds. Default is 180s (3 min) to 360s (6 min). You can skip with F7.",
            font=ctk.CTkFont(size=11),
            text_color="#94a3b8"
        ).pack(anchor="w", padx=12, pady=(0, 6))

        d_row = ctk.CTkFrame(c3, fg_color="transparent")
        d_row.pack(fill="x", padx=12, pady=(2, 10))

        ctk.CTkLabel(d_row, text="Min Duration (sec):", font=ctk.CTkFont(size=11), text_color="#cbd5e1").pack(side="left")
        self.ent_rp_min_secs = ctk.CTkEntry(d_row, width=60)
        self.ent_rp_min_secs.insert(0, str(rp_cfg.get("min_duration_seconds", 180)))
        self.ent_rp_min_secs.pack(side="left", padx=(4, 16))

        ctk.CTkLabel(d_row, text="Max Duration (sec):", font=ctk.CTkFont(size=11), text_color="#cbd5e1").pack(side="left")
        self.ent_rp_max_secs = ctk.CTkEntry(d_row, width=60)
        self.ent_rp_max_secs.insert(0, str(rp_cfg.get("max_duration_seconds", 360)))
        self.ent_rp_max_secs.pack(side="left", padx=(4, 10))

        # Helpful quick duration buttons
        d_pills = ctk.CTkFrame(c3, fg_color="transparent")
        d_pills.pack(fill="x", padx=12, pady=(0, 10))
        ctk.CTkLabel(d_pills, text="Presets:", font=ctk.CTkFont(size=10), text_color="#64748b").pack(side="left", padx=(0, 6))
        for label, mn, mx in [("1–2 min", 60, 120), ("2–4 min", 120, 240), ("3–6 min (Standard)", 180, 360), ("5–10 min", 300, 600)]:
            btn = ctk.CTkButton(
                d_pills,
                text=label,
                height=22,
                font=ctk.CTkFont(size=10),
                fg_color="#1e2230",
                hover_color="#2d3348",
                command=lambda mn=mn, mx=mx: self._set_rest_duration(mn, mx)
            )
            btn.pack(side="left", padx=2)

    def _set_rest_duration(self, mn: int, mx: int):
        self.ent_rp_min_secs.delete(0, "end")
        self.ent_rp_min_secs.insert(0, str(mn))
        self.ent_rp_max_secs.delete(0, "end")
        self.ent_rp_max_secs.insert(0, str(mx))

    # -------------------------------------------------------------------------
    # TAB 3: MOUSE MOVEMENT
    # -------------------------------------------------------------------------
    def _build_mouse_tab(self, tab):
        mouse_cfg = self.config_data.get("mouse", {})
        line_cfg = mouse_cfg.get("line_interaction", {})

        c1 = ctk.CTkFrame(tab, fg_color="#13141c", corner_radius=8, border_width=1, border_color="#272a38")
        c1.pack(fill="x", padx=10, pady=6)

        self.chk_mouse_enabled = ctk.CTkCheckBox(
            c1,
            text="Enable Natural Mouse Movement Between Lines (Move only, non-destructive)",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#f8fafc"
        )
        self.chk_mouse_enabled.select() if line_cfg.get("enabled", True) else self.chk_mouse_enabled.deselect()
        self.chk_mouse_enabled.pack(anchor="w", padx=12, pady=10)

        c2 = ctk.CTkFrame(tab, fg_color="#13141c", corner_radius=8, border_width=1, border_color="#272a38")
        c2.pack(fill="x", padx=10, pady=6)

        ctk.CTkLabel(c2, text="Movement Cadence & Kinematics", font=ctk.CTkFont(size=12, weight="bold"), text_color="#38bdf8").pack(anchor="w", padx=12, pady=(10, 2))

        m_row1 = ctk.CTkFrame(c2, fg_color="transparent")
        m_row1.pack(fill="x", padx=12, pady=(4, 6))

        ctk.CTkLabel(m_row1, text="Trigger every:", font=ctk.CTkFont(size=11), text_color="#cbd5e1").pack(side="left")
        self.ent_mouse_min_lines = ctk.CTkEntry(m_row1, width=44)
        self.ent_mouse_min_lines.insert(0, str(line_cfg.get("min_lines", 2)))
        self.ent_mouse_min_lines.pack(side="left", padx=(4, 6))

        ctk.CTkLabel(m_row1, text="to", font=ctk.CTkFont(size=11), text_color="#94a3b8").pack(side="left")
        self.ent_mouse_max_lines = ctk.CTkEntry(m_row1, width=44)
        self.ent_mouse_max_lines.insert(0, str(line_cfg.get("max_lines", 5)))
        self.ent_mouse_max_lines.pack(side="left", padx=(6, 16))
        ctk.CTkLabel(m_row1, text="completed lines", font=ctk.CTkFont(size=11), text_color="#94a3b8").pack(side="left")

        m_row2 = ctk.CTkFrame(c2, fg_color="transparent")
        m_row2.pack(fill="x", padx=12, pady=(4, 10))

        ctk.CTkLabel(m_row2, text="Kinematic Profile:", font=ctk.CTkFont(size=11), text_color="#cbd5e1").pack(side="left")
        self.opt_mouse_profile = ctk.CTkOptionMenu(
            m_row2,
            values=["Curved (Human Bezier & Micro-Jitter)", "Smooth (Eased Direct)", "Direct"],
            width=240,
            height=26
        )
        prof_val = mouse_cfg.get("movement_profile", "curved").lower()
        if "smooth" in prof_val:
            self.opt_mouse_profile.set("Smooth (Eased Direct)")
        elif "direct" in prof_val:
            self.opt_mouse_profile.set("Direct")
        else:
            self.opt_mouse_profile.set("Curved (Human Bezier & Micro-Jitter)")
        self.opt_mouse_profile.pack(side="left", padx=(6, 10))

        # Target Coordinates Card
        c3 = ctk.CTkFrame(tab, fg_color="#13141c", corner_radius=8, border_width=1, border_color="#272a38")
        c3.pack(fill="x", padx=10, pady=6)

        ctk.CTkLabel(c3, text="Safe Target Coordinates", font=ctk.CTkFont(size=12, weight="bold"), text_color="#38bdf8").pack(anchor="w", padx=12, pady=(10, 2))
        ctk.CTkLabel(c3, text="Safe screen location where the cursor will naturally move during breaks.", font=ctk.CTkFont(size=11), text_color="#94a3b8").pack(anchor="w", padx=12, pady=(0, 6))

        coord_row = ctk.CTkFrame(c3, fg_color="transparent")
        coord_row.pack(fill="x", padx=12, pady=(2, 10))

        ctk.CTkLabel(coord_row, text="Target X:", font=ctk.CTkFont(size=11), text_color="#cbd5e1").pack(side="left")
        self.ent_mouse_x = ctk.CTkEntry(coord_row, width=60)
        self.ent_mouse_x.insert(0, str(line_cfg.get("target_x", 600)))
        self.ent_mouse_x.pack(side="left", padx=(4, 14))

        ctk.CTkLabel(coord_row, text="Target Y:", font=ctk.CTkFont(size=11), text_color="#cbd5e1").pack(side="left")
        self.ent_mouse_y = ctk.CTkEntry(coord_row, width=60)
        self.ent_mouse_y.insert(0, str(line_cfg.get("target_y", 450)))
        self.ent_mouse_y.pack(side="left", padx=(4, 16))

        self.btn_pick_pos = ctk.CTkButton(
            coord_row,
            text="📍 Pick Position (2s delay)",
            height=26,
            fg_color="#1e293b",
            hover_color="#334155",
            command=self._handle_pick_mouse_pos
        )
        self.btn_pick_pos.pack(side="left")

    def _handle_pick_mouse_pos(self):
        """Countdown and capture user's mouse position."""
        self.btn_pick_pos.configure(text="Move mouse now... 2", state="disabled")

        def worker():
            time.sleep(1.0)
            self.after(0, lambda: self.btn_pick_pos.configure(text="Capturing... 1"))
            time.sleep(1.0)
            x, y = pyautogui.position()
            self.after(0, lambda: self._apply_picked_pos(x, y))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_picked_pos(self, x: int, y: int):
        self.ent_mouse_x.delete(0, "end")
        self.ent_mouse_x.insert(0, str(x))
        self.ent_mouse_y.delete(0, "end")
        self.ent_mouse_y.insert(0, str(y))
        self.btn_pick_pos.configure(text=f"📍 Captured ({x}, {y})", state="normal")
        self.after(2500, lambda: self.btn_pick_pos.configure(text="📍 Pick Position (2s delay)"))

    # -------------------------------------------------------------------------
    # TAB 4: GENERAL & EDITOR
    # -------------------------------------------------------------------------
    def _build_general_tab(self, tab):
        safety_cfg = self.config_data.get("safety", {})
        editor_cfg = self.config_data.get("editor", {})

        c1 = ctk.CTkFrame(tab, fg_color="#13141c", corner_radius=8, border_width=1, border_color="#272a38")
        c1.pack(fill="x", padx=10, pady=6)

        ctk.CTkLabel(c1, text="Automation Startup & Safety", font=ctk.CTkFont(size=12, weight="bold"), text_color="#38bdf8").pack(anchor="w", padx=12, pady=(10, 2))

        cd_row = ctk.CTkFrame(c1, fg_color="transparent")
        cd_row.pack(fill="x", padx=12, pady=(4, 6))

        ctk.CTkLabel(cd_row, text="Startup Countdown:", font=ctk.CTkFont(size=11), text_color="#cbd5e1").pack(side="left")
        self.opt_countdown = ctk.CTkOptionMenu(
            cd_row,
            values=["3 seconds", "5 seconds", "2 seconds", "1 second", "No countdown"],
            width=140,
            height=26
        )
        cd_sec = int(safety_cfg.get("countdown_seconds", 3))
        cd_map_rev = {3: "3 seconds", 5: "5 seconds", 2: "2 seconds", 1: "1 second", 0: "No countdown"}
        self.opt_countdown.set(cd_map_rev.get(cd_sec, "3 seconds"))
        self.opt_countdown.pack(side="left", padx=(8, 10))

        self.chk_failsafe = ctk.CTkCheckBox(
            c1,
            text="PyAutoGUI Fail-Safe (Move mouse to any screen corner to instantly abort)",
            font=ctk.CTkFont(size=11),
            text_color="#f8fafc"
        )
        self.chk_failsafe.select() if safety_cfg.get("failsafe", True) else self.chk_failsafe.deselect()
        self.chk_failsafe.pack(anchor="w", padx=12, pady=(4, 10))

        # Editor settings
        c2 = ctk.CTkFrame(tab, fg_color="#13141c", corner_radius=8, border_width=1, border_color="#272a38")
        c2.pack(fill="x", padx=10, pady=6)

        ctk.CTkLabel(c2, text="Editor Formatting & Visual Behavior", font=ctk.CTkFont(size=12, weight="bold"), text_color="#38bdf8").pack(anchor="w", padx=12, pady=(10, 2))

        ed_row = ctk.CTkFrame(c2, fg_color="transparent")
        ed_row.pack(fill="x", padx=12, pady=(4, 6))

        ctk.CTkLabel(ed_row, text="Tab Indentation Width:", font=ctk.CTkFont(size=11), text_color="#cbd5e1").pack(side="left")
        self.opt_indent = ctk.CTkOptionMenu(ed_row, values=["4 spaces", "2 spaces", "8 spaces"], width=110, height=26)
        curr_indent = int(editor_cfg.get("indent_width", 4))
        self.opt_indent.set(f"{curr_indent} spaces")
        self.opt_indent.pack(side="left", padx=(8, 10))

        self.chk_chime = ctk.CTkCheckBox(
            c2,
            text="Play audio alert chime on completion & rest pause",
            font=ctk.CTkFont(size=11),
            text_color="#f8fafc"
        )
        self.chk_chime.select() if safety_cfg.get("beep_on_countdown", True) else self.chk_chime.deselect()
        self.chk_chime.pack(anchor="w", padx=12, pady=(4, 6))

        self.chk_autoscroll = ctk.CTkCheckBox(
            c2,
            text="Auto-scroll editor to keep active typing line visible",
            font=ctk.CTkFont(size=11),
            text_color="#f8fafc"
        )
        self.chk_autoscroll.select()
        self.chk_autoscroll.pack(anchor="w", padx=12, pady=(2, 10))

    # -------------------------------------------------------------------------
    # FOOTER ACTIONS (SAVE & APPLY, RESET, CANCEL)
    # -------------------------------------------------------------------------
    def _create_footer_actions(self):
        ftr = ctk.CTkFrame(self, fg_color="#111319", height=50, corner_radius=0)
        ftr.pack(fill="x", side="bottom")
        ftr.pack_propagate(False)

        btn_save = ctk.CTkButton(
            ftr,
            text="💾 Save & Apply",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#059669",
            hover_color="#10b981",
            width=120,
            command=self._handle_save
        )
        btn_save.pack(side="right", padx=(6, 16), pady=10)

        btn_cancel = ctk.CTkButton(
            ftr,
            text="✖ Cancel",
            font=ctk.CTkFont(size=12),
            fg_color="#334155",
            hover_color="#475569",
            width=80,
            command=self.destroy
        )
        btn_cancel.pack(side="right", padx=6, pady=10)

        btn_reset = ctk.CTkButton(
            ftr,
            text="🔄 Defaults",
            font=ctk.CTkFont(size=11),
            fg_color="#1e2230",
            hover_color="#2d3348",
            width=80,
            command=self._handle_reset_defaults
        )
        btn_reset.pack(side="left", padx=16, pady=10)

    def _handle_save(self):
        """Validate, persist to settings.json, and invoke callback."""
        try:
            speed_val = max(0.2, min(20.0, float(self.ent_speed.get().strip())))
        except ValueError:
            speed_val = 3.0

        is_diff = (self.mode_var.get() == "Difficulty-Based")

        try:
            punct_ms = max(0, int(self.ent_punct.get().strip()))
        except ValueError:
            punct_ms = 150

        try:
            newline_ms = max(0, int(self.ent_newline.get().strip()))
        except ValueError:
            newline_ms = 250

        try:
            rp_min_l = max(1, int(self.ent_rp_min_lines.get().strip()))
            rp_max_l = max(rp_min_l, int(self.ent_rp_max_lines.get().strip()))
        except ValueError:
            rp_min_l, rp_max_l = 15, 30

        try:
            rp_min_s = max(10, int(self.ent_rp_min_secs.get().strip()))
            rp_max_s = max(rp_min_s, int(self.ent_rp_max_secs.get().strip()))
        except ValueError:
            rp_min_s, rp_max_s = 180, 360

        try:
            m_min_l = max(1, int(self.ent_mouse_min_lines.get().strip()))
            m_max_l = max(m_min_l, int(self.ent_mouse_max_lines.get().strip()))
        except ValueError:
            m_min_l, m_max_l = 2, 5

        try:
            mx = int(self.ent_mouse_x.get().strip())
            my = int(self.ent_mouse_y.get().strip())
        except ValueError:
            mx, my = 600, 450

        prof_choice = self.opt_mouse_profile.get().lower()
        if "smooth" in prof_choice:
            m_profile = "smooth"
        elif "direct" in prof_choice:
            m_profile = "direct"
        else:
            m_profile = "curved"

        cd_map = {"3 seconds": 3, "5 seconds": 5, "2 seconds": 2, "1 second": 1, "No countdown": 0}
        countdown_secs = cd_map.get(self.opt_countdown.get(), 3)
        indent_spaces = int(self.opt_indent.get().split()[0])

        new_config = {
            "typing": {
                "speed_cps": speed_val,
                "timing_mode": "difficulty" if is_diff else "fixed",
                "use_numpad": False,
                "punct_delay": punct_ms / 1000.0,
                "newline_delay": newline_ms / 1000.0,
                "base_delay": 1.0 / speed_val,
                "smart_indent": False
            },
            "random_pause": {
                "enabled": bool(self.chk_rest_enabled.get()),
                "min_interval_lines": rp_min_l,
                "max_interval_lines": rp_max_l,
                "min_duration_seconds": rp_min_s,
                "max_duration_seconds": rp_max_s
            },
            "mouse": {
                "movement_profile": m_profile,
                "line_interaction": {
                    "enabled": bool(self.chk_mouse_enabled.get()),
                    "min_lines": m_min_l,
                    "max_lines": m_max_l,
                    "target_x": mx,
                    "target_y": my,
                    "click_enabled": False
                }
            },
            "safety": {
                "failsafe": bool(self.chk_failsafe.get()),
                "countdown_seconds": countdown_secs,
                "beep_on_countdown": bool(self.chk_chime.get())
            },
            "editor": {
                "indent_width": indent_spaces,
                "autoscroll": bool(self.chk_autoscroll.get())
            }
        }

        # Merge with existing configuration and persist
        merged = load_config()
        for k, v in new_config.items():
            if k in merged and isinstance(merged[k], dict):
                merged[k].update(v)
            else:
                merged[k] = v

        save_config(merged)
        logger.info("SETTINGS", "User saved updated configuration.")

        if self.on_save_callback:
            self.on_save_callback(merged)

        self.destroy()

    def _handle_reset_defaults(self):
        """Reset inputs to DEFAULT_CONFIG values."""
        self._set_speed_value(3.0)
        self.mode_var.set("Difficulty-Based")
        self.ent_punct.delete(0, "end")
        self.ent_punct.insert(0, "150")
        self.ent_newline.delete(0, "end")
        self.ent_newline.insert(0, "250")

        self.chk_rest_enabled.select()
        self.ent_rp_min_lines.delete(0, "end")
        self.ent_rp_min_lines.insert(0, "15")
        self.ent_rp_max_lines.delete(0, "end")
        self.ent_rp_max_lines.insert(0, "30")
        self.ent_rp_min_secs.delete(0, "end")
        self.ent_rp_min_secs.insert(0, "180")
        self.ent_rp_max_secs.delete(0, "end")
        self.ent_rp_max_secs.insert(0, "360")

        self.chk_mouse_enabled.select()
        self.ent_mouse_min_lines.delete(0, "end")
        self.ent_mouse_min_lines.insert(0, "2")
        self.ent_mouse_max_lines.delete(0, "end")
        self.ent_mouse_max_lines.insert(0, "5")
        self.opt_mouse_profile.set("Curved (Human Bezier & Micro-Jitter)")
        self.ent_mouse_x.delete(0, "end")
        self.ent_mouse_x.insert(0, "600")
        self.ent_mouse_y.delete(0, "end")
        self.ent_mouse_y.insert(0, "450")

        self.opt_countdown.set("3 seconds")
        self.chk_failsafe.select()
        self.opt_indent.set("4 spaces")
        self.chk_chime.select()
        self.chk_autoscroll.select()
