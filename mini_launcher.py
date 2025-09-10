import os
import json
import urllib.request
import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import threading
import time
import hashlib
from pathlib import Path

# Dossier principal launcher_main à côté du script
BASE_DIR = Path(__file__).resolve().parent / "launcher_main"
VERSIONS_DIR = BASE_DIR / "versions"
ASSETS_DIR = BASE_DIR / "assets"
LIBRARIES_DIR = BASE_DIR / "libraries"
INDEXES_DIR = ASSETS_DIR / "indexes"
OBJECTS_DIR = ASSETS_DIR / "objects"

for d in [BASE_DIR, VERSIONS_DIR, ASSETS_DIR, LIBRARIES_DIR, INDEXES_DIR, OBJECTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

VERSION_MANIFEST = "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json"

class MiniLauncherApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Mini Minecraft Launcher")

        # Variables
        self.username_var = tk.StringVar(value="Steve")
        self.version_var = tk.StringVar()
        self.snapshot_var = tk.BooleanVar(value=False)
        self.ram_var = tk.IntVar(value=2048)

        # UI
        tk.Label(root, text="Pseudo :").pack(pady=2)
        self.username_entry = tk.Entry(root, textvariable=self.username_var)
        self.username_entry.pack(pady=2)

        tk.Label(root, text="Mémoire RAM (Mo) :").pack(pady=2)
        self.ram_spin = tk.Spinbox(root, from_=512, to=16384, increment=512,
                                   textvariable=self.ram_var)
        self.ram_spin.pack(pady=2)

        self.snapshot_check = tk.Checkbutton(root, text="Afficher les snapshots",
                                             variable=self.snapshot_var,
                                             command=self.refresh_version_list)
        self.snapshot_check.pack(pady=2)

        tk.Label(root, text="Version :").pack(pady=2)
        self.version_menu = ttk.Combobox(root, textvariable=self.version_var, state="readonly")
        self.version_menu.pack(pady=2)

        self.launch_btn = tk.Button(root, text="Lancer le jeu", command=self.launch_game)
        self.launch_btn.pack(pady=5)

        # Barre de progression stylée
        style = ttk.Style()
        style.theme_use('default')
        style.configure("blue.Horizontal.TProgressbar", troughcolor='grey', background='blue', thickness=20)
        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress = ttk.Progressbar(root, style="blue.Horizontal.TProgressbar",
                                        variable=self.progress_var, maximum=1.0, length=400)
        self.progress.pack(pady=2)
        self.progress_label = tk.Label(root, text="En attente...")
        self.progress_label.pack(pady=2)

        tk.Label(root, text="Logs :").pack(pady=2)
        self.log_text = tk.Text(root, height=15, width=80, bg="black", fg="white")
        self.log_text.pack(pady=2)
        self.log_text.tag_config("info", foreground="white")
        self.log_text.tag_config("success", foreground="green")
        self.log_text.tag_config("warn", foreground="orange")
        self.log_text.tag_config("error", foreground="red")
        self.log_text.tag_config("game", foreground="cyan")

        self.version_manifest = {}
        self.refresh_version_list()

    # UI lock/unlock
    def set_ui_state(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        self.username_entry.config(state=state)
        self.ram_spin.config(state=state)
        self.version_menu.config(state=state)
        self.snapshot_check.config(state=state)
        self.launch_btn.config(state=state)

    # Log colorée
    def log(self, msg, kind="info"):
        self.log_text.insert(tk.END, msg + "\n", kind)
        self.log_text.see(tk.END)
        self.root.update_idletasks()

    # Récupérer manifest et versions
    def refresh_version_list(self):
        try:
            urllib.request.urlretrieve(VERSION_MANIFEST, VERSIONS_DIR / "version_manifest.json")
            with open(VERSIONS_DIR / "version_manifest.json", "r", encoding="utf-8") as f:
                self.version_manifest = json.load(f)
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de récupérer le manifest : {e}")
            return

        items = []
        for v in self.version_manifest["versions"]:
            if v["type"] == "release" or (self.snapshot_var.get() and v["type"] == "snapshot"):
                items.append(v["id"])
        items.sort(reverse=True)
        self.version_menu["values"] = items
        if items:
            self.version_var.set(items[0])

    # Progression
    def update_progress(self, done, total, text=""):
        self.progress_var.set(done / total if total > 0 else 0)
        if text:
            self.progress_label.config(text=text)
        self.root.update_idletasks()

    # Préparer la version
    def prepare_version(self, version_id):
        version_info = next(v for v in self.version_manifest["versions"] if v["id"] == version_id)
        version_dir = VERSIONS_DIR / version_id
        version_dir.mkdir(parents=True, exist_ok=True)

        version_json_path = version_dir / f"{version_id}.json"
        version_jar_path = version_dir / f"{version_id}.jar"

        if not version_json_path.exists():
            urllib.request.urlretrieve(version_info["url"], version_json_path)
            self.log(f"Téléchargé {version_id}.json", "success")

        with open(version_json_path, "r", encoding="utf-8") as f:
            version_data = json.load(f)

        if not version_jar_path.exists():
            client_url = version_data["downloads"]["client"]["url"]
            tmp_path = version_dir / "client.jar"
            urllib.request.urlretrieve(client_url, tmp_path)
            tmp_path.rename(version_jar_path)
            self.log(f"Téléchargé {version_id}.jar", "success")

        # Assets
        asset_index_id = version_data["assetIndex"]["id"]
        asset_index_url = version_data["assetIndex"]["url"]
        asset_index_path = INDEXES_DIR / f"{asset_index_id}.json"
        if not asset_index_path.exists():
            urllib.request.urlretrieve(asset_index_url, asset_index_path)
            self.log(f"Téléchargé {asset_index_id}.json", "success")

        with open(asset_index_path, "r", encoding="utf-8") as f:
            asset_index = json.load(f)
        objects = asset_index.get("objects", {})

        # Librairies et assets
        tasks = []
        for lib in version_data.get("libraries", []):
            if "downloads" in lib and "artifact" in lib["downloads"]:
                path = lib["downloads"]["artifact"]["path"]
                url = lib["downloads"]["artifact"]["url"]
                sha1 = lib["downloads"]["artifact"].get("sha1")
                lib_path = LIBRARIES_DIR / path
                tasks.append(("lib", lib_path, url, sha1))
        for name, obj in objects.items():
            hash_val = obj["hash"]
            subdir = hash_val[:2]
            url = f"https://resources.download.minecraft.net/{subdir}/{hash_val}"
            obj_path = OBJECTS_DIR / subdir / hash_val
            tasks.append(("asset", obj_path, url, hash_val))

        # Téléchargement avec progression
        done = 0
        total = len(tasks)
        start_time = time.time()
        for kind, path, url, expected in tasks:
            path.parent.mkdir(parents=True, exist_ok=True)
            need = True
            if path.exists():
                with open(path, "rb") as f:
                    file_hash = hashlib.sha1(f.read()).hexdigest()
                if file_hash == expected:
                    need = False
            if need:
                try:
                    urllib.request.urlretrieve(url, path)
                    self.log(f"Téléchargé {kind}: {path.name}", "success")
                except Exception as e:
                    self.log(f"[WARN] Erreur téléchargement {url}: {e}", "warn")
            done += 1
            elapsed = time.time() - start_time
            speed = done / elapsed if elapsed > 0 else 0
            remaining = (total - done) / speed if speed > 0 else 0
            self.update_progress(done, total, f"{done}/{total} fichiers - reste {remaining:.1f}s")

        self.update_progress(total, total, "Prêt !")
        return version_data, version_jar_path

    # Lancer le jeu
    def launch_game(self):
        threading.Thread(target=self._launch_game_thread, daemon=True).start()

    def _launch_game_thread(self):
        username = self.username_var.get()
        version_id = self.version_var.get()
        ram = self.ram_var.get()

        try:
            version_data, version_jar_path = self.prepare_version(version_id)
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Erreur", f"Impossible de préparer la version : {e}"))
            return

        self.root.after(0, lambda: self.set_ui_state(False))

        # Classpath
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

        self.log(f"[Launcher] Commande: {' '.join(args)}", "info")

        game_process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in iter(game_process.stdout.readline, ''):
            self.root.after(0, lambda l=line: self.log(l.strip(), "game"))
        game_process.wait()

        self.root.after(0, lambda: self.set_ui_state(True))
        self.root.after(0, lambda: self.progress_label.config(text="Jeu fermé."))
        self.log("=== Jeu terminé ===", "info")

def main():
    root = tk.Tk()
    app = MiniLauncherApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
