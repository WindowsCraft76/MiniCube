import tkinter as tk
import sys
import time
import socket
import traceback
import threading
from tkinter import messagebox
from App import App
from SplashScreen import SplashScreen
from DiscordRPC import DiscordRPC
from Config import LOGS_DIR

SINGLE_INSTANCE_PORT = 51837

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

def _acquire_single_instance():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("127.0.0.1", SINGLE_INSTANCE_PORT))
    except OSError:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
                client.settimeout(1.0)
                client.connect(("127.0.0.1", SINGLE_INSTANCE_PORT))
                client.sendall(b"SHOW")
        except Exception:
            pass
        s.close()
        sys.exit(0)

    s.listen(1)
    return s

def main():
    instance_socket = _acquire_single_instance()

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
            app = App(root, rpc=rpc, debug=debug, instance_socket=instance_socket)

            root.update()
            root.after(100, splash.root.destroy)

            root.deiconify()

        except Exception as e:
            if debug:
                traceback.print_exc()
            messagebox.showerror("Startup Error", str(e))
            try:
                instance_socket.close()
            except Exception:
                pass
            root.destroy()

    root.after(100, start_launcher)
    root.mainloop()

if __name__ == "__main__":
    main()