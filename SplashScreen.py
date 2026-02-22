import tkinter as tk
from Config import CONTENT, center_window

class SplashScreen:
    def __init__(self, parent):
        self.root = tk.Toplevel(parent)
        self.root.overrideredirect(True)
        self.root.configure(bg="#2b2b2b")

        logo = tk.PhotoImage(file=f"{CONTENT}\\icon\\icon_64px.png")
        logo_label = tk.Label(self.root, image=logo, bg="#2b2b2b")
        logo_label.image = logo
        logo_label.pack(side="left", padx=10, pady=10)

        center_window(self.root, 350, 100)

        frame = tk.Frame(self.root, bg="#2b2b2b")
        frame.pack(expand=True, fill="both")

        self.label_title = tk.Label(
            frame,
            text="Mini Cube",
            font=("Segoe UI", 14, "bold"),
            fg="white",
            bg="#2b2b2b"
        )
        self.label_title.pack(side="top", pady=(25, 2))

        self.label_text = tk.Label(
            frame,
            text="Loading...",
            font=("Segoe UI", 10),
            fg="lightgray",
            bg="#2b2b2b"
        )
        self.label_text.pack(side="top", pady=(0, 25))
