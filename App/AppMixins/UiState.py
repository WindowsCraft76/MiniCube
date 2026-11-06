import contextlib
import os
import time
import tkinter as tk


class UiStateMixin:

    def open_folder(self):
        folder_path = self.game_dir
        with contextlib.suppress(OSError):
            folder_path.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(folder_path)

    # attribute, active state, blocked by _ui_locked, requires internet
    _WIDGET_RULES = (
        ("offline_entry",   "normal", True,  False),
        ("offline_check",   "normal", True,  False),
        ("old_check",       "normal", True,  False),
        ("keep_open_check", "normal", False,  False),
        ("repair_btn",      "normal", True,  True),
        ("add_account_btn", "normal", False, True),
        ("game_dir_browse_btn", "normal", True, False),
        ("game_dir_reset_btn",  "normal", True, False),
    )

    def _apply_widget_states(self):
        for attr, active, locks, needs_online in self._WIDGET_RULES:
            widget = getattr(self, attr, None)
            if widget is None:
                continue
            blocked = (locks and self._ui_locked) or (needs_online and self.no_internet)
            with contextlib.suppress(Exception):
                if widget.winfo_exists():
                    widget.config(state="disabled" if blocked else active)

        with contextlib.suppress(Exception):
            if self._ui_locked or not self.account_manager.get_all_accounts():
                self.account_menu.config(state="disabled")
            else:
                self.account_menu.config(state="readonly")

        self._sync_version_menu_state()
        self._sync_snapshot_check_state()

    def set_ui_state(self, enabled: bool):
        self._ui_locked = not enabled
        normal_state = "normal" if enabled else "disabled"

        profile_menu_index = self._find_toolbar_index_by_label("Profile")
        if profile_menu_index is not None:
            self.toolbar.entryconfig(profile_menu_index, state=normal_state)
        if hasattr(self, "profile_menu"):
            for profile_index in range(self.profile_menu.index("end") + 1):
                self.profile_menu.entryconfig(profile_index, state=normal_state)

        self.root.config(menu=self.toolbar)
        self._right_align_notifications()
        self.root.after(250, self._right_align_notifications)

        self._apply_widget_states()

        if enabled:
            self.launch_btn.config(state="normal", text="Play")
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