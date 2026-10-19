import contextlib
import sys
import threading
import time
import tkinter as tk
from Config import (
    ASSETS,
    TERMINAL_COLORS,
    TERMINAL_RESET
)

_print_lock = threading.Lock()


class LoggingMixin:

    def _append_log_to_window(self, msg, kind="info"):
        if self.log_text_win:
            try:
                self.log_text_win.insert(tk.END, msg + "\n", kind)
                self.log_text_win.see(tk.END)
            except Exception:
                pass

    def log(self, msg, kind="info"):
        timestamped = f"[{time.strftime('%H:%M:%S')}] {msg}"
        if self.debug:
            with _print_lock:
                terminal_message = f"[{kind.upper()}] {timestamped}"
                if sys.stdout.isatty():
                    color = TERMINAL_COLORS.get(kind, TERMINAL_COLORS["info"])
                    terminal_message = f"{color}{terminal_message}{TERMINAL_RESET}"
                print(terminal_message)
        self.log_buffer.append((timestamped, kind))
        self.root.after(0, lambda: self._append_log_to_window(timestamped, kind))

    def toggle_logs_window(self):
        if self.log_window and self.log_window.winfo_exists():
            self.log_window.deiconify()
            self.log_window.lift()
            self.log_window.focus_force()
        else:
            self.log_window = tk.Toplevel(self.root)
            self.log_window.title("Logs")
            self.log_window.iconbitmap(str(ASSETS / "icon" / "icon_64x64.ico"))
            self.log_window.geometry("600x300")
            self.log_window.protocol("WM_DELETE_WINDOW", self._on_close_log_window)

            self.log_text_win = tk.Text(self.log_window, height=25, width=120, bg="black", fg="white")
            self.log_text_win.pack(fill=tk.BOTH, expand=True)

            self.log_text_win.tag_config("info", foreground="white")
            self.log_text_win.tag_config("success", foreground="green")
            self.log_text_win.tag_config("warn", foreground="orange")
            self.log_text_win.tag_config("error", foreground="red")
            self.log_text_win.tag_config("game", foreground="cyan")
            self.log_text_win.tag_config("debug", foreground="purple")

            for line, kind in self.log_buffer:
                try:
                    self.log_text_win.insert(tk.END, line + "\n", kind)
                except Exception:
                    self.log_text_win.insert(tk.END, line + "\n")
            self.log_text_win.see(tk.END)

    def _on_close_log_window(self):
        if self.log_window:
            with contextlib.suppress(Exception):
                self.log_window.destroy()
        self.log_window = None
        self.log_text_win = None