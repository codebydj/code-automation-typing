"""
DeskPilot - Action Sequence Builder
Interactive workflow builder: add, edit, delete, reorder, save, load,
and execute multi-step desktop automation sequences.
"""

import time
import math
import json
import threading
from pathlib import Path
from tkinter import filedialog, messagebox
import customtkinter as ctk
from typing import List, Dict, Any, Optional, Callable
from config import load_config
from automation.sequence_executor import executor
from automation.mouse_controller import mouse_ctrl
from automation.safety import safety
from utils.storage import (
    save_sequence_to_file,
    load_sequence_from_file,
    list_saved_sequences,
    SEQUENCES_DIR
)
from utils.logger import logger


class ActionDialog(ctk.CTkToplevel):
    """Modal dialog for creating or editing a sequence action."""

    def __init__(self, parent, action_data: Optional[Dict[str, Any]] = None, on_save=None):
        super().__init__(parent)
        self.title("Configure Automation Action" if not action_data else "Edit Automation Action")
        self.geometry("540x560")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.on_save = on_save
        self.action_data = action_data or {}
        config = load_config()
        typing_cfg = config.get("typing", {})
        execution_cfg = config.get("execution", {})
        self.default_speed_delay = 1.0 / max(1.0, float(typing_cfg.get("speed_cps", 3.0)))
        self.default_action_pause = float(execution_cfg.get("default_action_pause", 0.1))

        self._build_ui()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # Title
        hdr = ctk.CTkFrame(self, fg_color="#181920", corner_radius=0)
        hdr.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        ctk.CTkLabel(
            hdr,
            text="Step Action Configuration",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color="#f3f4f6"
        ).pack(anchor="w", padx=20, pady=(14, 2))
        ctk.CTkLabel(
            hdr,
            text="Select action type and specify execution parameters.",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#9ca3af"
        ).pack(anchor="w", padx=20, pady=(0, 14))

        # Action Type Selector
        type_frame = ctk.CTkFrame(self, fg_color="transparent")
        type_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(12, 6))
        type_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(type_frame, text="Action Type:", font=ctk.CTkFont(size=13, weight="bold")).grid(row=0, column=0, sticky="w", padx=(0, 10))
        
        self.action_types = [
            "move_mouse",
            "type_text",
            "type_code",
            "press_key",
            "hotkey",
            "wait"
        ]
        
        curr_type = self.action_data.get("type", "move_mouse")

        self.opt_type = ctk.CTkOptionMenu(
            type_frame,
            values=self.action_types,
            command=self._on_type_changed
        )
        self.opt_type.set(curr_type)
        self.opt_type.grid(row=0, column=1, sticky="ew")

        # Dynamic parameter body
        self.body_frame = ctk.CTkFrame(self, fg_color="#181920", corner_radius=8)
        self.body_frame.grid(row=2, column=0, sticky="nsew", padx=20, pady=6)
        self.body_frame.grid_columnconfigure(1, weight=1)

        # Description and delay after (common to all actions)
        common_frame = ctk.CTkFrame(self, fg_color="transparent")
        common_frame.grid(row=3, column=0, sticky="ew", padx=20, pady=(4, 10))
        common_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(common_frame, text="Description:").grid(row=0, column=0, sticky="w", padx=(0, 10), pady=2)
        self.ent_desc = ctk.CTkEntry(common_frame, placeholder_text="e.g., Click target text box")
        self.ent_desc.insert(0, self.action_data.get("description", ""))
        self.ent_desc.grid(row=0, column=1, sticky="ew", pady=2)

        ctk.CTkLabel(common_frame, text="Delay After (s):").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=2)
        self.ent_delay = ctk.CTkEntry(common_frame, width=100)
        self.ent_delay.insert(0, str(self.action_data.get("delay_after", self.default_action_pause)))
        self.ent_delay.grid(row=1, column=1, sticky="w", pady=2)

        # Bottom buttons
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.grid(row=4, column=0, sticky="ew", padx=20, pady=(0, 16))

        btn_save = ctk.CTkButton(
            btn_row,
            text="Save Action",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color="#059669",
            hover_color="#10b981",
            width=130,
            command=self._handle_save
        )
        btn_save.pack(side="right", padx=(8, 0))

        btn_cancel = ctk.CTkButton(
            btn_row,
            text="Cancel",
            fg_color="#374151",
            hover_color="#4b5563",
            width=90,
            command=self.destroy
        )
        btn_cancel.pack(side="right")

        # Initialize parameter fields for current type
        self._on_type_changed(curr_type)

    def _clear_body(self):
        for widget in self.body_frame.winfo_children():
            widget.destroy()

    def _on_type_changed(self, choice: str):
        self._clear_body()

        if choice == "move_mouse":
            self._render_move_params()
        elif choice == "type_text":
            self._render_type_params()
        elif choice == "type_code":
            self._render_type_code_params()
        elif choice == "hotkey":
            self._render_hotkey_params()
        elif choice == "press_key":
            self._render_key_params()
        elif choice == "wait":
            self._render_wait_params()
        else:
            self._render_move_params()

    def _render_move_params(self):
        is_random = bool(self.action_data.get("random_movement", False))
        if "x" in self.action_data and self.action_data.get("x") is not None and "random_movement" not in self.action_data:
            is_random = False

        ctk.CTkLabel(self.body_frame, text="Movement Style:").grid(row=0, column=0, sticky="w", padx=12, pady=6)
        self.opt_move_mode = ctk.CTkOptionMenu(
            self.body_frame,
            values=["Random Human Movement (Random Time & Length, Move Only)", "Target Coordinates (X, Y)"],
            command=self._on_move_mode_changed
        )
        self.opt_move_mode.set("Random Human Movement (Random Time & Length, Move Only)" if is_random else "Target Coordinates (X, Y)")
        self.opt_move_mode.grid(row=0, column=1, sticky="ew", padx=12, pady=6)

        self.move_subframe = ctk.CTkFrame(self.body_frame, fg_color="transparent")
        self.move_subframe.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=0, pady=4)
        self.move_subframe.grid_columnconfigure(1, weight=1)

        self._render_move_subfields(is_random)

    def _on_move_mode_changed(self, choice: str):
        for widget in self.move_subframe.winfo_children():
            widget.destroy()
        is_random = "Random" in choice
        self._render_move_subfields(is_random)

    def _render_move_subfields(self, is_random: bool):
        if is_random:
            ctk.CTkLabel(
                self.move_subframe,
                text="✨ Human Cursor Movement (Move Only):\nNatural Bézier path with neuromuscular tremor for random time & length.\nNo clicking or unwanted cursor operations.",
                font=ctk.CTkFont(size=11),
                text_color="#38bdf8",
                justify="left"
            ).grid(row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(4, 8))

            ctk.CTkLabel(self.move_subframe, text="Min Duration (s):").grid(row=1, column=0, sticky="w", padx=12, pady=4)
            self.ent_min_dur = ctk.CTkEntry(self.move_subframe)
            self.ent_min_dur.insert(0, str(self.action_data.get("min_duration", 0.35)))
            self.ent_min_dur.grid(row=1, column=1, sticky="ew", padx=12, pady=4)

            ctk.CTkLabel(self.move_subframe, text="Max Duration (s):").grid(row=2, column=0, sticky="w", padx=12, pady=4)
            self.ent_max_dur = ctk.CTkEntry(self.move_subframe)
            self.ent_max_dur.insert(0, str(self.action_data.get("max_duration", 0.95)))
            self.ent_max_dur.grid(row=2, column=1, sticky="ew", padx=12, pady=4)

            ctk.CTkLabel(self.move_subframe, text="Min Length (px):").grid(row=3, column=0, sticky="w", padx=12, pady=4)
            self.ent_min_len = ctk.CTkEntry(self.move_subframe)
            self.ent_min_len.insert(0, str(self.action_data.get("min_length", 40)))
            self.ent_min_len.grid(row=3, column=1, sticky="ew", padx=12, pady=4)

            ctk.CTkLabel(self.move_subframe, text="Max Length (px):").grid(row=4, column=0, sticky="w", padx=12, pady=4)
            self.ent_max_len = ctk.CTkEntry(self.move_subframe)
            self.ent_max_len.insert(0, str(self.action_data.get("max_length", 220)))
            self.ent_max_len.grid(row=4, column=1, sticky="ew", padx=12, pady=4)

        else:
            ctk.CTkLabel(self.move_subframe, text="Target X:").grid(row=0, column=0, sticky="w", padx=12, pady=4)
            self.ent_x = ctk.CTkEntry(self.move_subframe)
            self.ent_x.insert(0, str(self.action_data.get("x", 500)))
            self.ent_x.grid(row=0, column=1, sticky="ew", padx=12, pady=4)

            ctk.CTkLabel(self.move_subframe, text="Target Y:").grid(row=1, column=0, sticky="w", padx=12, pady=4)
            self.ent_y = ctk.CTkEntry(self.move_subframe)
            self.ent_y.insert(0, str(self.action_data.get("y", 300)))
            self.ent_y.grid(row=1, column=1, sticky="ew", padx=12, pady=4)

            btn_pick = ctk.CTkButton(
                self.move_subframe,
                text="🎯 Pick Point (3s timer)",
                fg_color="#2563eb",
                hover_color="#3b82f6",
                command=lambda: self._countdown_pick_coords(self.ent_x, self.ent_y)
            )
            btn_pick.grid(row=2, column=0, columnspan=2, sticky="ew", padx=12, pady=6)

            ctk.CTkLabel(self.move_subframe, text="Duration (s):").grid(row=3, column=0, sticky="w", padx=12, pady=4)
            self.ent_dur = ctk.CTkEntry(self.move_subframe)
            self.ent_dur.insert(0, str(self.action_data.get("duration", 0.45)))
            self.ent_dur.grid(row=3, column=1, sticky="ew", padx=12, pady=4)

    def _render_type_params(self):
        ctk.CTkLabel(self.body_frame, text="Text Payload:").grid(row=0, column=0, sticky="nw", padx=12, pady=6)
        self.txt_type = ctk.CTkTextbox(self.body_frame, height=100, font=ctk.CTkFont(family="Consolas"))
        self.txt_type.insert("1.0", str(self.action_data.get("text", "")))
        self.txt_type.grid(row=0, column=1, sticky="ew", padx=12, pady=6)

        ctk.CTkLabel(self.body_frame, text="Fixed delay per char (seconds):").grid(row=1, column=0, sticky="w", padx=12, pady=6)
        self.ent_speed = ctk.CTkEntry(self.body_frame)
        self.ent_speed.insert(0, str(self.action_data.get("speed", self.default_speed_delay)))
        self.ent_speed.grid(row=1, column=1, sticky="ew", padx=12, pady=6)

    def _render_type_code_params(self):
        ctk.CTkLabel(
            self.body_frame,
            text="💻 Types code directly from center Code Editor at 3 chars/sec.\nPreserves all syntax, indentation, and newlines.",
            font=ctk.CTkFont(size=12),
            text_color="#38bdf8",
            justify="left"
        ).grid(row=0, column=0, columnspan=2, padx=12, pady=16)

        ctk.CTkLabel(self.body_frame, text="Fixed delay per char (seconds):").grid(row=1, column=0, sticky="w", padx=12, pady=6)
        self.ent_speed = ctk.CTkEntry(self.body_frame)
        self.ent_speed.insert(0, str(self.action_data.get("speed", self.default_speed_delay)))
        self.ent_speed.grid(row=1, column=1, sticky="ew", padx=12, pady=6)

    def _render_hotkey_params(self):
        ctk.CTkLabel(self.body_frame, text="Shortcut / Hotkey:").grid(row=0, column=0, sticky="w", padx=12, pady=6)
        self.ent_hotkey = ctk.CTkEntry(self.body_frame, placeholder_text="e.g. ctrl+c, alt+tab, win+r")
        self.ent_hotkey.insert(0, str(self.action_data.get("keys", "ctrl+c")))
        self.ent_hotkey.grid(row=0, column=1, sticky="ew", padx=12, pady=6)

    def _render_key_params(self):
        ctk.CTkLabel(self.body_frame, text="Key Name:").grid(row=0, column=0, sticky="w", padx=12, pady=6)
        self.ent_key = ctk.CTkEntry(self.body_frame, placeholder_text="enter, tab, backspace, delete")
        self.ent_key.insert(0, str(self.action_data.get("key", "enter")))
        self.ent_key.grid(row=0, column=1, sticky="ew", padx=12, pady=6)

        ctk.CTkLabel(self.body_frame, text="Repeat Count:").grid(row=1, column=0, sticky="w", padx=12, pady=6)
        self.ent_repeat = ctk.CTkEntry(self.body_frame)
        self.ent_repeat.insert(0, str(self.action_data.get("presses", 1)))
        self.ent_repeat.grid(row=1, column=1, sticky="ew", padx=12, pady=6)

    def _render_wait_params(self):
        ctk.CTkLabel(self.body_frame, text="Seconds to Sleep:").grid(row=0, column=0, sticky="w", padx=12, pady=6)
        self.ent_wait = ctk.CTkEntry(self.body_frame)
        self.ent_wait.insert(0, str(self.action_data.get("seconds", 1.0)))
        self.ent_wait.grid(row=0, column=1, sticky="ew", padx=12, pady=6)

    def _countdown_pick_coords(self, ent_x, ent_y):
        def worker():
            time.sleep(3.0)
            x, y = mouse_ctrl.get_position()
            self.after(0, lambda: self._set_picked(ent_x, ent_y, x, y))
        threading.Thread(target=worker, daemon=True).start()

    def _set_picked(self, ent_x, ent_y, x, y):
        ent_x.delete(0, "end")
        ent_x.insert(0, str(x))
        ent_y.delete(0, "end")
        ent_y.insert(0, str(y))

    def _handle_save(self):
        action_type = self.opt_type.get()
        data: Dict[str, Any] = {
            "type": action_type,
            "description": self.ent_desc.get().strip() or action_type
        }

        try:
            delay = float(self.ent_delay.get())
            if not math.isfinite(delay) or delay < 0:
                raise ValueError("Delay after an action must be a non-negative number of seconds.")
            data["delay_after"] = delay

            if action_type == "move_mouse":
                is_rand = hasattr(self, "opt_move_mode") and "Random" in self.opt_move_mode.get()
                data["random_movement"] = is_rand
                if is_rand:
                    data["min_duration"] = float(self.ent_min_dur.get()) if hasattr(self, "ent_min_dur") else 0.35
                    data["max_duration"] = float(self.ent_max_dur.get()) if hasattr(self, "ent_max_dur") else 0.95
                    data["min_length"] = int(self.ent_min_len.get()) if hasattr(self, "ent_min_len") else 40
                    data["max_length"] = int(self.ent_max_len.get()) if hasattr(self, "ent_max_len") else 220
                    data["description"] = self.ent_desc.get().strip() or "Human cursor movement (random length & time)"
                else:
                    data["x"] = int(self.ent_x.get())
                    data["y"] = int(self.ent_y.get())
                    data["duration"] = float(self.ent_dur.get())
                    data["description"] = self.ent_desc.get().strip() or f"Human cursor movement to ({data['x']}, {data['y']})"

            elif action_type in ["type_text", "type_code"]:
                if action_type == "type_text":
                    data["text"] = self.txt_type.get("1.0", "end-1c")
                speed = float(self.ent_speed.get())
                if not math.isfinite(speed) or speed <= 0:
                    raise ValueError("Per-character delay must be a positive number of seconds.")
                data["speed"] = speed
                data["description"] = self.ent_desc.get().strip() or ("Type custom text" if action_type == "type_text" else "Type editor code")

            elif action_type == "hotkey":
                data["keys"] = self.ent_hotkey.get().strip()
                data["description"] = self.ent_desc.get().strip() or f"Shortcut: {data['keys'].upper()}"

            elif action_type == "press_key":
                data["key"] = self.ent_key.get().strip()
                data["presses"] = int(self.ent_repeat.get())
                data["description"] = self.ent_desc.get().strip() or f"Press {data['key'].upper()} x{data['presses']}"

            elif action_type == "wait":
                data["seconds"] = float(self.ent_wait.get())
                data["description"] = self.ent_desc.get().strip() or f"Pause for {data['seconds']:.2f}s"

            if self.on_save:
                self.on_save(data)
            self.destroy()

        except Exception as e:
            messagebox.showerror("Validation Error", f"Please check your input values:\n{e}", parent=self)


