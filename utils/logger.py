"""
DeskPilot - Centralized Logging System
Supports file logging, in-memory history, category tags, and real-time UI listeners.
"""

import logging
import threading
from datetime import datetime
from typing import Callable, List, Dict, Any, Optional
from pathlib import Path
from config import LOGS_DIR

# Dedicated log file
LOG_FILE_PATH = LOGS_DIR / "deskpilot.log"

# Setup standard python logging
_file_handler = logging.FileHandler(LOG_FILE_PATH, encoding="utf-8")
_file_handler.setFormatter(logging.Formatter(
    "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
))

_base_logger = logging.getLogger("DeskPilot")
_base_logger.setLevel(logging.DEBUG)
if not _base_logger.handlers:
    _base_logger.addHandler(_file_handler)


class LogEntry:
    """Represents a structured log entry with optional diagnostic metadata."""
    def __init__(
        self,
        category: str,
        level: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        suggestion: Optional[str] = None
    ):
        self.timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.full_timestamp = datetime.now().isoformat()
        self.category = category.upper()  # KEYBOARD, MOUSE, ACTION, SAFETY, SYSTEM, ERROR
        self.level = level.upper()        # INFO, WARN, ERROR, SUCCESS
        self.message = message
        self.details = details or {}
        self.suggestion = suggestion

    def to_dict(self) -> Dict[str, Any]:
        return {
            "time": self.timestamp,
            "category": self.category,
            "level": self.level,
            "message": self.message,
            "details": self.details,
            "suggestion": self.suggestion
        }

    def format_line(self) -> str:
        base = f"[{self.timestamp}] [{self.category}] [{self.level}] {self.message}"
        if self.suggestion and self.level == "ERROR":
            base += f" -> [Suggestion: {self.suggestion}]"
        return base



class EventLogger:
    """Thread-safe event logger with listener callbacks for real-time UI."""
    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        self._history: List[LogEntry] = []
        self._listeners: List[Callable[[LogEntry], None]] = []
        self._lock = threading.Lock()

    def add_listener(self, callback: Callable[[LogEntry], None]):
        """Register a callback for real-time log notifications."""
        with self._lock:
            if callback not in self._listeners:
                self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[LogEntry], None]):
        """Remove a previously registered callback."""
        with self._lock:
            if callback in self._listeners:
                self._listeners.remove(callback)

    def log(self, category: str, level: str, message: str) -> LogEntry:
        """Log an event, store it, write to file, and notify UI listeners."""
        entry = LogEntry(category, level, message)
        
        # Write to python logger
        py_level = getattr(logging, level.upper(), logging.INFO)
        _base_logger.log(py_level, f"[{category}] {message}")

        with self._lock:
            self._history.append(entry)
            if len(self._history) > self.max_history:
                self._history.pop(0)
            callbacks = list(self._listeners)

        # Notify UI callbacks without blocking lock
        for cb in callbacks:
            try:
                cb(entry)
            except Exception as e:
                print(f"[Logger Listener Error]: {e}")

        return entry

    def info(self, category: str, message: str) -> LogEntry:
        return self.log(category, "INFO", message)

    def action(self, category: str, message: str) -> LogEntry:
        return self.log(category, "ACTION", message)

    def warning(self, category: str, message: str) -> LogEntry:
        return self.log(category, "WARN", message)

    def error(self, category: str, message: str, details: Optional[Dict[str, Any]] = None, suggestion: Optional[str] = None) -> LogEntry:
        entry = LogEntry(category, "ERROR", message, details=details, suggestion=suggestion)
        _base_logger.error(f"[{category}] {message}" + (f" (Suggestion: {suggestion})" if suggestion else ""))
        with self._lock:
            self._history.append(entry)
            if len(self._history) > self.max_history:
                self._history.pop(0)
            callbacks = list(self._listeners)
        for cb in callbacks:
            try:
                cb(entry)
            except Exception as e:
                print(f"[Logger Listener Error]: {e}")
        return entry

    def error_detailed(
        self,
        category: str,
        message: str,
        error_type: str,
        action_type: Optional[str] = None,
        action_params: Optional[Dict[str, Any]] = None,
        coordinates: Optional[tuple] = None,
        suggestion: Optional[str] = None
    ) -> LogEntry:
        """Log a rich diagnostic error with full action context."""
        details = {
            "error_type": error_type,
            "action_type": action_type,
            "action_params": action_params or {},
            "coordinates": coordinates
        }
        return self.error(category, message, details=details, suggestion=suggestion)

    def success(self, category: str, message: str) -> LogEntry:
        return self.log(category, "SUCCESS", message)


    def get_history(self) -> List[LogEntry]:
        """Return a copy of recent history."""
        with self._lock:
            return list(self._history)

    def clear(self):
        """Clear memory history."""
        with self._lock:
            self._history.clear()


# Singleton application logger instance
logger = EventLogger()
