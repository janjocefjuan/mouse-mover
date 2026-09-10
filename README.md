# Mouse Mover

A small cross-platform desktop app that periodically nudges your mouse cursor —
useful for preventing your screen/status from going idle (e.g. Teams/Slack
"Away" status) or your OS from sleeping.

## Features

- **Jiggle mode**: moves the cursor a few pixels and back, barely noticeable.
- **Random mode**: moves the cursor to a random point on screen each interval.
- Configurable interval and jiggle distance.
- Live move counter and status indicator.
- Built-in safety: slam the cursor into any screen corner to instantly force-stop
  (this is `pyautogui`'s fail-safe).

## Requirements

- Python 3.8+
- Tkinter (ships with most Python installs; on Linux you may need to install
  it separately, e.g. `sudo apt install python3-tk`)
- On Linux, `pyautogui` also needs `scrot` for some features:
  `sudo apt install scrot`

## Setup

```bash
pip install -r requirements.txt
```

## Run

```bash
python mouse_mover.py
```

Pick a movement style, set the interval (seconds) and distance, then click
**Start**. Click **Stop** to pause it, or drag the cursor into any corner of
the screen to force-stop immediately.

## Notes

- On macOS you'll need to grant the terminal/Python app **Accessibility**
  permissions (System Settings → Privacy & Security → Accessibility) for
  `pyautogui` to move the cursor.
- To build a standalone executable, you can use
  [PyInstaller](https://pyinstaller.org/):

  ```bash
  pip install pyinstaller
  pyinstaller --onefile --windowed mouse_mover.py
  ```
