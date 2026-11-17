"""
DeskPilot - Mouse Controller Panel
Comprehensive mouse automation workbench: smooth movement, visual radar canvas,
coordinate picker, clicking, mouse wheel scrolling, drag-and-drop,
and multi-mode text selection (drag, double-click word, triple-click line, select all).
"""

import time
import threading
import customtkinter as ctk
from automation.mouse_controller import mouse_ctrl
from automation.safety import safety
from ui.cursor_indicator import CursorRadarCanvas, DesktopSpotlight
from utils.logger import logger


class MousePanel(ctk.CTkFrame):
    """Modern mouse automation and coordinate telemetry panel with visual radar."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Left Column: Movement, Visual Radar, Coordinates Picker & Clicks
        self._create_movement_and_clicks(col=0)

        # Right Column: Drag & Drop, Text Selection Suite, and Scrolling
        self._create_drag_and_selection(col=1)

        # Start live coordinate telemetry
        self._update_live_coords()

    def _create_movement_and_clicks(self, col: int):
        """Card for cursor positioning, visual radar, coordinate picking, and clicking actions."""
        container = ctk.CTkFrame(self, fg_color="#181920", corner_radius=10, border_width=1, border_color="#2b2d3c")
        container.grid(row=0, column=col, sticky="nsew", padx=(16, 8), pady=16)
        container.grid_columnconfigure(0, weight=1)

        # Header
        hdr = ctk.CTkFrame(container, fg_color="transparent")
        hdr.pack(fill="x", padx=16, pady=(14, 6))
        
        lbl_title = ctk.CTkLabel(
            hdr,
            text="🖱️ Cursor Navigation & Visual Radar",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color="#f3f4f6"
        )
        lbl_title.pack(anchor="w")

        lbl_desc = ctk.CTkLabel(
            hdr,
            text="Control cursor trajectory, view live visual radar, and dispatch clicks.",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#9ca3af"
        )
        lbl_desc.pack(anchor="w")

        # Live Coordinate Inspector & Visual Radar
        picker_box = ctk.CTkFrame(container, fg_color="#1f212a", corner_radius=8)
        picker_box.pack(fill="x", padx=16, pady=4)
        picker_box.grid_columnconfigure((0, 1), weight=1)

        lbl_pick_hdr = ctk.CTkLabel(
            picker_box,
            text="📍 Live Coordinates & Screen Radar",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color="#38bdf8"
        )
        lbl_pick_hdr.grid(row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(8, 2))

        self.lbl_live_pos = ctk.CTkLabel(
            picker_box,
            text="Current Mouse: X: 0   Y: 0",
            font=ctk.CTkFont(family="Consolas", size=13, weight="bold"),
            text_color="#e5e7eb"
        )
        self.lbl_live_pos.grid(row=1, column=0, sticky="w", padx=12, pady=(0, 2))

        # Action buttons: Pick Point & Desktop Spotlight
        btn_box = ctk.CTkFrame(picker_box, fg_color="transparent")
        btn_box.grid(row=1, column=1, sticky="e", padx=10, pady=(0, 2))

        btn_spotlight = ctk.CTkButton(
            btn_box,
            text="Spotlight",
            font=ctk.CTkFont(size=11, weight="bold"),
            width=70,
            height=26,
            fg_color="#374151",
            hover_color="#4b5563",
            command=self._handle_spotlight
        )
        btn_spotlight.pack(side="left", padx=2)

        self.btn_pick_coord = ctk.CTkButton(
            btn_box,
            text="🎯 Pick Point (3s)",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#2563eb",
            hover_color="#3b82f6",
            width=110,
            height=26,
            command=self._handle_pick_coordinates
        )
        self.btn_pick_coord.pack(side="left", padx=2)

        # Embedded Visual Cursor Radar Canvas
        self.radar = CursorRadarCanvas(picker_box, width=220, height=84)
        self.radar.grid(row=2, column=0, columnspan=2, padx=10, pady=(2, 4))

        self.lbl_picker_feedback = ctk.CTkLabel(
            picker_box,
            text="Click 'Pick Point', move cursor anywhere on desktop, and wait 3s.",
            font=ctk.CTkFont(size=10),
            text_color="#9ca3af"
        )
        self.lbl_picker_feedback.grid(row=3, column=0, columnspan=2, sticky="w", padx=12, pady=(0, 6))

        # Target Coordinates & Move Configuration
        move_box = ctk.CTkFrame(container, fg_color="#1f212a", corner_radius=8)
        move_box.pack(fill="x", padx=16, pady=4)
        move_box.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(move_box, text="Target Coordinates & Motion:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#d1d5db").grid(row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(6, 2))

        coord_row = ctk.CTkFrame(move_box, fg_color="transparent")
        coord_row.grid(row=1, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 4))
        coord_row.grid_columnconfigure((1, 3), weight=1)

        ctk.CTkLabel(coord_row, text="Target X:").grid(row=0, column=0, padx=(0, 4))
        self.ent_target_x = ctk.CTkEntry(coord_row, width=70, font=ctk.CTkFont(family="Consolas"))
        self.ent_target_x.insert(0, "500")
        self.ent_target_x.grid(row=0, column=1, padx=(0, 8), sticky="ew")

        ctk.CTkLabel(coord_row, text="Target Y:").grid(row=0, column=2, padx=(0, 4))
        self.ent_target_y = ctk.CTkEntry(coord_row, width=70, font=ctk.CTkFont(family="Consolas"))
        self.ent_target_y.insert(0, "300")
        self.ent_target_y.grid(row=0, column=3, sticky="ew")

        # Duration & Easing
        ctk.CTkLabel(move_box, text="Move Duration (s):", font=ctk.CTkFont(size=11)).grid(row=2, column=0, sticky="w", padx=12, pady=2)
        self.lbl_dur_val = ctk.CTkLabel(move_box, text="0.45 s", font=ctk.CTkFont(size=11), text_color="#38bdf8")
        self.lbl_dur_val.grid(row=2, column=1, sticky="e", padx=12, pady=2)

        self.slider_duration = ctk.CTkSlider(move_box, from_=0.1, to=1.5, number_of_steps=28, command=lambda v: self.lbl_dur_val.configure(text=f"{v:.2f} s"))
        self.slider_duration.set(0.45)
        self.slider_duration.grid(row=3, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 4))

        ctk.CTkLabel(move_box, text="Easing Function:", font=ctk.CTkFont(size=11)).grid(row=4, column=0, sticky="w", padx=12, pady=2)
        self.opt_easing = ctk.CTkOptionMenu(move_box, values=["easeInOutQuad", "easeOutQuad", "easeInQuad", "linear"], height=26)
        self.opt_easing.set("easeInOutQuad")
        self.opt_easing.grid(row=4, column=1, sticky="e", padx=12, pady=2)

        btn_move = ctk.CTkButton(
            move_box,
            text="🚀 Move Cursor to Coordinates",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="#059669",
            hover_color="#10b981",
            height=30,
            command=self._handle_test_move
        )
        btn_move.grid(row=5, column=0, columnspan=2, sticky="ew", padx=12, pady=(6, 4))

        btn_rand_move = ctk.CTkButton(
            move_box,
            text="🎲 Random Human Move (Time & Length)",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="#2563eb",
            hover_color="#3b82f6",
            height=30,
            command=self._handle_random_human_move
        )
        btn_rand_move.grid(row=6, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 8))

        # Clicks section
        click_box = ctk.CTkFrame(container, fg_color="#1f212a", corner_radius=8)
        click_box.pack(fill="x", padx=16, pady=4)
        click_box.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(click_box, text="Mouse Clicks:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#d1d5db").grid(row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(6, 4))

        btn_left = ctk.CTkButton(
            click_box,
            text="Left Click",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#2b2d3c",
            hover_color="#3b82f6",
            height=30,
            command=lambda: self._handle_click("left", 1)
        )
        btn_left.grid(row=1, column=0, padx=4, pady=(0, 8))

        btn_double = ctk.CTkButton(
            click_box,
            text="Double Click",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#2b2d3c",
            hover_color="#3b82f6",
            height=30,
            command=lambda: self._handle_click("left", 2)
        )
        btn_double.grid(row=1, column=1, padx=4, pady=(0, 8))

    def _create_drag_and_selection(self, col: int):
        """Card for Drag & Drop, Text Selection Suite, and Scrolling."""
        container = ctk.CTkFrame(self, fg_color="#181920", corner_radius=10, border_width=1, border_color="#2b2d3c")
        container.grid(row=0, column=col, sticky="nsew", padx=(8, 16), pady=16)
        container.grid_columnconfigure(0, weight=1)

        # Header
        hdr = ctk.CTkFrame(container, fg_color="transparent")
        hdr.pack(fill="x", padx=16, pady=(14, 6))
        
        lbl_title = ctk.CTkLabel(
            hdr,
            text="🔄 Drag & Text Selection Suite",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color="#f3f4f6"
        )
        lbl_title.pack(anchor="w")

        lbl_desc = ctk.CTkLabel(
            hdr,
            text="Select text via mouse drag, double-click word, triple-click line, or Ctrl+A.",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#9ca3af"
        )
        lbl_desc.pack(anchor="w")

        # Drag and Drop Box
        drag_box = ctk.CTkFrame(container, fg_color="#1f212a", corner_radius=8)
        drag_box.pack(fill="x", padx=16, pady=4)
        drag_box.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(drag_box, text="Drag & Drop Coordinates:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#d1d5db").grid(row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(6, 2))

        # Start Coords
        row_start = ctk.CTkFrame(drag_box, fg_color="transparent")
        row_start.grid(row=1, column=0, columnspan=2, sticky="ew", padx=12, pady=2)
        row_start.grid_columnconfigure((1, 3), weight=1)

        ctk.CTkLabel(row_start, text="Start X:").grid(row=0, column=0, padx=(0, 4))
        self.ent_drag_sx = ctk.CTkEntry(row_start, width=65, font=ctk.CTkFont(family="Consolas"))
        self.ent_drag_sx.insert(0, "400")
        self.ent_drag_sx.grid(row=0, column=1, padx=(0, 8), sticky="ew")

        ctk.CTkLabel(row_start, text="Start Y:").grid(row=0, column=2, padx=(0, 4))
        self.ent_drag_sy = ctk.CTkEntry(row_start, width=65, font=ctk.CTkFont(family="Consolas"))
        self.ent_drag_sy.insert(0, "300")
        self.ent_drag_sy.grid(row=0, column=3, sticky="ew")

        btn_cap_start = ctk.CTkButton(
            row_start,
            text="Pick Start",
            width=70,
            height=24,
            fg_color="#374151",
            hover_color="#4b5563",
            command=lambda: self._pick_to_entries(self.ent_drag_sx, self.ent_drag_sy)
        )
        btn_cap_start.grid(row=0, column=4, padx=(6, 0))

        # End Coords
        row_end = ctk.CTkFrame(drag_box, fg_color="transparent")
        row_end.grid(row=2, column=0, columnspan=2, sticky="ew", padx=12, pady=2)
        row_end.grid_columnconfigure((1, 3), weight=1)

        ctk.CTkLabel(row_end, text="End X:").grid(row=0, column=0, padx=(0, 4))
        self.ent_drag_ex = ctk.CTkEntry(row_end, width=65, font=ctk.CTkFont(family="Consolas"))
        self.ent_drag_ex.insert(0, "700")
        self.ent_drag_ex.grid(row=0, column=1, padx=(0, 8), sticky="ew")

        ctk.CTkLabel(row_end, text="End Y:").grid(row=0, column=2, padx=(0, 4))
        self.ent_drag_ey = ctk.CTkEntry(row_end, width=65, font=ctk.CTkFont(family="Consolas"))
        self.ent_drag_ey.insert(0, "300")
        self.ent_drag_ey.grid(row=0, column=3, sticky="ew")

        btn_cap_end = ctk.CTkButton(
            row_end,
            text="Pick End",
            width=70,
            height=24,
            fg_color="#374151",
            hover_color="#4b5563",
            command=lambda: self._pick_to_entries(self.ent_drag_ex, self.ent_drag_ey)
        )
        btn_cap_end.grid(row=0, column=4, padx=(6, 0))

        btn_test_drag = ctk.CTkButton(
            drag_box,
            text="Test Drag & Drop (1.5s countdown)",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="#2563eb",
            hover_color="#3b82f6",
            height=28,
            command=self._handle_test_drag
        )
        btn_test_drag.grid(row=3, column=0, columnspan=2, sticky="ew", padx=12, pady=(6, 8))

        # Full Text Selection Suite
        select_box = ctk.CTkFrame(container, fg_color="#1f212a", corner_radius=8)
        select_box.pack(fill="x", padx=16, pady=4)
        select_box.grid_columnconfigure((0, 1, 2), weight=1)

        ctk.CTkLabel(select_box, text="Multi-Mode Text Selection:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#38bdf8").grid(row=0, column=0, columnspan=3, sticky="w", padx=12, pady=(6, 4))

        btn_drag_select = ctk.CTkButton(
            select_box,
            text="1. Drag Select",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#2b2d3c",
            hover_color="#2563eb",
            height=30,
            command=self._handle_drag_select
        )
        btn_drag_select.grid(row=1, column=0, padx=3, pady=3, sticky="ew")

        btn_word_select = ctk.CTkButton(
            select_box,
            text="2. Select Word",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#2b2d3c",
            hover_color="#2563eb",
            height=30,
            command=self._handle_word_select
        )
        btn_word_select.grid(row=1, column=1, padx=3, pady=3, sticky="ew")

        btn_line_select = ctk.CTkButton(
            select_box,
            text="3. Select Line",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#2b2d3c",
            hover_color="#2563eb",
            height=30,
            command=self._handle_line_select
        )
        btn_line_select.grid(row=1, column=2, padx=3, pady=3, sticky="ew")

        btn_sel_all = ctk.CTkButton(
            select_box,
            text="4. Select All (Ctrl+A)",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#2b2d3c",
            hover_color="#2563eb",
            height=30,
            command=self._handle_select_all
        )
        btn_sel_all.grid(row=2, column=0, padx=3, pady=3, sticky="ew")

        btn_deselect = ctk.CTkButton(
            select_box,
            text="5. Deselect Text",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#2b2d3c",
            hover_color="#ef4444",
            height=30,
            command=self._handle_deselect
        )
        btn_deselect.grid(row=2, column=1, columnspan=2, padx=3, pady=3, sticky="ew")

        self.lbl_select_hint = ctk.CTkLabel(
            select_box,
            text="All selection actions countdown 1.5s so you can focus target editor.",
            font=ctk.CTkFont(size=10),
            text_color="#9ca3af"
        )
        self.lbl_select_hint.grid(row=3, column=0, columnspan=3, sticky="w", padx=12, pady=(2, 6))

        # Mouse Wheel Scrolling Section
        scroll_box = ctk.CTkFrame(container, fg_color="#1f212a", corner_radius=8)
        scroll_box.pack(fill="x", padx=16, pady=4)
        scroll_box.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(scroll_box, text="Mouse Wheel Scrolling:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#d1d5db").grid(row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(6, 2))

        row_scroll = ctk.CTkFrame(scroll_box, fg_color="transparent")
        row_scroll.grid(row=1, column=0, columnspan=2, sticky="ew", padx=12, pady=2)
        row_scroll.grid_columnconfigure((0, 1), weight=1)

        btn_scroll_up = ctk.CTkButton(
            row_scroll,
            text="▲ Scroll Up (+5)",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#2b2d3c",
            hover_color="#3b82f6",
            height=28,
            command=lambda: mouse_ctrl.scroll(5)
        )
        btn_scroll_up.grid(row=0, column=0, padx=(0, 4), sticky="ew")

        btn_scroll_down = ctk.CTkButton(
            row_scroll,
            text="▼ Scroll Down (-5)",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#2b2d3c",
            hover_color="#3b82f6",
            height=28,
            command=lambda: mouse_ctrl.scroll(-5)
        )
        btn_scroll_down.grid(row=0, column=1, padx=(4, 0), sticky="ew")

        ctk.CTkLabel(scroll_box, text="Scrolls immediately at current mouse position.", font=ctk.CTkFont(size=10), text_color="#9ca3af").grid(row=2, column=0, columnspan=2, sticky="w", padx=12, pady=(0, 6))

    def _update_live_coords(self):
        """Update live coordinate text."""
        try:
            x, y = mouse_ctrl.get_position()
            self.lbl_live_pos.configure(text=f"Current Mouse: X: {x:<5} Y: {y:<5}")
        except Exception:
            pass
        self.after(50, self._update_live_coords)

    def _handle_spotlight(self):
        """Ping current mouse position with on-screen spotlight."""
        x, y = mouse_ctrl.get_position()
        DesktopSpotlight.ping(x, y)
        if hasattr(self, "radar"):
            self.radar.ping_target(x, y)

    def _handle_pick_coordinates(self):
        """3-second countdown to pick any screen point and fill Target X/Y."""
        def worker():
            for remaining in range(3, 0, -1):
                self.after(0, lambda r=remaining: self.lbl_picker_feedback.configure(
                    text=f"Place mouse over target position... Capturing in {r}s!",
                    text_color="#f59e0b"
                ))
                time.sleep(1.0)

            x, y = mouse_ctrl.get_position()
            self.after(0, lambda: self._apply_picked_coords(x, y))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_picked_coords(self, x: int, y: int):
        self.ent_target_x.delete(0, "end")
        self.ent_target_x.insert(0, str(x))
        self.ent_target_y.delete(0, "end")
        self.ent_target_y.insert(0, str(y))
        self.lbl_picker_feedback.configure(
            text=f"Captured coordinates: ({x}, {y})",
            text_color="#10b981"
        )
        DesktopSpotlight.ping(x, y)
        if hasattr(self, "radar"):
            self.radar.ping_target(x, y)

    def _pick_to_entries(self, ent_x, ent_y):
        """Pick coordinate to specific entry fields with 3s timer."""
        def worker():
            for remaining in range(3, 0, -1):
                self.after(0, lambda r=remaining: self.lbl_picker_feedback.configure(
                    text=f"Place mouse over coordinate... Capturing in {r}s!",
                    text_color="#f59e0b"
                ))
                time.sleep(1.0)

            x, y = mouse_ctrl.get_position()
            self.after(0, lambda: self._fill_entries(ent_x, ent_y, x, y))

        threading.Thread(target=worker, daemon=True).start()

    def _fill_entries(self, ent_x, ent_y, x, y):
        ent_x.delete(0, "end")
        ent_x.insert(0, str(x))
        ent_y.delete(0, "end")
        ent_y.insert(0, str(y))
        self.lbl_picker_feedback.configure(text=f"Captured point: ({x}, {y})", text_color="#10b981")
        DesktopSpotlight.ping(x, y)

    def _handle_test_move(self):
        try:
            x = int(self.ent_target_x.get())
            y = int(self.ent_target_y.get())
            duration = self.slider_duration.get()
            easing = self.opt_easing.get()
            
            def move_worker():
                DesktopSpotlight.ping(x, y)
                if hasattr(self, "radar"):
                    self.radar.ping_target(x, y)
                mouse_ctrl.move_to(x, y, duration=duration, easing_name=easing)

            threading.Thread(target=move_worker, daemon=True).start()
        except ValueError:
            self.lbl_picker_feedback.configure(text="Invalid X or Y integer!", text_color="#ef4444")

    def _handle_random_human_move(self):
        def worker():
            mouse_ctrl.human_move_random()
        threading.Thread(target=worker, daemon=True).start()

    def _handle_click(self, button: str, clicks: int):
        def click_worker():
            time.sleep(1.2)
            try:
                x = int(self.ent_target_x.get())
                y = int(self.ent_target_y.get())
                DesktopSpotlight.ping(x, y)
                mouse_ctrl.click(x=x, y=y, button=button, clicks=clicks)
            except ValueError:
                curr_x, curr_y = mouse_ctrl.get_position()
                DesktopSpotlight.ping(curr_x, curr_y)
                mouse_ctrl.click(button=button, clicks=clicks)

        threading.Thread(target=click_worker, daemon=True).start()

    def _handle_test_drag(self):
        try:
            sx = int(self.ent_drag_sx.get())
            sy = int(self.ent_drag_sy.get())
            ex = int(self.ent_drag_ex.get())
            ey = int(self.ent_drag_ey.get())

            def drag_worker():
                time.sleep(1.5)
                mouse_ctrl.drag_and_drop(sx, sy, ex, ey, duration=0.6)

            threading.Thread(target=drag_worker, daemon=True).start()
        except ValueError:
            pass

    def _handle_drag_select(self):
        try:
            sx = int(self.ent_drag_sx.get())
            sy = int(self.ent_drag_sy.get())
            ex = int(self.ent_drag_ex.get())
            ey = int(self.ent_drag_ey.get())

            def sel_worker():
                time.sleep(1.5)
                mouse_ctrl.select_text_by_drag(sx, sy, ex, ey)

            threading.Thread(target=sel_worker, daemon=True).start()
        except ValueError:
            pass

    def _handle_word_select(self):
        def worker():
            time.sleep(1.2)
            x, y = mouse_ctrl.get_position()
            mouse_ctrl.select_word_at(x, y)
        threading.Thread(target=worker, daemon=True).start()

    def _handle_line_select(self):
        def worker():
            time.sleep(1.2)
            x, y = mouse_ctrl.get_position()
            mouse_ctrl.select_line_at(x, y)
        threading.Thread(target=worker, daemon=True).start()

    def _handle_deselect(self):
        def desel_worker():
            time.sleep(1.2)
            mouse_ctrl.deselect_text()

        threading.Thread(target=desel_worker, daemon=True).start()

    def _handle_select_all(self):
        def sel_all_worker():
            time.sleep(1.2)
            mouse_ctrl.select_all()

        threading.Thread(target=sel_all_worker, daemon=True).start()
