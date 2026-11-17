# ⚡ DeskPilot – Minimal Code Typing Automation

**DeskPilot** is a lightweight, human-style Windows desktop typing automation studio. It is designed with a minimal interface focused exclusively on writing code and typing that code into a selected target application (such as Visual Studio Code, Notepad, or an active window) using natural character-by-character keyboard keystrokes and automatic human-like mouse movements between lines.

All complex dashboards, activity monitors, separate mouse/keyboard builder panels, multi-tab settings, and unneeded menus have been removed to deliver a fast, clutter-free code typing tool.

Target Operating System: **Windows 10 / Windows 11**

---

## 🏗️ Minimal UI Layout

```
========================================================================================================
[⚡ DeskPilot] │ [📄 New] [📂 Open] [💾 Save (F9)] │ [🔖 Checkpoint (F10)] [⏱ Est. Time] │ [▶ Start (F5)] [⏸ Pause (F6)] [⏯ Resume (F7)] [⏹ Stop (F8)] │ Target: [VS Code ▼] │ Mode: [Difficulty-Based ▼] │ Speed: [3 CPS ▼]
========================================================================================================
│                                                                                                      │
│                                                                                                      │
│                                      ONE LARGE CODE EDITOR                                           │
│                              (occupies almost the entire window)                                     │
│                         Line numbers • Syntax Highlighting • Monospace font                          │
│                               Vertical and Horizontal Scrollbars                                     │
│                                                                                                      │
│                                                                                                      │
========================================================================================================
● Ready to Automate │ Line: 1 / 45 │ Progress: 0.0% (0 / 520 chars) │ Est. Remaining: 00:02:45 • Elapsed: 00:00:00
========================================================================================================
```

### 1. Top Toolbar
- **📄 New**: Resets the editor and clears any active checkpoints.
- **📂 Open**: Opens Python, JavaScript, HTML, CSS, SQL, or Plain Text files.
- **💾 Save (F9)**: Saves the current editor script to disk.
- **🔖 Checkpoint (F10)**: Saves the current execution position or editor cursor position so typing can safely resume without duplicating already typed lines. A small `✖` button clears the checkpoint.
- **⏱ Estimated Time**: Displays the calculated completion time in `HH:MM:SS`. Clicking it opens a detailed statistics dialog.
- **▶ Start (F5)**: Begins typing code into the target application (from line 1 or from the active checkpoint).
- **⏸ Pause (F6)**: Temporarily halts execution after the current character.
- **⏯ Resume (F7)**: Continues typing from the exact paused character position.
- **⏹ Stop (F8)**: Immediately cancels execution and releases all held hardware keys/buttons.
- **Target**: Dropdown to select the target window (`VS Code`, `Notepad`, `Active Window / Manual Focus`).
- **Mode**: Dropdown to switch typing timing profile (`Difficulty-Based` vs `Fixed CPS`).
- **Speed**: Dropdown to adjust typing rate (`3 CPS` default, `1 CPS`, `1.5 CPS`, `2 CPS`, `2.5 CPS`, `3.5 CPS`).

### 2. Main Workspace (Code Editor)
- One large code editor occupying almost the entire window (~95% of screen).
- Synchronized line numbers gutter with an active glowing pointer (`▶`) on the currently typed line.
- Real-time syntax coloring for **Python, JavaScript, HTML, CSS, SQL, and Plain Text**.
- Vertical and horizontal scrolling.
- Full support for indentation, spaces, tabs, uppercase/lowercase letters, numbers, and programming symbols.

### 3. Bottom Status Bar
- **Current execution status**: `● Ready to Automate`, `● Countdown: 3s`, `● Typing...`, `● Paused`, `● Stopped`, `● Completed Successfully`.
- **Current line / total lines**: `Line: 12 / 85`.
- **Typing progress**: `Progress: 45.2% (128 / 283 chars)`.
- **Estimated remaining time & elapsed time**: `Est. Remaining: 00:01:15 • Elapsed: 00:00:45`.

---

## ⌨️ Dynamic Character Difficulty & Natural Typing Engine

The keyboard automation engine replaces static delays with dynamic character difficulty and physical keyboard row geometry while strictly preserving exact source code without skipping or mutating characters:

### 1. Character Difficulty Tiers & Distinct Row Behaviors
- **Middle / Home Row** (`a–l`, `;`, `'`): $\text{Diff: } 0.72\times$, $\text{Row: } 0.85\times$ ($\sim 0.20\text{s}$ at 3 CPS) – natural resting posture, fast fluid reflex.
- **Top Letter Row** (`q–p`): $\text{Diff: } 0.88\text{--}1.25\times$, $\text{Row: } 1.15\times$ ($\sim 0.34\text{s}$ at 3 CPS) – upward finger extension, steady reach.
- **Bottom Letter Row** (`z–m`): $\text{Diff: } 0.95\text{--}1.50\times$, $\text{Row: } 1.35\times$ ($\sim 0.43\text{--}0.65\text{s}$ at 3 CPS) – downward finger curl, awkward flexion.
- **Top Number Row** (`0–9`): $\text{Diff: } 1.40\times$, $\text{Row: } 1.55\times$ ($\sim 0.72\text{s}$ at 3 CPS) – stretch to top row, deliberate strike.
- **Programming Brackets** (`{}`, `[]`, `()`, `<>`): $\text{Diff: } 3.20\times$, $\text{Row: } 1.15\times$ ($\sim 1.23\text{s}$ at 3 CPS) – deliberate cognitive search hesitation.
- **Shifted Special Symbols** (`@`, `#`, `$`, `%`, `^`, `&`, `*`, `~`, `_`, `+`, `|`, `?`, `!`): $\text{Diff: } 3.40\times$, $\text{Row: } 1.55\times$ ($\sim 1.76\text{s}$ at 3 CPS) – shift key depression + high reach, deliberate pause.
- **Syntax Operators** (`:`, `;`, `'`, `"`, `=`, `\`, `/`, `-`): $\text{Diff: } 2.60\times$ ($\sim 0.74\text{--}1.00\text{s}$ at 3 CPS).
- **Consecutive Symbols** (`->`, `!=`, `==`, `{}`, `[]`, `():`): $+ 0.40\text{--}0.70\times \text{Base Delay}$ ($\sim 2.10\text{--}2.40\text{s}$).

### 2. Natural Typing Cadence & Cognitive Pauses
- **Special Characters No Longer Fast**: Complex symbols and brackets now receive deliberate, human-like pauses ($1.2\text{s}$ to $1.8\text{s}$ at 3 CPS).
- **Jitter**: Bounded variations between consecutive keystrokes ($\pm 5\text{--}8\%$).
- **Word Spacing**: Subtle natural pauses after spaces completing words ($+0.07\text{s}$).
- **Punctuation & Bracket Pauses**: Natural micro-pauses after colons, semicolons, commas, and closing brackets ($+0.10\text{--}0.20\text{s}$).
- **Line Ending Pauses**: Controlled pause after completing a line ($+0.10\text{s}$) before line mouse transitions.
- **Timing Limits**:
  - Default base speed: **3.0 CPS**.
  - Maximum speed: **3.5 CPS**.
  - Absolute hard limit: **$\le 3.5$ seconds per character** (strictly enforced).
  - Higher CPS strictly decreases delays; lower CPS strictly increases delays.

### 3. Dual Typing Speed Modes: "Difficulty-Based" vs "Fixed CPS"
- **Difficulty-Based Mode**:
  - Dynamically scales delays based on character difficulty category and physical keyboard row reach (Middle < Top < Bottom < Number < Brackets < Shifted Symbols).
  - Deliberate human cognitive pauses for special characters and consecutive symbol transitions.
- **Fixed CPS Mode ("as usual")**:
  - Typing speed is constant across all characters at exactly $\frac{1}{\text{CPS}}$ (e.g. $0.333\text{s}$ at $3.0\text{ CPS}$).
  - Character difficulty scaling is bypassed for steady, uniform cadence.
- Selected via the **Mode** dropdown in the top toolbar; immediately updates estimated completion times.

### 4. Strict Typing Automation Rules
- **Allowed**: Letters (`A–Z`, `a–z`), numbers (`0–9`), programming symbols, spaces, tabs, and newlines.
- **Strictly NOT Allowed**: Ctrl/Alt/Windows shortcuts, copy/paste, cut, select all, text selection commands, delete/backspace commands, arrow-key navigation, or undo/redo.
- **No Clipboard Bulk Pasting**: Characters are typed sequentially through the keyboard controller using exact virtual keycodes.
- **Guaranteed Modifier Release**: Shift modifier keys required for uppercase and symbols are released immediately in `finally` blocks, on pause, on stop, and during emergency abort.

---

## 🖱️ Human-Like Mouse Movement Every Random 2–5 Lines for Multiple Seconds

Mouse movement is triggered after completing newlines at **randomized intervals between 2 and 5 lines** (`min_lines: 2, max_lines: 5`), moving for **multiple seconds randomly**:

1. **Sequential Execution**: Finishes typing the current line completely (after Enter/newline).
2. **Key Reset**: Releases all held keyboard modifier keys.
3. **Multi-Second Movement Duration**:
   - **Fast reposition**: $1.10\text{--}1.60\text{s}$
   - **Medium natural move**: $1.70\text{--}2.40\text{s}$
   - **Slow thoughtful reposition**: $2.50\text{--}3.20\text{s}$
   - **Pauses**: Pre-movement pause ($0.20\text{--}0.42\text{s}$) and post-movement settle pause ($0.25\text{--}0.52\text{s}$). Total mouse cycle lasts **$1.6\text{s}$ to $4.1\text{s}$ randomly**.
4. **Varied Movement**:
   - **Lengths**: Short ($80\text{--}150\text{px}$), Medium ($160\text{--}270\text{px}$), Long ($280\text{--}420\text{px}$).
   - **Directions**: Omnidirectional with boundary reflection keeping the pointer $\ge 140\text{px}$ below top tabs.
   - **Trajectory Profiles**: Curved Bézier demonstration paths with human micro-tremor or smooth easing.
5. **Safety Guarantees**:
   - **Zero-click guarantee**: DeskPilot never clicks or sends mouseUp/mouseDown. All click, double-click, drag, and scroll operations are permanently removed.
   - Does **not** change window focus or text caret position.
   - **Trajectory Profiles**: Curved Bézier demonstration paths with human micro-tremor or smooth acceleration/deceleration easing.
   - **Pre/Post Pauses**: Pre-movement pause ($0.03\text{--}0.07\text{s}$) and post-movement settle pause ($0.08\text{--}0.16\text{s}$).
4. **Safety Guarantees & Removal of Non-Movement Mouse Functions**:
   - **Movement Only**: All mouse operations other than cursor movement—especially **left-click, right-click, double-click, triple-click, drag-and-drop, and scrolling**—have been permanently removed from DeskPilot.
   - Bounded safely inside screen margins ($\ge 110\text{px}$ horizontal, $\ge 90\text{px}$ vertical away from corners and taskbars).
   - Zero-click guarantee: DeskPilot never emits clicks of any kind.
   - Never changes window focus or text caret position.
   - Completely finishes before the next line starts typing.

---

## ⏱️ Central Timing Controller & Estimated Time

- Centralized singleton (`automation.timing_controller.timing_controller`) orchestrates typing delays, pause durations, and mouse movement trajectories.
- Dynamic duration estimate calculates precise expected completion time across all characters, difficulty tiers, newlines, and mouse movements.
- Top toolbar and bottom status bar update live with remaining time and progress percentage.

---

## 🔖 Checkpoint System

- Pressing **F10** (or clicking **Checkpoint**) records the current character offset and completed line number.
- When automation starts, if a checkpoint is active, typing automatically begins from the checkpoint character offset.
- Text prior to the checkpoint is **never duplicated**.
- Clicking the small `✖` button clears the checkpoint and returns start position to line 1.

---

## ⌨️ Essential Hotkeys

| Hotkey | Action | Description |
|---|---|---|
| **F5** | **Start** | Begins automated typing into the target application |
| **F6** | **Pause** | Temporarily pauses typing at the current character |
| **F7** | **Resume** | Continues typing from the exact paused position |
| **F8** | **Stop** | Cancels automation and releases all inputs |
| **F9** | **Save** | Opens save dialog to save code file |
| **F10** | **Checkpoint** | Saves/restores recovery checkpoint |
| **Ctrl+Alt+Esc** | **Emergency Stop** | Global hardware safety abort |

Hotkeys work globally via a low-level Windows hook (`WH_KEYBOARD_LL`) that passes through normal keystrokes, does not suppress keys, ignores injected events, and cleanly unregisters upon exit.

---

## 🧪 Verification & Testing

Run all unit tests:
```powershell
python -m unittest tests/test_minimal_redesign.py
python -m unittest tests/test_input_coordination.py
python -m unittest tests/test_deskpilot.py
```

Run DeskPilot:
```powershell
python main.py
```
