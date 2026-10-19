import contextlib
import os
import time
import tkinter as tk
from Config import (
    GAME_DIR
)


class UiStateMixin:

    def open_folder(self):
        folder_path = GAME_DIR
        if os.name == "nt":
            os.startfile(folder_path)

    def set_ui_state(self, enabled: bool):
        self._ui_locked = not enabled
        normal_state = "normal" if enabled else "disabled"
        combo_state = "readonly" if enabled else "disabled"

        profile_menu_index = self._find_toolbar_index_by_label("Profile")
        if profile_menu_index is not None:
            self.toolbar.entryconfig(profile_menu_index, state=normal_state)
        if hasattr(self, "profile_menu"):
            for profile_index in range(self.profile_menu.index("end") + 1):
                self.profile_menu.entryconfig(profile_index, state=normal_state)

        self.root.config(menu=self.toolbar)
        self._right_align_notifications()

        self.account_menu.config(state=combo_state)
        self.root.after(250, self._right_align_notifications)
        self._sync_version_menu_state()

        self.offline_entry.config(state=normal_state)
        self.offline_check.config(state=normal_state)
        self._sync_snapshot_check_state()
        if enabled:
            self.launch_btn.config(state="normal", text="Play")

        if hasattr(self, "ram_spin") and self.ram_spin.winfo_exists():
            self.ram_spin.config(state=normal_state)

        if hasattr(self, "old_check") and self.old_check and self.old_check.winfo_exists():
            self.old_check.config(state=normal_state)

        if hasattr(self, "keep_open_check") and self.keep_open_check.winfo_exists():
            self.keep_open_check.config(state=normal_state)

        self._sync_online_widgets()

        if enabled:
            self.refresh_version_list()

    def update_progress(self, text=""):
        if text:
            self.root.after(0, lambda: self.progress_label.config(text=text))

    def _update_game_status(self):
        if self._game_started_at is None:
            return
        elapsed = self.format_duration(time.monotonic() - self._game_started_at)
        self.update_progress(f"Game in progress - {elapsed}")
        self._game_status_after_id = self.root.after(1000, self._update_game_status)

    def _stop_game_status_timer(self):
        if self._game_status_after_id is not None:
            with contextlib.suppress(tk.TclError):
                self.root.after_cancel(self._game_status_after_id)
            self._game_status_after_id = None

    def _set_launch_button(self, text, state="normal"):
        self.root.after(0, lambda: self.launch_btn.config(text=text, state=state))

    def format_duration(self, seconds: float) -> str:
        secs = int(max(0, round(seconds)))
        if secs >= 3600:
            h = secs // 3600
            m = (secs % 3600) // 60
            s = secs % 60
            return f"{h}h{m:02d}m{s:02d}s"
        if secs >= 60:
            m = secs // 60
            s = secs % 60
            return f"{m}m{s:02d}s"
        return f"{secs}s"