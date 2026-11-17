"""Non-suppressing Windows hotkeys that ignore automation-injected key events."""

import ctypes
import threading
from ctypes import wintypes
from typing import Callable, Dict, Iterable, Optional, Set, Tuple

from utils.logger import logger


_MODIFIERS = {"ctrl", "alt", "shift", "win"}
_VK_BY_NAME = {
    "backspace": 0x08,
    "tab": 0x09,
    "enter": 0x0D,
    "shift": 0x10,
    "ctrl": 0x11,
    "alt": 0x12,
    "pause": 0x13,
    "caps lock": 0x14,
    "esc": 0x1B,
    "space": 0x20,
    "page up": 0x21,
    "page down": 0x22,
    "end": 0x23,
    "home": 0x24,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
    "insert": 0x2D,
    "delete": 0x2E,
    "win": 0x5B,
}
_PROTECTED_KEYS = {
    "a", "c", "s", "v", "x", "z",
    "1", "2", "3", "4",
    "enter", "tab", "left", "right", "up", "down",
}


def normalize_hotkey(value: str) -> Tuple[str, ...]:
    aliases = {
        "control": "ctrl",
        "escape": "esc",
        "return": "enter",
        "windows": "win",
        "command": "win",
    }
    parts = tuple(
        aliases.get(part.strip().lower(), part.strip().lower())
        for part in str(value).split("+")
        if part.strip()
    )
    if not parts or len(set(parts)) != len(parts):
        raise ValueError(f"Invalid hotkey: {value!r}")
    action_keys = [part for part in parts if part not in _MODIFIERS]
    if len(action_keys) != 1:
        raise ValueError(f"Hotkey {value!r} must have exactly one non-modifier key.")

    act_key = action_keys[0]
    is_fn_key = act_key.startswith("f") and act_key[1:].isdigit()

    if not is_fn_key:
        if len(parts) < 3 or not {"ctrl", "alt"}.issubset(parts):
            raise ValueError(
                f"Hotkey {value!r} must include Ctrl+Alt or be a dedicated function key (F1-F24) "
                "to avoid standard editor shortcuts."
            )
        if act_key in _PROTECTED_KEYS:
            raise ValueError(f"Hotkey {value!r} conflicts with a standard editor key.")

    _virtual_key(act_key)
    return tuple(sorted(parts))


def _virtual_key(name: str) -> int:
    if name in _VK_BY_NAME:
        return _VK_BY_NAME[name]
    if len(name) == 1 and name.isalpha():
        return ord(name.upper())
    if len(name) == 1 and name.isdigit():
        return ord(name)
    if name.startswith("f") and name[1:].isdigit():
        number = int(name[1:])
        if 1 <= number <= 24:
            return 0x6F + number
    raise ValueError(f"Unsupported hotkey key: {name!r}")


def _name_for_virtual_key(vk: int) -> Optional[str]:
    if vk in (0x11, 0xA2, 0xA3):
        return "ctrl"
    if vk in (0x12, 0xA4, 0xA5):
        return "alt"
    if vk in (0x10, 0xA0, 0xA1):
        return "shift"
    if vk in (0x5B, 0x5C):
        return "win"
    for name, value in _VK_BY_NAME.items():
        if value == vk and name not in _MODIFIERS:
            return name
    if 0x30 <= vk <= 0x39 or 0x41 <= vk <= 0x5A:
        return chr(vk).lower()
    if 0x70 <= vk <= 0x87:
        return f"f{vk - 0x6F}"
    return None


