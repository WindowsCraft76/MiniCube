import contextlib
import threading
from tkinter import messagebox
from Config import (
    CONNECTIVITY_CHECK_INTERVAL_MS
)
from Network import is_online


class ConnectivityMixin:

    def _online_only_state(self, enabled=True):
        return "normal" if enabled and not self.no_internet else "disabled"

    def _sync_online_widgets(self):
        widgets_enabled = {
            "repair_btn": not self._ui_locked,
            "add_account_btn": True,
        }
        for name, enabled in widgets_enabled.items():
            widget = getattr(self, name, None)
            if widget is None:
                continue
            with contextlib.suppress(Exception):
                if widget.winfo_exists():
                    widget.config(state=self._online_only_state(enabled))

    def _show_no_internet_info(self):
        message = (
            "Internet connection lost!\n"
            "It seems to only play the version that is already installed."
        )
        messagebox.showwarning("No internet connection", message, parent=self.root)

    def _enter_offline_ui(self):
        self._set_notification("internet", self.NO_INTERNET_LABEL, self._show_no_internet_info)
        self.refresh_version_list()
        self._sync_snapshot_check_state()
        self._sync_online_widgets()
        if self._ui_ready:
            self._show_no_internet_info()
        else:
            self._pending_no_internet_popup = True

    def _schedule_connectivity_check(self):
        self._connectivity_after_id = self.root.after(
            CONNECTIVITY_CHECK_INTERVAL_MS, self._connectivity_tick
        )

    def _connectivity_tick(self):
        def worker():
            online = is_online()
            self.root.after(0, lambda: self._on_connectivity_result(online))

        threading.Thread(target=worker, daemon=True).start()

    def _on_connectivity_result(self, online):
        self._set_no_internet(not online)
        self._schedule_connectivity_check()

    def _set_no_internet(self, value):
        if value == self.no_internet:
            return
        self.no_internet = value

        if value:
            self.log("Internet connection lost!", "warn")
            self._set_notification("internet", self.NO_INTERNET_LABEL, self._show_no_internet_info)
            self._show_no_internet_info()
            if self.rpc and self.rpc.is_running():
                self.rpc.stop_rpc()
            if not self._ui_locked:
                self.refresh_version_list()
        else:
            self.log("Internet connection restored!", "success")
            self._clear_notification("internet")
            if self.discord_rpc_var.get():
                self.rpc.start_rpc()
            previous = self.version_var.get()
            threading.Thread(target=self._run_online_tasks, args=(previous,), daemon=True).start()

        self._sync_snapshot_check_state()
        self._sync_online_widgets()