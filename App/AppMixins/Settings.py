import contextlib
import json
import tkinter as tk
from Config import (
    ASSETS,
    SETTINGS_FILE
)
from SplashScreen import center_window


class SettingsMixin:

    def toggle_settings_window(self):
        if getattr(self, "settings_window", None) and self.settings_window.winfo_exists():
            try:
                self._sync_settings_from_file()
                self.settings_window.deiconify()
                self.settings_window.lift()
                self.settings_window.focus_force()
            except Exception:
                pass
            return

        self._sync_settings_from_file()

        self.settings_window = tk.Toplevel(self.root)
        self.settings_window.title("Settings")
        self.settings_window.resizable(False, False)
        self.settings_window.iconbitmap(str(ASSETS / "icon" / "icon_64x64.ico"))
        center_window(self.settings_window, 350, 220)

        tk.Label(self.settings_window, text="RAM Memory (MB):").pack(pady=2)

        self._temp_ram_var = tk.IntVar(value=self.ram_var.get())
        self.ram_spin = tk.Spinbox(self.settings_window, from_=512, to=16384, increment=512, textvariable=self._temp_ram_var)
        self.ram_spin.pack(pady=5)

        self._temp_show_old_var = tk.BooleanVar(value=self.show_old_var.get())
        self._temp_discord_rpc_var = tk.BooleanVar(value=self.discord_rpc_var.get())
        self._temp_keep_open_var = tk.BooleanVar(value=self.keep_open_var.get())

        self.old_check = tk.Checkbutton(self.settings_window, text="Show historical versions", variable=self._temp_show_old_var)
        self.old_check.pack(pady=5)

        self.discord_rpc_check = tk.Checkbutton(
            self.settings_window,
            text="Enable Discord RPC",
            variable=self._temp_discord_rpc_var
        )
        self.discord_rpc_check.pack(pady=5)

        self.keep_open_check = tk.Checkbutton(
            self.settings_window,
            text="Keep running in background while Minecraft is open",
            variable=self._temp_keep_open_var
        )
        self.keep_open_check.pack(pady=5)

        btn_frame = tk.Frame(self.settings_window)
        btn_frame.pack(pady=(20, 5))

        self.save_btn = tk.Button(btn_frame, text="Save", command=lambda: [self._apply_settings_from_temp(), self.save_settings()])
        self.save_btn.pack(side=tk.LEFT, padx=5)

        self.reset_btn = tk.Button(btn_frame, text="Reset settings", command=self.reset_settings)
        self.reset_btn.pack(side=tk.LEFT, padx=5)

        self.repair_btn = tk.Button(btn_frame, text="Repair version", command=self._confirm_repair_selected_version)
        self.repair_btn.pack(side=tk.LEFT, padx=5)
        self._sync_online_widgets()

        if self._ui_locked:
            self.ram_spin.config(state="disabled")
            self.old_check.config(state="disabled")
            self.keep_open_check.config(state="disabled")
            self.repair_btn.config(state="disabled")

        def _on_close():
            with contextlib.suppress(Exception):
                self.settings_window.destroy()
            self.settings_window = None
            if getattr(self, "old_check", None):
                with contextlib.suppress(Exception):
                    self.old_check.destroy()
                self.old_check = None
            if getattr(self, "repair_btn", None):
                with contextlib.suppress(Exception):
                    self.repair_btn.destroy()
                self.repair_btn = None
        
        self.settings_window.protocol("WM_DELETE_WINDOW", _on_close)

    def load_settings(self):

        self.log("Loading settings...", "info")

        if not SETTINGS_FILE.exists():
            return

        try:
            with open(SETTINGS_FILE, encoding="utf-8") as f:
                data = json.load(f)

            self.username_var.set(data.get("username", "Steve"))
            self.ram_var.set(data.get("ram", 2048))
            self.show_snapshots_var.set(data.get("show_snapshots", False))
            self.show_old_var.set(data.get("show_old_versions", False))
            self.discord_rpc_var.set(data.get("discord_rpc", True))
            self.keep_open_var.set(data.get("keep_open_if_minecraft_running", True))
            self.default_account = data.get("default_account")
            self.last_used_account = data.get("last_used_account")

            self.log("Settings loaded!", "success")
        except Exception as e:
            self.log(f"Error loading settings! {e}", "error")

    def _load_settings_file(self):
        if not SETTINGS_FILE.exists():
            return {}
        try:
            with open(SETTINGS_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _write_settings_file(self, data):
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            self.log(f"Error saving settings: {e}", "error")

    def save_settings(self):
        data = self._load_settings_file()

        data.update({
            "username": self.username_var.get(),
            "ram": self.ram_var.get(),
            "show_snapshots": self.show_snapshots_var.get(),
            "show_old_versions": self.show_old_var.get(),
            "discord_rpc": self.discord_rpc_var.get(),
            "keep_open_if_minecraft_running": self.keep_open_var.get(),
            "default_account": self.default_account,
            "last_used_account": self.last_used_account
        })

        self._write_settings_file(data)

    def _update_account_prefs(self, **updates):
        for key, value in updates.items():
            setattr(self, key, value)

        data = self._load_settings_file()
        data["default_account"] = self.default_account
        data["last_used_account"] = self.last_used_account

        self._write_settings_file(data)

    def reset_settings(self):
        self.username_var.set("Steve")
        self.ram_var.set(2048)
        self.show_snapshots_var.set(False)
        self.show_old_var.set(False)
        self.discord_rpc_var.set(True)
        self.keep_open_var.set(True)

        if SETTINGS_FILE.exists():
            SETTINGS_FILE.unlink()

        self.log("Settings reset to defaults!", "info")
        self._apply_discord_rpc()
        self.load_settings()

    def _sync_settings_from_file(self):
        if not SETTINGS_FILE.exists():
            return

        try:
            with open(SETTINGS_FILE, encoding="utf-8") as f:
                data = json.load(f)

            self.username_var.set(data.get("username", "Steve"))
            self.ram_var.set(data.get("ram", 2048))

            new_show_snapshots = data.get("show_snapshots", False)
            new_show_old = data.get("show_old_versions", False)
            new_discord_rpc = data.get("discord_rpc", True)
            new_keep_open = data.get("keep_open_if_minecraft_running", True)

            if self.show_snapshots_var.get() != new_show_snapshots:
                self.show_snapshots_var.set(new_show_snapshots)
                self.refresh_version_list()

            if self.show_old_var.get() != new_show_old:
                self.show_old_var.set(new_show_old)
                self.refresh_version_list()

            if self.discord_rpc_var.get() != new_discord_rpc:
                self.discord_rpc_var.set(new_discord_rpc)
                self._apply_discord_rpc()

            if self.keep_open_var.get() != new_keep_open:
                self.keep_open_var.set(new_keep_open)

            self.log("Settings synced from file.", "info")
        except Exception as e:
            self.log(f"Error syncing settings from file: {e}", "error")

    def _apply_settings_from_temp(self):
        self.ram_var.set(self._temp_ram_var.get())

        old_changed = self.show_old_var.get() != self._temp_show_old_var.get()
        self.show_old_var.set(self._temp_show_old_var.get())
        if old_changed:
            self.refresh_version_list()

        rpc_changed = self.discord_rpc_var.get() != self._temp_discord_rpc_var.get()
        self.discord_rpc_var.set(self._temp_discord_rpc_var.get())
        if rpc_changed:
            self._apply_discord_rpc()

        self.keep_open_var.set(self._temp_keep_open_var.get())

    def _apply_discord_rpc(self):
        running = self.rpc.is_running()
        if self.discord_rpc_var.get() and not self.no_internet:
            if not running:
                self.rpc.start_rpc()
        elif running:
            self.rpc.stop_rpc()