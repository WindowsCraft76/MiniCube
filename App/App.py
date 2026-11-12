import platform
import threading
import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk
import requests
from AccountManager import AccountManager
from Config import (
    ASSETS,
    DISCLAIMER_URL,
    GAME_DIR,
    HELP_INSTALLED_VERSION_URL,
    ISSUES_URL,
    PAGE_URL,
    PRIVACY_URL,
    TERMS_URL,
    USER_AGENT,
    copyright,
    FEEDBACK_URL
)
from DiscordRPC import DiscordRPC
from Network import is_online
from ProfileManager import ProfileManager
from VersionManager import (
    format_local_version_for_display,
    get_local_version_type,
    read_local_version,
)
from AppMixins.Lifecycle import LifecycleMixin
from AppMixins.Logging import LoggingMixin
from AppMixins.Settings import SettingsMixin
from AppMixins.Accounts import AccountsMixin
from AppMixins.Updates import UpdatesMixin
from AppMixins.Toolbar import ToolbarMixin
from AppMixins.Connectivity import ConnectivityMixin
from AppMixins.VersionList import VersionListMixin
from AppMixins.UiState import UiStateMixin
from AppMixins.Download import DownloadMixin
from AppMixins.VersionData import VersionDataMixin
from AppMixins.Java import JavaMixin
from AppMixins.Crash import CrashMixin
from AppMixins.Launch import LaunchMixin
from i18n import t
from ScrollingButton import ScrollingButton


