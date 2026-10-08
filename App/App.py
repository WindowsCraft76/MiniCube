import contextlib
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
import webbrowser
import zipfile
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from tkinter import messagebox, ttk
import requests
from AccountManager import AccountManager
from Config import (
    API_AZUL_URL,
    ASSETS,
    ASSETS_DIR,
    CACHE_DIR,
    CONNECTIVITY_CHECK_INTERVAL_MS,
    DISCLAIMER_URL,
    DOWNLOADLAST_URL,
    GAME_DIR,
    HELP_INSTALLED_VERSION_URL,
    INDEXES_DIR,
    ISSUES_URL,
    JAVA_DIR,
    LIBRARIES_DIR,
    LIBRARIES_MC_URL,
    NATIVES_DIR,
    OBJECTS_DIR,
    PAGE_URL,
    PRIVACY_URL,
    RESSOURCE_MC_URL,
    SETTINGS_FILE,
    TERMS_URL,
    UPDATE_POPUP_MESSAGE_DEFAULT,
    UPDATE_POPUP_MESSAGES,
    USER_AGENT,
    VERSION_MANIFEST_URL,
    VERSIONS_DIR,
    copyright,
    TERMINAL_COLORS,
    TERMINAL_RESET,
)
from DiscordRPC import DiscordRPC
from MicrosoftAuth import MicrosoftAuth
from Network import is_online
from ProfileManager import ProfileManager
from SplashScreen import center_window
from VersionManager import (
    check_for_update,
    format_local_version_for_display,
    get_local_version_type,
    get_update_page_url,
    read_local_version,
)

_print_lock = threading.Lock()

class _AbortLaunch(Exception):
    pass

