import tkinter as tk
from Config import ASSETS

def center_window(window: tk.BaseWidget, width: int, height: int):
    x = (window.winfo_screenwidth()  - width)  // 2
    y = (window.winfo_screenheight() - height) // 2
    window.geometry(f"{width}x{height}+{x}+{y}")

class SplashScreen:
    def __init__(self, parent: tk.Tk):
        self.root = tk.Toplevel(parent)
        self.root.overrideredirect(True)
        center_window(self.root, 330, 90)
        self.background_image = tk.PhotoImage(file=str(ASSETS / "background" / "splashscreen.png"))

        self.background_label = tk.Label(self.root, image=self.background_image, borderwidth=0)
        self.background_label.place(x=0, y=0, relwidth=1, relheight=1)