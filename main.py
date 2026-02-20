import os
import json
import urllib.request
import tkinter as tk
import subprocess
import threading
import time
import webbrowser
import zipfile
import platform
import winreg
import re
from pathlib import Path
from tkinter import ttk, messagebox

# ------------------ File paths ------------------
BASE_DIR = Path(__file__).resolve().parent

GAME_DIR = Path(__file__).resolve().parent / "GameFile"
VERSIONS_DIR = GAME_DIR / "versions"
ASSETS_DIR = GAME_DIR / "Assets"
LIBRARIES_DIR = GAME_DIR / "libraries"
INDEXES_DIR = ASSETS_DIR / "indexes"
OBJECTS_DIR = ASSETS_DIR / "objects"
JAVA_DIR = GAME_DIR / "java_versions"

for d in [GAME_DIR, VERSIONS_DIR, ASSETS_DIR, LIBRARIES_DIR, INDEXES_DIR, OBJECTS_DIR, JAVA_DIR]:
    d.mkdir(parents=True, exist_ok=True)

SETTINGS_FILE = BASE_DIR / "settings.json"
CONTENT = BASE_DIR / "Content"

VERSION_MANIFEST = "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json"
PAGE_URL = "https://github.com/WindowsCraft76/mini-launcher-minecraft"
REPO_URL = "https://github.com/WindowsCraft76/mini-launcher-minecraft.git"

# ------------------ Center window ------------------
def center_window(window, width, height):
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    x = (screen_width - width) // 2
    y = (screen_height - height) // 2
    window.geometry(f"{width}x{height}+{x}+{y}")

# ------------------ Version launcher ------------------
def get_info_version():
    reg_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\Mini Launcher Minecraft"

    try:
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path)
        except FileNotFoundError:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path)

        version, _ = winreg.QueryValueEx(key, "DisplayVersion")
        winreg.CloseKey(key)

        return str(version)

    except FileNotFoundError:
        try:
            return "No version found"
        except Exception as e:
            return f"Error reading fallback version: {e}"

    except Exception as e:
        return f"Registry error: {e}"


# ------------------ Read remote version ------------------
def get_remote_version():
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--tags", "--sort=-v:refname", REPO_URL],
            capture_output=True,
            text=True,
            timeout=6,
            check=True
        )

        lines = result.stdout.strip().splitlines()
        if not lines:
            return "No tags found"

        last_tag_line = lines[0]
        tag_ref = last_tag_line.split("\t")[1]

        tag_name = tag_ref.replace("refs/tags/", "").replace("^{}", "")
        return tag_name

    except Exception as e:
        return f"Error fetching remote version: {e}"
    
UPDATE_PAGE_URL = f"https://github.com/WindowsCraft76/mini-launcher-minecraft/releases/tag/{get_remote_version()}"

def _normalize_version(version: str):
    version = version.strip().lower().lstrip("v")

    numbers = re.findall(r"\d+", version)

    if not numbers:
        return [0]

    return [int(n) for n in numbers]


def is_version_lower(local_version: str, remote_version: str) -> bool:
    try:
        local_parts = _normalize_version(local_version)
        remote_parts = _normalize_version(remote_version)

        length = max(len(local_parts), len(remote_parts))
        local_parts += [0] * (length - len(local_parts))
        remote_parts += [0] * (length - len(remote_parts))

        return local_parts < remote_parts

    except Exception:
        return False

