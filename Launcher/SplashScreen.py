import tkinter as tk
from Config import CONTENT


def center_window(window: tk.BaseWidget, width: int, height: int):
    x = (window.winfo_screenwidth()  - width)  // 2
    y = (window.winfo_screenheight() - height) // 2
    window.geometry(f"{width}x{height}+{x}+{y}")


class SplashScreen:
    def __init__(self, parent: tk.Tk):
        self.root = tk.Toplevel(parent)
        self.root.overrideredirect(True)
        self.root.configure(bg="#2b2b2b")
        center_window(self.root, 350, 100)

        logo = tk.PhotoImage(file=str(CONTENT / "logo" / "logo_64x64.png"))
        logo_label = tk.Label(self.root, image=logo, bg="#2b2b2b")
        logo_label.image = logo
        logo_label.pack(side="left", padx=10, pady=10)

        frame = tk.Frame(self.root, bg="#2b2b2b")
        frame.pack(expand=True, fill="both")

        tk.Label(frame, text="MiniCube", font=("Segoe UI", 14, "bold"),
                 fg="white", bg="#2b2b2b").pack(side="top", pady=(25, 2))

        self.label_text = tk.Label(frame, text="Loading...", font=("Segoe UI", 10),
                                   fg="lightgray", bg="#2b2b2b")
        self.label_text.pack(side="top", pady=(0, 25))