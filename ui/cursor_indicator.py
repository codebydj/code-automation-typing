"""
DeskPilot - Visual Mouse Cursor Position Indicator
Provides an interactive screen radar canvas widget for panels,
and an on-screen desktop coordinate spotlight overlay.
"""

import math
import tkinter as tk
import customtkinter as ctk
from typing import Tuple, Optional
from automation.mouse_controller import mouse_ctrl


class CursorRadarCanvas(ctk.CTkFrame):
    """
    Miniature visual radar canvas representing the full Windows desktop.
    Draws a glowing crosshair and live coordinate telemetry at the exact relative mouse position.
    """

    def __init__(self, master, width: int = 220, height: int = 124, **kwargs):
        super().__init__(master, fg_color="#121317", corner_radius=8, border_width=1, border_color="#2b2d3c", **kwargs)
        self.radar_width = width
        self.radar_height = height

        self.canvas = tk.Canvas(
            self,
            width=self.radar_width,
            height=self.radar_height,
            bg="#0e1015",
            highlightthickness=0
        )
        self.canvas.pack(padx=8, pady=8)

        self._sw, self._sh = mouse_ctrl.get_screen_size()
        self._target_x = 0
        self._target_y = 0

        self._draw_grid()
        self._update_radar()

    def _draw_grid(self):
        """Draw subtle grid lines and center guides."""
        self.canvas.delete("grid")
        mid_x = self.radar_width // 2
        mid_y = self.radar_height // 2

        # Subtle crosshairs
        self.canvas.create_line(mid_x, 0, mid_x, self.radar_height, fill="#1f2430", dash=(2, 2), tags="grid")
        self.canvas.create_line(0, mid_y, self.radar_width, mid_y, fill="#1f2430", dash=(2, 2), tags="grid")

        # Corner quadrant markers
        self.canvas.create_rectangle(2, 2, self.radar_width - 2, self.radar_height - 2, outline="#2b2d3c", width=1, tags="grid")

    def _update_radar(self):
        """Periodically query mouse coordinates and update radar indicator."""
        try:
            curr_x, curr_y = mouse_ctrl.get_position()
            rx = int((curr_x / max(1, self._sw)) * self.radar_width)
            ry = int((curr_y / max(1, self._sh)) * self.radar_height)

            # Clamp inside canvas
            rx = max(4, min(self.radar_width - 4, rx))
            ry = max(4, min(self.radar_height - 4, ry))

            # Redraw indicator
            self.canvas.delete("cursor_dot")
            
            # Outer glowing halo
            self.canvas.create_oval(rx - 8, ry - 8, rx + 8, ry + 8, outline="#0284c7", width=1, tags="cursor_dot")
            # Inner bright dot
            self.canvas.create_oval(rx - 3, ry - 3, rx + 3, ry + 3, fill="#38bdf8", outline="#ffffff", width=1, tags="cursor_dot")
            # Crosshair tics
            self.canvas.create_line(rx - 12, ry, rx - 5, ry, fill="#38bdf8", width=1, tags="cursor_dot")
            self.canvas.create_line(rx + 5, ry, rx + 12, ry, fill="#38bdf8", width=1, tags="cursor_dot")
            self.canvas.create_line(rx, ry - 12, rx, ry - 5, fill="#38bdf8", width=1, tags="cursor_dot")
            self.canvas.create_line(rx, ry + 5, rx, ry + 12, fill="#38bdf8", width=1, tags="cursor_dot")

            # Small coordinate tag
            tag_text = f"{curr_x},{curr_y}"
            text_x = rx + 14 if rx < self.radar_width - 60 else rx - 40
            text_y = ry - 10 if ry > 20 else ry + 12
            self.canvas.create_text(text_x, text_y, text=tag_text, fill="#9ca3af", font=("Consolas", 8), tags="cursor_dot")

        except Exception:
            pass

        self.after(50, self._update_radar)

    def ping_target(self, target_x: int, target_y: int):
        """Flash a distinct yellow/orange target ring at specific coordinate."""
        try:
            rx = int((target_x / max(1, self._sw)) * self.radar_width)
            ry = int((target_y / max(1, self._sh)) * self.radar_height)
            self.canvas.delete("target_ping")
            self.canvas.create_oval(rx - 10, ry - 10, rx + 10, ry + 10, outline="#fbbf24", width=2, tags="target_ping")
            self.after(500, lambda: self.canvas.delete("target_ping"))
        except Exception:
            pass


class DesktopSpotlight:
    """Non-intrusive on-screen spotlight ring around cursor position."""
    _instance: Optional[tk.Toplevel] = None

    @classmethod
    def ping(cls, x: int, y: int, radius: int = 36, duration_ms: int = 600):
        """Display a momentary pulsing target circle on Windows screen."""
        try:
            if cls._instance:
                try:
                    cls._instance.destroy()
                except Exception:
                    pass

            top = tk.Toplevel()
            top.overrideredirect(True)
            top.attributes("-topmost", True)
            top.attributes("-alpha", 0.75)
            # Make transparent background
            top.config(bg="magenta")
            top.wm_attributes("-transparentcolor", "magenta")

            size = radius * 2 + 10
            top.geometry(f"{size}x{size}+{x - size//2}+{y - size//2}")

            canvas = tk.Canvas(top, width=size, height=size, bg="magenta", highlightthickness=0)
            canvas.pack()

            # Draw outer ring and crosshair
            canvas.create_oval(5, 5, size - 5, size - 5, outline="#38bdf8", width=3)
            canvas.create_oval(15, 15, size - 15, size - 15, outline="#10b981", width=2)
            canvas.create_line(size//2, 0, size//2, size, fill="#ef4444", width=1)
            canvas.create_line(0, size//2, size, size//2, fill="#ef4444", width=1)

            top.after(duration_ms, lambda: top.destroy())
            cls._instance = top
        except Exception:
            pass
