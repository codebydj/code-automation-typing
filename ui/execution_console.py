"""Compact execution status, progress, and log console for the main window."""

import queue
import tkinter as tk
from typing import Any, Dict

import customtkinter as ctk

from utils.logger import LogEntry, logger


class ExecutionConsole(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            fg_color="#181920",
            corner_radius=8,
            border_width=1,
            border_color="#2b2d3c",
            **kwargs
        )
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self._updates = queue.Queue()

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=8, pady=(5, 2))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header,
            text="Execution Console",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#cbd5e1"
        ).grid(row=0, column=0, sticky="w")
        self.lbl_status = ctk.CTkLabel(
            header,
            text="Ready",
            font=ctk.CTkFont(size=10),
            text_color="#34d399"
        )
        self.lbl_status.grid(row=0, column=1, sticky="e")

        self.progress = ctk.CTkProgressBar(self, height=6)
        self.progress.set(0)
        self.progress.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 4))

        self.txt_logs = ctk.CTkTextbox(
            self,
            height=95,
            font=ctk.CTkFont(family="Consolas", size=10),
            fg_color="#111318",
            text_color="#d1d5db",
            wrap="word"
        )
        self.txt_logs.grid(row=2, column=0, sticky="nsew", padx=6, pady=(0, 6))
        logger.add_listener(self._on_log_entry)
        self._after_id = self.after(40, self._drain_updates)

    def _on_log_entry(self, entry: LogEntry):
        self._updates.put(("log", entry))

    def update_state(self, state: str):
        self._updates.put(("state", state))

    def update_telemetry(self, data: Dict[str, Any]):
        self._updates.put(("telemetry", dict(data)))

    def _drain_updates(self):
        for _ in range(100):
            try:
                kind, value = self._updates.get_nowait()
            except queue.Empty:
                break

            if kind == "log":
                self.txt_logs.insert("end", value.format_line() + "\n")
                line_count = int(self.txt_logs.index("end-1c").split(".")[0])
                if line_count > 500:
                    self.txt_logs.delete("1.0", f"{line_count - 500}.0")
                self.txt_logs.see("end")
            elif kind == "state":
                self.lbl_status.configure(text=str(value).replace("_", " ").title())
            elif kind == "telemetry":
                if "state" in value:
                    self.lbl_status.configure(text=str(value["state"]).replace("_", " ").title())
                if "pct" in value:
                    self.progress.set(max(0.0, min(1.0, float(value["pct"]) / 100.0)))
                if "message" in value:
                    self.lbl_status.configure(text=str(value["message"]))

        self._after_id = self.after(40, self._drain_updates)

    def destroy(self):
        logger.remove_listener(self._on_log_entry)
        after_id = getattr(self, "_after_id", None)
        if after_id:
            try:
                self.after_cancel(after_id)
            except tk.TclError:
                pass
        super().destroy()
