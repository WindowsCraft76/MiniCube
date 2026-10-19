import contextlib
import os
import platform
import subprocess
import threading
import time
import tkinter as tk
from collections import deque
from tkinter import messagebox
from Config import (
    ASSETS,
    GAME_DIR
)
from AppMixins.Exceptions import _AbortLaunch


class CrashMixin:

    def _show_error_and_wait(self, title, message):
        closed = threading.Event()

        def show():
            try:
                messagebox.showerror(title, message)
            finally:
                closed.set()

        self.root.after(0, show)
        closed.wait()

    def _build_debug_report(self, error, app_info=None):
        lines = ["Information details:"]
        lines.append(f"     OS: {platform.platform()}")
        lines.append(f"     Python: {platform.python_version()}")
        if app_info:
            for key, value in app_info.items():
                lines.append(f"     {key}: {value}")
        lines.append("")
        lines.append("Error:")
        lines.append(f"     {error}")
        return "\n".join(lines)

    def _open_with_default_app(self, path):
        try:
            system = platform.system().lower()
            if system.startswith("win"):
                os.startfile(str(path))
            elif system.startswith("darwin"):
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as e:
            self.log(f"Unable to open {path}: {e}", "error")

    def _copy_to_clipboard(self, text):
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
        except Exception as e:
            self.log(f"Unable to copy to clipboard: {e}", "error")

    def _show_launch_error_dialog(self, title, summary, details="", report_path=None):
        result = {"choice": "cancel"}
        event = threading.Event()

        def build():
            dialog = tk.Toplevel(self.root)
            dialog.title(title)
            dialog.transient(self.root)
            dialog.grab_set()
            dialog.resizable(False, False)
            with contextlib.suppress(Exception):
                dialog.iconbitmap(str(ASSETS / "icon" / "icon_64x64.ico"))

            tk.Label(
                dialog, text=summary, wraplength=440, justify="left",
                font=("Segoe UI", 10, "bold")
            ).pack(padx=15, pady=(15, 5), anchor="w")

            if details:
                frame = tk.Frame(dialog)
                frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)
                frame.columnconfigure(0, weight=1)
                frame.rowconfigure(0, weight=1)

                text_widget = tk.Text(frame, height=12, width=64, bg="black", fg="white", wrap="none")
                vbar = tk.Scrollbar(frame, orient="vertical", command=text_widget.yview)
                hbar = tk.Scrollbar(frame, orient="horizontal", command=text_widget.xview)
                text_widget.config(yscrollcommand=vbar.set, xscrollcommand=hbar.set)
                text_widget.insert("1.0", details)
                text_widget.config(state="disabled")

                text_widget.grid(row=0, column=0, sticky="nsew")
                vbar.grid(row=0, column=1, sticky="ns")
                hbar.grid(row=1, column=0, sticky="ew")

            if report_path:
                tk.Button(
                    dialog, text="Open crash report", width=18,
                    command=lambda: self._open_with_default_app(report_path)
                ).pack(pady=(0, 5))
            elif details:
                tk.Button(
                    dialog, text="Copy", width=18,
                    command=lambda: self._copy_to_clipboard(details)
                ).pack(pady=(0, 5))

            btn_frame = tk.Frame(dialog)
            btn_frame.pack(pady=15)

            def choose(choice):
                result["choice"] = choice
                dialog.destroy()
                event.set()

            tk.Button(btn_frame, text="Repair", width=12, command=lambda: choose("repair")).pack(side=tk.LEFT, padx=5)
            tk.Button(btn_frame, text="Retry", width=12, command=lambda: choose("retry")).pack(side=tk.LEFT, padx=5)
            tk.Button(btn_frame, text="Abandoned", width=12, command=lambda: choose("cancel")).pack(side=tk.LEFT, padx=5)

            dialog.protocol("WM_DELETE_WINDOW", lambda: choose("cancel"))
            dialog.update_idletasks()
            x = self.root.winfo_x() + (self.root.winfo_width() - dialog.winfo_width()) // 2
            y = self.root.winfo_y() + (self.root.winfo_height() - dialog.winfo_height()) // 2
            dialog.geometry(f"+{x}+{y}")

        self.root.after(0, build)
        event.wait()
        return result["choice"]

    def _find_latest_crash_report(self, since_str):
        crash_dir = GAME_DIR / "crash-reports"
        if not crash_dir.exists():
            return None
        try:
            since = time.mktime(time.strptime(since_str, "%Y-%m-%d %H:%M:%S"))
            candidates = [
                f for f in crash_dir.glob("*.txt")
                if f.stat().st_mtime >= since
            ]
            if not candidates:
                return None
            latest = max(candidates, key=lambda f: f.stat().st_mtime)
            return str(latest)
        except Exception:
            return None

    def _retry_or_abort(self, version_id, ram, title="Launch error", summary="", details="", report_path=None):
        choice = self._show_launch_error_dialog(title, summary, details, report_path=report_path)

        if choice == "repair" and self.no_internet:
            self.log("Repair is unavailable while offline.", "warn")
            self._show_error_and_wait("Repair version", "You are offline.\nRepairing a version requires an internet connection.")
            raise _AbortLaunch()

        if choice == "repair":
            self.log(f"Preparing to repair Minecraft {version_id}...", "info")
            return self._attempt_launch(version_id, ram, force=True)

        if choice == "retry":
            return self._attempt_launch(version_id, ram)

        raise _AbortLaunch()

    def _handle_crash(self, version_id, ram, reason, launch_time, log_tail, exit_code, java_info, command):
        crash_report_path = self._find_latest_crash_report(launch_time)

        debug_text = None
        if crash_report_path:
            try:
                with open(crash_report_path, encoding="utf-8", errors="replace") as f:
                    debug_text = f.read()
            except Exception:
                crash_report_path = None

        if debug_text is None:
            error_text = reason
            if log_tail:
                error_text += "\n\nLast log lines:\n" + "\n".join(log_tail)
            debug_text = self._build_debug_report(
                error_text,
                app_info={"Java version": java_info, "Exit code": exit_code, "Launch command": command},
            )

        return self._retry_or_abort(
            version_id, ram,
            title="Game crashed",
            summary=reason,
            details=debug_text,
            report_path=crash_report_path,
        )

    def _watch_game_output(self, game_process):
        crash_pattern = "Failed to parse vanilla pack metadata"
        known_crash_reason = None
        log_tail = deque(maxlen=25)

        for line in iter(game_process.stdout.readline, ""):
            clean_line = line.strip("\n")
            self.log(clean_line, "game")
            log_tail.append(clean_line)
            if crash_pattern in clean_line:
                known_crash_reason = "Failed to parse vanilla pack metadata."
                self.log("Corrupted pack metadata detected, stopping the game...", "error")
                game_process.terminate()
                break

        return known_crash_reason, log_tail