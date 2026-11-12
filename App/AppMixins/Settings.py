import contextlib
import json
import shutil
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from Config import (
    ASSETS,
    CACHE_DIR,
    GAME_DIR,
    SETTINGS_FILE
)
from SplashScreen import center_window
from i18n import i18n, t
from ScrollingButton import ScrollingButton

_MAX_DOWNLOAD_LIMIT_KBPS = 1_000_000


class SettingsMixin:

    @staticmethod
    def _parse_download_limit(value, fallback=0):
        try:
            number = int(str(value).strip())
        except (TypeError, ValueError):
            return fallback
        return max(0, min(_MAX_DOWNLOAD_LIMIT_KBPS, number))

    def _load_language_setting(self):
        self._language_setting = i18n.current
        if not SETTINGS_FILE.exists():
            return

        try:
            with open(SETTINGS_FILE, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            self.log(f"Error loading language setting: {e}", "error")
            return

        if not isinstance(data, dict):
            self.log("Error loading language setting: settings must contain a JSON object.", "error")
            return

        language = data.get("language", "en_us")
        if language in i18n.available():
            self._language_setting = language
            i18n.set_language(language)
        else:
            i18n.set_language(i18n.default_language)
            self._language_setting = i18n.current
            self.log(f"Unknown language setting {language!r}, using {i18n.current}.", "warn")

    def _cache_size(self):
        total = 0
        for path in CACHE_DIR.rglob("*"):
            with contextlib.suppress(OSError):
                if path.is_file():
                    total += path.stat().st_size
        return total

    def _confirm_clear_cache(self):
        parent = getattr(self, "settings_window", None) or self.root
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

        if not messagebox.askyesno(
            t("settings.yesno_box.clear_cache.title"),
            t('settings.yesno_box.clear_cache.detail'),
            parent=parent,
        ):
            return

        removed = failed = 0
        for item in CACHE_DIR.iterdir():
            try:
                if item.is_dir() and not item.is_symlink():
                    shutil.rmtree(item)
                else:
                    item.unlink()
                removed += 1
            except OSError as e:
                failed += 1
                self.log(f"Unable to delete {item.name} from the cache: {e}", "error")

        self.log(f"Cache cleared ({removed} item(s) removed, {failed} failed).", "success" if not failed else "warn")
        self.refresh_account_listbox()

        if failed:
            messagebox.showwarning(
                t("settings.warning_box.clear_cache_failed.title"),
                t("settings.warning_box.clear_cache_failed.detail").format(a=failed),
                parent=parent,
            )
        else:
            messagebox.showinfo(
                t("settings.info_box.cache_cleared.title"),
                t("settings.info_box.cache_cleared.detail"),
                parent=parent
            )

    @property
    def game_dir(self) -> Path:
        return Path(self.game_dir_var.get() or GAME_DIR)

    def _browse_game_dir(self):
        chosen = filedialog.askdirectory(
            parent=self.settings_window,
            title=t("settings.directory_box.game_directory.title"),
            initialdir=self._temp_game_dir_var.get(),
            mustexist=False,
        )
        if chosen:
            self._temp_game_dir_var.set(str(Path(chosen)))

    def _reset_game_dir(self):
        self._temp_game_dir_var.set(str(GAME_DIR))

    def _apply_game_dir(self):
        new_dir = self._temp_game_dir_var.get().strip()
        current = self.game_dir_var.get()
        if not new_dir or new_dir == current:
            self._temp_game_dir_var.set(current)
            return

        parent = self.settings_window if getattr(self, "settings_window", None) else self.root

        if self._minecraft_running() or self._ui_locked:
            messagebox.showwarning(
                t("settings.warning_box.game_open_change_directory.title"),
                t("settings.warning_box.game_open_change_directory.detail"),
                parent=parent,
            )
            self._temp_game_dir_var.set(current)
            return

        path = Path(new_dir)
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe = path / ".minicube_write_test"
            probe.write_text("")
            probe.unlink()
        except OSError as e:
            self.log(f"Invalid game directory {path}: {e}", "error")
            messagebox.showerror(
                t("settings.error_box.game_directory_invalid.title"),
                t("settings.error_box.game_directory_invalid.detail").format(a=e),
                parent=parent,
            )
            self._temp_game_dir_var.set(current)
            return

        self.game_dir_var.set(str(path))
        self.log(f"Game directory changed to {path}", "success")
        messagebox.showinfo(
            t("settings.info_box.game_directory_changed.title"),
            t("settings.info_box.game_directory_changed.detail"),
            parent=parent,
        )

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

        win = self.settings_window = tk.Toplevel(self.root)
        win.title(t("settings.window.title"))
        win.resizable(False, False)
        win.iconbitmap(str(ASSETS / "icon" / "icon_64x64.ico"))
        center_window(win, 500, 320)

        self._temp_ram_var = tk.IntVar(value=self.ram_var.get())
        self._temp_show_old_var = tk.BooleanVar(value=self.show_old_var.get())
        self._temp_discord_rpc_var = tk.BooleanVar(value=self.discord_rpc_var.get())
        self._temp_keep_open_var = tk.BooleanVar(value=self.keep_open_var.get())
        self._temp_close_on_launch_var = tk.BooleanVar(value=self.close_on_launch_var.get())
        self._temp_game_dir_var = tk.StringVar(value=self.game_dir_var.get())
        self._temp_download_limit_var = tk.StringVar(value=str(self.download_limit_kbps))
        self._temp_language_var = tk.StringVar(value=i18n.current)

        btn_frame = tk.Frame(win)
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)

        def _on_save():
            if getattr(self, "_commit_ram_entry", None):
                self._commit_ram_entry()
            self._apply_settings_from_temp()
            self.save_settings()

        self.save_btn = ScrollingButton(btn_frame, text=t("settings.button.save"), command=_on_save, width=7)
        self.save_btn.pack(side=tk.RIGHT, padx=5)

        self.reset_btn = ScrollingButton(btn_frame, text=t("settings.button.reset"), command=self.reset_settings, width=12)
        self.reset_btn.pack(side=tk.RIGHT, padx=5)

        self.repair_btn = ScrollingButton(
                    btn_frame,
                    text=t("settings.button.repair"),
                    command=self._confirm_repair_selected_version,
                    width=13
                )
        self.repair_btn.pack(side=tk.RIGHT, padx=5)

        self.clear_cache_btn = ScrollingButton(btn_frame, text=t("settings.button.clear_cache"), command=self._confirm_clear_cache, width=11)
        self.clear_cache_btn.pack(side=tk.RIGHT, padx=5)

        tabs_bar = tk.Frame(win)
        tabs_bar.pack(fill=tk.X, padx=10, pady=(3, 0))

        content = tk.Frame(win, relief="groove", bd=2)
        content.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 0))

        tab_app = tk.Frame(content, padx=15, pady=15)
        tab_language = tk.Frame(content, padx=15, pady=15)
        tab_java_memory = tk.Frame(content, padx=15, pady=15)
        tab_privacy = tk.Frame(content, padx=15, pady=15)

        tabs = {
            t("settings.tab.app"): tab_app,
            t("settings.tab.language"): tab_language,
            t("settings.tab.java_memory"): tab_java_memory,
            t("settings.tab.privacy"): tab_privacy
        }
        current_tab = tk.StringVar(value=t("settings.tab.app"))

        def show_tab():
            for frame in tabs.values():
                frame.pack_forget()
            tabs[current_tab.get()].pack(fill=tk.BOTH, expand=True)

        for name in tabs:
            tk.Radiobutton(
                tabs_bar,
                text=name,
                value=name,
                variable=current_tab,
                indicatoron=False,
                padx=12,
                pady=4,
                command=show_tab,
            ).pack(side=tk.LEFT)

        show_tab()

        self.old_check = tk.Checkbutton(
            tab_app,
            text=t("settings.check.show_old_versions"),
            variable=self._temp_show_old_var
        )
        self.old_check.pack(anchor="w", pady=5)

        self.close_on_launch_check = tk.Checkbutton(
            tab_app,
            text=t("settings.check.close_on_launch"),
            variable=self._temp_close_on_launch_var
        )
        self.close_on_launch_check.pack(anchor="w", pady=5)

        self.keep_open_check = tk.Checkbutton(
            tab_app,
            text=t("settings.check.keep_background"),
            variable=self._temp_keep_open_var
        )
        self.keep_open_check.pack(anchor="w", pady=5)

        tk.Label(tab_app, text=t("settings.label.game_directory")).pack(anchor="w", pady=(5, 0))

        game_dir_row = tk.Frame(tab_app)
        game_dir_row.pack(fill=tk.X, pady=(3, 0))

        self.game_dir_entry = tk.Entry(game_dir_row, textvariable=self._temp_game_dir_var, state="readonly")
        self.game_dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.game_dir_reset_btn = ScrollingButton(game_dir_row, text=t("settings.button.default"), command=self._reset_game_dir, width=7)
        self.game_dir_reset_btn.pack(side=tk.RIGHT, padx=(4, 0))

        self.game_dir_browse_btn = ScrollingButton(game_dir_row, text=t("settings.button.browse"), command=self._browse_game_dir, width=8)
        self.game_dir_browse_btn.pack(side=tk.RIGHT, padx=(4, 0))

        limit_row = tk.Frame(tab_app)
        limit_row.pack(fill=tk.X, pady=(10, 0))

        tk.Label(limit_row, text=t("settings.label.download_limit")).pack(side=tk.LEFT)

        self.download_limit_spin = tk.Spinbox(
            limit_row,
            from_=0,
            to=_MAX_DOWNLOAD_LIMIT_KBPS,
            increment=256,
            width=9,
            justify="right",
            textvariable=self._temp_download_limit_var,
        )
        self.download_limit_spin.pack(side=tk.LEFT, padx=(6, 0))
        tk.Label(limit_row, text="KB/s").pack(side=tk.LEFT, padx=(3, 0))

        tk.Label(tab_language, text=t("settings.label.available_languages")).pack(anchor="w", pady=(0, 5))

        language_list_frame = tk.Frame(tab_language)
        language_list_frame.pack(fill=tk.BOTH, expand=True)

        language_scrollbar = ttk.Scrollbar(language_list_frame, orient=tk.VERTICAL)
        self.language_listbox = tk.Listbox(
            language_list_frame,
            height=8,
            exportselection=False,
            yscrollcommand=language_scrollbar.set,
        )
        language_scrollbar.configure(command=self.language_listbox.yview)
        self.language_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        language_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        tk.Label(tab_language, text=t("settings.label.language_restart")).pack(anchor="w", pady=(5, 0))

        self._language_codes = i18n.available()
        for language_code in self._language_codes:
            self.language_listbox.insert(tk.END, i18n.display_name(language_code))
        if self._temp_language_var.get() in self._language_codes:
            selected_index = self._language_codes.index(self._temp_language_var.get())
            self.language_listbox.selection_set(selected_index)
            self.language_listbox.activate(selected_index)

        def _on_language_selected(_event=None):
            selection = self.language_listbox.curselection()
            if selection:
                self._temp_language_var.set(self._language_codes[selection[0]])

        self.language_listbox.bind("<<ListboxSelect>>", _on_language_selected)

        self.discord_rpc_check = tk.Checkbutton(
            tab_privacy,
            text=t("settings.check.discord_rpc"),
            variable=self._temp_discord_rpc_var
        )
        self.discord_rpc_check.pack(anchor="w", pady=5)

        tk.Label(tab_java_memory, text=t("settings.label.ram_allocate")).pack(anchor="w")

        ram_row = tk.Frame(tab_java_memory)
        ram_row.pack(fill=tk.X, pady=3)

        self._ram_entry_var = tk.StringVar(value=str(self._temp_ram_var.get()))

        RAM_MIN = 512
        RAM_MAX = 16384
        RAM_STEP = 512
        RAM_MARKERS = (2048, 4096, 8192)

        def _on_scale(val):
            v = int(float(val))
            if v < RAM_MIN:
                self.ram_scale.set(RAM_MIN)
                return
            self._temp_ram_var.set(v)
            self._ram_entry_var.set(str(v))

        def _commit_entry(event=None):
            try:
                v = int(self._ram_entry_var.get())
            except ValueError:
                v = self._temp_ram_var.get()
            v = max(RAM_MIN, min(RAM_MAX, round(v / RAM_STEP) * RAM_STEP))
            self._temp_ram_var.set(v)
            self._ram_entry_var.set(str(v))
            self.ram_scale.set(v)

        self._commit_ram_entry = _commit_entry

        scale_col = tk.Frame(ram_row)
        scale_col.pack(side=tk.LEFT)

        self.ram_scale = tk.Scale(
            scale_col,
            from_=RAM_MIN,
            to=RAM_MAX,
            resolution=RAM_STEP,
            orient=tk.HORIZONTAL,
            showvalue=False,
            length=300,
            command=_on_scale,
        )
        self.ram_scale.set(self._temp_ram_var.get())
        self.ram_scale.pack()

        marks = tk.Canvas(scale_col, width=1, height=24, highlightthickness=0)
        marks.pack(fill=tk.X)

        def _draw_markers(event=None):
            if not self.ram_scale:
                return
            marks.delete("all")
            offset = self.ram_scale.winfo_rootx() - marks.winfo_rootx()
            for m in RAM_MARKERS:
                x = self.ram_scale.coords(m)[0] + offset
                marks.create_line(x, 0, x, 6)
                marks.create_text(x, 8, text=f"{m // 1024} GB", anchor="n", font=("TkDefaultFont", 8))

        self.ram_scale.pack(fill=tk.X)
        self.ram_scale.bind("<Configure>", _draw_markers)
        marks.bind("<Configure>", _draw_markers)

        self.ram_entry = tk.Entry(ram_row, textvariable=self._ram_entry_var, width=7, justify="right")
        self.ram_entry.pack(side=tk.LEFT, padx=(10, 0), anchor="n", pady=(4, 0))
        self.ram_entry.bind("<Return>", _commit_entry)
        self.ram_entry.bind("<FocusOut>", _commit_entry)

        tk.Label(ram_row, text="MB").pack(side=tk.LEFT, padx=(3, 0), anchor="n", pady=(4, 0))
        
        tk.Frame(tab_java_memory, height=2, bd=1, relief=tk.SUNKEN).pack(
            fill=tk.X, pady=(5, 10)
        )
        tk.Label(tab_java_memory, text=t("settings.label.java_soon"), fg="red").pack(
            anchor="center", pady=5
        )

        self._apply_widget_states()

        def _on_close():
            with contextlib.suppress(Exception):
                win.destroy()
            self.settings_window = None
            self.old_check = None
            self.repair_btn = None
            self.ram_scale = None
            self.ram_entry = None
            self._commit_ram_entry = None
            self.close_on_launch_check = None
            self.keep_open_check = None
            self.game_dir_entry = None
            self.game_dir_reset_btn = None
            self.game_dir_browse_btn = None
            self.download_limit_spin = None
            self.clear_cache_btn = None
            self.language_listbox = None

        win.protocol("WM_DELETE_WINDOW", _on_close)

    def _refresh_temp_vars(self):
        if not (getattr(self, "settings_window", None) and self.settings_window.winfo_exists()):
            return
        with contextlib.suppress(Exception):
            self._temp_ram_var.set(self.ram_var.get())
            self.ram_scale.set(self.ram_var.get())
            self._ram_entry_var.set(str(self.ram_var.get()))
            self._temp_show_old_var.set(self.show_old_var.get())
            self._temp_discord_rpc_var.set(self.discord_rpc_var.get())
            self._temp_keep_open_var.set(self.keep_open_var.get())
            self._temp_close_on_launch_var.set(self.close_on_launch_var.get())
            self._temp_game_dir_var.set(self.game_dir_var.get())
            self._temp_download_limit_var.set(str(self.download_limit_kbps))
            self._temp_language_var.set(self._language_setting)
            if self._temp_language_var.get() in self._language_codes:
                selected_index = self._language_codes.index(self._temp_language_var.get())
                self.language_listbox.selection_clear(0, tk.END)
                self.language_listbox.selection_set(selected_index)
                self.language_listbox.activate(selected_index)

    def load_settings(self):

        self.log("Loading settings...", "info")
        if not hasattr(self, "_language_setting"):
            self._language_setting = i18n.current

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
            self.close_on_launch_var.set(data.get("close_on_launch", False))
            self.game_dir_var.set(data.get("game_dir") or str(GAME_DIR))
            self.download_limit_kbps = self._parse_download_limit(data.get("download_limit_kbps", 0))
            language = data.get("language", "en_us")
            if language in i18n.available():
                self._language_setting = language

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
            "last_used_account": self.last_used_account,
            "close_on_launch": self.close_on_launch_var.get(),
            "game_dir": self.game_dir_var.get(),
            "download_limit_kbps": self.download_limit_kbps,
            "language": self._language_setting,
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
        self.close_on_launch_var.set(False)
        self.game_dir_var.set(str(GAME_DIR))
        self.download_limit_kbps = 0
        self._language_setting = "en_us"

        if SETTINGS_FILE.exists():
            SETTINGS_FILE.unlink()

        self.log("Settings reset to defaults!", "info")
        self._apply_discord_rpc()
        self.load_settings()
        self._refresh_temp_vars()

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
            new_close_on_launch = data.get("close_on_launch", False)
            new_game_dir = data.get("game_dir") or str(GAME_DIR)
            new_language = data.get("language", i18n.current)

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

            if self.close_on_launch_var.get() != new_close_on_launch:
                self.close_on_launch_var.set(new_close_on_launch)

            if self.game_dir_var.get() != new_game_dir:
                self.game_dir_var.set(new_game_dir)

            if new_language in i18n.available():
                self._language_setting = new_language
            if (
                getattr(self, "_temp_language_var", None)
                and getattr(self, "language_listbox", None)
                and getattr(self, "_language_codes", None) is not None
            ):
                self._temp_language_var.set(self._language_setting)
                if self._language_setting in self._language_codes:
                    selected_index = self._language_codes.index(self._language_setting)
                    self.language_listbox.selection_clear(0, tk.END)
                    self.language_listbox.selection_set(selected_index)
                    self.language_listbox.activate(selected_index)

            self.download_limit_kbps = self._parse_download_limit(
                data.get("download_limit_kbps", 0), fallback=self.download_limit_kbps
            )

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
        self.close_on_launch_var.set(self._temp_close_on_launch_var.get())
        self._apply_game_dir()

        self.download_limit_kbps = self._parse_download_limit(
            self._temp_download_limit_var.get(), fallback=self.download_limit_kbps
        )
        self._temp_download_limit_var.set(str(self.download_limit_kbps))

        selected_language = self._temp_language_var.get()
        if selected_language in i18n.available():
            self._language_setting = selected_language

    def _apply_discord_rpc(self):
        running = self.rpc.is_running()
        if self.discord_rpc_var.get() and not self.no_internet:
            if not running:
                self.rpc.start_rpc()
        elif running:
            self.rpc.stop_rpc()