class SequenceBuilderPanel(ctk.CTkFrame):
    """Main sequence builder visual manager."""

    def __init__(self, master, on_actions_changed: Optional[Callable[[], None]] = None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self.on_actions_changed = on_actions_changed
        self.current_sequence_name = "Untitled Sequence"
        self.current_filepath: Optional[Path] = None
        self.actions: List[Dict[str, Any]] = []

        self._create_header_bar()
        self._create_toolbar()
        self._create_action_list_view()
        self._create_bottom_bar()

        # Load initial sequence from sample
        saved = list_saved_sequences()
        if saved:
            self._load_from_filepath(Path(saved[0]["path"]))

    def _create_header_bar(self):
        """Header showing sequence name, description, and save/load buttons."""
        hdr = ctk.CTkFrame(self, fg_color="#181920", corner_radius=10, border_width=1, border_color="#2b2d3c")
        hdr.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 10))
        hdr.grid_columnconfigure(0, weight=1)

        left = ctk.CTkFrame(hdr, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w", padx=16, pady=12)

        self.lbl_seq_title = ctk.CTkLabel(
            left,
            text=f"🔄 Sequence: {self.current_sequence_name}",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color="#f3f4f6"
        )
        self.lbl_seq_title.pack(anchor="w")

        self.lbl_seq_sub = ctk.CTkLabel(
            left,
            text="Compose ordered steps: mouse movements, clicks, text typing, shortcuts, and delays.",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#9ca3af"
        )
        self.lbl_seq_sub.pack(anchor="w")

        # Right Action buttons
        right = ctk.CTkFrame(hdr, fg_color="transparent")
        right.grid(row=0, column=1, sticky="e", padx=16, pady=12)

        btn_new = ctk.CTkButton(
            right,
            text="✨ New",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#374151",
            hover_color="#4b5563",
            width=75,
            command=self._handle_new_sequence
        )
        btn_new.pack(side="left", padx=3)

        btn_load = ctk.CTkButton(
            right,
            text="📂 Load",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#374151",
            hover_color="#4b5563",
            width=80,
            command=self._handle_load_dialog
        )
        btn_load.pack(side="left", padx=3)

        btn_save = ctk.CTkButton(
            right,
            text="💾 Save",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#2563eb",
            hover_color="#3b82f6",
            width=80,
            command=self._handle_save_sequence
        )
        btn_save.pack(side="left", padx=3)

    def _create_toolbar(self):
        """Action management buttons: Add, Edit, Delete, Move Up, Move Down, Clear."""
        tb = ctk.CTkFrame(self, fg_color="#1f212a", corner_radius=10, border_width=1, border_color="#2b2d3c")
        tb.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 10))

        btn_add = ctk.CTkButton(
            tb,
            text="➕ Add Action",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color="#059669",
            hover_color="#10b981",
            height=34,
            command=self._handle_add_action
        )
        btn_add.pack(side="left", padx=(14, 6), pady=8)

        self.btn_edit = ctk.CTkButton(
            tb,
            text="✏️ Edit",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#374151",
            hover_color="#4b5563",
            width=85,
            height=34,
            command=self._handle_edit_action
        )
        self.btn_edit.pack(side="left", padx=4, pady=8)

        self.btn_del = ctk.CTkButton(
            tb,
            text="🗑️ Delete",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#7f1d1d",
            hover_color="#991b1b",
            width=85,
            height=34,
            command=self._handle_delete_action
        )
        self.btn_del.pack(side="left", padx=4, pady=8)

        self.btn_up = ctk.CTkButton(
            tb,
            text="▲ Move Up",
            font=ctk.CTkFont(size=12),
            fg_color="#374151",
            hover_color="#4b5563",
            width=90,
            height=34,
            command=self._handle_move_up
        )
        self.btn_up.pack(side="left", padx=4, pady=8)

        self.btn_down = ctk.CTkButton(
            tb,
            text="▼ Move Down",
            font=ctk.CTkFont(size=12),
            fg_color="#374151",
            hover_color="#4b5563",
            width=95,
            height=34,
            command=self._handle_move_down
        )
        self.btn_down.pack(side="left", padx=4, pady=8)

        self.btn_run_one = ctk.CTkButton(
            tb, text="▶ Run selected", font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#2563eb", hover_color="#3b82f6", width=105, height=34,
            command=self._handle_run_selected
        )
        self.btn_run_one.pack(side="left", padx=4, pady=8)

        btn_clear = ctk.CTkButton(
            tb,
            text="Clear All",
            font=ctk.CTkFont(size=12),
            fg_color="#374151",
            hover_color="#4b5563",
            width=85,
            height=34,
            command=self._handle_clear_all
        )
        btn_clear.pack(side="right", padx=(4, 14), pady=8)

    def _create_action_list_view(self):
        """Scrollable frame displaying each action step with card layout."""
        self.list_container = ctk.CTkScrollableFrame(
            self,
            fg_color="#181920",
            corner_radius=10,
            border_width=1,
            border_color="#2b2d3c"
        )
        self.list_container.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 10))
        self.list_container.grid_columnconfigure(0, weight=1)

        self.selected_action_index: Optional[int] = None
        self._action_item_widgets = []

    def _create_bottom_bar(self):
        """Bottom bar with action count summary and Run Sequence button."""
        bottom = ctk.CTkFrame(self, fg_color="#181920", corner_radius=10, border_width=1, border_color="#2b2d3c")
        bottom.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 16))
        bottom.grid_columnconfigure(0, weight=1)

        self.lbl_summary = ctk.CTkLabel(
            bottom,
            text="0 actions in sequence",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color="#9ca3af"
        )
        self.lbl_summary.grid(row=0, column=0, sticky="w", padx=16, pady=12)

        ctk.CTkLabel(bottom, text="Use Start in the top toolbar to run the sequence.",
                     font=ctk.CTkFont(size=11), text_color="#6b7280").grid(row=0, column=1, sticky="e", padx=16, pady=12)

    def _refresh_list(self):
        """Re-render all action cards in list."""
        for w in self.list_container.winfo_children():
            w.destroy()
        self._action_item_widgets.clear()
        default_action_pause = float(
            load_config().get("execution", {}).get("default_action_pause", 0.1)
        )

        icon_map = {
            "move_mouse": "🖱️",
            "type_text": "🔤",
            "type_code": "💻",
            "hotkey": "⚡",
            "press_key": "↵",
            "wait": "⏳"
        }

        if not self.actions:
            empty_lbl = ctk.CTkLabel(
                self.list_container,
                text="No actions in sequence. Click '➕ Add Action' to start building your automated workflow.",
                font=ctk.CTkFont(family="Segoe UI", size=13),
                text_color="#6b7280"
            )
            empty_lbl.pack(pady=40)
            self.lbl_summary.configure(text="0 actions in sequence")
            return

        for idx, act in enumerate(self.actions):
            act_type = act.get("type", "action")
            icon = icon_map.get(act_type, "⚙️")
            desc = act.get("description", act_type)
            delay = act.get("delay_after", default_action_pause)

            # Details string
            details = []
            if act_type == "move_mouse":
                if act.get("random_movement", False) or ("x" not in act and "y" not in act):
                    min_d = act.get("min_duration", 0.35)
                    max_d = act.get("max_duration", 0.95)
                    min_l = act.get("min_length", 40)
                    max_l = act.get("max_length", 220)
                    details.append(f"Human motion: random {min_l}-{max_l}px over {min_d:.2f}-{max_d:.2f}s (move only)")
                else:
                    details.append(f"Human motion to ({act.get('x', 0)}, {act.get('y', 0)}) over {act.get('duration', 0.45)}s (move only)")
            elif act_type == "type_code":
                spd = act.get("speed", 0.333)
                details.append(f"Center Editor Code at {round(1.0/max(0.001, spd), 1)} chars/sec")
            elif act_type == "type_text":
                txt = repr(act.get("text", ""))
                details.append(f"payload: {txt[:25]}..." if len(txt) > 25 else f"payload: {txt}")
            elif act_type == "hotkey":
                details.append(f"keys: [{act.get('keys', '').upper()}]")
            elif act_type == "press_key":
                details.append(f"key: [{act.get('key', '').upper()}] x{act.get('presses', 1)}")
            elif act_type == "wait":
                details.append(f"duration: {act.get('seconds', 1.0)}s")
            else:
                details.append(str(act_type))

            details_str = " • ".join(details)
            is_selected = (self.selected_action_index == idx)
            card_bg = "#2563eb" if is_selected else "#1f212a"

            card = ctk.CTkFrame(
                self.list_container,
                fg_color=card_bg,
                corner_radius=8,
                border_width=1,
                border_color="#3b82f6" if is_selected else "#2b2d3c"
            )
            card.pack(fill="x", padx=6, pady=4)
            card.grid_columnconfigure(1, weight=1)

            # Step number badge
            badge = ctk.CTkLabel(
                card,
                text=f"Step {idx + 1}",
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                fg_color="#374151" if not is_selected else "#1d4ed8",
                corner_radius=6,
                width=60,
                height=26
            )
            badge.grid(row=0, column=0, padx=10, pady=8)

            # Info text
            text_box = ctk.CTkFrame(card, fg_color="transparent")
            text_box.grid(row=0, column=1, sticky="w", padx=6, pady=6)

            title_lbl = ctk.CTkLabel(
                text_box,
                text=f"{icon}  [{act_type.upper()}] - {desc}",
                font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                text_color="#f3f4f6"
            )
            title_lbl.pack(anchor="w")

            sub_lbl = ctk.CTkLabel(
                text_box,
                text=f"{details_str} • Delay after: {delay:.2f}s",
                font=ctk.CTkFont(family="Segoe UI", size=11),
                text_color="#9ca3af"
            )
            sub_lbl.pack(anchor="w")

            # Selection bind
            for w in [card, badge, text_box, title_lbl, sub_lbl]:
                w.bind("<Button-1>", lambda e, i=idx: self._select_action(i))

            self._action_item_widgets.append(card)

        self.lbl_summary.configure(text=f"{len(self.actions)} actions in sequence")

    def _select_action(self, index: int):
        self.selected_action_index = index
        self._refresh_list()

    def _handle_add_action(self):
        def on_saved(new_action):
            self.actions.append(new_action)
            self.selected_action_index = len(self.actions) - 1
            self._refresh_list()
            if self.on_actions_changed:
                self.on_actions_changed()
        ActionDialog(self, on_save=on_saved)

    def _handle_edit_action(self):
        if self.selected_action_index is None or self.selected_action_index >= len(self.actions):
            messagebox.showinfo("Select Action", "Please select an action from the list first.", parent=self)
            return

        act = self.actions[self.selected_action_index]
        def on_saved(updated_action):
            self.actions[self.selected_action_index] = updated_action
            self._refresh_list()
            if self.on_actions_changed:
                self.on_actions_changed()
        ActionDialog(self, action_data=act, on_save=on_saved)

    def _handle_delete_action(self):
        if self.selected_action_index is None or self.selected_action_index >= len(self.actions):
            return
        del self.actions[self.selected_action_index]
        if self.actions:
            self.selected_action_index = min(self.selected_action_index, len(self.actions) - 1)
        else:
            self.selected_action_index = None
        self._refresh_list()
        if self.on_actions_changed:
            self.on_actions_changed()

    def _handle_run_selected(self):
        """Run exactly the selected action in the background executor."""
        idx = self.selected_action_index
        if idx is None or idx >= len(self.actions):
            messagebox.showinfo("Select Action", "Select an action to execute.", parent=self)
            return
        executor.run_single_action(dict(self.actions[idx]))

    def _handle_move_up(self):
        idx = self.selected_action_index
        if idx is not None and idx > 0:
            self.actions[idx], self.actions[idx - 1] = self.actions[idx - 1], self.actions[idx]
            self.selected_action_index = idx - 1
            self._refresh_list()

    def _handle_move_down(self):
        idx = self.selected_action_index
        if idx is not None and idx < len(self.actions) - 1:
            self.actions[idx], self.actions[idx + 1] = self.actions[idx + 1], self.actions[idx]
            self.selected_action_index = idx + 1
            self._refresh_list()

    def _handle_clear_all(self):
        if not self.actions:
            return
        if messagebox.askyesno("Confirm Clear", "Clear all actions from this sequence?", parent=self):
            self.actions.clear()
            self.selected_action_index = None
            self._refresh_list()

    def _handle_new_sequence(self):
        self.actions.clear()
        self.selected_action_index = None
        self.current_sequence_name = "Untitled Sequence"
        self.current_filepath = None
        self.lbl_seq_title.configure(text=f"🔄 Sequence: {self.current_sequence_name}")
        self._refresh_list()

    def _handle_save_sequence(self):
        if not self.actions:
            messagebox.showwarning("Empty Sequence", "Add at least one action before saving.", parent=self)
            return

        filepath = filedialog.asksaveasfilename(
            initialdir=str(SEQUENCES_DIR),
            initialfile="my_automation_sequence.json",
            defaultextension=".json",
            filetypes=[("JSON Sequence Files", "*.json")]
        )
        if filepath:
            data = {
                "name": Path(filepath).stem.replace("_", " ").title(),
                "description": "User created automated sequence",
                "actions": self.actions
            }
            if save_sequence_to_file(data, Path(filepath)):
                self.current_sequence_name = data["name"]
                self.current_filepath = Path(filepath)
                self.lbl_seq_title.configure(text=f"🔄 Sequence: {self.current_sequence_name}")
                messagebox.showinfo("Saved", f"Sequence successfully saved to:\n{Path(filepath).name}", parent=self)

    def _handle_load_dialog(self):
        filepath = filedialog.askopenfilename(
            initialdir=str(SEQUENCES_DIR),
            filetypes=[("JSON Sequence Files", "*.json"), ("All Files", "*.*")]
        )
        if filepath:
            self._load_from_filepath(Path(filepath))

    def _load_from_filepath(self, path: Path):
        data = load_sequence_from_file(path)
        if data and "actions" in data:
            self.actions = data["actions"]
            self.current_sequence_name = data.get("name", path.stem)
            self.current_filepath = path
            self.lbl_seq_title.configure(text=f"🔄 Sequence: {self.current_sequence_name}")
            self.selected_action_index = 0 if self.actions else None
            self._refresh_list()
            logger.info("SEQUENCE", f"Loaded sequence '{self.current_sequence_name}' ({len(self.actions)} actions).")
            if self.on_actions_changed:
                self.on_actions_changed()

    def _handle_run_sequence(self):
        """Execute active sequence with safety confirmation & countdown."""
        if not self.actions:
            messagebox.showwarning("Empty Sequence", "Add at least one action to execute.", parent=self)
            return

        # Safety confirmation
        confirm = messagebox.askyesno(
            "Confirm Execution",
            f"Are you ready to execute sequence '{self.current_sequence_name}'?\n\n"
            f"• Total actions: {len(self.actions)}\n"
            f"• A 3-second countdown will begin to let you focus your target window.\n"
            f"• Press ESC anytime to trigger Emergency Stop.",
            parent=self
        )
        if not confirm:
            return

        executor.start(self.actions, countdown_seconds=3)