class _KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vk_code", wintypes.DWORD),
        ("scan_code", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class HotkeyManager:
    """Owns one low-level hook; never suppresses input and ignores injected events."""

    _WH_KEYBOARD_LL = 13
    _HC_ACTION = 0
    _WM_QUIT = 0x0012
    _LLKHF_INJECTED = 0x10
    _LLKHF_LOWER_IL_INJECTED = 0x02

    def __init__(self):
        self._callbacks: Dict[Tuple[str, ...], Callable[[], None]] = {}
        self._key_sets: Dict[Tuple[str, ...], Set[str]] = {}
        self._pressed: Set[str] = set()
        self._fired: Set[Tuple[str, ...]] = set()
        self._state_lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._thread_id = 0
        self._hook = None
        self._hook_proc = None
        self._ready = threading.Event()
        self._startup_error: Optional[BaseException] = None

    def configure(self, bindings: Iterable[Tuple[str, Callable[[], None]]]):
        normalized: Dict[Tuple[str, ...], Callable[[], None]] = {}
        key_sets: Dict[Tuple[str, ...], Set[str]] = {}
        for hotkey, callback in bindings:
            chord = normalize_hotkey(hotkey)
            if chord in normalized:
                raise ValueError(f"Duplicate hotkey binding: {'+'.join(chord)}")
            normalized[chord] = callback
            key_sets[chord] = set(chord)

        self.unregister()
        self._callbacks = normalized
        self._key_sets = key_sets
        if not normalized:
            return

        if self._thread is None or not self._thread.is_alive():
            self._ready.clear()
            self._startup_error = None
            self._thread = threading.Thread(
                target=self._hook_worker,
                daemon=True,
                name="DeskPilot-HotkeyHook"
            )
            self._thread.start()
            if not self._ready.wait(5.0):
                raise RuntimeError("Timed out while starting the global hotkey hook.")
            if self._startup_error:
                raise RuntimeError("Could not start the global hotkey hook.") from self._startup_error

        logger.info("HOTKEY", f"Registered {len(normalized)} non-suppressing global hotkeys.")

    def _hook_worker(self):
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._thread_id = kernel32.GetCurrentThreadId()
        hook_proc_type = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)(
            ctypes.c_ssize_t,
            ctypes.c_int,
            wintypes.WPARAM,
            wintypes.LPARAM
        )
        kernel32.GetModuleHandleW.restype = wintypes.HMODULE
        kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        user32.SetWindowsHookExW.argtypes = [
            ctypes.c_int,
            hook_proc_type,
            wintypes.HINSTANCE,
            wintypes.DWORD
        ]
        call_next = user32.CallNextHookEx
        call_next.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
        call_next.restype = ctypes.c_ssize_t
        user32.GetMessageW.argtypes = [
            ctypes.POINTER(wintypes.MSG),
            wintypes.HWND,
            wintypes.UINT,
            wintypes.UINT
        ]
        user32.GetMessageW.restype = ctypes.c_int
        user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
        user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
        user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]

        def handle_key(n_code, w_param, l_param):
            if n_code == self._HC_ACTION:
                event = ctypes.cast(
                    l_param, ctypes.POINTER(_KBDLLHOOKSTRUCT)
                ).contents
                self._handle_hook_event(
                    int(event.vk_code),
                    int(w_param),
                    int(event.flags)
                )
            return call_next(self._hook, n_code, w_param, l_param)

        self._hook_proc = hook_proc_type(handle_key)
        user32.SetWindowsHookExW.restype = wintypes.HHOOK
        hook = user32.SetWindowsHookExW(
            self._WH_KEYBOARD_LL,
            self._hook_proc,
            kernel32.GetModuleHandleW(None),
            0
        )
        if not hook:
            self._startup_error = ctypes.WinError()
            self._ready.set()
            return

        self._hook = hook
        self._ready.set()
        message = wintypes.MSG()
        try:
            while True:
                result = user32.GetMessageW(ctypes.byref(message), None, 0, 0)
                if result <= 0:
                    break
                user32.TranslateMessage(ctypes.byref(message))
                user32.DispatchMessageW(ctypes.byref(message))
        finally:
            user32.UnhookWindowsHookEx(hook)
            self._hook = None

    def _process_key_event(self, vk: int, event_type: int):
        name = _name_for_virtual_key(vk)
        if not name:
            return

        key_down = event_type in (0x0100, 0x0104)
        triggered = []
        with self._state_lock:
            if key_down:
                self._pressed.add(name)
                for chord, keys in self._key_sets.items():
                    if name in keys and keys.issubset(self._pressed) and chord not in self._fired:
                        self._fired.add(chord)
                        triggered.append(self._callbacks[chord])
            else:
                self._pressed.discard(name)
                self._fired = {
                    chord for chord in self._fired
                    if name not in self._key_sets[chord]
                }

        for callback in triggered:
            try:
                callback()
            except Exception as exc:
                logger.error_detailed(
                    "HOTKEY",
                    f"Global hotkey callback failed: {exc}",
                    error_type=type(exc).__name__
                )

    def _handle_hook_event(self, vk: int, event_type: int, flags: int):
        if flags & (self._LLKHF_INJECTED | self._LLKHF_LOWER_IL_INJECTED):
            return
        self._process_key_event(vk, event_type)

    def unregister(self):
        thread = self._thread
        thread_id = self._thread_id
        if thread and thread.is_alive() and thread_id:
            ctypes.windll.user32.PostThreadMessageW(thread_id, self._WM_QUIT, 0, 0)
            if threading.current_thread() is not thread:
                thread.join(timeout=2.0)
                if thread.is_alive():
                    raise RuntimeError("The global hotkey hook did not shut down.")
        self._thread = None
        self._thread_id = 0
        self._hook = None
        self._hook_proc = None
        with self._state_lock:
            self._pressed.clear()
            self._fired.clear()
