import contextlib
import re
import sys
import threading
import time
import tkinter as tk
import traceback
from tkinter import messagebox
from App import App
from Config import (
    LOGS_DIR,
)
from DiscordRPC import DiscordRPC
from SplashScreen import SplashScreen
from InstanceLock import acquire_instance_slot

_ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")

class Tee:
    def __init__(self, *files):
        self.files = files

    def write(self, data):
        for f in self.files:
            output = data if f is sys.__stdout__ else _ANSI_ESCAPE.sub("", data)
            f.write(output)
            f.flush()

    def flush(self):
        for f in self.files:
            f.flush()

    def isatty(self):
        return any(f.isatty() for f in self.files)

def _show_fatal_error(error):
    with contextlib.suppress(Exception):
        temp_root = tk.Tk()
        temp_root.withdraw()
        messagebox.showerror(
            "MiniCube Startup Error",
            "MiniCube could not start.\n\n"
            f"{type(error).__name__}: {error}\n\n"
            "If the problem persists, please report it to the developers."
        )
        temp_root.destroy()

def main():

    instance_lock, other_running = acquire_instance_slot()
    root = tk.Tk()
    root.withdraw()

    if other_running and not messagebox.askyesno(
        "MiniCube",
        "MiniCube is already running.\n"
        "Opening a new instance may cause conflicts\n\n"
        "Do you want to open a new instance anyway?",
        icon="warning",
    ):
        root.destroy()
        sys.exit(0)

    splash = SplashScreen(root)
    rpc = DiscordRPC()

    debug = "--debug" in sys.argv[1:]

    if debug:
        log_file = open(
            LOGS_DIR / f"debug_{time.strftime('%Y-%m-%d_%H-%M-%S')}.log",
            "w",
            encoding="utf-8"
        )

        sys.stdout = Tee(sys.__stdout__, log_file)
        sys.stderr = Tee(sys.__stderr__, log_file)

        print("Starting MiniCube...")

        sys.excepthook = traceback.print_exception

        if hasattr(threading, "excepthook"):
            threading.excepthook = (
                lambda a: traceback.print_exception(
                    a.exc_type,
                    a.exc_value,
                    a.exc_traceback
                )
            )

    def start_launcher():
        try:
            app = App(root, rpc=rpc, debug=debug)
            root.app = app

            root.update()
            root.after(100, splash.root.destroy)

            root.deiconify()

        except Exception as e:
            if debug:
                traceback.print_exc()
            messagebox.showerror("Startup Error", str(e))
            root.destroy()

    root.after(100, start_launcher)
    root.mainloop()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        if "--debug" in sys.argv[1:]:
            traceback.print_exc()
        _show_fatal_error(e)
        sys.exit(1)