import tkinter as tk
from tkinter import messagebox
from MiniCubeApp import MiniCubeApp
from SplashScreen import SplashScreen
from DiscordRPC import DiscordRPC

### Main entry point for the Mini Cube application. Initializes the splash screen and then launches the main application window.

def main():
    root = tk.Tk()
    root.withdraw()

    splash = SplashScreen(root)

    rpc = DiscordRPC()

    def start_launcher():
        try:
            app = MiniCubeApp(root, rpc=rpc)

            root.update()
            root.after(500, splash.root.destroy)

            root.deiconify()

            def on_close():
                app.save_settings()
                rpc.stop_rpc()
                root.update()
                root.destroy()

            root.protocol("WM_DELETE_WINDOW", on_close)

        except Exception as e:
            messagebox.showerror("Startup Error", str(e))
            root.destroy()

    root.after(100, start_launcher)
    root.mainloop()

if __name__ == "__main__":
    main()