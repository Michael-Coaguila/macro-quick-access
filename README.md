# Macro Quick Access

A floating, touch-friendly keyboard shortcut overlay for Windows — built for users with reduced mobility who rely on touchscreens or assistive technology.

**Born from personal need:** This tool was created by Michael Coaguila after a spinal cord injury, to make computer use faster and more independent with limited hand mobility. If it helps even one more person, it was worth sharing.

---

## Features

- **Floating overlay** — always on top, transparent background, freely movable and resizable
- **Touch-first design** — large tap targets, swipe left/right to flip pages, drag to reorder shortcuts
- **Multiple profiles** — organize shortcuts by context (General, VS Code, Browser, etc.)
- **Auto-switch** — detects the active foreground app and automatically loads the matching profile
- **Three action types per button:**
  - ⌨ **Hotkey** — sends a keyboard combo (e.g. `Ctrl+C`, `Alt+Tab`, `Win+D`)
  - 🌐 **URL** — opens a link in the default browser
  - 📂 **App / Command** — launches any executable or command
- **Color-coded buttons** — group and highlight shortcuts visually
- **Pinned profile** — keep a base profile (e.g. General) always visible alongside any active profile
- **Global hotkey** — show/hide the overlay from anywhere with `Ctrl+Shift+M`
- **System tray** — runs quietly in the background; accessible from the notification area

---

## Screenshots

> *(Coming soon — contributions welcome!)*

---

## Download

The easiest way to get started — no Python required:

1. Go to the [Releases](https://github.com/Michael-Coaguila/macro-quick-access/releases) page
2. Download `MacroQuickAccess-vX.X.X.zip`
3. Extract anywhere and run `MacroQuickAccess.exe`

> **Note:** Windows may show a SmartScreen warning on first run. Click **"More info → Run anyway"** to proceed. This is normal for unsigned apps.

---

## Requirements (for developers)

- **Windows 10 or 11**
- **Python 3.10+**

---

## Installation (from source)

```bash
git clone https://github.com/Michael-Coaguila/macro-quick-access.git
cd macro-quick-access
pip install -r requirements.txt
python main.py
```

On first run, a `profiles.json` file is created automatically with default shortcuts.
To start from the included template instead:

```bash
copy profiles.example.json profiles.json
```

---

## Usage

### Basic use
1. The overlay appears on screen as a floating panel of colored buttons.
2. **Tap a button** to send its hotkey, open its URL, or launch its app.
3. **Drag the top bar** (≡) to reposition the overlay anywhere on screen.
4. **Swipe left/right** on the button grid to navigate between pages of shortcuts.
5. **Press `Ctrl+Shift+M`** or click the system tray icon to show/hide the overlay.

### Managing shortcuts
1. Tap **✏** in the top bar to open the edit panel.
2. Use **＋ Atajo** to add a new shortcut — choose type, label, color, and action.
3. **Drag** the ≡ handle on any shortcut row to reorder.
4. Use **✓** to return to use mode.

### Profiles
- Use the **dropdown** in the top bar to switch profiles manually.
- Set a **process name** (e.g. `code.exe`) per profile so the overlay auto-switches when that app is in the foreground.
- Use **📌** to pin a base profile that stays visible as a second tab alongside any active profile.

### Adjusting appearance
- **◐ / ●** buttons adjust transparency.
- **A− / A+** buttons change button size.
- **Drag the ⊿ corner handle** to resize the window manually.

---

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| [PyQt5](https://pypi.org/project/PyQt5/) | ≥ 5.15.0 | GUI framework |
| [pyautogui](https://pypi.org/project/pyautogui/) | ≥ 0.9.54 | Keyboard/mouse simulation |
| [pywin32](https://pypi.org/project/pywin32/) | ≥ 306 | Windows API (foreground app detection) |
| [pynput](https://pypi.org/project/pynput/) | ≥ 1.7.6 | Global hotkey listener |

Install all at once:
```bash
pip install -r requirements.txt
```

> **Note:** `pynput` is optional. If not installed, the `Ctrl+Shift+M` global hotkey is disabled, but all other features work normally.

---

## Project structure

```
macro-quick-access/
├── main.py                  # Entry point: tray icon, global hotkey, app lifecycle
├── overlay.py               # Main overlay window, button grid, profile management
├── edit_panel.py            # Edit mode: add/edit/reorder shortcuts, profile settings
├── requirements.txt         # Python dependencies
├── icon_collapsed.png       # Icon shown when overlay is minimized
└── profiles.example.json    # Example profile structure (copy to profiles.json)
```

User data (created on first run, not tracked by git):
```
profiles.json                # Your shortcuts and preferences
macro_quick_access.log       # Warning/error log
```

---

## Contributing

Contributions, bug reports, and ideas are welcome — especially from people with accessibility needs who can provide real-world feedback.

1. Fork the repository
2. Create a branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m "Add your feature"`
4. Push and open a Pull Request

---

## Author

**Michael Coaguila**

- 🔗 [LinkedIn](https://www.linkedin.com/in/michael-coaguila)
- 🐙 [GitHub](https://github.com/Michael-Coaguila)
- 📧 michael.coaguila.h@gmail.com

---

## License

[MIT License](LICENSE) — free to use, modify, and distribute.
