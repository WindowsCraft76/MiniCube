import tkinter as tk
from tkinter import messagebox
from App import App
from SplashScreen import SplashScreen
from DiscordRPC import DiscordRPC

def main():
    root = tk.Tk()
    root.withdraw()

    splash = SplashScreen(root)

    rpc = DiscordRPC()

    def start_launcher():
        try:
            app = App(root, rpc=rpc)

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