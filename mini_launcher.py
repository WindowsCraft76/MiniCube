import os
import json
import urllib.request
import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import threading
import time
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
        self.ram_var = tk.IntVar(value=2048)
        self.show_snapshots_var = tk.BooleanVar(value=False)
        self.show_old_var = tk.BooleanVar(value=False)

        self.download_thread = None
        self.cancel_download = False

        # UI
        tk.Label(root, text="Pseudo:").pack(pady=2)
        self.username_entry = tk.Entry(root, textvariable=self.username_var)
        self.username_entry.pack(pady=2)

        tk.Label(root, text="Mémoire RAM (Mo):").pack(pady=2)
        self.ram_spin = tk.Spinbox(root, from_=512, to=16384, increment=512,
                                   textvariable=self.ram_var)
        self.ram_spin.pack(pady=2)

        self.snapshot_check = tk.Checkbutton(root, text="Afficher les snapshots",
                                             variable=self.show_snapshots_var,
                                             command=self.refresh_version_list)
        self.snapshot_check.pack(pady=2)

        self.old_check = tk.Checkbutton(root, text="Afficher old_alpha / old_beta",
                                        variable=self.show_old_var,
                                        command=self.refresh_version_list)
        self.old_check.pack(pady=2)

        tk.Label(root, text="Version:").pack(pady=2)
        self.version_menu = ttk.Combobox(root, textvariable=self.version_var, state="readonly")
        self.version_menu.pack(pady=2)

        self.launch_btn = tk.Button(root, text="Lancer le jeu", command=self.launch_game)
        self.launch_btn.pack(pady=5)

        # Barre de progression stylée
        style = ttk.Style()
        style.theme_use('classic')
        style.configure("blue.Horizontal.TProgressbar", troughcolor='grey', background='blue', thickness=20)
        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress = ttk.Progressbar(root, style="blue.Horizontal.TProgressbar",
                                        variable=self.progress_var, maximum=1.0, length=400)
        self.progress.pack(pady=2)
        self.progress_label = tk.Label(root, text="En attente...")
        self.progress_label.pack(pady=2)

        tk.Label(root, text="Logs:").pack(pady=2)
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
        self.old_check.config(state=state)
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
            messagebox.showerror("Erreur", f"Impossible de récupérer le manifest: {e}")
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

        # Tri par date de sortie (latest first)
        items.sort(key=lambda v: v["releaseTime"], reverse=True)
        version_ids = [v["id"] for v in items]

        self.version_menu["values"] = version_ids
        if version_ids:
            self.version_var.set(version_ids[0])

    # Progression
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
                lib_path = LIBRARIES_DIR / path
                tasks.append(("lib", lib_path, url))
        for name, obj in objects.items():
            hash_val = obj["hash"]
            subdir = hash_val[:2]
            url = f"https://resources.download.minecraft.net/{subdir}/{hash_val}"
            obj_path = OBJECTS_DIR / subdir / hash_val
            tasks.append(("asset", obj_path, url))

        # Téléchargement avec progression
        done = 0
        total = len(tasks)
        start_time = time.time()
        for kind, path, url in tasks:
            if self.cancel_download:
                self.log("[Launcher] Téléchargement annulé !", "warn")
                self.update_progress(0, 1, "Téléchargement annulé")
                return None, None
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                self.log(f"{kind.capitalize()} existe déjà, on saute: {path.name}", "info")
            else:
                try:
                    urllib.request.urlretrieve(url, path)
                    self.log(f"Téléchargé {kind}: {path.name}", "success")
                except Exception as e:
                    self.log(f"[WARN] Erreur téléchargement {url}: {e}", "warn")
            done += 1
            elapsed = time.time() - start_time
            speed = done / elapsed if elapsed > 0 else 0
            remaining = (total - done) / speed if speed > 0 else 0
            remaining_str = self.format_duration(remaining)
            self.update_progress(done, total, f"{done}/{total} fichiers - reste {remaining_str}")

        self.update_progress(total, total, "Prêt !")
        return version_data, version_jar_path

    # Lancer le jeu
    def launch_game(self):
        if self.download_thread and self.download_thread.is_alive():
            # Annuler le téléchargement
            self.cancel_download = True
            self.log("[Launcher] Annulation du téléchargement demandée.", "warn")
            return

        # Début d’un nouveau téléchargement / lancement
        self.cancel_download = False
        self.launch_btn.config(text="Annuler")
        self.download_thread = threading.Thread(target=self._launch_game_thread, daemon=True)
        self.download_thread.start()

    def _launch_game_thread(self):
        username = self.username_var.get()
        version_id = self.version_var.get()
        ram = self.ram_var.get()

        try:
            version_data, version_jar_path = self.prepare_version(version_id)
            if version_data is None:
                # Téléchargement annulé
                self.root.after(0, lambda: self.launch_btn.config(text="Lancer le jeu"))
                self.root.after(0, lambda: self.set_ui_state(True))
                return
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Erreur", f"Impossible de préparer la version : {e}"))
            self.root.after(0, lambda: self.launch_btn.config(text="Lancer le jeu"))
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

        self.root.after(0, lambda: self.launch_btn.config(text="Lancer le jeu"))
        self.root.after(0, lambda: self.set_ui_state(True))
        self.root.after(0, lambda: self.progress_label.config(text="Jeu fermé."))
        self.log("=== Jeu terminé ===", "info")


def main():
    root = tk.Tk()
    app = MiniLauncherApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
