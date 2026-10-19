import contextlib
import os
import re
import threading
import time
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import messagebox, ttk
import ctypes
import shutil
from urllib.parse import unquote, urlparse
from Config import (
    ASSETS,
    DOWNLOADLAST_URL,
    UPDATE_POPUP_MESSAGE_DEFAULT,
    UPDATE_POPUP_MESSAGES,
    TEMP_DIR
)
from VersionManager import (
    check_for_update,
    get_update_page_url,
)


class UpdatesMixin:

    def check_version_mismatch(self):

        info = check_for_update()

        local_display = info["local_display_version"]
        remote_display = info["remote_display_version"]
        remote_numeric = info["remote_version"]
        remote_type = info["remote_type"]

        if self.debug:
            self.log(f"Info version:\nLocal version: {local_display}\nRemote version: {remote_display}", "debug")
            return

        self.log("Checking for updates...", "info")

        if remote_numeric.startswith("Error"):
            self.log(f"Unable to check for updates: {remote_numeric}", "error")
            self.root.after(0, self._remove_update_toolbar_entry)
            self.root.after(0, self._hide_update_button)
            return

        if info["update_available"]:
            self.log(f"Update available: {local_display} -> {remote_display} ({DOWNLOADLAST_URL})", "info")
            self._update_download_url = info.get("download_url", "")
            self.root.after(
                0,
                lambda: self._add_update_toolbar_entry(remote_display, remote_numeric, remote_type),
            )
        else:
            self.log(f"Launcher up to date ({local_display})", "info")
            self.root.after(0, self._remove_update_toolbar_entry)
            self.root.after(0, self._hide_update_button)

    def _hide_update_button(self):
        with contextlib.suppress(Exception):
            self.update_btn.pack_forget()

    def _add_update_toolbar_entry(self, remote_version, remote_numeric, remote_type):
        self._set_notification("update", self.UPDATE_LABEL, lambda: self._start_auto_update(remote_version))

        if self._ui_ready:
            self._show_update_popup(remote_version, remote_numeric, remote_type)
        else:
            self._pending_update_version = (remote_version, remote_numeric, remote_type)

    def _show_update_popup(self, remote_version, remote_numeric, remote_type):

        message_template = UPDATE_POPUP_MESSAGES.get(remote_type.lower(), UPDATE_POPUP_MESSAGE_DEFAULT)
        message = message_template.format(version=remote_version)

        popup = tk.Toplevel(self.root)
        popup.title("New update available!")
        popup.iconbitmap(str(ASSETS / "icon" / "icon_64x64.ico"))
        popup.resizable(False, False)
        popup.transient(self.root)

        tk.Label(
            popup,
            text=message,
            justify="center"
        ).pack(pady=(15, 10), padx=15)

        btn_frame = tk.Frame(popup)
        btn_frame.pack(pady=(0, 15), anchor="s", side="bottom")

        def on_yes():
            self._start_auto_update(remote_version)
            popup.destroy()

        def on_no():
            popup.destroy()

        tk.Button(btn_frame, text="Yes, update now!", width=25, command=on_yes).pack(side="right", padx=(5, 25))
        tk.Button(btn_frame, text="No, later", width=15, command=on_no).pack(side="right", padx=(25, 5))

        popup.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (popup.winfo_width() // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (popup.winfo_height() // 2)
        popup.geometry(f"+{x}+{y}")

    def _remove_update_toolbar_entry(self):
        self._clear_notification("update")

    def _start_auto_update(self, remote_display):
        if self._updating:
            return
        url = self._update_download_url
        if not url:
            webbrowser.open(get_update_page_url())
            return
        if self._minecraft_running():
            messagebox.showwarning("Update", "Close Minecraft before updating.")
            return

        self._updating = True
        self._cancel_update.clear()
        self._hide_all_windows()
        self._build_update_window(remote_display)
        threading.Thread(target=self._download_installer, args=(url,), daemon=True).start()

    def _build_update_window(self, remote_display):
        win = tk.Toplevel(self.root)
        win.title("MiniCube Update")
        win.iconbitmap(str(ASSETS / "icon" / "icon_64x64.ico"))
        win.resizable(False, False)
        win.protocol("WM_DELETE_WINDOW", self._cancel_auto_update)

        tk.Label(win, text=f"Downloading setup for {remote_display}...").pack(pady=(15, 5), padx=20)
        self._update_bar = ttk.Progressbar(win, length=300, mode="determinate", maximum=100)
        self._update_bar.pack(padx=20)
        self._update_status = tk.Label(win, text="Starting...")
        self._update_status.pack(pady=5)
        tk.Button(win, text="Cancel", width=12, command=self._cancel_auto_update).pack(pady=(5, 15))

        win.update_idletasks()
        x = (win.winfo_screenwidth() - win.winfo_width()) // 2
        y = (win.winfo_screenheight() - win.winfo_height()) // 2
        win.geometry(f"+{x}+{y}")
        self._update_win = win

    def _download_installer(self, url):
        try:
            with self._http.get(url, stream=True, timeout=15) as r:
                r.raise_for_status()
                total = int(r.headers.get("Content-Length", 0))
                name = None
                cd = r.headers.get("Content-Disposition", "")
                match = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', cd, re.IGNORECASE)
                if match:
                    name = unquote(match.group(1)).strip()
                if not name:
                    name = Path(unquote(urlparse(r.url).path)).name
                if Path(name).suffix.lower() != ".exe":
                    name = "MiniCube-Setup.exe"
                dest = TEMP_DIR / name
                done, last_ui = 0, 0.0
                with open(dest, "wb") as f:
                    for chunk in r.iter_content(chunk_size=64 * 1024):
                        if self._cancel_update.is_set():
                            shutil.rmtree(TEMP_DIR, ignore_errors=True)
                            return
                        f.write(chunk)
                        done += len(chunk)
                        now = time.monotonic()
                        if now - last_ui > 0.1:
                            last_ui = now
                            self.root.after(0, self._set_update_progress, done, total)
            self.root.after(0, self._finish_auto_update, dest)
        except Exception as e:
            shutil.rmtree(TEMP_DIR, ignore_errors=True)
            if not self._cancel_update.is_set():
                self.root.after(0, self._on_update_failed, str(e))

    def _set_update_progress(self, done, total):
        if not (self._update_win and self._update_win.winfo_exists()):
            return
        mb = done / 1048576
        if total:
            pct = done * 100 / total
            self._update_bar["value"] = pct
            self._update_status.config(text=f"{mb:.1f} / {total / 1048576:.1f} MB ({pct:.0f}%)")
        else:
            self._update_status.config(text=f"{mb:.1f} MB")

    def _close_update_window(self):
        with contextlib.suppress(Exception):
            if self._update_win:
                self._update_win.destroy()
        self._update_win = None

    def _cancel_auto_update(self):
        self._cancel_update.set()
        self._close_update_window()
        self._updating = False
        self._restore_all_windows()
        self.update_progress("Update canceled")

    def _on_update_failed(self, error):
        self._close_update_window()
        self._updating = False
        self._restore_all_windows()
        self.log(f"Update download failed: {error}", "error")
        if messagebox.askyesno(
            "Update failed",
            f"Unable to download the update.\n\n{error}\n\nOpen the download page instead?",
        ):
            webbrowser.open(get_update_page_url())

    def _finish_auto_update(self, installer: Path):
        self._update_status.config(text="Launching the installer...")
        self._update_win.update_idletasks()
        self.log(f"Launching installer: {installer} --update", "info")

        self._shutdown_app()

        try:
            rc = ctypes.windll.shell32.ShellExecuteW(
                None, "open", str(installer), "--update", str(installer.parent), 1
            )
            launched = rc > 32
        except Exception:
            launched = False
        if not launched:
            webbrowser.open(get_update_page_url())

        os._exit(0)