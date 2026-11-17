"""
DeskPilot IDE - Left Panel: Project Explorer & Script Library
Provides file browsing, sequence templates, automation task sets, and recent files.
"""

from pathlib import Path
from typing import Callable, Optional, List, Dict, Any
import customtkinter as ctk
from config import SEQUENCES_DIR, BASE_DIR
from utils.storage import list_saved_sequences, load_sequence_from_file

DEMO_SCRIPTS = [
    {
        "name": "python_demo.py",
        "lang": "Python",
        "desc": "Function with special symbols & dictionary",
        "code": (
            "# DeskPilot IDE - Python Demo\n"
            "def authenticate_user(username: str, token: str) -> dict:\n"
            "    \"\"\"Validate user session credentials.\"\"\"\n"
            "    symbols = \"{} [] () <> =+ -* &| !? @#$%^~ :;\"\n"
            "    if username and len(token) >= 16:\n"
            "        return {\"status\": \"SUCCESS\", \"code\": 200}\n"
            "    return {\"status\": \"DENIED\", \"code\": 401}\n"
        )
    },
    {
        "name": "calc_velocity.py",
        "lang": "Python",
        "desc": "Calculates speed with error handling",
        "code": (
            "def calculate_velocity(distance_km: float, time_hr: float) -> float:\n"
            "    \"\"\"Compute average velocity in km/h.\"\"\"\n"
            "    if time_hr <= 0:\n"
            "        raise ValueError(\"Time must be greater than zero.\")\n"
            "    return round(distance_km / time_hr, 2)\n"
        )
    },
    {
        "name": "async_task.js",
        "lang": "JavaScript",
        "desc": "Modern JS async/await automation",
        "code": (
            "async function submitData(payload) {\n"
            "    const response = await fetch('/api/tasks', {\n"
            "        method: 'POST',\n"
            "        body: JSON.stringify(payload)\n"
            "    });\n"
            "    return await response.json();\n"
            "}\n"
        )
    },
    {
        "name": "query_logs.sql",
        "lang": "SQL",
        "desc": "SQL aggregation query",
        "code": (
            "SELECT action_type, COUNT(*) as total_count\n"
            "FROM audit_logs\n"
            "WHERE created_at >= NOW() - INTERVAL '24 HOURS'\n"
            "GROUP BY action_type\n"
            "ORDER BY total_count DESC;\n"
        )
    }
]


