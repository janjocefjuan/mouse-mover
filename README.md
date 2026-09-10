# Mouse Mover

A small cross-platform desktop app that periodically nudges your mouse cursor —
useful for preventing your screen/status from going idle (e.g. Teams/Slack
"Away" status) or your OS from sleeping.

## Features

- **Jiggle mode**: moves the cursor a couple of pixels and back, barely noticeable.
- **Random mode**: moves the cursor to a random point on screen each interval.
- Configurable interval and jiggle distance.
- **Randomized timing**: each interval varies ±25% so movement doesn't happen
  on a perfectly predictable beat.
- **Runs in the background**: minimizes to a plain system tray icon (generic
  dot icon, neutral tooltip) instead of sitting open on screen or in the
  taskbar/dock. Closing the window hides it to the tray rather than quitting.
- Settings (mode, interval, distance, start-minimized, auto-start) persist
  between runs in `~/.mouse_mover_config.json`.
- Built-in safety: slam the cursor into any screen corner to instantly force-stop
  (this is `pyautogui`'s fail-safe).

## Requirements

- Python 3.8+
- Tkinter (ships with most Python installs; on Linux you may need to install
  it separately, e.g. `sudo apt install python3-tk`)
- On Linux, `pyautogui` also needs `scrot` for some features:
  `sudo apt install scrot`
- `pystray` + `pillow` (in `requirements.txt`) enable the system tray /
  background mode. Without them the app still works but always shows its
  window and quitting the window quits the app.

## Setup

```bash
pip install -r requirements.txt
```

## Run

```bash
python mouse_mover.py
```

Pick a movement style, set the interval (seconds) and distance, then click
**Start**. Click **Minimize to Tray** (or just close the window) to keep it
running quietly in the background — control it from the tray icon's menu
(Show window / Start / Stop / Quit). Drag the cursor into any corner of the
screen to force-stop immediately.

Check **Start minimized to tray** and **Start moving automatically** to have
it launch straight into the background already running next time.

To launch already hidden (e.g. from a login/startup entry):

```bash
python mouse_mover.py --minimized
```

## Running automatically at login

- **Windows**: put a shortcut to `pythonw.exe mouse_mover.py --minimized` in
  the Startup folder (`Win+R` → `shell:startup`). `pythonw.exe` avoids a
  console window popping up.
- **macOS**: add the app/script as a Login Item (System Settings → General →
  Login Items), or use a `launchd` agent that runs
  `python3 mouse_mover.py --minimized`.
- **Linux**: create a `.desktop` file in `~/.config/autostart/` that runs
  `python3 /path/to/mouse_mover.py --minimized`.

## Notes

- On macOS you'll need to grant the terminal/Python app **Accessibility**
  permissions (System Settings → Privacy & Security → Accessibility) for
  `pyautogui` to move the cursor.
- On Linux, the tray icon requires a system tray host in your desktop
  environment (GNOME needs an extension like AppIndicator; KDE/XFCE have one
  built in).
- To build a standalone executable, you can use
  [PyInstaller](https://pyinstaller.org/):

  ```bash
  pip install pyinstaller
  pyinstaller --onefile --windowed mouse_mover.py
  ```
