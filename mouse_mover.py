#!/usr/bin/env python3
"""Mouse Mover - keeps your system awake / status "active" by nudging the cursor.

Run with:       python mouse_mover.py
Start hidden:   python mouse_mover.py --minimized
"""

import argparse
import json
import os
import random
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox

import pyautogui

try:
    import pystray
    from PIL import Image, ImageDraw
    TRAY_AVAILABLE = True
except Exception:
    # pystray can fail at import time (not just ImportError) when no tray
    # backend / display is available - degrade gracefully either way.
    TRAY_AVAILABLE = False

pyautogui.FAILSAFE = True  # slam the cursor into a screen corner to force-stop
pyautogui.PAUSE = 0

# On Windows, simply repositioning the cursor (what the mouse movement below
# does) does not reliably reset the OS idle timer used for sleep/display-off
# on modern builds. Use the official power-management API instead so the
# system and display are told directly to stay awake.
if sys.platform == "win32":
    import ctypes

    ES_CONTINUOUS = 0x80000000
    ES_SYSTEM_REQUIRED = 0x00000001
    ES_DISPLAY_REQUIRED = 0x00000002

    def _set_keep_awake(enabled):
        flags = ES_CONTINUOUS
        if enabled:
            flags |= ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
        try:
            ctypes.windll.kernel32.SetThreadExecutionState(flags)
        except Exception:
            pass
else:
    def _set_keep_awake(enabled):
        pass

APP_TITLE = "Mouse Mover"
TRAY_TOOLTIP = "Background Helper"  # deliberately generic tray tooltip
MODE_JIGGLE = "jiggle"
MODE_RANDOM = "random"

CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".mouse_mover_config.json")
DEFAULT_CONFIG = {
    "mode": MODE_JIGGLE,
    "interval": 45,
    "distance": 2,
    "jitter": True,
    "start_minimized": False,
    "auto_start": False,
}


def load_config():
    config = dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH, "r") as f:
            config.update(json.load(f))
    except (FileNotFoundError, ValueError, OSError):
        pass
    return config


def save_config(config):
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(config, f)
    except OSError:
        pass


class MoverThread(threading.Thread):
    """Background thread that nudges the mouse until told to stop."""

    def __init__(self, interval, mode, distance, jitter=True, on_tick=None, on_error=None):
        super().__init__(daemon=True)
        self.interval = interval
        self.mode = mode
        self.distance = distance
        self.jitter = jitter
        self.on_tick = on_tick
        self.on_error = on_error
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        _set_keep_awake(True)
        try:
            while not self._stop_event.is_set():
                self._move_once()
                _set_keep_awake(True)  # re-assert - some builds let it lapse
                if self.on_tick:
                    self.on_tick()
                self._stop_event.wait(self._next_wait())
        except pyautogui.FailSafeException:
            if self.on_error:
                self.on_error("Fail-safe triggered (cursor hit a screen corner). Stopped.")
        except Exception as exc:  # pragma: no cover - defensive
            if self.on_error:
                self.on_error(str(exc))
        finally:
            _set_keep_awake(False)

    def _next_wait(self):
        if not self.jitter:
            return self.interval
        # +/- 25% so movement doesn't happen on a perfectly predictable beat
        spread = self.interval * 0.25
        return max(1.0, self.interval + random.uniform(-spread, spread))

    def _move_once(self):
        if self.mode == MODE_JIGGLE:
            x, y = pyautogui.position()
            width, height = pyautogui.size()
            dx = self.distance if x + self.distance < width else -self.distance
            pyautogui.moveTo(x + dx, y, duration=0.15)
            pyautogui.moveTo(x, y, duration=0.15)
        else:
            width, height = pyautogui.size()
            nx = random.randint(0, max(width - 1, 0))
            ny = random.randint(0, max(height - 1, 0))
            pyautogui.moveTo(nx, ny, duration=0.4)


def _make_tray_image():
    """A plain, non-descript dot icon - nothing that screams 'mouse mover'."""
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((14, 14, size - 14, size - 14), fill=(90, 100, 110, 255))
    return img


