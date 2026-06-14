import tkinter as tk
import sys
import time
import traceback
import threading
from tkinter import messagebox
from App import App
from SplashScreen import SplashScreen
from DiscordRPC import DiscordRPC
from Config import LOGS_DIR

class Tee:
    def __init__(self, *files):
        self.files = files

    def write(self, data):
        for f in self.files:
            f.write(data)
            f.flush()

    def flush(self):
        for f in self.files:
            f.flush()

def main():
    root = tk.Tk()
    root.withdraw()

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

        sys.excepthook = lambda t, v, tb: traceback.print_exception(t, v, tb)

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

            root.update()
            root.after(500, splash.root.destroy)

            root.deiconify()

            def on_close():
                app.save_settings()
                rpc.stop_rpc()
                root.update()
                root.destroy()
                if debug:
                    print("Closing!")

            root.protocol("WM_DELETE_WINDOW", on_close)

        except Exception as e:
            if debug:
                traceback.print_exc()
            messagebox.showerror("Startup Error", str(e))
            root.destroy()

    root.after(100, start_launcher)
    root.mainloop()

if __name__ == "__main__":
    main()