class App(
    LifecycleMixin,
    LoggingMixin,
    SettingsMixin,
    AccountsMixin,
    UpdatesMixin,
    ToolbarMixin,
    ConnectivityMixin,
    VersionListMixin,
    UiStateMixin,
    DownloadMixin,
    VersionDataMixin,
    JavaMixin,
    CrashMixin,
    LaunchMixin,
):
    def __init__(self, root, rpc=None, debug=None, instance_socket=None):
        self.root = root
        self.debug = debug
        self._ui_locked = False

        self.log_window = None
        self.log_text_win = None
        self.log_buffer = []
        self._load_language_setting()

        self.game_process = None
        self._playing_username = None
        self._game_stop_requested = False
        self._game_started_at = None
        self._game_status_after_id = None
        self._hidden_in_background = False
        self._launcher_exiting = False
        self._instance_socket = instance_socket
        if self._instance_socket:
            threading.Thread(target=self._listen_for_instance_signal, daemon=True).start()

        self._ui_ready = False
        self._pending_update_version = None
        self._update_download_url = ""
        self._updating = False
        self._update_win = None
        self._cancel_update = threading.Event()

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

        self.toolbar = tk.Menu(root, tearoff=0)
        menu = tk.Menu(self.toolbar, tearoff=0)
        self._toolbar_menu = menu
        menu.add_command(label=t("toolbar.menu.logs"), command=self.toggle_logs_window)
        menu.add_command(label=t("toolbar.menu.accounts"), command=self.toggle_accounts_manager_window)
        menu.add_command(label=t("toolbar.menu.settings"), command=self.toggle_settings_window)
        menu.add_command(label=t("toolbar.menu.open_folder"), command=self.open_folder)
        menu.add_separator()
        menu.add_command(label=t("toolbar.menu.check_updates"), command=self.check_version_mismatch)
        menu.add_command(label=t("toolbar.menu.exit"), command=self._on_close_request)
        self.toolbar.add_cascade(label=t("toolbar.menu"), menu=menu)

        self.root.protocol("WM_DELETE_WINDOW", self._on_close_request)

        profile_menu = tk.Menu(self.toolbar, tearoff=0)
        self.profile_menu = profile_menu
        profile_menu.add_radiobutton(label=t("toolbar.profile.vanilla"), variable=self.profile_var, value="vanilla", command=self._on_profile_changed)
        profile_menu.add_radiobutton(label=t("toolbar.profile.installed"), variable=self.profile_var, value="installed", command=self._on_profile_changed)
        self.toolbar.add_cascade(label=t("toolbar.profile"), menu=profile_menu)

        help = tk.Menu(self.toolbar, tearoff=0)
        self.help_menu = help
        help.add_command(
            label=t("toolbar.help.about"),
            command=lambda:
            messagebox.showinfo(
            t("about.windows.title"),
            f"MiniCube\nCreated by WindowsCraft76\n\nVersion installed: {local_display} ({local_version_type})\nOperating system: {platform.platform()}\nPython version: {platform.python_version()} {platform.python_build()}\n\nThis is an open-source project under the MIT license.\nMiniCube is not affiliated with, endorsed by, or supported by Mojang Studios or Microsoft.\n\n{copyright}",
        ))
        help.add_command(label=t("toolbar.help.open_page"), command=lambda: webbrowser.open(PAGE_URL))
        help.add_separator()
        help.add_command(label=t("toolbar.help.terms_of_service"), command=lambda: webbrowser.open(f"{TERMS_URL}"))
        help.add_command(label=t("toolbar.help.privacy_policy"), command=lambda: webbrowser.open(f"{PRIVACY_URL}"))
        help.add_command(label=t("toolbar.help.disclaimer"), command=lambda: webbrowser.open(f"{DISCLAIMER_URL}"))
        help.add_separator()
        help.add_command(label=t("toolbar.help.report_issue"), command=lambda: webbrowser.open(f"{ISSUES_URL}"))
        help.add_command(label=t("toolbar.help.feedback"), command=lambda: webbrowser.open(f"{FEEDBACK_URL}"))
        self.toolbar.add_cascade(label=t("toolbar.help"), menu=help)
        self._notif_anchor_index = self.toolbar.index("end") + 1

        self.root.config(menu=self.toolbar)
        self.root.after(500, self._right_align_notifications)

        self.start_launch_sequence()

        if debug:
            self.log("Debug mode enabled!", "debug")

        self.rpc = rpc if rpc else DiscordRPC(self)
        if self.rpc.app is None:
            self.rpc.app = self

        self.username_var = tk.StringVar(value="Steve")
        self.version_state = "loading"
        self.version_var = tk.StringVar(value=t("version_list.state.loading"))
        self.ram_var = tk.IntVar(value=2048)
        self.show_snapshots_var = tk.BooleanVar(value=False)
        self.show_old_var = tk.BooleanVar(value=False)
        self.discord_rpc_var = tk.BooleanVar(value=True)
        self.keep_open_var = tk.BooleanVar(value=True)
        self.close_on_launch_var = tk.BooleanVar(value=False)
        self.game_dir_var = tk.StringVar(value=str(GAME_DIR))
        self.download_limit_kbps = 0

        self.download_thread = None
        self._cancel_event = threading.Event()

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

        self.account_label = tk.Label(self.account_frame, text=t("app.label.account"))
        self.account_menu = ttk.Combobox(
            self.account_frame,
            textvariable=self.selected_account_var,
            state="readonly"
        )
        self.account_menu.bind("<<ComboboxSelected>>", self._on_account_selected)

        self.offline_label = tk.Label(self.account_frame, text=t("app.label.username"))
        self.offline_entry = tk.Entry(self.account_frame, textvariable=self.username_var)

        self.offline_check = tk.Checkbutton(
            root, 
            text=t("app.check.offline"),
            variable=self.is_offline_var, 
            command=self.toggle_account_mode
        )
        self.offline_check.pack(pady=(3, 15))

        self.refresh_accounts_ui()

        self.version_label = tk.Label(root, text=t("app.label.version"))
        self.version_label.pack(pady=(0, 2))
        self.version_menu = ttk.Combobox(root, textvariable=self.version_var, state="disabled", width=25)
        self.version_menu.pack(pady=(0, 0))

        self.snapshot_check = tk.Checkbutton(root, text=t("app.check.snapshot"), variable=self.show_snapshots_var, command=self.refresh_version_list)
        self.snapshot_check.pack(pady=(3, 0))
        self.snapshot_link = tk.Label(root, text=t("app.label.help.installed_version"), fg="blue", cursor="hand2")
        self.snapshot_link.bind("<Button-1>", lambda _event: webbrowser.open(HELP_INSTALLED_VERSION_URL))

        self.launch_btn = ScrollingButton(root, text=t("launch_button.play"), command=self._on_launch_button, width=15, anchor="center")
        self.launch_btn.pack(pady=(20, 0))

        self.progress_label = tk.Label(root, text=t("progress_label.waiting"))
        self.progress_label.pack(pady=(10, 0))

        self.version_manifest = {}