class IDEExplorer(ctk.CTkFrame):
    """
    Left sidebar for the IDE containing File Explorer, Automation Tasks,
    Saved Sequences, and Quick Scripts.
    """
    def __init__(
        self,
        master,
        on_open_file: Optional[Callable[[str, str, str], None]] = None,
        on_load_sequence: Optional[Callable[[Dict[str, Any]], None]] = None,
        **kwargs
    ):
        super().__init__(master, fg_color="#181920", corner_radius=8, border_width=1, border_color="#2b2d3c", **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.on_open_file = on_open_file
        self.on_load_sequence = on_load_sequence

        self._create_header()
        self._create_tabs()

    def _create_header(self):
        """Explorer panel title and quick file action buttons."""
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))

        lbl_title = ctk.CTkLabel(
            hdr,
            text="📁 EXPLORER",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color="#f3f4f6"
        )
        lbl_title.pack(side="left")

        btn_refresh = ctk.CTkButton(
            hdr,
            text="🔄",
            width=28,
            height=24,
            fg_color="#2b2d3c",
            hover_color="#374151",
            font=ctk.CTkFont(size=11),
            command=self.refresh
        )
        btn_refresh.pack(side="right")

    def _create_tabs(self):
        """Segmented view for Files, Saved Scripts, and Automation Tasks."""
        self.tabview = ctk.CTkTabview(
            self,
            fg_color="transparent",
            segmented_button_fg_color="#14151b",
            segmented_button_selected_color="#2563eb",
            segmented_button_selected_hover_color="#3b82f6"
        )
        self.tabview.grid(row=1, column=0, sticky="nsew", padx=6, pady=4)

        # Tab 1: Project Scripts
        self.tab_files = self.tabview.add("Scripts")
        self._build_scripts_tab(self.tab_files)

        # Tab 2: Saved Automation Sequences
        self.tab_seq = self.tabview.add("Sequences")
        self._build_sequences_tab(self.tab_seq)

    def _build_scripts_tab(self, parent):
        """Build the scripts and templates list."""
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            parent,
            text="Built-in IDE Scripts & Templates:",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#9ca3af",
            anchor="w"
        ).grid(row=0, column=0, sticky="w", padx=4, pady=(4, 6))

        scroll_box = ctk.CTkScrollableFrame(parent, fg_color="#14151b", corner_radius=6)
        scroll_box.grid(row=1, column=0, sticky="nsew", padx=2, pady=2)
        scroll_box.grid_columnconfigure(0, weight=1)

        for idx, item in enumerate(DEMO_SCRIPTS):
            card = ctk.CTkFrame(scroll_box, fg_color="#1f212a", corner_radius=6)
            card.pack(fill="x", padx=4, pady=3)
            card.grid_columnconfigure(0, weight=1)

            btn = ctk.CTkButton(
                card,
                text=f"📄 {item['name']}",
                anchor="w",
                font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
                fg_color="transparent",
                hover_color="#2d303e",
                text_color="#38bdf8",
                height=26,
                command=lambda s=item: self._on_script_clicked(s)
            )
            btn.pack(fill="x", padx=4, pady=(4, 0))

            lbl_sub = ctk.CTkLabel(
                card,
                text=f"{item['lang']} • {item['desc']}",
                font=ctk.CTkFont(size=10),
                text_color="#9ca3af",
                anchor="w"
            )
            lbl_sub.pack(fill="x", padx=8, pady=(0, 4))

    def _build_sequences_tab(self, parent):
        """Build the saved sequences list."""
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            parent,
            text="Saved Multi-Task Sequences:",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#9ca3af",
            anchor="w"
        ).grid(row=0, column=0, sticky="w", padx=4, pady=(4, 6))

        self.seq_scroll_box = ctk.CTkScrollableFrame(parent, fg_color="#14151b", corner_radius=6)
        self.seq_scroll_box.grid(row=1, column=0, sticky="nsew", padx=2, pady=2)
        self.seq_scroll_box.grid_columnconfigure(0, weight=1)

        self._populate_sequences()

    def _populate_sequences(self):
        """Load JSON sequence files from disk into UI."""
        for child in self.seq_scroll_box.winfo_children():
            child.destroy()

        saved_files = list_saved_sequences()
        if not saved_files:
            ctk.CTkLabel(
                self.seq_scroll_box,
                text="No saved sequences found.",
                font=ctk.CTkFont(size=11),
                text_color="#6b7280"
            ).pack(padx=8, pady=12)
            return

        for p in saved_files:
            file_path = p.get("path") if isinstance(p, dict) else str(p)
            seq_data = load_sequence_from_file(file_path)
            if not seq_data:
                continue

            name = seq_data.get("name", p.get("name", "Sequence") if isinstance(p, dict) else "Sequence")
            actions = seq_data.get("actions", [])
            filename = p.get("filename", "") if isinstance(p, dict) else ""
            
            card = ctk.CTkFrame(self.seq_scroll_box, fg_color="#1f212a", corner_radius=6)
            card.pack(fill="x", padx=4, pady=3)

            btn = ctk.CTkButton(
                card,
                text=f"⚡ {name}",
                anchor="w",
                font=ctk.CTkFont(size=12, weight="bold"),
                fg_color="transparent",
                hover_color="#2d303e",
                text_color="#10b981",
                height=26,
                command=lambda d=seq_data: self._on_sequence_clicked(d)
            )
            btn.pack(fill="x", padx=4, pady=(4, 0))

            lbl_info = ctk.CTkLabel(
                card,
                text=f"{len(actions)} tasks • {filename}",
                font=ctk.CTkFont(size=10),
                text_color="#9ca3af",
                anchor="w"
            )
            lbl_info.pack(fill="x", padx=8, pady=(0, 4))

    def _on_script_clicked(self, script_item: Dict[str, Any]):
        if self.on_open_file:
            self.on_open_file(script_item["code"], script_item["name"], script_item["lang"])

    def _on_sequence_clicked(self, sequence_data: Dict[str, Any]):
        if self.on_load_sequence:
            self.on_load_sequence(sequence_data)

    def refresh(self):
        """Reload saved sequences and scripts."""
        self._populate_sequences()