# ------------------ SplashScreen ------------------
class SplashScreen:
    def __init__(self):
        self.root = tk.Toplevel()
        self.root.overrideredirect(True)
        self.root.configure(bg="#2b2b2b")

        logo = tk.PhotoImage(file=f"{CONTENT}\\icon\\icon_64px.png")
        logo_label = tk.Label(self.root, image=logo, bg="#2b2b2b")
        logo_label.image = logo
        logo_label.pack(side="left", padx=10, pady=10)

        self.center_window(350, 100)

        frame = tk.Frame(self.root, bg="#2b2b2b")
        frame.pack(expand=True, fill="both")

        self.label_title = tk.Label(
            frame,
            text="Mini Launcher Minecraft",
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

    def center_window(self, width, height):
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.root.geometry(f"{width}x{height}+{x}+{y}")

# ------------------ Main Launcher ------------------
class MiniLauncherApp:
    def __init__(self, root):
        self.root = root

        # Variables Default values
        self.username_var = tk.StringVar(value="Steve")
        self.version_var = tk.StringVar()
        self.ram_var = tk.IntVar(value=2048)
        self.show_snapshots_var = tk.BooleanVar(value=False)
        self.show_old_var = tk.BooleanVar(value=False)

        self.download_thread = None
        self.cancel_download = False

        # Log window variables
        self.log_window = None
        self.log_text_win = None
        self.log_buffer = []

        # Load saved settings
        self.load_settings()

    # ------------------ Interface ------------------
        self.log("Loading interface...", "info")
        # Principal window #

        # Main
        self.root.title("Mini Launcher Minecraft")
        self.root.geometry("350x270")
        self.root.resizable(False, False)
        root.iconbitmap(f"{CONTENT}\\icon\\icon_32px.ico")

        # Menu bar
        self.toolbar = tk.Menu(root)
        menu = tk.Menu(self.toolbar, tearoff=0)
        menu.add_command(label="Show logs", command=self.toggle_logs_window)
        menu.add_command(label="Settings", command=self.toggle_settings_window)
        menu.add_command(label="Open folder", command=self.open_folder)
        menu.add_separator()
        menu.add_command(label="Exit", command=root.quit)
        self.toolbar.add_cascade(label="Menu", menu=menu)

        help = tk.Menu(self.toolbar, tearoff=0)
        help.add_command(
            label="About",
            command=lambda: messagebox.showinfo("About", f"Mini Launcher Minecraft\n\nCreate by WindowsCraft76\nVersion: {get_info_version()}"))
        help.add_command(label="Open page", command=lambda: webbrowser.open(PAGE_URL))
        self.toolbar.add_cascade(label="Help", menu=help)

        root.config(menu=self.toolbar)

        self.UPDATE_LABEL = "New update available"

        # UI
        tk.Label(root, text="Username:").pack(pady=2)
        self.username_entry = tk.Entry(root, textvariable=self.username_var)
        self.username_entry.pack(pady=2)

        tk.Label(root, text="Version:").pack(pady=2)
        self.version_menu = ttk.Combobox(root, textvariable=self.version_var, state="readonly")
        self.version_menu.pack(pady=2)

        self.snapshot_check = tk.Checkbutton(root, text="Show snapshots", variable=self.show_snapshots_var, command=lambda: [self.refresh_version_list(), self.save_settings()])
        self.snapshot_check.pack(pady=2)

        self.launch_btn = tk.Button(root, text="Launch game", command=lambda: [ self.save_settings(), self.update_progress(0, 1, "Loading..."), style.configure("blue.Horizontal.TProgressbar", background='green'), self.launch_game()])
        self.launch_btn.pack(pady=(20, 5))

        # Styled progress bar
        style = ttk.Style()
        style.theme_use('classic')
        style.configure("blue.Horizontal.TProgressbar", troughcolor='grey', background='green', thickness=20)
        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress = ttk.Progressbar(root, style="blue.Horizontal.TProgressbar", variable=self.progress_var, maximum=1.0, length=320)
        self.progress.pack(pady=5)
        self.progress_label = tk.Label(root, text="Waiting...")
        self.progress_label.pack(pady=(5, 10))

        self.version_manifest = {}
        self.check_version_mismatch_async()
        self.refresh_version_list()


    # Settings window #
    def toggle_settings_window(self):
        if getattr(self, "settings_window", None) and self.settings_window.winfo_exists():
            try:
                self.settings_window.deiconify()
                self.settings_window.lift()
                self.settings_window.focus_force()
            except Exception:
                pass
            return

        # Main
        self.settings_window = tk.Toplevel(self.root)
        self.settings_window.title("Settings - Mini Launcher Minecraft")
        self.settings_window.resizable(False, False)
        self.settings_window.iconbitmap(f"{CONTENT}\\icon\\icon_32px.ico")
        center_window(self.settings_window, 360, 150)

        # UI
        tk.Label(self.settings_window, text="RAM Memory (MB):").pack(pady=2)
        self.ram_spin = tk.Spinbox(self.settings_window, from_=512, to=16384, increment=512, textvariable=self.ram_var, command=self.save_settings)
        self.ram_spin.pack(pady=5)

        self.old_check = tk.Checkbutton(self.settings_window, text="Show historical versions", variable=self.show_old_var, command=lambda: [self.refresh_version_list(), self.save_settings()])
        self.old_check.pack(pady=5)

        self.reset_btn = tk.Button(self.settings_window, text="Reset settings", command=self.reset_settings)
        self.reset_btn.pack(pady=(20, 5))

        def _on_close():
            try:
                self.settings_window.destroy()
            except Exception:
                pass
            self.settings_window = None
            if getattr(self, "old_check", None):
                try:
                    self.old_check.destroy()
                except Exception:
                    pass
                self.old_check = None
        
        self.settings_window.protocol("WM_DELETE_WINDOW", _on_close)

    # Logs window #
    def log(self, msg, kind="info"):
        timestamped = f"[{time.strftime('%H:%M:%S')}] {msg}"
        self.log_buffer.append((timestamped, kind))
        self.root.after(0, lambda: self._append_log_to_window(timestamped + "\n", kind))

    def _append_log_to_window(self, msg, kind="info"):
        if self.log_text_win:
            try:
                self.log_text_win.insert(tk.END, msg + "", kind)
                self.log_text_win.see(tk.END)
            except Exception:
                pass

    def toggle_logs_window(self):
        if self.log_window and self.log_window.winfo_exists():
            self.log_window.deiconify()
            self.log_window.lift()
            self.log_window.focus_force()
        else:
            self.log_window = tk.Toplevel(self.root)
            self.log_window.title("Logs - Mini Launcher Minecraft")
            self.log_window.iconbitmap(f"{CONTENT}\\icon\\icon_32px.ico")
            self.log_window.geometry("600x300")
            self.log_window.protocol("WM_DELETE_WINDOW", self._on_close_log_window)

            self.log_text_win = tk.Text(self.log_window, height=25, width=120, bg="black", fg="white")
            self.log_text_win.pack(fill=tk.BOTH, expand=True)

            self.log_text_win.tag_config("info", foreground="white")
            self.log_text_win.tag_config("success", foreground="green")
            self.log_text_win.tag_config("warn", foreground="orange")
            self.log_text_win.tag_config("error", foreground="red")
            self.log_text_win.tag_config("game", foreground="cyan")

            for line, kind in self.log_buffer:
                try:
                    self.log_text_win.insert(tk.END, line + "\n", kind)
                except Exception:
                    self.log_text_win.insert(tk.END, line + "\n")
            self.log_text_win.see(tk.END)

    def _on_close_log_window(self):
        if self.log_window:
            try:
                self.log_window.destroy()
            except Exception:
                pass
        self.log_window = None
        self.log_text_win = None

    # ------------------ Settings Save/Load ------------------
    def load_settings(self):

        self.log("Loading settings...", "info")

        if not SETTINGS_FILE.exists():
            return

        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Default values if keys are missing
            self.username_var.set(data.get("username", "Steve"))
            self.ram_var.set(data.get("ram", 2048))
            self.show_snapshots_var.set(data.get("show_snapshots", False))
            self.show_old_var.set(data.get("show_old_versions", False))

            self.log("Settings loaded!", "success")
        except Exception as e:
            self.log(f"Error loading settings!", "error")

    def save_settings(self):
        data = {
            "username": self.username_var.get(),
            "ram": self.ram_var.get(),
            "show_snapshots": self.show_snapshots_var.get(),
            "show_old_versions": self.show_old_var.get()
        }

        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            self.log(f"Error saving settings: {e}", "error")

    def reset_settings(self):
    # Set default values
        self.username_var.set("Steve")
        self.ram_var.set(2048)
        self.show_snapshots_var.set(False)
        self.show_old_var.set(False)

        if SETTINGS_FILE.exists():
            SETTINGS_FILE.unlink()

        self.log("Settings reset to defaults!", "info")

        self.load_settings()

    # ------------------ Version mismatch check ------------------
    def check_version_mismatch(self):

        self.log("Checking for updates...", "info")

        local = get_info_version()
        remote = get_remote_version()

        if remote.startswith("Error"):
            self._remove_update_toolbar_entry()
            try:
                self.update_btn.pack_forget()
            except Exception:
                pass
            return

        if is_version_lower(local, remote):
            self._add_update_toolbar_entry()
            self.log(f"Update available: {local} -> {remote}", "warn")
        else:
            self._remove_update_toolbar_entry()
            try:
                self.update_btn.pack_forget()
            except Exception:
                pass
                self.log(f"Launcher up to date ({local})", "success")


    def check_version_mismatch_async(self):
        threading.Thread(target=self._check_version_thread, daemon=True).start()

    def _check_version_thread(self):
        try:
            self.check_version_mismatch()
        except Exception as e:
            try:
                self.log(f"Erreur checking for updates!", "error")
            except Exception:
                pass

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

    def _add_update_toolbar_entry(self):
        if self._find_toolbar_index_by_label(self.UPDATE_LABEL) is None:
            self.toolbar.add_command(label=self.UPDATE_LABEL, command=lambda: webbrowser.open(UPDATE_PAGE_URL))
            answer = messagebox.askyesno("New update available", f"The new version {get_remote_version()} is available!\nDo you want to open the version page?")
            if answer:
                webbrowser.open(UPDATE_PAGE_URL)

    def _remove_update_toolbar_entry(self):
        idx = self._find_toolbar_index_by_label(self.UPDATE_LABEL)
        if idx is not None:
            try:
                self.toolbar.delete(idx)
            except Exception:
                pass

    # ------------------ Versions Minecraft ------------------
    def refresh_version_list(self):

        self.log("Fetching version manifest...", "info")

        try:
            urllib.request.urlretrieve(VERSION_MANIFEST, VERSIONS_DIR / "version_manifest.json")
            with open(VERSIONS_DIR / "version_manifest.json", "r", encoding="utf-8") as f:
                self.version_manifest = json.load(f)
                self.log("Version manifest fetched successfully!", "success")
        except Exception as e:
            messagebox.showerror("Error", f"Unable to fetch manifest!")
            self.log(f"Error fetching version manifest!", "error")
            return

        items = []
        for v in self.version_manifest["versions"]:
            vtype = v.get("type", "")
            if vtype == "release":
                items.append(v)
            elif vtype == "snapshot" and self.show_snapshots_var.get():
                items.append(v)
            elif vtype in ["old_alpha", "old_beta"] and self.show_old_var.get():
                items.append(v)

        items.sort(key=lambda v: v["releaseTime"], reverse=True)
        version_ids = [v["id"] for v in items]

        self.version_menu["values"] = version_ids
        if version_ids:
            self.version_var.set(version_ids[0])

    # ------------------ Open folder ------------------
    def open_folder(self):
        folder_path = GAME_DIR
        if os.name == "nt":
            os.startfile(folder_path)

    # ------------------ Get required Java version ------------------
    def get_required_java_version(self, version_data):

        java_info = version_data.get("javaVersion")
        if not java_info:
            return 8
        return java_info.get("majorVersion", 8)

    # ------------------ UI lock/unlock ------------------
    def set_ui_state(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        self.username_entry.config(state=state)
        self.version_menu.config(state=state)
        self.snapshot_check.config(state=state)
        self.launch_btn.config(state=state)

        if hasattr(self, "ram_spin") and self.ram_spin:
            self.ram_spin.config(state=state)

        if hasattr(self, "old_check") and self.old_check:
            self.old_check.config(state=state)

    # ------------------ Progress ------------------
    def update_progress(self, done, total, text=""):
        self.progress_var.set(done / total if total > 0 else 0)
        if text:
            self.progress_label.config(text=text)
        self.root.update_idletasks()

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

    # ------------------ Prepare the version ------------------
    def prepare_version(self, version_id):
        version_info = next(v for v in self.version_manifest["versions"] if v["id"] == version_id)
        version_dir = VERSIONS_DIR / version_id
        version_dir.mkdir(parents=True, exist_ok=True)

        version_json_path = version_dir / f"{version_id}.json"
        version_jar_path = version_dir / f"{version_id}.jar"

        if not version_json_path.exists():
            urllib.request.urlretrieve(version_info["url"], version_json_path)
            self.log(f"Downloaded {version_id}.json", "success")

        with open(version_json_path, "r", encoding="utf-8") as f:
            version_data = json.load(f)

        if not version_jar_path.exists():
            client_url = version_data["downloads"]["client"]["url"]
            tmp_path = version_dir / "client.jar"
            urllib.request.urlretrieve(client_url, tmp_path)
            tmp_path.rename(version_jar_path)
            self.log(f"Downloaded {version_id}.jar", "success")

        asset_index_id = version_data["assetIndex"]["id"]
        asset_index_url = version_data["assetIndex"]["url"]
        asset_index_path = INDEXES_DIR / f"{asset_index_id}.json"
        if not asset_index_path.exists():
            urllib.request.urlretrieve(asset_index_url, asset_index_path)
            self.log(f"Downloaded {asset_index_id}.json", "success")

        with open(asset_index_path, "r", encoding="utf-8") as f:
            asset_index = json.load(f)
        objects = asset_index.get("objects", {})

        tasks = []
        for lib in version_data.get("libraries", []):
            downloads = lib.get("downloads")
            if not downloads:
                continue
            artifact = downloads.get("artifact")
            if artifact:
                path = artifact["path"]
                url = artifact["url"]
                lib_path = LIBRARIES_DIR / path
                tasks.append(("lib", lib_path, url))
            classifiers = downloads.get("classifiers", {})
            for classifier in classifiers.values():
                path = classifier["path"]
                url = classifier["url"]
                lib_path = LIBRARIES_DIR / path
                tasks.append(("lib", lib_path, url))
        for name, obj in objects.items():
            hash_val = obj["hash"]
            subdir = hash_val[:2]
            url = f"https://resources.download.minecraft.net/{subdir}/{hash_val}"
            obj_path = OBJECTS_DIR / subdir / hash_val
            tasks.append(("asset", obj_path, url))

        done = 0
        total = len(tasks)
        start_time = time.time()
        style = ttk.Style()
        for kind, path, url in tasks:
            if self.cancel_download:
                self.log("Download canceled!", "info")
                self.update_progress(done, total, "Download canceled")
                style.configure("blue.Horizontal.TProgressbar", background='orange')
                return None, None
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                self.log(f"{kind.capitalize()} already exists, skipping: {path.name}", "info")
            else:
                try:
                    urllib.request.urlretrieve(url, path)
                    self.log(f"Downloaded {kind}: {path.name}", "success")
                except Exception as e:
                    self.log(f"Error downloading {url}: {e}", "error")
            done += 1
            elapsed = time.time() - start_time
            speed = done / elapsed if elapsed > 0 else 0
            remaining = (total - done) / speed if speed > 0 else 0
            remaining_str = self.format_duration(remaining)
            self.update_progress(done, total, f"{done}/{total} files - remaining {remaining_str}")

        self.update_progress(total, total, "Download finished!")
        return version_data, version_jar_path

    # ------------------ Ensure Java installed ------------------
    def ensure_java_installed(self, major_version: int):

        for item in JAVA_DIR.iterdir():
            if not item.is_dir():
                continue

            name = item.name.lower()
            if not name.startswith(f"zulu{major_version}"):
                continue

            javaw = item / "bin" / "javaw.exe"
            if javaw.exists():
                self.log(f"Java {major_version} already present", "info")
                return javaw

        self.log(f"Downloading Java {major_version}...", "info")

        api_url = (
            "https://api.azul.com/metadata/v1/zulu/packages/"
            f"?java_version={major_version}"
            "&os=windows"
            "&java_package_type=jre"
            "&javafx_bundled=false"
        )

        with urllib.request.urlopen(api_url) as resp:
            packages = json.load(resp)

        if not packages:
            raise Exception(f"No Java package found for Java {major_version}", "error")
            self.log(f"No Java package found for Java {major_version}", "error")

        pkg = packages[0]
        download_url = pkg["download_url"]
        zip_name = Path(download_url).name
        zip_path = JAVA_DIR / zip_name

        self.root.after(0, lambda: self.progress_label.config(text=f"Downloading Java..."))
        urllib.request.urlretrieve(download_url, zip_path)

        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(JAVA_DIR)

        zip_path.unlink(missing_ok=True)

        for item in JAVA_DIR.iterdir():
            if not item.is_dir():
                continue

            name = item.name.lower()
            if not name.startswith(f"zulu{major_version}"):
                continue

            javaw = item / "bin" / "javaw.exe"
            if javaw.exists():
                self.log(f"Java {major_version} installed successfully!", "success")
                return javaw

        raise Exception(f"javaw.exe for Java {major_version} not found", "error")
        self.log(f"javaw.exe for Java {major_version} not found", "error")

    # ------------------ Extract natives ------------------
    def extract_natives(self, version_data):

        version_id = version_data["id"]

        natives_dir = GAME_DIR / "natives" / version_id
        natives_dir.mkdir(parents=True, exist_ok=True)

        system = platform.system().lower()
        if system.startswith("win"):
            os_name = "windows"
        elif system.startswith("linux"):
            os_name = "linux"
        elif system.startswith("darwin"):
            os_name = "osx"
        else:
            raise Exception(f"Unsupported OS: {system}")

        self.log(f"Extracting natives for {version_id}...", "info")

        self.root.after(0, lambda: self.progress_label.config(text=f"Extracting natives..."))
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
            except Exception as e:
                self.log(f"Failed to extract natives from {jar_path}: {e}", "error")

        self.log(f"Natives successfully extracted!", "success")

        return natives_dir


    # ------------------ Launch ------------------
    def launch_game(self):
        if self.download_thread and self.download_thread.is_alive():
            self.cancel_download = True
            self.log("Canceling download...", "warn")
            self.progress_label.config(text="Canceling download...")
            return

        self.cancel_download = False
        self.launch_btn.config(text="Cancel")
        self.download_thread = threading.Thread(target=self._launch_game_thread, daemon=True)
        self.download_thread.start()

    def _launch_game_thread(self):
        username = self.username_var.get()
        version_id = self.version_var.get()
        ram = self.ram_var.get()

        try:
            version_data, version_jar_path = self.prepare_version(version_id)
            if version_data is None:
                self.root.after(0, lambda: self.launch_btn.config(text="Launch game"))
                self.root.after(0, lambda: self.set_ui_state(True))
                return
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Unable to prepare the version: {e}"))
            self.root.after(0, lambda: self.launch_btn.config(text="Launch game"))
            return

        self.root.after(0, lambda: self.set_ui_state(False))

        classpath = []
        for lib in version_data.get("libraries", []):
            if "downloads" in lib and "artifact" in lib["downloads"]:
                path = lib["downloads"]["artifact"]["path"]
                jar_path = LIBRARIES_DIR / path
                if jar_path.exists():
                    classpath.append(str(jar_path))
        classpath.append(str(version_jar_path))

        version_jar = VERSIONS_DIR / version_id / f"{version_id}.jar"
        classpath.append(str(version_jar))

        cp_str = os.pathsep.join(classpath)
        java_major = self.get_required_java_version(version_data)
        self.root.after(0, lambda: self.progress_label.config(text=f"Download Java..."))
        java_path = self.ensure_java_installed(java_major)
        main_class = version_data.get("mainClass", "net.minecraft.client.main.Main")
        natives_dir = self.extract_natives(version_data)

        args = [
            str(java_path),
            f"-Djava.library.path={natives_dir}",
            f"-Xms{ram}M",
            f"-Xmx{ram}M",
            "-cp", cp_str,
            main_class,
            "--username", username,
            "--version", version_id,
            "--gameDir", str(GAME_DIR),
            "--assetsDir", str(ASSETS_DIR),
            "--assetIndex", version_data["assetIndex"]["id"],
            "--uuid", "00000000-0000-0000-0000-000000000000",
            "--accessToken", "0"
        ]

        self.log(f"Command: {' '.join(args)}", "info")

        try:
            self.root.after(0, lambda: self.progress_label.config(text="Ready!"))
            game_process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        except Exception as e:
            self.log(f"[ERROR] Unable to start Java process: {e}", "error")
            self.root.after(0, lambda: self.launch_btn.config(text="Launch game"))
            self.root.after(0, lambda: self.set_ui_state(True))
            return

        for line in iter(game_process.stdout.readline, ''):
            self.log(line.strip("\n"), "game")
        game_process.wait()

        style = ttk.Style()

        self.root.after(0, lambda: self.launch_btn.config(text="Launch game"))
        self.root.after(0, lambda: self.set_ui_state(True))
        self.root.after(0, lambda: self.progress_label.config(text="Game closed"))
        self.root.after(0, lambda: style.configure("blue.Horizontal.TProgressbar", background='red'))
        self.log("=== Game finished ===", "info")


# ------------------ Main ------------------
def main():
    root = tk.Tk()
    root.withdraw()

    splash = SplashScreen()

    def start_launcher():
        try:
            root.update()
            app = MiniLauncherApp(root)

            root.update()
            time.sleep(0.5)

            splash.root.destroy()
            root.deiconify()

            def on_close():
                app.save_settings()
                root.destroy()

            root.protocol("WM_DELETE_WINDOW", on_close)

        except Exception as e:
            messagebox.showerror("Startup Error", str(e))
            root.destroy()

    root.after(100, start_launcher)
    root.mainloop()

if __name__ == "__main__":
    main()
