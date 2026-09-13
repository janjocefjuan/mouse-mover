#!/usr/bin/env python3
"""Marksman - keeps your system awake / status "active" by nudging the cursor.

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
from tkinter import messagebox

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

APP_TITLE = "Marksman"
APP_TAGLINE = "Stay awake. Stay active."
TRAY_TOOLTIP = "Marksman"
MODE_JIGGLE = "jiggle"
MODE_RANDOM = "random"

CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".marksman_config.json")
DEFAULT_CONFIG = {
    "mode": MODE_JIGGLE,
    "interval": 45,
    "distance": 2,
    "jitter": True,
    "start_minimized": False,
    "auto_start": False,
}

C = {
    "bg": "#13151a",
    "card": "#1b1e26",
    "card_hi": "#252935",
    "border": "#272b36",
    "track": "#2a2f3b",
    "text": "#e9ecf4",
    "muted": "#878ea3",
    "disabled": "#555b6b",
    "accent": "#4f8cff",
    "accent_hi": "#6b9dff",
    "danger": "#ff6b6b",
    "danger_hi": "#ff8585",
    "success": "#3ecf8e",
}


def ui_font(size=10, weight="normal"):
    if sys.platform == "win32":
        family = "Segoe UI"
    elif sys.platform == "darwin":
        family = "SF Pro Text"
    else:
        family = "DejaVu Sans"
    return (family, size, weight)


def round_rect(canvas, x1, y1, x2, y2, r, **kwargs):
    points = [
        x1 + r, y1, x1 + r, y1, x2 - r, y1, x2 - r, y1, x2, y1,
        x2, y1 + r, x2, y1 + r, x2, y2 - r, x2, y2 - r, x2, y2,
        x2 - r, y2, x2 - r, y2, x1 + r, y2, x1 + r, y2, x1, y2,
        x1, y2 - r, x1, y2 - r, x1, y1 + r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


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
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    ring = (108, 146, 232, 255)
    draw.ellipse((8, 8, 56, 56), outline=ring, width=6)
    draw.ellipse((26, 26, 38, 38), fill=ring)
    return img


class RoundedButton(tk.Canvas):
    def __init__(self, parent, text, command, width=120, height=36, radius=9,
                 fill=None, hover=None, fg=None, bg=None, font=None):
        bg = bg or C["card"]
        super().__init__(parent, width=width, height=height, bg=bg,
                         highlightthickness=0, bd=0)
        self._command = command
        self._fill = fill or C["accent"]
        self._hover = hover or C["accent_hi"]
        self._fg = fg or "#ffffff"
        self._enabled = True
        self._shape = round_rect(self, 1, 1, width - 1, height - 1, radius,
                                 fill=self._fill, outline="")
        self._label = self.create_text(width // 2, height // 2, text=text,
                                       fill=self._fg, font=font or ui_font(10, "bold"))
        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.configure(cursor="hand2")

    def _on_click(self, _event):
        if self._enabled and self._command:
            self._command()

    def _on_enter(self, _event):
        if self._enabled:
            self.itemconfigure(self._shape, fill=self._hover)

    def _on_leave(self, _event):
        if self._enabled:
            self.itemconfigure(self._shape, fill=self._fill)

    def set_text(self, text):
        self.itemconfigure(self._label, text=text)

    def set_colors(self, fill, hover, fg=None):
        self._fill, self._hover = fill, hover
        if fg:
            self._fg = fg
        if self._enabled:
            self.itemconfigure(self._shape, fill=fill)
            self.itemconfigure(self._label, fill=self._fg)

    def set_enabled(self, enabled):
        self._enabled = enabled
        self.itemconfigure(self._shape, fill=self._fill if enabled else C["card_hi"])
        self.itemconfigure(self._label, fill=self._fg if enabled else C["disabled"])
        self.configure(cursor="hand2" if enabled else "arrow")


class ToggleSwitch(tk.Canvas):
    def __init__(self, parent, variable, command=None, bg=None):
        width, height = 42, 22
        super().__init__(parent, width=width, height=height, bg=bg or C["card"],
                         highlightthickness=0, bd=0)
        self.var = variable
        self.command = command
        # NB: not self._w / self._h - tkinter uses self._w internally for the
        # widget's Tcl command name and overwriting it breaks the widget.
        self._width, self._height = width, height
        self._track = round_rect(self, 1, 1, width - 1, height - 1,
                                 (height - 2) // 2, fill=C["track"], outline="")
        self._knob = self.create_oval(3, 3, height - 3, height - 3,
                                      fill=C["muted"], outline="")
        self.bind("<Button-1>", self._toggle)
        self.configure(cursor="hand2")
        self.render()

    def _toggle(self, _event=None):
        self.var.set(not self.var.get())
        self.render()
        if self.command:
            self.command()

    def render(self):
        on = bool(self.var.get())
        self.itemconfigure(self._track, fill=C["accent"] if on else C["track"])
        knob = self._height - 6
        x1 = (self._width - 3 - knob) if on else 3
        self.coords(self._knob, x1, 3, x1 + knob, 3 + knob)
        self.itemconfigure(self._knob, fill="#ffffff" if on else C["muted"])


class Stepper(tk.Frame):
    def __init__(self, parent, variable, minimum, maximum, step=1, bg=None):
        bg = bg or C["card"]
        super().__init__(parent, bg=bg)
        self.var = variable
        self.minimum, self.maximum, self.step = minimum, maximum, step
        self.enabled = True

        self.minus = RoundedButton(self, "−", lambda: self._nudge(-step),
                                   width=30, height=30, radius=8, fill=C["track"],
                                   hover=C["card_hi"], fg=C["text"], bg=bg,
                                   font=ui_font(12, "bold"))
        self.minus.pack(side="left")
        self.value_label = tk.Label(self, textvariable=variable, bg=bg, fg=C["text"],
                                    font=ui_font(11, "bold"), width=4)
        self.value_label.pack(side="left", padx=2)
        self.plus = RoundedButton(self, "+", lambda: self._nudge(step),
                                  width=30, height=30, radius=8, fill=C["track"],
                                  hover=C["card_hi"], fg=C["text"], bg=bg,
                                  font=ui_font(12, "bold"))
        self.plus.pack(side="left")

    def _nudge(self, delta):
        try:
            current = int(self.var.get())
        except (tk.TclError, ValueError):
            current = self.minimum
        self.var.set(max(self.minimum, min(self.maximum, current + delta)))

    def set_enabled(self, enabled):
        self.enabled = enabled
        self.value_label.configure(fg=C["text"] if enabled else C["disabled"])
        self.minus.set_enabled(enabled)
        self.plus.set_enabled(enabled)


class Segmented(tk.Frame):
    def __init__(self, parent, options, variable, command=None, width=326):
        super().__init__(parent, bg=C["track"], highlightthickness=0, bd=0)
        self.var = variable
        self.command = command
        self._buttons = {}
        seg_w = (width - 8) // len(options)
        for value, label in options:
            button = RoundedButton(self, label, lambda v=value: self._select(v),
                                   width=seg_w, height=32, radius=8, fill=C["track"],
                                   hover=C["card_hi"], fg=C["muted"], bg=C["track"],
                                   font=ui_font(9, "bold"))
            button.pack(side="left", padx=2, pady=2)
            self._buttons[value] = button
        self.render()

    def _select(self, value):
        self.var.set(value)
        self.render()
        if self.command:
            self.command()

    def render(self):
        current = self.var.get()
        for value, button in self._buttons.items():
            if value == current:
                button.set_colors(C["accent"], C["accent_hi"], "#ffffff")
            else:
                button.set_colors(C["track"], C["card_hi"], C["muted"])


class MarksmanApp:
    def __init__(self, root, start_minimized=False):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.resizable(False, False)

        self.config = load_config()
        self.mover_thread = None
        self.tick_count = 0
        self.tray_icon = None

        self.mode_var = tk.StringVar(value=self.config["mode"])
        self.interval_var = tk.IntVar(value=self.config["interval"])
        self.distance_var = tk.IntVar(value=self.config["distance"])
        self.jitter_var = tk.BooleanVar(value=self.config["jitter"])
        self.always_on_top_var = tk.BooleanVar(value=False)
        self.start_minimized_var = tk.BooleanVar(value=self.config["start_minimized"])
        self.auto_start_var = tk.BooleanVar(value=self.config["auto_start"])
        self.status_var = tk.StringVar(value="Stopped")
        self.ticks_var = tk.StringVar(value="0 moves")

        self._build_ui()
        self._apply_window_chrome()
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

    # -- UI -------------------------------------------------------------

    def _build_ui(self):
        self.root.configure(bg=C["bg"])
        outer = tk.Frame(self.root, bg=C["bg"], padx=20, pady=18)
        outer.pack(fill="both", expand=True)

        self._build_header(outer)

        movement = self._card(outer, "Movement")
        Segmented(movement,
                  [(MODE_JIGGLE, "Jiggle"), (MODE_RANDOM, "Random")],
                  self.mode_var, command=self._on_mode_change).pack(fill="x", pady=(0, 4))
        right = self._row(movement, "Jiggle distance", "pixels per nudge")
        self.distance_stepper = Stepper(right, self.distance_var, 1, 50)
        self.distance_stepper.pack()

        timing = self._card(outer, "Timing")
        right = self._row(timing, "Interval", "seconds between nudges")
        Stepper(right, self.interval_var, 5, 900, step=5).pack()
        right = self._row(timing, "Randomize timing", "vary each interval by ±25%")
        ToggleSwitch(right, self.jitter_var).pack()

        behavior = self._card(outer, "Behavior")
        right = self._row(behavior, "Start minimized", "launch straight to the tray")
        ToggleSwitch(right, self.start_minimized_var, command=self._save_prefs).pack()
        right = self._row(behavior, "Start moving automatically", "begin on launch")
        ToggleSwitch(right, self.auto_start_var, command=self._save_prefs).pack()
        right = self._row(behavior, "Keep window on top")
        ToggleSwitch(right, self.always_on_top_var,
                     command=self._toggle_always_on_top).pack()

        self.toggle_button = RoundedButton(outer, "Start", self._toggle_running,
                                           width=326, height=44, radius=11,
                                           bg=C["bg"], font=ui_font(11, "bold"))
        self.toggle_button.pack(pady=(4, 8))

        if TRAY_AVAILABLE:
            RoundedButton(outer, "Minimize to tray", self._hide_window,
                          width=326, height=36, radius=10, fill=C["card"],
                          hover=C["card_hi"], fg=C["muted"], bg=C["bg"],
                          font=ui_font(9, "bold")).pack(pady=(0, 12))

        self._build_status(outer)

        tk.Label(outer,
                 text="Tip: slam the cursor into any screen corner to force-stop.",
                 bg=C["bg"], fg=C["disabled"], font=ui_font(8),
                 wraplength=326, justify="left").pack(anchor="w", pady=(10, 0))

        self._on_mode_change()

    def _build_header(self, parent):
        head = tk.Frame(parent, bg=C["bg"])
        head.pack(fill="x", pady=(0, 16))

        logo = tk.Canvas(head, width=38, height=38, bg=C["bg"],
                         highlightthickness=0, bd=0)
        logo.pack(side="left")
        logo.create_oval(6, 6, 32, 32, outline=C["accent"], width=2)
        logo.create_oval(16, 16, 22, 22, fill=C["accent"], outline="")
        logo.create_line(19, 1, 19, 9, fill=C["accent"], width=2)
        logo.create_line(19, 29, 19, 37, fill=C["accent"], width=2)
        logo.create_line(1, 19, 9, 19, fill=C["accent"], width=2)
        logo.create_line(29, 19, 37, 19, fill=C["accent"], width=2)

        text = tk.Frame(head, bg=C["bg"])
        text.pack(side="left", padx=(12, 0))
        tk.Label(text, text=APP_TITLE, bg=C["bg"], fg=C["text"],
                 font=ui_font(17, "bold")).pack(anchor="w")
        tk.Label(text, text=APP_TAGLINE, bg=C["bg"], fg=C["muted"],
                 font=ui_font(9)).pack(anchor="w")

    def _card(self, parent, title):
        card = tk.Frame(parent, bg=C["card"], highlightbackground=C["border"],
                        highlightthickness=1, bd=0)
        card.pack(fill="x", pady=(0, 12))
        inner = tk.Frame(card, bg=C["card"], padx=16, pady=14)
        inner.pack(fill="x")
        tk.Label(inner, text=title.upper(), bg=C["card"], fg=C["muted"],
                 font=ui_font(8, "bold")).pack(anchor="w", pady=(0, 10))
        return inner

    def _row(self, parent, label, sublabel=None):
        row = tk.Frame(parent, bg=C["card"])
        row.pack(fill="x", pady=5)
        left = tk.Frame(row, bg=C["card"])
        left.pack(side="left", fill="x", expand=True)
        tk.Label(left, text=label, bg=C["card"], fg=C["text"],
                 font=ui_font(10)).pack(anchor="w")
        if sublabel:
            tk.Label(left, text=sublabel, bg=C["card"], fg=C["muted"],
                     font=ui_font(8)).pack(anchor="w")
        right = tk.Frame(row, bg=C["card"])
        right.pack(side="right")
        return right

    def _build_status(self, parent):
        strip = tk.Frame(parent, bg=C["card"], highlightbackground=C["border"],
                         highlightthickness=1, bd=0)
        strip.pack(fill="x")
        inner = tk.Frame(strip, bg=C["card"], padx=14, pady=11)
        inner.pack(fill="x")

        self.dot = tk.Canvas(inner, width=10, height=10, bg=C["card"],
                             highlightthickness=0, bd=0)
        self._dot_item = self.dot.create_oval(1, 1, 9, 9, fill=C["danger"], outline="")
        self.dot.pack(side="left")
        self.status_label = tk.Label(inner, textvariable=self.status_var, bg=C["card"],
                                     fg=C["danger"], font=ui_font(10, "bold"))
        self.status_label.pack(side="left", padx=(8, 0))
        tk.Label(inner, textvariable=self.ticks_var, bg=C["card"], fg=C["muted"],
                 font=ui_font(9)).pack(side="right")

    def _apply_window_chrome(self):
        if TRAY_AVAILABLE:
            try:
                from PIL import ImageTk
                self._window_icon = ImageTk.PhotoImage(_make_tray_image())
                self.root.iconphoto(True, self._window_icon)
            except Exception:
                pass
        if sys.platform == "win32":
            self.root.after(10, self._enable_dark_titlebar)

    def _enable_dark_titlebar(self):
        try:
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            value = ctypes.c_int(1)
            for attribute in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE, old + new
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value))
        except Exception:
            pass

    # -- Behavior -------------------------------------------------------

    def _on_mode_change(self):
        self.distance_stepper.set_enabled(self.mode_var.get() == MODE_JIGGLE)
        self._save_prefs()

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
        self.ticks_var.set("0 moves")
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
        self.status_label.configure(fg=C["success"])
        self.dot.itemconfigure(self._dot_item, fill=C["success"])
        self.toggle_button.set_text("Stop")
        self.toggle_button.set_colors(C["danger"], C["danger_hi"], "#ffffff")
        self._update_tray_menu()

    def _stop(self):
        if self.mover_thread is not None:
            self.mover_thread.stop()
            self.mover_thread = None
        self.status_var.set("Stopped")
        self.status_label.configure(fg=C["danger"])
        self.dot.itemconfigure(self._dot_item, fill=C["danger"])
        self.toggle_button.set_text("Start")
        self.toggle_button.set_colors(C["accent"], C["accent_hi"], "#ffffff")
        self._update_tray_menu()

    def _on_tick(self):
        self.tick_count += 1
        count = self.tick_count
        self.root.after(0, lambda: self.ticks_var.set(
            f"{count} move" if count == 1 else f"{count} moves"))

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
            self.tray_icon = pystray.Icon("marksman", _make_tray_image(), TRAY_TOOLTIP, menu)
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
    MarksmanApp(root, start_minimized=args.minimized)
    root.mainloop()


if __name__ == "__main__":
    main()
