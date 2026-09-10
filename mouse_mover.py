#!/usr/bin/env python3
"""Mouse Mover - keeps your system awake / status "active" by nudging the cursor.

Run with:  python mouse_mover.py
"""

import random
import threading
import tkinter as tk
from tkinter import ttk, messagebox

import pyautogui

pyautogui.FAILSAFE = True  # slam the cursor into a screen corner to force-stop
pyautogui.PAUSE = 0

APP_TITLE = "Mouse Mover"
MODE_JIGGLE = "jiggle"
MODE_RANDOM = "random"


class MoverThread(threading.Thread):
    """Background thread that nudges the mouse until told to stop."""

    def __init__(self, interval, mode, distance, on_tick=None, on_error=None):
        super().__init__(daemon=True)
        self.interval = interval
        self.mode = mode
        self.distance = distance
        self.on_tick = on_tick
        self.on_error = on_error
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        try:
            while not self._stop_event.is_set():
                self._move_once()
                if self.on_tick:
                    self.on_tick()
                self._stop_event.wait(self.interval)
        except pyautogui.FailSafeException:
            if self.on_error:
                self.on_error("Fail-safe triggered (cursor hit a screen corner). Stopped.")
        except Exception as exc:  # pragma: no cover - defensive
            if self.on_error:
                self.on_error(str(exc))

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


class MouseMoverApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.resizable(False, False)

        self.mover_thread = None
        self.tick_count = 0

        self.mode_var = tk.StringVar(value=MODE_JIGGLE)
        self.interval_var = tk.IntVar(value=30)
        self.distance_var = tk.IntVar(value=5)
        self.always_on_top_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="Stopped")
        self.ticks_var = tk.StringVar(value="Moves so far: 0")

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

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

        # Always on top
        ttk.Checkbutton(
            frame, text="Keep window on top", variable=self.always_on_top_var,
            command=self._toggle_always_on_top,
        ).grid(row=4, column=0, columnspan=2, sticky="w", **pad)

        # Start/Stop
        self.toggle_button = ttk.Button(frame, text="Start", command=self._toggle_running)
        self.toggle_button.grid(row=5, column=0, columnspan=2, sticky="ew", padx=10, pady=(10, 4))

        # Status
        status_frame = ttk.Frame(frame)
        status_frame.grid(row=6, column=0, columnspan=2, sticky="ew", padx=10, pady=(4, 0))
        ttk.Label(status_frame, text="Status:").pack(side="left")
        self.status_label = ttk.Label(status_frame, textvariable=self.status_var, foreground="#b00")
        self.status_label.pack(side="left", padx=(4, 0))

        ttk.Label(frame, textvariable=self.ticks_var, foreground="#666").grid(
            row=7, column=0, columnspan=2, sticky="w", padx=10, pady=(2, 0)
        )

        ttk.Label(
            frame,
            text="Tip: slam the cursor into any screen corner to force-stop instantly.",
            foreground="#666", wraplength=320, justify="left",
        ).grid(row=8, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 0))

    def _update_mode_controls(self):
        state = "normal" if self.mode_var.get() == MODE_JIGGLE else "disabled"
        self.distance_spin.configure(state=state)

    def _toggle_always_on_top(self):
        self.root.attributes("-topmost", self.always_on_top_var.get())

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

        self.tick_count = 0
        self.ticks_var.set("Moves so far: 0")
        self.mover_thread = MoverThread(
            interval=interval,
            mode=self.mode_var.get(),
            distance=distance,
            on_tick=self._on_tick,
            on_error=self._on_error,
        )
        self.mover_thread.start()

        self.status_var.set("Running")
        self.status_label.configure(foreground="#0a0")
        self.toggle_button.configure(text="Stop")

    def _stop(self):
        if self.mover_thread is not None:
            self.mover_thread.stop()
            self.mover_thread = None
        self.status_var.set("Stopped")
        self.status_label.configure(foreground="#b00")
        self.toggle_button.configure(text="Start")

    def _on_tick(self):
        self.tick_count += 1
        self.root.after(0, lambda: self.ticks_var.set(f"Moves so far: {self.tick_count}"))

    def _on_error(self, message):
        def handle():
            self._stop()
            messagebox.showwarning(APP_TITLE, message)
        self.root.after(0, handle)

    def _on_close(self):
        if self.mover_thread is not None:
            self.mover_thread.stop()
        self.root.destroy()


def main():
    root = tk.Tk()
    MouseMoverApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