class MouseMoverApp:
    def __init__(self, root, start_minimized=False):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.resizable(False, False)

        self.config = load_config()
        self.mover_thread = None
        self.tick_count = 0
        self.tray_icon = None
        self._quitting = False

        self.mode_var = tk.StringVar(value=self.config["mode"])
        self.interval_var = tk.IntVar(value=self.config["interval"])
        self.distance_var = tk.IntVar(value=self.config["distance"])
        self.jitter_var = tk.BooleanVar(value=self.config["jitter"])
        self.always_on_top_var = tk.BooleanVar(value=False)
        self.start_minimized_var = tk.BooleanVar(value=self.config["start_minimized"])
        self.auto_start_var = tk.BooleanVar(value=self.config["auto_start"])
        self.status_var = tk.StringVar(value="Stopped")
        self.ticks_var = tk.StringVar(value="Moves so far: 0")

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        if TRAY_AVAILABLE:
            self._start_tray()
        elif start_minimized or self.config["start_minimized"]:
            messagebox.showinfo(
                APP_TITLE,
                "Install 'pystray' and 'pillow' (see requirements.txt) to run "
                "hidden in the background. Starting with the window visible.",
            )

        if self.config["auto_start"]:
            self._start()

        if TRAY_AVAILABLE and (start_minimized or self.config["start_minimized"]):
            self.root.after(0, self._hide_window)

    def _build_ui(self):
        pad = {"padx": 10, "pady": 6}
        frame = ttk.Frame(self.root)
        frame.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)

        ttk.Label(frame, text=APP_TITLE, font=("TkDefaultFont", 14, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8)
        )

        # Mode
        mode_frame = ttk.LabelFrame(frame, text="Movement style")
        mode_frame.grid(row=1, column=0, columnspan=2, sticky="ew", **pad)
        ttk.Radiobutton(
            mode_frame, text="Jiggle (tiny, barely visible nudge)",
            variable=self.mode_var, value=MODE_JIGGLE, command=self._update_mode_controls,
        ).grid(row=0, column=0, sticky="w", padx=8, pady=4)
        ttk.Radiobutton(
            mode_frame, text="Random position on screen",
            variable=self.mode_var, value=MODE_RANDOM, command=self._update_mode_controls,
        ).grid(row=1, column=0, sticky="w", padx=8, pady=4)

        # Interval
        ttk.Label(frame, text="Interval (seconds):").grid(row=2, column=0, sticky="w", **pad)
        interval_spin = ttk.Spinbox(
            frame, from_=1, to=3600, textvariable=self.interval_var, width=8
        )
        interval_spin.grid(row=2, column=1, sticky="w", **pad)

        # Distance (jiggle only)
        self.distance_label = ttk.Label(frame, text="Jiggle distance (pixels):")
        self.distance_label.grid(row=3, column=0, sticky="w", **pad)
        self.distance_spin = ttk.Spinbox(
            frame, from_=1, to=200, textvariable=self.distance_var, width=8
        )
        self.distance_spin.grid(row=3, column=1, sticky="w", **pad)
        self._update_mode_controls()

        # Jitter
        ttk.Checkbutton(
            frame, text="Randomize timing (less predictable pattern)",
            variable=self.jitter_var,
        ).grid(row=4, column=0, columnspan=2, sticky="w", **pad)

        # Always on top
        ttk.Checkbutton(
            frame, text="Keep window on top", variable=self.always_on_top_var,
            command=self._toggle_always_on_top,
        ).grid(row=5, column=0, columnspan=2, sticky="w", **pad)

        # Background behavior
        bg_frame = ttk.LabelFrame(frame, text="Background behavior")
        bg_frame.grid(row=6, column=0, columnspan=2, sticky="ew", **pad)
        ttk.Checkbutton(
            bg_frame, text="Start minimized to tray", variable=self.start_minimized_var,
            command=self._save_prefs,
        ).grid(row=0, column=0, sticky="w", padx=8, pady=4)
        ttk.Checkbutton(
            bg_frame, text="Start moving automatically", variable=self.auto_start_var,
            command=self._save_prefs,
        ).grid(row=1, column=0, sticky="w", padx=8, pady=4)
        if not TRAY_AVAILABLE:
            ttk.Label(
                bg_frame, text="(install pystray + pillow to enable tray/background mode)",
                foreground="#a60", wraplength=300, justify="left",
            ).grid(row=2, column=0, sticky="w", padx=8, pady=(0, 4))

        # Start/Stop
        self.toggle_button = ttk.Button(frame, text="Start", command=self._toggle_running)
        self.toggle_button.grid(row=7, column=0, columnspan=2, sticky="ew", padx=10, pady=(10, 4))

        if TRAY_AVAILABLE:
            ttk.Button(frame, text="Minimize to Tray", command=self._hide_window).grid(
                row=8, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 4)
            )

        # Status
        status_frame = ttk.Frame(frame)
        status_frame.grid(row=9, column=0, columnspan=2, sticky="ew", padx=10, pady=(4, 0))
        ttk.Label(status_frame, text="Status:").pack(side="left")
        self.status_label = ttk.Label(status_frame, textvariable=self.status_var, foreground="#b00")
        self.status_label.pack(side="left", padx=(4, 0))

        ttk.Label(frame, textvariable=self.ticks_var, foreground="#666").grid(
            row=10, column=0, columnspan=2, sticky="w", padx=10, pady=(2, 0)
        )

        ttk.Label(
            frame,
            text="Tip: slam the cursor into any screen corner to force-stop instantly.",
            foreground="#666", wraplength=320, justify="left",
        ).grid(row=11, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 0))

    def _update_mode_controls(self):
        state = "normal" if self.mode_var.get() == MODE_JIGGLE else "disabled"
        self.distance_spin.configure(state=state)

    def _toggle_always_on_top(self):
        self.root.attributes("-topmost", self.always_on_top_var.get())

    def _save_prefs(self):
        self.config.update({
            "mode": self.mode_var.get(),
            "interval": self.interval_var.get(),
            "distance": self.distance_var.get(),
            "jitter": self.jitter_var.get(),
            "start_minimized": self.start_minimized_var.get(),
            "auto_start": self.auto_start_var.get(),
        })
        save_config(self.config)

    def _toggle_running(self):
        if self.mover_thread is None:
            self._start()
        else:
            self._stop()

    def _start(self):
        try:
            interval = max(1, int(self.interval_var.get()))
            distance = max(1, int(self.distance_var.get()))
        except (tk.TclError, ValueError):
            messagebox.showerror(APP_TITLE, "Interval and distance must be whole numbers.")
            return

        self._save_prefs()
        self.tick_count = 0
        self.ticks_var.set("Moves so far: 0")
        self.mover_thread = MoverThread(
            interval=interval,
            mode=self.mode_var.get(),
            distance=distance,
            jitter=self.jitter_var.get(),
            on_tick=self._on_tick,
            on_error=self._on_error,
        )
        self.mover_thread.start()

        self.status_var.set("Running")
        self.status_label.configure(foreground="#0a0")
        self.toggle_button.configure(text="Stop")
        self._update_tray_menu()

    def _stop(self):
        if self.mover_thread is not None:
            self.mover_thread.stop()
            self.mover_thread = None
        self.status_var.set("Stopped")
        self.status_label.configure(foreground="#b00")
        self.toggle_button.configure(text="Start")
        self._update_tray_menu()

    def _on_tick(self):
        self.tick_count += 1
        self.root.after(0, lambda: self.ticks_var.set(f"Moves so far: {self.tick_count}"))

    def _on_error(self, message):
        def handle():
            self._stop()
            messagebox.showwarning(APP_TITLE, message)
        self.root.after(0, handle)

    # -- Tray -----------------------------------------------------------

    def _start_tray(self):
        global TRAY_AVAILABLE
        try:
            menu = pystray.Menu(
                pystray.MenuItem("Show window", lambda: self.root.after(0, self._show_window)),
                pystray.MenuItem(
                    "Start", lambda: self.root.after(0, self._start),
                    visible=lambda item: self.mover_thread is None,
                ),
                pystray.MenuItem(
                    "Stop", lambda: self.root.after(0, self._stop),
                    visible=lambda item: self.mover_thread is not None,
                ),
                pystray.MenuItem("Quit", lambda: self.root.after(0, self._full_quit)),
            )
            self.tray_icon = pystray.Icon("bghelper", _make_tray_image(), TRAY_TOOLTIP, menu)
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
        except Exception:
            # No usable tray backend on this system - fall back to normal
            # (always-visible-window) behavior instead of crashing.
            TRAY_AVAILABLE = False
            self.tray_icon = None

    def _update_tray_menu(self):
        if self.tray_icon is not None:
            self.tray_icon.update_menu()

    def _hide_window(self):
        if not TRAY_AVAILABLE:
            messagebox.showinfo(
                APP_TITLE,
                "Install 'pystray' and 'pillow' to minimize to the system tray.",
            )
            return
        self.root.withdraw()

    def _show_window(self):
        self.root.deiconify()
        self.root.lift()

    def _full_quit(self):
        self._quitting = True
        if self.mover_thread is not None:
            self.mover_thread.stop()
        if self.tray_icon is not None:
            self.tray_icon.stop()
        self.root.destroy()

    def _on_close(self):
        self._save_prefs()
        if TRAY_AVAILABLE:
            self._hide_window()
        else:
            self._full_quit()


def main():
    parser = argparse.ArgumentParser(description=APP_TITLE)
    parser.add_argument(
        "--minimized", action="store_true",
        help="start hidden in the system tray (requires pystray + pillow)",
    )
    args = parser.parse_args()

    root = tk.Tk()
    MouseMoverApp(root, start_minimized=args.minimized)
    root.mainloop()


if __name__ == "__main__":
    main()
