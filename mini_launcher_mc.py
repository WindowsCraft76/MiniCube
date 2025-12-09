import os
import json
import urllib.request
import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import threading
import time
import webbrowser
from pathlib import Path

# ------------------ File paths ------------------
BASE_DIR = Path(__file__).resolve().parent / "GameFile"
VERSIONS_DIR = BASE_DIR / "versions"
ASSETS_DIR = BASE_DIR / "assets"
LIBRARIES_DIR = BASE_DIR / "libraries"
INDEXES_DIR = ASSETS_DIR / "indexes"
OBJECTS_DIR = ASSETS_DIR / "objects"

for d in [BASE_DIR, VERSIONS_DIR, ASSETS_DIR, LIBRARIES_DIR, INDEXES_DIR, OBJECTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

VERSION_MANIFEST = "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json"
PAGE_URL = "https://github.com/WindowsCraft76/mini-launcher-minecraft"
REMOTE_VERSION_URL = "https://raw.githubusercontent.com/WindowsCraft76/mini-launcher-minecraft/refs/heads/main/version.txt"

# ------------------ Center window ------------------
def center_window(window, width, height):
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    x = (screen_width - width) // 2
    y = (screen_height - height) // 2
    window.geometry(f"{width}x{height}+{x}+{y}")

# ------------------ Read version.txt (local) ------------------
def get_info_version():
    try:
        version_file = Path(__file__).parent / "version.txt"
        if version_file.exists():
            with open(version_file, "r", encoding="utf-8") as f:
                first_line = f.readline().strip()
                return first_line if first_line else "Empty version.txt"
        else:
            return "No version info available"
    except Exception as e:
        return f"Error reading version.txt: {e}"

# ------------------ Read remote version ------------------
def get_remote_version():
    try:
        with urllib.request.urlopen(REMOTE_VERSION_URL, timeout=6) as resp:
            text = resp.read().decode("utf-8")
            for line in text.splitlines():
                line = line.strip()
                if line:
                    return line
            return "Empty remote version"
    except Exception as e:
        return f"Error fetching remote version: {e}"
    
UPDATE_PAGE_URL = f"https://github.com/WindowsCraft76/mini-launcher-minecraft/releases/tag/{get_remote_version()}"

# ------------------ Main Launcher ------------------
class MiniLauncherApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Mini Launcher Minecraft")
        self.root.geometry("400x320")
        self.root.resizable(False, False)

        # Variables
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
            command=lambda: messagebox.showinfo("About", f"Mini Launcher Minecraft\nCreate by WindowsCraft76\nVersion: {get_info_version()}"))
        help.add_command(label="Open page", command=lambda: webbrowser.open(PAGE_URL))
        self.toolbar.add_cascade(label="Help", menu=help)

        root.config(menu=self.toolbar)

        self.UPDATE_LABEL = "New update available"

        # UI
        tk.Label(root, text="Username:").pack(pady=2)
        self.username_entry = tk.Entry(root, textvariable=self.username_var)
        self.username_entry.pack(pady=2)

        tk.Label(root, text="RAM Memory (MB):").pack(pady=2)
        self.ram_spin = tk.Spinbox(root, from_=512, to=16384, increment=512,
                                   textvariable=self.ram_var)
        self.ram_spin.pack(pady=2)

        tk.Label(root, text="Version:").pack(pady=2)
        self.version_menu = ttk.Combobox(root, textvariable=self.version_var, state="readonly")
        self.version_menu.pack(pady=2)

        self.snapshot_check = tk.Checkbutton(root, text="Show snapshots", variable=self.show_snapshots_var, command=self.refresh_version_list)
        self.snapshot_check.pack(pady=2)

        self.launch_btn = tk.Button(root, text="Launch game", command=self.launch_game)
        self.launch_btn.pack(pady=(20, 5))

        # Styled progress bar
        style = ttk.Style()
        style.theme_use('classic')
        style.configure("blue.Horizontal.TProgressbar", troughcolor='grey', background='green', thickness=20)
        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress = ttk.Progressbar(root, style="blue.Horizontal.TProgressbar", variable=self.progress_var, maximum=1.0, length=350)
        self.progress.pack(pady=5)
        self.progress_label = tk.Label(root, text="Waiting...")
        self.progress_label.pack(pady=(5, 10))

        self.version_manifest = {}
        self.check_version_mismatch_async()
        self.refresh_version_list()

    # ------------------ Version mismatch check ------------------
    def check_version_mismatch(self):
        local = get_info_version()
        remote = get_remote_version()
        if remote.startswith("Error"):
            self._remove_update_toolbar_entry()
            try:
                self.update_btn.pack_forget()
            except Exception:
                pass
            return

        if str(local).strip() != str(remote).strip():
            self._add_update_toolbar_entry()
        else:
            self._remove_update_toolbar_entry()
            try:
                self.update_btn.pack_forget()
            except Exception:
                pass

    def check_version_mismatch_async(self):
        threading.Thread(target=self._check_version_thread, daemon=True).start()

    def _check_version_thread(self):
        try:
            self.check_version_mismatch()
        except Exception as e:
            try:
                self.log(f"Erreur check_version_mismatch: {e}", "error")
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

    # ------------------ Open folder ------------------
    def open_folder(self):
        folder_path = BASE_DIR
        if os.name == "nt":
            os.startfile(folder_path)

    # ------------------ UI lock/unlock ------------------
    def set_ui_state(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        self.username_entry.config(state=state)
        self.ram_spin.config(state=state)
        self.version_menu.config(state=state)
        self.snapshot_check.config(state=state)
        if getattr(self, "old_check", None):
            self.old_check.config(state=state)
        self.launch_btn.config(state=state)

    # ------------------ Setting ------------------
    def toggle_settings_window(self):
        if getattr(self, "settings_window", None) and self.settings_window.winfo_exists():
            try:
                self.settings_window.deiconify()
                self.settings_window.lift()
                self.settings_window.focus_force()
            except Exception:
                pass
            return

        self.settings_window = tk.Toplevel(self.root)
        self.settings_window.title("Settings - Mini Launcher Minecraft")
        self.settings_window.resizable(False, False)
        center_window(self.settings_window, 360, 220)

        self.old_check = tk.Checkbutton(self.settings_window, text="Show historical versions", variable=self.show_old_var, command=self.refresh_version_list)
        self.old_check.pack(pady=1)

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

    # ------------------ Logs ------------------
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

    # ------------------ Versions ------------------
    def refresh_version_list(self):
        try:
            urllib.request.urlretrieve(VERSION_MANIFEST, VERSIONS_DIR / "version_manifest.json")
            with open(VERSIONS_DIR / "version_manifest.json", "r", encoding="utf-8") as f:
                self.version_manifest = json.load(f)
        except Exception as e:
            messagebox.showerror("Error", f"Unable to fetch manifest: {e}")
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

        self.check_version_mismatch_async()

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
            if "downloads" in lib and "artifact" in lib["downloads"]:
                path = lib["downloads"]["artifact"]["path"]
                url = lib["downloads"]["artifact"]["url"]
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
        for kind, path, url in tasks:
            if self.cancel_download:
                self.log("Download canceled!", "info")
                self.update_progress(0, 1, "Download canceled")
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

        self.update_progress(total, total, "Ready!")
        return version_data, version_jar_path

    # ------------------ Launch ------------------
    def launch_game(self):
        if self.download_thread and self.download_thread.is_alive():
            self.cancel_download = True
            self.log("Download cancellation requested.", "warn")
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

        cp_str = os.pathsep.join(classpath)
        args = [
            "java",
            f"-Xms{ram}M",
            f"-Xmx{ram}M",
            "-cp", cp_str,
            "net.minecraft.client.main.Main",
            "--username", username,
            "--version", version_id,
            "--gameDir", str(BASE_DIR),
            "--assetsDir", str(ASSETS_DIR),
            "--assetIndex", version_data["assetIndex"]["id"],
            "--uuid", "00000000-0000-0000-0000-000000000000",
            "--accessToken", "0"
        ]

        self.log(f"[Launcher] Command: {' '.join(args)}", "info")

        try:
            game_process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        except Exception as e:
            self.log(f"[ERROR] Unable to start Java process: {e}", "error")
            self.root.after(0, lambda: self.launch_btn.config(text="Launch game"))
            self.root.after(0, lambda: self.set_ui_state(True))
            return

        for line in iter(game_process.stdout.readline, ''):
            self.log(line.strip("\n"), "game")
        game_process.wait()

        self.root.after(0, lambda: self.launch_btn.config(text="Launch game"))
        self.root.after(0, lambda: self.set_ui_state(True))
        self.root.after(0, lambda: self.progress_label.config(text="Game closed."))
        self.log("=== Game finished ===", "info")


# ------------------ Main ------------------
def main():
    root = tk.Tk()

    app = MiniLauncherApp(root)

    root.mainloop()

if __name__ == "__main__":
    main()
