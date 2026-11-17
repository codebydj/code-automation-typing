"""
DeskPilot - Character Mapping and Keyboard Layout System
Provides physical key mapping, required modifier keys, key event emission,
character categorization, and layout-aware validation for programming languages
(Python, JavaScript, HTML, CSS, SQL) and arbitrary text.
"""

from enum import Enum
from typing import NamedTuple, Tuple, Optional, Dict, Any
import pyautogui
from utils.logger import logger
from automation.input_dispatcher import input_dispatcher


class CharacterCategory(str, Enum):
    ALPHABETIC_LOWER = "ALPHABETIC_LOWER"
    ALPHABETIC_UPPER = "ALPHABETIC_UPPER"
    NUMERIC_ROW = "NUMERIC_ROW"
    NUMERIC_PAD = "NUMERIC_PAD"
    SPECIAL_SYMBOL = "SPECIAL_SYMBOL"
    WHITESPACE = "WHITESPACE"
    NEWLINE = "NEWLINE"


class KeyMapping(NamedTuple):
    primary_key: str
    modifiers: Tuple[str, ...]
    category: CharacterCategory
    row: str  # "number_row", "top_row", "home_row", "bottom_row", "space_row", "numpad", "control"


class CharacterMapper:
    """
    Layout-aware character-to-key mapper for standard US QWERTY and Windows keyboards.
    Explicitly tracks primary keycodes, modifier states (e.g. Shift), and keyboard rows.
    """

    def __init__(self, use_numpad: bool = False):
        self.use_numpad = use_numpad
        self._key_map: Dict[str, KeyMapping] = {}
        self._build_standard_map()

    def _build_standard_map(self):
        # 1. Lowercase alphabet (home, top, bottom rows)
        top_row = "qwertyuiop"
        home_row = "asdfghjkl"
        bottom_row = "zxcvbnm"

        for ch in top_row:
            self._key_map[ch] = KeyMapping(ch, (), CharacterCategory.ALPHABETIC_LOWER, "top_row")
            self._key_map[ch.upper()] = KeyMapping(ch, ("shift",), CharacterCategory.ALPHABETIC_UPPER, "top_row")

        for ch in home_row:
            self._key_map[ch] = KeyMapping(ch, (), CharacterCategory.ALPHABETIC_LOWER, "home_row")
            self._key_map[ch.upper()] = KeyMapping(ch, ("shift",), CharacterCategory.ALPHABETIC_UPPER, "home_row")

        for ch in bottom_row:
            self._key_map[ch] = KeyMapping(ch, (), CharacterCategory.ALPHABETIC_LOWER, "bottom_row")
            self._key_map[ch.upper()] = KeyMapping(ch, ("shift",), CharacterCategory.ALPHABETIC_UPPER, "bottom_row")

        # 2. Number row digits
        for digit in "1234567890":
            self._key_map[digit] = KeyMapping(digit, (), CharacterCategory.NUMERIC_ROW, "number_row")

        # 3. Number row shifted symbols
        num_shifted = {
            "!": ("1", "number_row"),
            "@": ("2", "number_row"),
            "#": ("3", "number_row"),
            "$": ("4", "number_row"),
            "%": ("5", "number_row"),
            "^": ("6", "number_row"),
            "&": ("7", "number_row"),
            "*": ("8", "number_row"),
            "(": ("9", "number_row"),
            ")": ("0", "number_row"),
            "_": ("-", "number_row"),
            "+": ("=", "number_row"),
            "~": ("`", "number_row"),
        }
        for sym, (base_key, row) in num_shifted.items():
            self._key_map[sym] = KeyMapping(base_key, ("shift",), CharacterCategory.SPECIAL_SYMBOL, row)

        # 4. Standard unshifted punctuation and symbols
        unshifted_symbols = {
            "-": ("-", "number_row"),
            "=": ("=", "number_row"),
            "`": ("`", "number_row"),
            "[": ("[", "top_row"),
            "]": ("]", "top_row"),
            "\\": ("\\", "top_row"),
            ";": (";", "home_row"),
            "'": ("'", "home_row"),
            ",": (",", "bottom_row"),
            ".": (".", "bottom_row"),
            "/": ("/", "bottom_row"),
        }
        for sym, (base_key, row) in unshifted_symbols.items():
            self._key_map[sym] = KeyMapping(base_key, (), CharacterCategory.SPECIAL_SYMBOL, row)

        # 5. Shifted punctuation and programming symbols
        shifted_symbols = {
            "{": ("[", "top_row"),
            "}": ("]", "top_row"),
            "|": ("\\", "top_row"),
            ":": (";", "home_row"),
            '"': ("'", "home_row"),
            "<": (",", "bottom_row"),
            ">": (".", "bottom_row"),
            "?": ("/", "bottom_row"),
        }
        for sym, (base_key, row) in shifted_symbols.items():
            self._key_map[sym] = KeyMapping(base_key, ("shift",), CharacterCategory.SPECIAL_SYMBOL, row)

        # 6. Whitespace and Control
        self._key_map[" "] = KeyMapping("space", (), CharacterCategory.WHITESPACE, "space_row")
        self._key_map["\t"] = KeyMapping("tab", (), CharacterCategory.WHITESPACE, "top_row")
        self._key_map["\n"] = KeyMapping("enter", (), CharacterCategory.NEWLINE, "home_row")
        self._key_map["\r"] = KeyMapping("enter", (), CharacterCategory.NEWLINE, "home_row")

    def get_mapping(self, ch: str) -> Optional[KeyMapping]:
        """
        Lookup KeyMapping for a character.
        If use_numpad is active and ch is a digit, returns NUMERIC_PAD mapping.
        """
        if self.use_numpad and ch in "0123456789":
            return KeyMapping(f"num{ch}", (), CharacterCategory.NUMERIC_PAD, "numpad")
        return self._key_map.get(ch, None)

    def get_category(self, ch: str) -> CharacterCategory:
        """Return the category of a character."""
        mapping = self.get_mapping(ch)
        if mapping:
            return mapping.category
        if ch.isalpha():
            return CharacterCategory.ALPHABETIC_UPPER if ch.isupper() else CharacterCategory.ALPHABETIC_LOWER
        if ch.isdigit():
            return CharacterCategory.NUMERIC_PAD if self.use_numpad else CharacterCategory.NUMERIC_ROW
        if ch in "\r\n":
            return CharacterCategory.NEWLINE
        if ch in " \t":
            return CharacterCategory.WHITESPACE
        return CharacterCategory.SPECIAL_SYMBOL

    def is_supported(self, ch: str) -> bool:
        """Check if character has a known direct key mapping."""
        return ch in self._key_map or (self.use_numpad and ch in "0123456789")


# Singleton instance
character_mapper = CharacterMapper()