class App:
    def __init__(self, root, rpc=None, debug=None, instance_socket=None):
        self.root = root
        self.debug = debug

        self.log_window = None
        self.log_text_win = None
        self.log_buffer = []

        self.game_process = None
        self._playing_username = None
        self._game_stop_requested = False
        self._game_started_at = None
        self._game_status_after_id = None
        self._hidden_in_background = False
        self._instance_socket = instance_socket
        if self._instance_socket:
            threading.Thread(target=self._listen_for_instance_signal, daemon=True).start()

        self._ui_ready = False
        self._pending_update_version = None

        self.no_internet = not is_online()
        self._pending_no_internet_popup = False
        self._notifications = {}
        self._connectivity_after_id = None
        self.root.bind("<Map>", self._on_first_map, add="+")

        self.profile_var = tk.StringVar(value="vanilla")
        self.installed_profiles_map = {}

        local_raw_version = read_local_version()
        local_display = format_local_version_for_display(local_raw_version)
        local_version_type = get_local_version_type(local_raw_version)

        style = ttk.Style()
        style.theme_use('default')
        if debug:
            self.root.title("MiniCube - Debug Mode")
        else:
            self.root.title("MiniCube")
        self.root.geometry("330x270")
        self.root.resizable(False, False)
        self.root.iconbitmap(str(ASSETS / "icon" / "icon_64x64.ico"))

        self.toolbar = tk.Menu(root)
        menu = tk.Menu(self.toolbar, tearoff=0)
        menu.add_command(label="Show logs", command=self.toggle_logs_window)
        menu.add_command(label="Manage accounts", command=self.toggle_accounts_manager_window)
        menu.add_command(label="Settings", command=self.toggle_settings_window)
        menu.add_command(label="Open folder", command=self.open_folder)
        menu.add_separator()
        menu.add_command(label="Exit", command=self._on_close_request)
        self.toolbar.add_cascade(label="Menu", menu=menu)

        self.root.protocol("WM_DELETE_WINDOW", self._on_close_request)

        profile_menu = tk.Menu(self.toolbar, tearoff=0)
        self.profile_menu = profile_menu
        profile_menu.add_radiobutton(label="Vanilla", variable=self.profile_var, value="vanilla", command=self._on_profile_changed)
        profile_menu.add_radiobutton(label="Installed", variable=self.profile_var, value="installed", command=self._on_profile_changed)
        self.toolbar.add_cascade(label="Profile", menu=profile_menu)

        help = tk.Menu(self.toolbar, tearoff=0)
        help.add_command(
            label="About",
            command=lambda:
            messagebox.showinfo(
            "About",
            f"MiniCube\nCreated by WindowsCraft76\n\nVersion installed: {local_display} ({local_version_type})\nOperating system: {platform.platform()}\nPython version: {platform.python_version()} {platform.python_build()}\n\nThis is an open-source project under the MIT license.\nMiniCube is not affiliated with, endorsed by, or supported by Mojang Studios or Microsoft.\n\n{copyright}",
        ))
        help.add_command(label="Open page", command=lambda: webbrowser.open(PAGE_URL))
        help.add_separator()
        help.add_command(label="Terms of Service", command=lambda: webbrowser.open(f"{TERMS_URL}"))
        help.add_command(label="Privacy Policy", command=lambda: webbrowser.open(f"{PRIVACY_URL}"))
        help.add_command(label="Disclaimer", command=lambda: webbrowser.open(f"{DISCLAIMER_URL}"))
        help.add_separator()
        help.add_command(label="Report Issue", command=lambda: webbrowser.open(f"{ISSUES_URL}"))
        self.toolbar.add_cascade(label="Help", menu=help)

        self.UPDATE_LABEL = "New update available"
        self.NO_INTERNET_LABEL = "No internet"

        self.toolbar.add_command(label=" ", state="disabled")
        self._notif_anchor_index = self.toolbar.index("end")

        self.root.config(menu=self.toolbar)
        self.root.after(500, self._right_align_notifications)

        self.start_launch_sequence()

        if debug:
            self.log("Debug mode enabled!", "debug")

        self.rpc = rpc if rpc else DiscordRPC(self)
        if self.rpc.app is None:
            self.rpc.app = self

        self.username_var = tk.StringVar(value="Steve")
        self.version_var = tk.StringVar(value="Loading...")
        self.ram_var = tk.IntVar(value=2048)
        self.show_snapshots_var = tk.BooleanVar(value=False)
        self.show_old_var = tk.BooleanVar(value=False)
        self.discord_rpc_var = tk.BooleanVar(value=True)
        self.keep_open_var = tk.BooleanVar(value=True)

        self.download_thread = None
        self._cancel_event = threading.Event()
        self._ui_locked = False

        self._http = requests.Session()
        self._http.headers.update({"User-Agent": USER_AGENT})
        adapter = requests.adapters.HTTPAdapter(pool_connections=16, pool_maxsize=16, max_retries=2)
        self._http.mount("https://", adapter)
        self._http.mount("http://", adapter)

        self.account_manager = AccountManager(app=self)
        self.profile_manager = ProfileManager()
        self.profile_manager.ensure_file()
        self.selected_account_var = tk.StringVar()
        self.is_offline_var = tk.BooleanVar(value=False)
        self.default_account = None
        self.last_used_account = None

        self.load_settings()

        if self.discord_rpc_var.get() and not self.no_internet:
            self.rpc.start_rpc()

        self.log("Loading interface...", "info")

        self.account_frame = tk.Frame(root)
        self.account_frame.pack(pady=(5, 0))

        self.account_label = tk.Label(self.account_frame, text="Account:")
        self.account_menu = ttk.Combobox(
            self.account_frame,
            textvariable=self.selected_account_var,
            state="readonly"
        )
        self.account_menu.bind("<<ComboboxSelected>>", self._on_account_selected)

        self.offline_label = tk.Label(self.account_frame, text="Username:")
        self.offline_entry = tk.Entry(self.account_frame, textvariable=self.username_var)

        self.offline_check = tk.Checkbutton(
            root, 
            text="Use offline mode", 
            variable=self.is_offline_var, 
            command=self.toggle_account_mode
        )
        self.offline_check.pack(pady=(3, 15))

        self.refresh_accounts_ui()

        tk.Label(root, text="Version:").pack(pady=(0, 2))
        self.version_menu = ttk.Combobox(root, textvariable=self.version_var, state="disabled", width=25)
        self.version_menu.pack(pady=(0, 0))

        self.snapshot_check = tk.Checkbutton(root, text="Show snapshots", variable=self.show_snapshots_var, command=self.refresh_version_list)
        self.snapshot_check.pack(pady=(3, 0))
        self.snapshot_link = tk.Label(root, text="Don't know what to do? Click here!", fg="blue", cursor="hand2")
        self.snapshot_link.bind("<Button-1>", lambda _event: webbrowser.open(HELP_INSTALLED_VERSION_URL))

        self.launch_btn = tk.Button(root, text="Play", command=self._on_launch_button, width=15, anchor="center")
        self.launch_btn.pack(pady=(20, 0))

        self.progress_label = tk.Label(root, text="Waiting...")
        self.progress_label.pack(pady=(10, 0))

        self.version_manifest = {}

    def _listen_for_instance_signal(self):
        while True:
            try:
                conn, _ = self._instance_socket.accept()
            except OSError:
                return
            try:
                data = conn.recv(16)
                if data == b"SHOW":
                    self.root.after(0, self._restore_window)
            except Exception:
                pass
            finally:
                with contextlib.suppress(Exception):
                    conn.close()

    def _restore_window(self):
        try:
            self._hidden_in_background = False
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
            self.root.attributes("-topmost", True)
            self.root.after(200, lambda: self.root.attributes("-topmost", False))
        except Exception:
            pass

    def _minecraft_running(self):
        return self.game_process is not None and self.game_process.poll() is None

    def _on_close_request(self):
        if self._minecraft_running() and self.keep_open_var.get():
            self._hidden_in_background = True
            self.root.withdraw()
        else:
            self._shutdown_app()

    def _on_launch_button(self):
        if self._minecraft_running():
            self.stop_game()
            return
        self.save_settings()
        self.update_progress("Starting...")
        self.launch_game()

    def _cancel_or_stop(self):
        if self._minecraft_running():
            self.stop_game()
            return
        if self.download_thread and self.download_thread.is_alive():
            self._cancel_event.set()
            self.log("Cancellation requested!", "warn")
            self.update_progress("Canceling...")

    def stop_game(self):
        process = self.game_process
        if not process or process.poll() is not None:
            return
        self.log(f"Stop requested for Java process! (PID {process.pid})", "warn")
        self._game_stop_requested = True
        self.update_progress("Stopping game...")
        try:
            process.terminate()
        except OSError as error:
            self.log(f"Unable to stop Java process: {error}", "error")

    def _shutdown_app(self):
        with contextlib.suppress(Exception):
            self.save_settings()
        try:
            if self.rpc:
                self.rpc.stop_rpc()
        except Exception:
            pass
        try:
            if self._instance_socket:
                self._instance_socket.close()
        except Exception:
            pass
        if self.debug:
            print("Closing!")
        with contextlib.suppress(Exception):
            self.root.destroy()

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

    def _append_log_to_window(self, msg, kind="info"):
        if self.log_text_win:
            try:
                self.log_text_win.insert(tk.END, msg + "\n", kind)
                self.log_text_win.see(tk.END)
            except Exception:
                pass

    def log(self, msg, kind="info"):
        timestamped = f"[{time.strftime('%H:%M:%S')}] {msg}"
        if self.debug:
            with _print_lock:
                terminal_message = f"[{kind.upper()}] {timestamped}"
                if sys.stdout.isatty():
                    color = TERMINAL_COLORS.get(kind, TERMINAL_COLORS["info"])
                    terminal_message = f"{color}{terminal_message}{TERMINAL_RESET}"
                print(terminal_message)
        self.log_buffer.append((timestamped, kind))
        self.root.after(0, lambda: self._append_log_to_window(timestamped, kind))

    def toggle_logs_window(self):
        if self.log_window and self.log_window.winfo_exists():
            self.log_window.deiconify()
            self.log_window.lift()
            self.log_window.focus_force()
        else:
            self.log_window = tk.Toplevel(self.root)
            self.log_window.title("Logs")
            self.log_window.iconbitmap(str(ASSETS / "icon" / "icon_64x64.ico"))
            self.log_window.geometry("600x300")
            self.log_window.protocol("WM_DELETE_WINDOW", self._on_close_log_window)

            self.log_text_win = tk.Text(self.log_window, height=25, width=120, bg="black", fg="white")
            self.log_text_win.pack(fill=tk.BOTH, expand=True)

            self.log_text_win.tag_config("info", foreground="white")
            self.log_text_win.tag_config("success", foreground="green")
            self.log_text_win.tag_config("warn", foreground="orange")
            self.log_text_win.tag_config("error", foreground="red")
            self.log_text_win.tag_config("game", foreground="cyan")
            self.log_text_win.tag_config("debug", foreground="purple")

            for line, kind in self.log_buffer:
                try:
                    self.log_text_win.insert(tk.END, line + "\n", kind)
                except Exception:
                    self.log_text_win.insert(tk.END, line + "\n")
            self.log_text_win.see(tk.END)

    def _on_close_log_window(self):
        if self.log_window:
            with contextlib.suppress(Exception):
                self.log_window.destroy()
        self.log_window = None
        self.log_text_win = None

    def _on_account_selected(self, event=None):
        username = self.selected_account_var.get()
        if not username or username == "No account":
            return

        account_data = self.account_manager.get_account_by_name(username)
        if account_data and account_data.get("uuid"):
            self._update_account_prefs(last_used_account=account_data["uuid"])

    def toggle_accounts_manager_window(self):
        if getattr(self, "acc_win", None) and self.acc_win.winfo_exists():
            try:
                self.acc_win.deiconify()
                self.acc_win.lift()
                self.acc_win.focus_force()
            except Exception:
                pass
            return
        
        self.acc_win = tk.Toplevel(self.root)
        self.acc_win.title("Accounts Manager")
        self.acc_win.iconbitmap(str(ASSETS / "icon" / "icon_64x64.ico"))
        self.acc_win.resizable(False, False)
        center_window(self.acc_win, 300, 250)

        self.acc_list_container = tk.Frame(self.acc_win, relief=tk.SUNKEN, bd=1, bg="white")
        self.acc_list_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=1)

        self.acc_rows_frame = tk.Frame(self.acc_list_container, bg="white")
        self.acc_rows_frame.place(x=0, y=0, relwidth=1, relheight=1)

        self.acc_empty_label = tk.Label(
            self.acc_list_container,
            text="No account available",
            fg="gray"
        )

        self.acc_head_images = {}
        self.acc_row_widgets = {}
        self.selected_account_row = None

        btn_frame = tk.Frame(self.acc_win)
        btn_frame.pack(pady=10)

        self.add_account_btn = tk.Button(btn_frame, text="Add account", command=self.add_microsoft_account)
        self.add_account_btn.pack(side=tk.LEFT, padx=5)
        self._sync_online_widgets()

        self.refresh_account_listbox()

        self.acc_win.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        with contextlib.suppress(Exception):
            self.acc_win.destroy()
        self.acc_win = None

    def add_microsoft_account(self):
        if self.no_internet:
            messagebox.showwarning("Add account", "You are offline.\nAdding an account requires an internet connection.")
            return

        if hasattr(self, "add_account_btn"):
            self.add_account_btn.config(state="disabled")

        self._show_connecting_popup()

        def worker():
            ms_auth = MicrosoftAuth(app=self)
            account_data = ms_auth.login()
            self.root.after(0, lambda: self._on_login_finished(account_data))

        threading.Thread(target=worker, daemon=True).start()

    def _show_connecting_popup(self):
        self.connecting_win = tk.Toplevel(self.acc_win)
        self.connecting_win.title("Connecting...")
        self.connecting_win.resizable(False, False)
        with contextlib.suppress(Exception):
            self.connecting_win.iconbitmap(str(ASSETS / "icon" / "icon_64x64.ico"))
        center_window(self.connecting_win, 280, 90)
        self.connecting_win.transient(self.acc_win)
        self.connecting_win.protocol("WM_DELETE_WINDOW", lambda: None)

        tk.Label(
            self.connecting_win,
            text="Connecting to Microsoft...\nPlease continue in your browser.",
            justify="center",
            padx=15,
            pady=25
        ).pack()

        self.connecting_win.grab_set()

    def _on_login_finished(self, account_data):
        if getattr(self, "connecting_win", None) and self.connecting_win.winfo_exists():
            try:
                self.connecting_win.grab_release()
                self.connecting_win.destroy()
            except Exception:
                pass
        self.connecting_win = None

        if hasattr(self, "add_account_btn"):
            self.add_account_btn.config(state=self._online_only_state())

        if account_data:
            self.account_manager.add_account(account_data)
            self.refresh_account_listbox()
            self.refresh_accounts_ui()

    def refresh_accounts_ui(self):
        accounts = self.account_manager.get_all_accounts()

        if not accounts:
            self.account_menu['values'] = ["No account"]
            self.selected_account_var.set("No account")
            self.account_menu.config(state="disabled")
        else:
            names = [acc['username'] for acc in accounts]
            usernames_by_uuid = {acc.get('uuid'): acc['username'] for acc in accounts}
            self.account_menu['values'] = names

            if self.default_account in usernames_by_uuid:
                chosen = usernames_by_uuid[self.default_account]
            elif self.last_used_account in usernames_by_uuid:
                chosen = usernames_by_uuid[self.last_used_account]
            else:
                chosen = names[0]

            self.selected_account_var.set(chosen)
            self.account_menu.config(state="readonly")

        self.toggle_account_mode()

    def _get_head_photoimage(self, uuid, size=25):
        if not uuid:
            return None

        head_path = CACHE_DIR / f"{uuid}.png"
        if not head_path.exists():
            return None

        try:
            img = tk.PhotoImage(file=str(head_path))
            factor = max(1, img.width() // size)
            if factor > 1:
                img = img.subsample(factor, factor)
            return img
        except Exception:
            return None

    def _select_account_row(self, username):
        self.selected_account_row = username
        for uname, row in self.acc_row_widgets.items():
            color = "#cde6ff" if uname == username else "white"
            try:
                row.config(bg=color)
                for child in row.winfo_children():
                    child.config(bg=color)
            except Exception:
                pass

    def refresh_account_listbox(self):
        if not getattr(self, "acc_rows_frame", None):
            return

        try:
            if not self.acc_rows_frame.winfo_exists():
                return
        except tk.TclError:
            return

        for widget in self.acc_rows_frame.winfo_children():
            widget.destroy()
        self.acc_row_widgets = {}
        self.acc_head_images = {}

        accounts = self.account_manager.get_all_accounts()
        accounts = sorted(
            accounts,
            key=lambda acc: 0 if acc.get("uuid") == self.default_account else 1
        )

        if not accounts:
            self.acc_empty_label.place(relx=0.5, rely=0.5, anchor="center")
            self.selected_account_row = None
            return

        self.acc_empty_label.place_forget()

        for acc in accounts:
            username = acc.get("username")
            uuid = acc.get("uuid")

            row = tk.Frame(self.acc_rows_frame, height=40, cursor="hand2", bg="white")
            row.pack(fill=tk.X)
            row.pack_propagate(False)

            head_img = self._get_head_photoimage(uuid)
            if head_img is not None:
                self.acc_head_images[username] = head_img
                icon_label = tk.Label(row, image=head_img, bg="white")
            else:
                icon_label = tk.Label(row, width=4, bg="white")
            icon_label.pack(side=tk.LEFT, padx=(10, 4))

            options_btn = tk.Button(
                row, text="⋮", bg="white", relief=tk.FLAT,
                font=("Segoe UI", 12, "bold"), width=2,
                command=lambda u=username, uid=uuid: self._open_account_options_menu(u, uid)
            )
            options_btn.pack(side=tk.RIGHT, padx=(4, 10))

            star_label = tk.Label(
                row, text="★" if uuid == self.default_account else "",
                bg="white", fg="#f4b400", font=("Segoe UI", 12, "bold"), width=2
            )
            star_label.pack(side=tk.RIGHT)

            name_label = tk.Label(
                row, text=username, bg="white",
                font=("Segoe UI", 10), anchor="center"
            )
            name_label.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            for widget in (row, icon_label, name_label):
                widget.bind("<Button-1>", lambda e, u=username: self._select_account_row(u))

            self.acc_row_widgets[username] = row

        if self.selected_account_row in self.acc_row_widgets:
            self._select_account_row(self.selected_account_row)

    def _open_account_options_menu(self, username, uuid):
        self._select_account_row(username)
        is_default = (uuid == self.default_account)

        menu = tk.Menu(self.acc_win, tearoff=0)
        menu.add_command(
            label="Refresh token",
            state="disabled" if self.no_internet else "normal",
            command=lambda: self._refresh_selected_account_token(username),
        )
        if is_default:
            menu.add_command(label="Remove default account", command=lambda: self._unset_default_account(uuid))
        else:
            menu.add_command(label="Set as default account", command=lambda: self._set_default_account(uuid))
        menu.add_command(label="Delete account", command=lambda: self._delete_account(username))

        try:
            x = self.acc_win.winfo_pointerx()
            y = self.acc_win.winfo_pointery()
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _set_default_account(self, uuid):
        self._update_account_prefs(default_account=uuid)
        self.refresh_account_listbox()

    def _unset_default_account(self, uuid):
        if self.default_account == uuid:
            self._update_account_prefs(default_account=None)
        self.refresh_account_listbox()

    def _refresh_selected_account_token(self, username):
        if self.no_internet:
            messagebox.showwarning("Refresh token", "You are offline.\nRefreshing a token requires an internet connection.")
            return

        account_data = self.account_manager.get_account_by_name(username)
        if not account_data:
            return

        def worker():
            auth = MicrosoftAuth(app=self)
            refreshed = auth.refresh_token(account_data, force=True)

            def finish():
                if refreshed:
                    self.account_manager.update_account(refreshed)
                    if getattr(self, "acc_win", None) and self.acc_win.winfo_exists():
                        self.refresh_account_listbox()
                    self.refresh_accounts_ui()
                else:
                    messagebox.showerror(
                        "Authentication Error",
                        f"Failed to refresh token for {username}.\nPlease log in again."
                    )

            self.root.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def _delete_account(self, username):
        if self._minecraft_running() and username == self._playing_username:
            messagebox.showwarning(
                "Delete account",
                f"{username} is currently playing.\nStop the game before deleting this account."
            )
            return

        if not messagebox.askyesno("Delete account", f"Delete account {username}?"):
            return

        account_data = self.account_manager.get_account_by_name(username)
        uuid = account_data.get("uuid") if account_data else None

        self.account_manager.remove_account(username)
        if self.selected_account_row == username:
            self.selected_account_row = None

        updates = {}
        if uuid and self.default_account == uuid:
            updates["default_account"] = None
        if uuid and self.last_used_account == uuid:
            updates["last_used_account"] = None
        if updates:
            self._update_account_prefs(**updates)

        self.refresh_account_listbox()
        self.refresh_accounts_ui()

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

    def toggle_account_mode(self):
        has_official = len(self.account_manager.get_all_accounts()) > 0

        for widget in self.account_frame.winfo_children():
            widget.pack_forget()

        if self.is_offline_var.get():
            if not has_official:
                self.is_offline_var.set(False)
                self.toggle_account_mode()
                messagebox.showwarning(
                    "Warning",
                    "Connect at least one Microsoft account to unlock Offline mode."
                )
                return
            
            self.offline_label.pack(pady=(0, 2))
            self.offline_entry.pack(pady=(0, 0))
            self.log("Switching to offline mode.", "info")
        else:
            self.account_label.pack(pady=(0, 2))
            self.account_menu.pack(pady=(0, 0))
            self.log("Switching to online mode.", "info")

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


    def start_launch_sequence(self):
        threading.Thread(target=self._launch_sequence_worker, daemon=True).start()

    def _launch_sequence_worker(self):
        self.log("Starting up...", "info")

        if self.no_internet:
            self.log("No internet connection!", "warn")
            self.root.after(0, self._enter_offline_ui)
        else:
            self._run_online_tasks()

        self.root.after(0, self._schedule_connectivity_check)

        self.log("Startup checks complete.", "info")

    def _run_online_tasks(self, previous_version=None):
        def run_update_check():
            try:
                self.check_version_mismatch()
            except Exception as e:
                with contextlib.suppress(Exception):
                    self.log(f"Error checking for updates! ({e})", "error")

        def run_manifest_fetch():
            try:
                if self._fetch_version_manifest():
                    self.root.after(0, lambda: self._apply_version_list_keeping(previous_version))
                else:
                    self.root.after(0, lambda: self._set_version_list([], error=True))
            except Exception as e:
                with contextlib.suppress(Exception):
                    self.log(f"Error loading versions! ({e})", "error")
                self.root.after(0, lambda: self._set_version_list([], error=True))

        threads = [
            threading.Thread(target=run_update_check, daemon=True),
            threading.Thread(target=run_manifest_fetch, daemon=True),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    def _find_toolbar_index_by_label(self, label):
        try:
            end = self.toolbar.index("end")
            if end is None:
                return None
            for i in range(end + 1):
                try:
                    lbl = self.toolbar.entrycget(i, "label")
                    if lbl == label:
                        return i
                except Exception:
                    continue
        except Exception:
            return None
        return None

    def _on_first_map(self, event):
        if self._ui_ready:
            return
        self._ui_ready = True
        self.root.unbind("<Map>")
        self.root.after(50, self._right_align_notifications)
        if self._pending_no_internet_popup:
            self._pending_no_internet_popup = False
            self._show_no_internet_info()
        if self._pending_update_version:
            remote_version, remote_numeric, remote_type = self._pending_update_version
            self._pending_update_version = None
            self._show_update_popup(remote_version, remote_numeric, remote_type)

    def _add_update_toolbar_entry(self, remote_version, remote_numeric, remote_type):
        update_page_url = get_update_page_url()
        self._set_notification("update", self.UPDATE_LABEL, lambda: webbrowser.open(update_page_url))

        if self._ui_ready:
            self._show_update_popup(remote_version, remote_numeric, remote_type)
        else:
            self._pending_update_version = (remote_version, remote_numeric, remote_type)

    def _show_update_popup(self, remote_version, remote_numeric, remote_type):
        update_page_url = get_update_page_url()

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
            webbrowser.open(update_page_url)
            popup.destroy()

        def on_no():
            popup.destroy()

        tk.Button(btn_frame, text="Yes, open the download page", width=25, command=on_yes).pack(side="right", padx=(5, 25))
        tk.Button(btn_frame, text="No, later", width=15, command=on_no).pack(side="right", padx=(25, 5))

        popup.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (popup.winfo_width() // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (popup.winfo_height() // 2)
        popup.geometry(f"+{x}+{y}")

    def _remove_update_toolbar_entry(self):
        self._clear_notification("update")

    def _set_notification(self, key, label, command):
        self._notifications = {key: (label, command)}
        self._render_notifications()

    def _clear_notification(self, key):
        if key in self._notifications:
            self._notifications = {}
            self._render_notifications()

    def _render_notifications(self):
        with contextlib.suppress(Exception):
            end = self.toolbar.index("end")
            for i in range(end, self._notif_anchor_index, -1):
                self.toolbar.delete(i)
            for label, command in self._notifications.values():
                self.toolbar.add_command(label=label, command=command)
        self._right_align_notifications()
        self.root.after(250, self._right_align_notifications)

    def _right_align_notifications(self):
        if os.name != "nt":
            return
        job = getattr(self, "_align_after_id", None)
        if job is not None:
            with contextlib.suppress(Exception):
                self.root.after_cancel(job)
        self._align_after_id = self.root.after(60, self._apply_right_align)

    def _resolve_root_hwnd(self):
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        GA_ROOT = 2
        user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        user32.GetAncestor.restype = wintypes.HWND
        user32.GetMenu.argtypes = [wintypes.HWND]
        user32.GetMenu.restype = wintypes.HMENU

        candidates = []
        with contextlib.suppress(Exception):
            frame = self.root.wm_frame()
            if frame:
                candidates.append(int(frame, 16))
        with contextlib.suppress(Exception):
            candidates.append(user32.GetAncestor(self.root.winfo_id(), GA_ROOT))

        for hwnd in candidates:
            if hwnd and user32.GetMenu(hwnd):
                return hwnd
        return candidates[0] if candidates else 0

    def _apply_right_align(self):
        self._align_after_id = None
        try:
            import ctypes
            from ctypes import wintypes

            class MENUITEMINFOW(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.UINT), ("fMask", wintypes.UINT),
                    ("fType", wintypes.UINT), ("fState", wintypes.UINT),
                    ("wID", wintypes.UINT), ("hSubMenu", wintypes.HMENU),
                    ("hbmpChecked", wintypes.HBITMAP), ("hbmpUnchecked", wintypes.HBITMAP),
                    ("dwItemData", ctypes.c_size_t), ("dwTypeData", wintypes.LPWSTR),
                    ("cch", wintypes.UINT), ("hbmpItem", wintypes.HBITMAP),
                ]

            user32 = ctypes.windll.user32
            user32.GetMenu.argtypes = [wintypes.HWND]
            user32.GetMenu.restype = wintypes.HMENU
            user32.GetMenuItemCount.argtypes = [wintypes.HMENU]
            user32.GetMenuItemInfoW.argtypes = [wintypes.HMENU, wintypes.UINT, wintypes.BOOL, ctypes.POINTER(MENUITEMINFOW)]
            user32.SetMenuItemInfoW.argtypes = [wintypes.HMENU, wintypes.UINT, wintypes.BOOL, ctypes.POINTER(MENUITEMINFOW)]
            user32.DrawMenuBar.argtypes = [wintypes.HWND]

            hwnd = self._resolve_root_hwnd()
            if not hwnd:
                if self.debug:
                    self.log("Notification align: no window handle found.", "debug")
                return
            hmenu = user32.GetMenu(hwnd)
            if not hmenu:
                if self.debug:
                    self.log("Notification align: GetMenu returned no native menu.", "debug")
                return

            MIIM_FTYPE = 0x00000100
            MFT_RIGHTJUSTIFY = 0x00004000
            item_count = user32.GetMenuItemCount(hmenu)
            if item_count <= self._notif_anchor_index:
                return

            applied = 0
            for pos in range(self._notif_anchor_index, item_count):
                info = MENUITEMINFOW()
                info.cbSize = ctypes.sizeof(MENUITEMINFOW)
                info.fMask = MIIM_FTYPE
                if not user32.GetMenuItemInfoW(hmenu, pos, True, ctypes.byref(info)):
                    continue
                info.fType |= MFT_RIGHTJUSTIFY
                if user32.SetMenuItemInfoW(hmenu, pos, True, ctypes.byref(info)):
                    applied += 1
            user32.DrawMenuBar(hwnd)
            if self.debug:
                self.log(f"Notification align: flagged {applied}/{item_count - self._notif_anchor_index} item(s).", "debug")
        except Exception as e:
            if self.debug:
                self.log(f"Notification align failed: {e}", "debug")

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

    def _apply_version_list_keeping(self, previous_version=None):
        if self.no_internet:
            return
        if previous_version is not None and (self._is_installed_profile() or self._ui_locked):
            return
        self._apply_version_list_to_ui()
        if previous_version and previous_version in self.version_menu["values"]:
            self.version_var.set(previous_version)

    def _apply_offline_vanilla_list(self):
        try:
            profiles = self.profile_manager.get_all_profiles()
        except Exception as e:
            self.log(f"Error loading profiles! {e}", "error")
            self._set_version_list([], error=True)
            return

        entries = [
            (profile.get("lastUsed", ""), profile.get("lastVersionId", key))
            for key, profile in profiles.items()
            if profile.get("type") == "vanilla"
        ]
        entries.sort(reverse=True)
        self._set_version_list([version_id for _, version_id in entries])

    _VERSION_PLACEHOLDERS = ("Loading...", "No version found", "Error")

    def _on_profile_changed(self):
        self._sync_snapshot_check_state()
        self.refresh_version_list()

    def _sync_snapshot_check_state(self):
        if self.profile_var.get() == "installed":
            self.snapshot_check.pack_forget()
            self.snapshot_link.pack(before=self.launch_btn, pady=(3, 0))
        else:
            self.snapshot_link.pack_forget()
            if not self.snapshot_check.winfo_ismapped():
                self.snapshot_check.pack(before=self.launch_btn, pady=(3, 0))
            self.snapshot_check.config(state="disabled" if (self._ui_locked or self.no_internet) else "normal")

    def _sync_version_menu_state(self):
        if self.version_var.get() in self._VERSION_PLACEHOLDERS:
            self.version_menu.config(state="disabled")
        else:
            self.version_menu.config(state="disabled" if self._ui_locked else "readonly")

    @staticmethod
    def _is_valid_jar(path):
        return path.is_file() and path.stat().st_size > 0 and zipfile.is_zipfile(path)

    @staticmethod
    def _has_sha1(path, expected_hash):
        if not path.is_file() or path.stat().st_size == 0:
            return False
        digest = hashlib.sha1()
        with open(path, "rb") as data_file:
            for chunk in iter(lambda: data_file.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest() == expected_hash

    def _load_json_file(self, path, url=None, expected_hash=None, force=False, announce_download=True):
        valid = path.is_file() and not force
        if valid and expected_hash:
            valid = self._has_sha1(path, expected_hash)
        if valid:
            try:
                with open(path, encoding="utf-8") as data_file:
                    data = json.load(data_file)
                self.log(f"{path.name} already present.", "info")
                return data
            except (OSError, json.JSONDecodeError):
                valid = False

        if not url:
            raise ValueError(f"Invalid JSON file: {path}")
        self._download_file(url, path)
        with open(path, encoding="utf-8") as data_file:
            data = json.load(data_file)
        if expected_hash and not self._has_sha1(path, expected_hash):
            path.unlink(missing_ok=True)
            raise ValueError(f"SHA-1 mismatch for JSON file: {path}")
        if announce_download:
            self.log(f"Downloaded {path.name}", "success")
        return data

    def _set_version_list(self, values, error=False):
        self.version_menu["values"] = values
        if values and not error:
            self.version_var.set(values[0])
        elif not error:
            self.version_var.set("No version found")
        else:
            self.version_var.set("Error")
        self._sync_version_menu_state()

    def refresh_version_list(self):
        if self.profile_var.get() == "installed":
            self._apply_installed_version_list()
            return

        if self.no_internet:
            self._apply_offline_vanilla_list()
            return

        if self._fetch_version_manifest():
            self._apply_version_list_to_ui()
        else:
            self._set_version_list([], error=True)

    def _apply_installed_version_list(self):
        try:
            profiles = self.profile_manager.get_all_profiles()
        except Exception as e:
            self.log(f"Error loading installed profiles! {e}", "error")
            self._set_version_list([], error=True)
            return

        self.installed_profiles_map = {
            profile.get("lastVersionId", key): profile.get("lastVersionId", key)
            for key, profile in profiles.items()
            if profile.get("type") == "custom"
        }

        self._set_version_list(list(self.installed_profiles_map.keys()))

    def _get_selected_version_id(self):
        if self.profile_var.get() == "installed":
            return self.installed_profiles_map.get(self.version_var.get())
        return self.version_var.get()

    def _fetch_version_manifest(self) -> bool:
        if self.no_internet:
            self.log("Offline: version manifest not fetched.", "warn")
            return False

        self.log("Fetching version manifest...", "info")

        try:
            self._urlretrieve(VERSION_MANIFEST_URL, VERSIONS_DIR / "version_manifest.json")
            with open(VERSIONS_DIR / "version_manifest.json", encoding="utf-8") as f:
                self.version_manifest = json.load(f)
            self.log(f"Version manifest fetched successfully! ({len(self.version_manifest.get('versions', []))} versions available)", "success")
            return True
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", "Unable to fetch manifest! See logs for details."))
            self.log(f"Error fetching version manifest! {e}", "error")
            return False

    def _apply_version_list_to_ui(self):
        items = []
        for v in self.version_manifest.get("versions", []):
            vtype = v.get("type", "")
            if (
                vtype == "release"
                or (vtype == "snapshot" and self.show_snapshots_var.get())
                or (vtype in ("old_alpha", "old_beta") and self.show_old_var.get())
            ):
                items.append(v)

        items.sort(key=lambda v: v["releaseTime"], reverse=True)
        version_ids = [v["id"] for v in items]

        self._set_version_list(version_ids)

    def open_folder(self):
        folder_path = GAME_DIR
        if os.name == "nt":
            os.startfile(folder_path)

    def get_required_java_version(self, version_data):

        java_info = version_data.get("javaVersion")
        if not java_info:
            return 8
        return java_info.get("majorVersion", 8)

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

    def prepare_version(self, version_id, force=False):
        self.log(f"Preparing to repair Minecraft {version_id}..." if force else f"Preparing Minecraft {version_id}...", "info")
        self.update_progress("Repairing..." if force else "Preparing...")
        self.log(f"Downloading Minecraft {self.version_var.get()} files...", "info")

        version_info = next(v for v in self.version_manifest["versions"] if v["id"] == version_id)
        version_dir = VERSIONS_DIR / version_id
        version_dir.mkdir(parents=True, exist_ok=True)

        version_json_path = version_dir / f"{version_id}.json"
        version_jar_path = version_dir / f"{version_id}.jar"

        version_data = self._load_json_file(
            version_json_path,
            version_info["url"],
            version_info.get("sha1"),
            force=force,
        )
        version_data = self._resolve_version_data(version_id, version_data)

        if force or not self._is_valid_jar(version_jar_path):
            self._download_version_jar(version_id, version_data, version_jar_path)
        else:
            self.log(f"{version_id}.jar already present.", "info")

        asset_index_id = version_data["assetIndex"]["id"]
        asset_index_url = version_data["assetIndex"]["url"]
        asset_index_path = INDEXES_DIR / f"{asset_index_id}.json"
        asset_index = self._load_json_file(
            asset_index_path,
            asset_index_url,
            version_data["assetIndex"].get("sha1"),
            force=force,
        )
        objects = asset_index.get("objects", {})

        if not self._download_version_files(version_data, objects, force=force):
            return None, None

        return version_data, version_jar_path

    def _download_batch(self, label, items):
        if not items:
            self.log(f"No {label} to download. (already present)", "info")
            return True

        total = len(items)
        self.log(f"Downloading {total} {label}{'s' if total != 1 and not label.endswith('s') else ''}...", "info")
        self.update_progress(f"Downloading {label}s...")

        done = 0
        errors = []
        progress_lock = threading.Lock()
        start_time = time.time()

        def download_one(item):
            path, url = item
            if self._cancel_event.is_set():
                return
            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                self._download_file(url, path)
                self.log(f"Downloaded {label}: {path.name}", "success")
            except Exception as e:
                self.log(f"Error downloading {url}: {e}", "error")
                with progress_lock:
                    errors.append(url)
                return

            nonlocal done
            with progress_lock:
                done += 1
                elapsed = time.time() - start_time
                speed = done / elapsed if elapsed > 0 else 0
                remaining = (total - done) / speed if speed > 0 else 0
                remaining_str = self.format_duration(remaining)
                self.update_progress(f"Downloading {label}s: {done}/{total} ({remaining_str} left)")

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(download_one, item) for item in items]
            for _ in as_completed(futures):
                pass

        if self._cancel_event.is_set():
            self.log("Download canceled by user.", "info")
            self.update_progress("Download canceled")
            return False

        if errors:
            self.log(f"{len(errors)} {label}(s) failed to download, see above for details.", "error")
            self.update_progress(f"{len(errors)} {label}(s) failed to download!")
            return False

        elapsed_str = self.format_duration(time.time() - start_time)
        self.log(f"Downloaded {total} {label}{'s' if total != 1 else ''} in {elapsed_str}.", "success")
        return True

    def _download_version_files(self, version_data, objects, force=False):
        missing_libs = []
        for path, url in self._iter_library_artifacts(version_data):
            if not url:
                continue
            lib_path = LIBRARIES_DIR / path
            if force or not (lib_path.is_file() and lib_path.stat().st_size > 0):
                missing_libs.append((lib_path, url))

        missing_assets = []
        for obj in objects.values():
            hash_val = obj["hash"]
            subdir = hash_val[:2]
            url = f"{RESSOURCE_MC_URL}/{subdir}/{hash_val}"
            obj_path = OBJECTS_DIR / subdir / hash_val
            if force or not (obj_path.is_file() and obj_path.stat().st_size > 0):
                missing_assets.append((obj_path, url))

        self.log("Checking libraries and assets...", "info")
        self.log(
            f"Verification complete! ({len(missing_libs)} libraries and {len(missing_assets)} assets to download)",
            "info"
        )

        return (
            self._download_batch("library", missing_libs)
            and self._download_batch("asset", missing_assets)
        )

    def _fetch_json(self, url):
        if self._cancel_event.is_set():
            raise _AbortLaunch()
        response = self._http.get(url, timeout=30)
        response.raise_for_status()
        if self._cancel_event.is_set():
            raise _AbortLaunch()
        return response.json()

    def _urlretrieve(self, url, dest_path):
        with self._http.get(url, stream=True, timeout=30) as response:
            response.raise_for_status()
            with open(dest_path, "wb") as out_file:
                for chunk in response.iter_content(chunk_size=131072):
                    if self._cancel_event.is_set():
                        raise _AbortLaunch()
                    if chunk:
                        out_file.write(chunk)

    def _download_file(self, url, path):
        if self._cancel_event.is_set():
            raise _AbortLaunch()
        temp_path = path.with_name(f"{path.name}.part")
        temp_path.unlink(missing_ok=True)
        try:
            self._urlretrieve(url, temp_path)
            if not temp_path.is_file() or temp_path.stat().st_size == 0:
                raise OSError(f"Downloaded file is empty: {url}")
            temp_path.replace(path)
        finally:
            temp_path.unlink(missing_ok=True)

    def _download_version_jar(self, version_id, version_data, version_jar_path, allow_library_fallback=True):
        client = version_data.get("downloads", {}).get("client")
        if client and client.get("url"):
            self._download_file(client["url"], version_jar_path)
            self.log(f"Downloaded {version_id}.jar", "success")
            return

        if not allow_library_fallback:
            raise FileNotFoundError(f"No client JAR download URL found in {version_id}.json")

        for relative_path, url in self._iter_library_artifacts(version_data):
            if not url:
                continue
            artifact_name = Path(relative_path).stem
            if version_id.lower() in artifact_name.lower() or "loader" in artifact_name.lower():
                self._download_file(url, version_jar_path)
                self.log(f"Downloaded {version_id}.jar from mod loader artifact", "success")
                return

        raise FileNotFoundError(f"No client or mod loader JAR found for {version_id}")

    def _resolve_version_data(self, version_id, version_data, _seen=None):
        parent_id = version_data.get("inheritsFrom")
        if not parent_id:
            return version_data

        _seen = _seen or set()
        if parent_id in _seen:
            return version_data
        _seen.add(version_id)

        parent_json_path = VERSIONS_DIR / parent_id / f"{parent_id}.json"
        version_info = next(
            (v for v in self.version_manifest.get("versions", []) if v["id"] == parent_id),
            None
        )
        if version_info is None:
            raise FileNotFoundError(f"Parent version {parent_id} not found locally or in the manifest")
        parent_json_path.parent.mkdir(parents=True, exist_ok=True)
        parent_data = self._load_json_file(
            parent_json_path,
            version_info["url"],
            version_info.get("sha1"),
        )
        parent_data = self._resolve_version_data(parent_id, parent_data, _seen)

        merged = dict(parent_data)
        merged.update({k: v for k, v in version_data.items() if k not in ("libraries", "arguments")})
        merged["libraries"] = version_data.get("libraries", []) + parent_data.get("libraries", [])

        parent_args = parent_data.get("arguments")
        child_args = version_data.get("arguments")
        if parent_args or child_args:
            parent_args = parent_args or {}
            child_args = child_args or {}
            merged["arguments"] = {
                "game": parent_args.get("game", []) + child_args.get("game", []),
                "jvm": parent_args.get("jvm", []) + child_args.get("jvm", []),
            }
        return merged

    def load_local_version_data(self, version_id, force=False, check_dependencies=True):
        version_dir = VERSIONS_DIR / version_id
        version_json_path = version_dir / f"{version_id}.json"
        version_jar_path = version_dir / f"{version_id}.jar"

        if not check_dependencies and not force and version_json_path.is_file() and version_jar_path.is_file():
            try:
                with open(version_json_path, encoding="utf-8") as data_file:
                    local_version_data = json.load(data_file)
                parent_paths = []
                version_data = self._resolve_local_version_data(
                    version_id, local_version_data, existing_parent_paths=parent_paths
                )
                asset_index = version_data.get("assetIndex", {})
                asset_index_id = asset_index["id"]
                asset_index_path = INDEXES_DIR / f"{asset_index_id}.json"
                asset_index_valid = asset_index_path.is_file()
                if asset_index_valid and asset_index.get("sha1"):
                    asset_index_valid = self._has_sha1(asset_index_path, asset_index["sha1"])
                if asset_index_valid:
                    with open(asset_index_path, encoding="utf-8") as asset_file:
                        json.load(asset_file)
                    for parent_path in parent_paths:
                        self.log(f"{parent_path.name} already present.", "info")
                    self.log(f"{version_id}.json already present.", "info")
                    self.log(f"{version_id}.jar already present.", "info")
                    self.log(f"{asset_index_path.name} already present.", "info")
                    return version_data, version_jar_path
            except (OSError, json.JSONDecodeError, KeyError, TypeError):
                pass

        version_dir.mkdir(parents=True, exist_ok=True)

        version_url = None
        version_sha1 = None
        version_info = next(
            (v for v in self.version_manifest.get("versions", []) if v["id"] == version_id),
            None
        )
        if version_info is None:
            if not version_json_path.is_file():
                raise FileNotFoundError(f"Version {version_id} not found in the manifest")
        else:
            version_url = version_info["url"]
            version_sha1 = version_info.get("sha1")

        local_version_data = self._load_json_file(
            version_json_path,
            version_url,
            version_sha1,
            force=force and version_url is not None,
        )
        version_data = self._resolve_version_data(version_id, local_version_data)

        if force or not self._is_valid_jar(version_jar_path):
            is_installed_profile = self._is_installed_profile()
            self._download_version_jar(
                version_id,
                version_data,
                version_jar_path,
                allow_library_fallback=not is_installed_profile,
            )
        else:
            self.log(f"{version_id}.jar already present.", "info")

        if not self._is_valid_jar(version_jar_path):
            raise OSError(f"Invalid or empty version JAR: {version_jar_path}")

        asset_index_id = version_data["assetIndex"]["id"]
        asset_index_url = version_data["assetIndex"]["url"]
        asset_index_path = INDEXES_DIR / f"{asset_index_id}.json"
        asset_index = self._load_json_file(
            asset_index_path,
            asset_index_url,
            version_data["assetIndex"].get("sha1"),
            force=force,
        )
        objects = asset_index.get("objects", {})

        if not self._download_version_files(version_data, objects, force=force):
            raise _AbortLaunch()

        return version_data, version_jar_path

    def _resolve_local_version_data(
        self, version_id, version_data, _seen=None, existing_parent_paths=None
    ):
        parent_id = version_data.get("inheritsFrom")
        if not parent_id:
            return version_data

        _seen = _seen or set()
        if parent_id in _seen:
            return version_data
        _seen.add(version_id)

        parent_path = VERSIONS_DIR / parent_id / f"{parent_id}.json"
        if parent_path.is_file() and existing_parent_paths is not None:
            existing_parent_paths.append(parent_path)
        with open(parent_path, encoding="utf-8") as data_file:
            parent_data = json.load(data_file)
        parent_data = self._resolve_local_version_data(
            parent_id, parent_data, _seen, existing_parent_paths
        )

        merged = dict(parent_data)
        merged.update({k: v for k, v in version_data.items() if k not in ("libraries", "arguments")})
        merged["libraries"] = version_data.get("libraries", []) + parent_data.get("libraries", [])

        parent_args = parent_data.get("arguments")
        child_args = version_data.get("arguments")
        if parent_args or child_args:
            parent_args = parent_args or {}
            child_args = child_args or {}
            merged["arguments"] = {
                "game": parent_args.get("game", []) + child_args.get("game", []),
                "jvm": parent_args.get("jvm", []) + child_args.get("jvm", []),
            }
        return merged

    def _maven_name_to_path(self, name, extension="jar"):
        parts = name.split(":")
        if len(parts) < 3:
            return None
        group, artifact, version = parts[0], parts[1], parts[2]
        filename = f"{artifact}-{version}"
        if len(parts) > 3:
            filename += f"-{parts[3]}"
        filename += f".{extension}"
        return f"{group.replace('.', '/')}/{artifact}/{version}/{filename}"

    def _iter_library_artifacts(self, version_data):
        for lib in version_data.get("libraries", []):
            if not self._rules_allow(lib.get("rules")):
                continue

            downloads = lib.get("downloads")
            if downloads:
                artifact = downloads.get("artifact")
                if artifact:
                    yield artifact["path"], artifact.get("url")
                for classifier in downloads.get("classifiers", {}).values():
                    yield classifier["path"], classifier.get("url")
                continue

            name = lib.get("name")
            if not name:
                continue
            relative_path = self._maven_name_to_path(name)
            if not relative_path:
                continue
            base_url = lib.get("url") or LIBRARIES_MC_URL
            if not base_url.endswith("/"):
                base_url += "/"
            yield relative_path, base_url + relative_path

    def _missing_libraries(self, version_data):
        return [
            path for path, _ in self._iter_library_artifacts(version_data)
            if not self._is_valid_jar(LIBRARIES_DIR / path)
        ]

    def _show_error_and_wait(self, title, message):
        closed = threading.Event()

        def show():
            try:
                messagebox.showerror(title, message)
            finally:
                closed.set()

        self.root.after(0, show)
        closed.wait()

    def _is_installed_profile(self):
        return self.profile_var.get() == "installed"

    def _get_version_ready_offline(self, version_id):
        self.log(f"Offline: checking version files for {version_id}...", "info")
        version_dir = VERSIONS_DIR / version_id
        json_path = version_dir / f"{version_id}.json"
        jar_path = version_dir / f"{version_id}.jar"

        missing = []
        version_data = None

        if not json_path.is_file():
            missing.append(json_path.name)
        if not self._is_valid_jar(jar_path):
            missing.append(jar_path.name)

        if not missing:
            try:
                with open(json_path, encoding="utf-8") as data_file:
                    local_data = json.load(data_file)
                version_data = self._resolve_local_version_data(version_id, local_data)
            except (OSError, json.JSONDecodeError) as e:
                self.log(f"Unreadable version file: {e}", "error")
                missing.append(json_path.name)

        if version_data is not None:
            asset_id = version_data.get("assetIndex", {}).get("id")
            index_path = INDEXES_DIR / f"{asset_id}.json" if asset_id else None
            if index_path is None or not index_path.is_file():
                missing.append(index_path.name if index_path else "asset index")

        if missing:
            for name in missing:
                self.log(f"Missing file for {version_id}: {name}", "error")
            shown = "\n".join(f"- {name}" for name in missing[:8])
            if len(missing) > 8:
                shown += f"\n- ... and {len(missing) - 8} more"
            self._show_error_and_wait(
                "Missing version files",
                f"{version_id} cannot be launched offline, some files are missing:\n\n{shown}\n\n"
                "Go back online and restart MiniCube to download or repair them."
            )
            raise _AbortLaunch()

        self.log(f"All files for {version_id} are present.", "success")
        self.profile_manager.create_or_update(
            version_id,
            profile_type="custom" if self._is_installed_profile() else "vanilla",
        )
        return version_data, jar_path

    def _get_version_ready(self, version_id, force=False):
        if self.no_internet:
            return self._get_version_ready_offline(version_id)

        is_installed_profile = self._is_installed_profile()

        if is_installed_profile:
            has_installed_profile = not force and self.profile_manager.has_profile(version_id)
            if has_installed_profile:
                self.log(f"Profile {version_id} found, checking files...", "info")
            else:
                self.log(f"Initializing installed version {version_id}...", "info")

            version_dir = VERSIONS_DIR / version_id
            required_files = [version_dir / f"{version_id}.json"]
            if has_installed_profile:
                required_files.append(version_dir / f"{version_id}.jar")
            missing_files = [path.name for path in required_files if not path.is_file()]
            if missing_files:
                for name in missing_files:
                    self.log(f"Missing installed version file: {version_dir / name}", "error")
                self._show_error_and_wait(
                    "Installed version missing files",
                    f"The version {version_id} is incomplete! Please reinstall.\n\n"
                    "The profile for this version will be deleted, but this does not affect your save files!"
                )
                self.profile_manager.remove_profile(version_id)
                self.log(f"Profile {version_id} removed!", "warn")
                self.root.after(0, self._apply_installed_version_list)
                raise _AbortLaunch()

            version_data, version_jar_path = self.load_local_version_data(
                version_id, force=force, check_dependencies=False
            )
            self.log(f"Refreshing profile for {version_id}...", "info")
            self.profile_manager.create_or_update(version_id, profile_type="custom")
            return version_data, version_jar_path

        if not force and self.profile_manager.has_profile(version_id):
            self.log(f"Profile {version_id} found, checking files...", "info")
            version_data, version_jar_path = self.load_local_version_data(
                version_id, check_dependencies=False
            )
            self.log(f"Refreshing profile for {version_id}...", "info")
            self.profile_manager.create_or_update(version_id)
            return version_data, version_jar_path

        version_data, version_jar_path = self.prepare_version(version_id, force=force)

        if version_data is None:
            raise _AbortLaunch()

        missing = self._missing_libraries(version_data)
        if missing:
            raise FileNotFoundError(f"{len(missing)} missing librar{'y' if len(missing) == 1 else 'ies'}")

        self.log(f"Creating profile for {version_id}...", "info")
        self.profile_manager.create_or_update(version_id)

        return version_data, version_jar_path

    def _find_local_java(self, major_version: int):
        for item in JAVA_DIR.iterdir():
            if not item.is_dir():
                continue

            name = item.name.lower()
            if (
                not name.startswith(f"zulu{major_version}")
                or not any(
                    architecture in name
                    for architecture in ("-x64", "_x64", "-amd64", "_amd64")
                )
                or "aarch64" in name
                or "arm64" in name
            ):
                continue

            javaw = item / "bin" / "javaw.exe"
            if javaw.exists():
                return javaw
        return None

    def ensure_java_installed(self, major_version: int):
        java_architecture = "x64"

        javaw = self._find_local_java(major_version)
        if javaw:
            self.log(f"Java {major_version} already present", "info")
            return javaw

        self.log(f"Downloading Java {major_version}...", "info")
        self.update_progress("Downloading Java...")

        api_url = (
            f"{API_AZUL_URL}/metadata/v1/zulu/packages/"
            f"?java_version={major_version}"
            "&os=windows"
            f"&arch={java_architecture}"
            "&java_package_type=jre"
            "&javafx_bundled=false"
        )

        packages = self._fetch_json(api_url)

        if not packages:
            raise RuntimeError(f"No Java package found for Java {major_version}")

        pkg = packages[0]
        download_url = pkg["download_url"]
        zip_name = Path(download_url).name
        zip_path = JAVA_DIR / zip_name

        self.log(f"Downloading {zip_name}...", "info")
        self._urlretrieve(download_url, zip_path)
        self.log(f"Downloaded {zip_name}", "success")

        self.update_progress("Extracting Java...")
        self.log(f"Extracting Java {major_version}...", "info")
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(JAVA_DIR)

        zip_path.unlink(missing_ok=True)

        javaw = self._find_local_java(major_version)
        if javaw:
            self.log(f"Java {major_version} installed successfully!", "success")
            self.update_progress("Java installed!")
            return javaw

        raise RuntimeError(f"No Java package found for Java {major_version}")

    def _current_os_name(self):
        system = platform.system().lower()
        if system.startswith("win"):
            return "windows"
        if system.startswith("linux"):
            return "linux"
        if system.startswith("darwin"):
            return "osx"
        raise RuntimeError(f"Unsupported OS: {system}")

    def _rules_allow(self, rules):
        if not rules:
            return True
        allowed = False
        for rule in rules:
            if rule.get("features"):
                continue
            action_allow = rule.get("action", "allow") == "allow"
            os_rule = rule.get("os")
            if os_rule:
                name = os_rule.get("name")
                if name and name != self._current_os_name():
                    continue
                arch = os_rule.get("arch")
                if arch and arch not in (platform.machine().lower(), platform.machine()):
                    continue
            allowed = action_allow
        return allowed

    def extract_natives(self, version_data):

        version_id = version_data["id"]
        natives_dir = NATIVES_DIR / version_id

        os_name = self._current_os_name()

        self.log(f"Extracting natives for {version_id}...", "info")
        self.update_progress("Extracting natives...")

        extracted_count = 0
        for lib in version_data.get("libraries", []):
            natives = lib.get("natives")
            downloads = lib.get("downloads")

            if not natives or not downloads:
                continue

            classifier_key = natives.get(os_name)
            if not classifier_key:
                continue

            classifiers = downloads.get("classifiers", {})
            native_info = classifiers.get(classifier_key)
            if not native_info:
                continue

            jar_path = LIBRARIES_DIR / native_info["path"]
            if not jar_path.exists():
                self.log(f"Missing native jar: {jar_path}", "error")
                continue

            try:
                with zipfile.ZipFile(jar_path, "r") as z:
                    for member in z.namelist():
                        if member.startswith("META-INF/"):
                            continue
                        z.extract(member, natives_dir)
                extracted_count += 1
            except Exception as e:
                self.log(f"Failed to extract natives from {jar_path}: {e}", "error")

        if extracted_count:
            self.log(f"Natives successfully extracted! ({extracted_count} librar{'y' if extracted_count == 1 else 'ies'})", "success")
        else:
            self.log("No natives needed extraction for this version/OS.", "info")

        return natives_dir

    def _build_debug_report(self, error, app_info=None):
        lines = ["Information details:"]
        lines.append(f"     OS: {platform.platform()}")
        lines.append(f"     Python: {platform.python_version()}")
        if app_info:
            for key, value in app_info.items():
                lines.append(f"     {key}: {value}")
        lines.append("")
        lines.append("Error:")
        lines.append(f"     {error}")
        return "\n".join(lines)

    def _open_with_default_app(self, path):
        try:
            system = platform.system().lower()
            if system.startswith("win"):
                os.startfile(str(path))
            elif system.startswith("darwin"):
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as e:
            self.log(f"Unable to open {path}: {e}", "error")

    def _copy_to_clipboard(self, text):
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
        except Exception as e:
            self.log(f"Unable to copy to clipboard: {e}", "error")

    def _show_launch_error_dialog(self, title, summary, details="", report_path=None):
        result = {"choice": "cancel"}
        event = threading.Event()

        def build():
            dialog = tk.Toplevel(self.root)
            dialog.title(title)
            dialog.transient(self.root)
            dialog.grab_set()
            dialog.resizable(False, False)
            with contextlib.suppress(Exception):
                dialog.iconbitmap(str(ASSETS / "icon" / "icon_64x64.ico"))

            tk.Label(
                dialog, text=summary, wraplength=440, justify="left",
                font=("Segoe UI", 10, "bold")
            ).pack(padx=15, pady=(15, 5), anchor="w")

            if details:
                frame = tk.Frame(dialog)
                frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)
                frame.columnconfigure(0, weight=1)
                frame.rowconfigure(0, weight=1)

                text_widget = tk.Text(frame, height=12, width=64, bg="black", fg="white", wrap="none")
                vbar = tk.Scrollbar(frame, orient="vertical", command=text_widget.yview)
                hbar = tk.Scrollbar(frame, orient="horizontal", command=text_widget.xview)
                text_widget.config(yscrollcommand=vbar.set, xscrollcommand=hbar.set)
                text_widget.insert("1.0", details)
                text_widget.config(state="disabled")

                text_widget.grid(row=0, column=0, sticky="nsew")
                vbar.grid(row=0, column=1, sticky="ns")
                hbar.grid(row=1, column=0, sticky="ew")

            if report_path:
                tk.Button(
                    dialog, text="Open crash report", width=18,
                    command=lambda: self._open_with_default_app(report_path)
                ).pack(pady=(0, 5))
            elif details:
                tk.Button(
                    dialog, text="Copy", width=18,
                    command=lambda: self._copy_to_clipboard(details)
                ).pack(pady=(0, 5))

            btn_frame = tk.Frame(dialog)
            btn_frame.pack(pady=15)

            def choose(choice):
                result["choice"] = choice
                dialog.destroy()
                event.set()

            tk.Button(btn_frame, text="Repair", width=12, command=lambda: choose("repair")).pack(side=tk.LEFT, padx=5)
            tk.Button(btn_frame, text="Retry", width=12, command=lambda: choose("retry")).pack(side=tk.LEFT, padx=5)
            tk.Button(btn_frame, text="Abandoned", width=12, command=lambda: choose("cancel")).pack(side=tk.LEFT, padx=5)

            dialog.protocol("WM_DELETE_WINDOW", lambda: choose("cancel"))
            dialog.update_idletasks()
            x = self.root.winfo_x() + (self.root.winfo_width() - dialog.winfo_width()) // 2
            y = self.root.winfo_y() + (self.root.winfo_height() - dialog.winfo_height()) // 2
            dialog.geometry(f"+{x}+{y}")

        self.root.after(0, build)
        event.wait()
        return result["choice"]

    def _find_latest_crash_report(self, since_str):
        crash_dir = GAME_DIR / "crash-reports"
        if not crash_dir.exists():
            return None
        try:
            since = time.mktime(time.strptime(since_str, "%Y-%m-%d %H:%M:%S"))
            candidates = [
                f for f in crash_dir.glob("*.txt")
                if f.stat().st_mtime >= since
            ]
            if not candidates:
                return None
            latest = max(candidates, key=lambda f: f.stat().st_mtime)
            return str(latest)
        except Exception:
            return None

    def _retry_or_abort(self, version_id, ram, title="Launch error", summary="", details="", report_path=None):
        choice = self._show_launch_error_dialog(title, summary, details, report_path=report_path)

        if choice == "repair" and self.no_internet:
            self.log("Repair is unavailable while offline.", "warn")
            self._show_error_and_wait("Repair version", "You are offline.\nRepairing a version requires an internet connection.")
            raise _AbortLaunch()

        if choice == "repair":
            self.log(f"Preparing to repair Minecraft {version_id}...", "info")
            return self._attempt_launch(version_id, ram, force=True)

        if choice == "retry":
            return self._attempt_launch(version_id, ram)

        raise _AbortLaunch()

    def _confirm_repair_selected_version(self):
        if self.no_internet:
            messagebox.showwarning("Repair version", "You are offline.\nRepairing a version requires an internet connection.")
            return

        version_id = self._get_selected_version_id()
        if not version_id:
            messagebox.showwarning("Repair version", "No version selected.")
            return

        if self.download_thread and self.download_thread.is_alive():
            messagebox.showwarning("Repair version", "Another operation is already in progress.")
            return

        if not messagebox.askyesno(
            "Repair version",
            f"This will re-download all files for Minecraft {version_id}.\nDo you want to continue?"
        ):
            return

        self._cancel_event.clear()
        self.root.after(0, lambda: self.set_ui_state(False))
        self.root.after(0, lambda: self.launch_btn.config(state="normal", text="Stop repair"))
        self.download_thread = threading.Thread(target=self._repair_version_thread, args=(version_id,), daemon=True)
        self.download_thread.start()

    def _repair_version_thread(self, version_id):
        try:
            self._get_version_ready(version_id, force=True)
            self.log(f"Version {version_id} repaired successfully!", "success")
            self.update_progress("Repair complete!")
            self.root.after(0, lambda: messagebox.showinfo("Repair version", f"Version {version_id} has been repaired."))
        except _AbortLaunch:
            self.log("Repair canceled.", "info")
        except Exception as e:
            self.log(f"Error repairing version {version_id}: {e}", "error")
            self.root.after(0, lambda: messagebox.showerror("Repair version", "Unable to repair the version! See logs for details."))
        finally:
            self.root.after(0, lambda: self.launch_btn.config(text="Play"))
            self.root.after(0, lambda: self.set_ui_state(True))

    def launch_game(self):
        if self.download_thread and self.download_thread.is_alive():
            self._cancel_or_stop()
            return

        self._cancel_event.clear()
        self._set_launch_button("Cancel", "normal")
        self.log("Starting preparation...", "info")
        self.download_thread = threading.Thread(target=self._launch_game_thread, daemon=True)
        self.download_thread.start()

    def _substitute(self, template, substitutions):
        def repl(match):
            key = match.group(1)
            if key not in substitutions:
                self.log(f"Unknown launch argument placeholder: ${{{key}}}", "warn")
                return ""
            return str(substitutions[key])
        return re.sub(r"\$\{([^}]+)\}", repl, template)

    def _process_argument_list(self, entries, substitutions):
        result = []
        for entry in entries:
            if isinstance(entry, str):
                result.append(self._substitute(entry, substitutions))
            elif isinstance(entry, dict):
                if not self._rules_allow(entry.get("rules")):
                    continue
                value = entry.get("value")
                if isinstance(value, list):
                    result.extend(self._substitute(v, substitutions) for v in value)
                elif isinstance(value, str):
                    result.append(self._substitute(value, substitutions))
        return result

    def _build_jvm_and_game_args(self, version_data, version_id, natives_dir, cp_str, active_user, uuid, token):
        substitutions = {
            "natives_directory": str(natives_dir),
            "launcher_name": "MiniCube",
            "launcher_version": "1.0",
            "classpath": cp_str,
            "classpath_separator": os.pathsep,
            "library_directory": str(LIBRARIES_DIR),
            "version_name": version_id,
            "game_directory": str(GAME_DIR),
            "assets_root": str(ASSETS_DIR),
            "game_assets": str(ASSETS_DIR),
            "assets_index_name": version_data.get("assetIndex", {}).get("id", ""),
            "auth_player_name": active_user,
            "auth_uuid": uuid,
            "auth_access_token": token,
            "auth_session": f"token:{token}:{uuid}",
            "auth_xuid": uuid,
            "clientid": "",
            "user_properties": "{}",
            "user_type": "legacy" if self.is_offline_var.get() else "msa",
            "version_type": version_data.get("type", "release"),
        }

        arguments = version_data.get("arguments")
        if arguments:
            jvm_args = self._process_argument_list(arguments.get("jvm", []), substitutions)
            game_args = self._process_argument_list(arguments.get("game", []), substitutions)
            if not jvm_args:
                jvm_args = [f"-Djava.library.path={natives_dir}", "-cp", cp_str]
            return jvm_args, game_args

        jvm_args = [f"-Djava.library.path={natives_dir}", "-cp", cp_str]
        legacy_args_str = version_data.get("minecraftArguments")
        if legacy_args_str:
            game_args = [self._substitute(tok, substitutions) for tok in legacy_args_str.split()]
        else:
            game_args = [
                "--username", active_user,
                "--version", version_id,
                "--gameDir", str(GAME_DIR),
                "--assetsDir", str(ASSETS_DIR),
                "--assetIndex", substitutions["assets_index_name"],
                "--uuid", uuid,
                "--accessToken", token,
            ]
        return jvm_args, game_args

    def _sanitize_args(self, args: list[str]) -> list[str]:
        sanitized = args.copy()
        sensitive_flags = {"--accessToken"}

        i = 0
        while i < len(sanitized):
            if sanitized[i] in sensitive_flags and i + 1 < len(sanitized):
                sanitized[i + 1] = "*****"
                i += 2
            else:
                i += 1
        return sanitized

    def _launch_game_thread(self):
        if not self.is_offline_var.get():
            account_name = self.selected_account_var.get()
            account_data = self.account_manager.get_account_by_name(account_name)

            if not account_data:
                self.root.after(0, lambda: messagebox.showerror(
                    "Error",
                    "Please select an account or enable offline mode."
                ))
                self.root.after(0, lambda: self.launch_btn.config(text="Play"))
                return

        version_id = self._get_selected_version_id()
        ram = self.ram_var.get()

        if not version_id:
            self.root.after(0, lambda: messagebox.showerror("Error", "Please select a valid version/profile."))
            self.root.after(0, lambda: self.launch_btn.config(text="Play"))
            return

        self.root.after(0, lambda: self.set_ui_state(False))

        try:
            self._attempt_launch(version_id, ram)
        except _AbortLaunch:
            pass
        except Exception as e:
            self.log(f"Unable to launch the game: {e}", "error")
            self.root.after(0, lambda: messagebox.showerror("Error", "Unable to launch the game! See logs for details."))

        self.root.after(0, lambda: self.launch_btn.config(text="Play"))
        self.root.after(0, lambda: self.set_ui_state(True))
        self.log("=== Game finished ===", "info")
        if self.rpc.is_running():
            self.rpc.update(details="In the launcher")

        if self._hidden_in_background:
            self.root.after(0, self._restore_window)

    def _build_classpath(self, version_data, version_id, is_direct_launch):
        classpath = []
        seen_lib_paths = set()
        for path, _ in self._iter_library_artifacts(version_data):
            if path in seen_lib_paths:
                continue
            seen_lib_paths.add(path)
            jar_path = LIBRARIES_DIR / path
            if is_direct_launch or self._is_valid_jar(jar_path):
                classpath.append(str(jar_path))

        classpath.append(str(VERSIONS_DIR / version_id / f"{version_id}.jar"))
        return os.pathsep.join(classpath)

    def _prepare_java_offline(self, version_id, version_data):
        java_major = self.get_required_java_version(version_data)
        self._set_launch_button("Loading...", "disabled")
        self.update_progress("Checking Java...")

        cached_profile = self.profile_manager.get_profile(version_id) or {}
        cached_path = cached_profile.get("javaPath")

        if not cached_path or not Path(cached_path).exists():
            self.log(f"Java path missing or invalid for {version_id}: {cached_path!r}", "error")
            self._show_error_and_wait(
                "Java not found",
                f"No valid Java runtime is recorded for {version_id}.\n"
                "Go back online and launch this version once to set it up."
            )
            raise _AbortLaunch()

        java_path = Path(cached_path)
        if cached_profile.get("javaMajor") != java_major:
            self.log(
                f"Warning: saved Java for {version_id} is major "
                f"{cached_profile.get('javaMajor')!r}, version requires {java_major}.",
                "warn",
            )

        natives_dir = NATIVES_DIR / version_id
        if not natives_dir.is_dir() or not any(natives_dir.iterdir()):
            natives_dir = self.extract_natives(version_data)
        return java_path, java_major, natives_dir

    def _prepare_java(self, version_id, version_data, is_direct_launch):
        if self.no_internet:
            return self._prepare_java_offline(version_id, version_data)

        java_major = self.get_required_java_version(version_data)
        cached_profile = self.profile_manager.get_profile(version_id)
        cached_java_path = cached_profile.get("javaPath") if cached_profile else None
        cached_java_major = cached_profile.get("javaMajor") if cached_profile else None

        self._set_launch_button("Loading...", "disabled")
        self.update_progress("Loading Java...")

        if cached_java_path and cached_java_major == java_major and Path(cached_java_path).exists():
            return Path(cached_java_path), java_major, NATIVES_DIR / version_id

        self.log(f"Preparing Java {java_major} runtime.", "info")
        java_path = self.ensure_java_installed(java_major)
        natives_dir = self.extract_natives(version_data)
        self.profile_manager.create_or_update(
            version_id,
            profile_type="custom" if self._is_installed_profile() else "vanilla",
            javaPath=str(java_path),
            javaMajor=java_major,
        )
        return java_path, java_major, natives_dir

    def _authenticate(self):
        if self.is_offline_var.get():
            return self.username_var.get(), "0", "0"

        if self.no_internet:
            account_name = self.selected_account_var.get()
            saved = self.account_manager.get_account_by_name(account_name)
            if not saved or not saved.get("access_token") or not saved.get("uuid"):
                self._show_error_and_wait(
                    "Authentication Error",
                    "No saved session for this account.\nConnect to the internet to sign in."
                )
                raise _AbortLaunch()
            self.log("Offline: using the last saved token (no refresh).", "warn")
            self._update_account_prefs(last_used_account=saved["uuid"])
            return saved["username"], saved["uuid"], saved["access_token"]

        self.update_progress("Signing in...")
        account_name = self.selected_account_var.get()
        account_data = self.account_manager.get_account_by_name(account_name)
        refreshed = MicrosoftAuth(app=self).refresh_token(account_data) if account_data else None

        if not refreshed:
            name = account_name or "the selected account"
            self.root.after(0, lambda: messagebox.showerror(
                "Authentication Error",
                f"Failed to refresh token for {name}.\nPlease log in again."
            ))
            raise _AbortLaunch()

        token_keys = ("access_token", "refresh_token", "access_token_expires_at")
        if any(refreshed.get(k) != account_data.get(k) for k in token_keys):
            self.account_manager.update_account(refreshed)

        self._update_account_prefs(last_used_account=refreshed["uuid"])
        return refreshed["username"], refreshed["uuid"], refreshed["access_token"]

    def _update_rpc_playing(self, version_id, active_user, uuid):
        if not self.rpc.is_running():
            return
        offline = self.is_offline_var.get()
        self.rpc.update(
            details=f"Playing Minecraft {version_id}",
            small_image=(
                "https://windowscraft76.fr/assets/minicube/steve_32x32.png"
                if offline else f"https://mc-heads.net/avatar/{uuid}/32"
            ),
            small_text=f"Playing offline as {active_user}" if offline else f"Playing as {active_user}",
        )

    def _watch_game_output(self, game_process):
        crash_pattern = "Failed to parse vanilla pack metadata"
        known_crash_reason = None
        log_tail = deque(maxlen=25)

        for line in iter(game_process.stdout.readline, ""):
            clean_line = line.strip("\n")
            self.log(clean_line, "game")
            log_tail.append(clean_line)
            if crash_pattern in clean_line:
                known_crash_reason = "Failed to parse vanilla pack metadata."
                self.log("Corrupted pack metadata detected, stopping the game...", "error")
                game_process.terminate()
                break

        return known_crash_reason, log_tail

    def _handle_crash(self, version_id, ram, reason, launch_time, log_tail, exit_code, java_info, command):
        crash_report_path = self._find_latest_crash_report(launch_time)

        debug_text = None
        if crash_report_path:
            try:
                with open(crash_report_path, encoding="utf-8", errors="replace") as f:
                    debug_text = f.read()
            except Exception:
                crash_report_path = None

        if debug_text is None:
            error_text = reason
            if log_tail:
                error_text += "\n\nLast log lines:\n" + "\n".join(log_tail)
            debug_text = self._build_debug_report(
                error_text,
                app_info={"Java version": java_info, "Exit code": exit_code, "Launch command": command},
            )

        return self._retry_or_abort(
            version_id, ram,
            title="Game crashed",
            summary=reason,
            details=debug_text,
            report_path=crash_report_path,
        )

    def _attempt_launch(self, version_id, ram, force=False):
        is_direct_launch = not force and self.profile_manager.has_profile(version_id)

        self._set_launch_button("Stop repair" if force else "Cancel", "normal")

        try:
            version_data, _ = self._get_version_ready(version_id, force=force)
        except _AbortLaunch:
            raise
        except Exception as e:
            self.log(f"Unable to prepare the version {version_id}: {e}", "error")
            return self._retry_or_abort(
                version_id, ram,
                title="An error occurred!",
                summary=f"An error occurred while preparing version {version_id}.",
                details=self._build_debug_report(e, app_info={"Minecraft version": version_id})
            )

        cp_str = self._build_classpath(version_data, version_id, is_direct_launch)
        main_class = version_data.get("mainClass", "net.minecraft.client.main.Main")
        java_path, java_major, natives_dir = self._prepare_java(version_id, version_data, is_direct_launch)
        active_user, uuid, token = self._authenticate()

        jvm_args, game_args = self._build_jvm_and_game_args(
            version_data, version_id, natives_dir, cp_str, active_user, uuid, token
        )
        args = [str(java_path), f"-Xms{ram}M", f"-Xmx{ram}M", *jvm_args, main_class, *game_args]

        safe_args = self._sanitize_args(args)
        command = " ".join(safe_args)
        java_info = f"{java_major} ({java_path})"
        self.log(f"[Command] {command}", "info")

        try:
            self.update_progress("Loading...")
            self._update_rpc_playing(version_id, active_user, uuid)
            launch_time = time.strftime("%Y-%m-%d %H:%M:%S")
            game_process = subprocess.Popen(
                args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace"
            )
            self._game_stop_requested = False
            self.game_process = game_process
            self._playing_username = active_user
            self._game_started_at = time.monotonic()
            self.log(f"Game started (PID {game_process.pid}) as {active_user}.", "success")
            self._set_launch_button("Stop", "normal")
            self._update_game_status()
        except Exception as e:
            self.log(f"Unable to start Java process: {e}", "error")
            return self._retry_or_abort(
                version_id, ram,
                title="Launch error",
                summary="Unable to start the Java process.",
                details=self._build_debug_report(e, app_info={"Java version": java_info, "Command": command})
            )

        known_crash_reason, log_tail = self._watch_game_output(game_process)

        game_process.wait()
        exit_code = game_process.returncode
        played_for = time.monotonic() - self._game_started_at if self._game_started_at is not None else 0
        self._stop_game_status_timer()
        self._game_started_at = None
        self.game_process = None
        self._playing_username = None
        self.update_progress(f"Closed game - You played for {self.format_duration(played_for)}")
        self.log(f"Java process ended with exit code {exit_code}.", "info")

        crashed = not self._game_stop_requested and (known_crash_reason is not None or exit_code not in (0, None))
        if crashed:
            reason = known_crash_reason or "The game closed unexpectedly."
            return self._handle_crash(
                version_id, ram, reason, launch_time, log_tail, exit_code, java_info, command
            )
        return None