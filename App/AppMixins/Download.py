import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from Config import (
    INDEXES_DIR,
    LIBRARIES_DIR,
    OBJECTS_DIR,
    RESSOURCE_MC_URL,
    VERSIONS_DIR
)
from AppMixins.Exceptions import _AbortLaunch


class DownloadMixin:

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
                self.update_progress(f"Downloading {label}s: {done}/{total} - {remaining_str} left")

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
        dest_path = Path(dest_path)
        temp_path = dest_path.with_name(f"{dest_path.name}.part")
        try:
            with self._http.get(url, stream=True, timeout=30) as response:
                response.raise_for_status()
                with open(temp_path, "wb") as out_file:
                    for chunk in response.iter_content(chunk_size=131072):
                        if self._cancel_event.is_set():
                            raise _AbortLaunch()
                        if chunk:
                            out_file.write(chunk)
            temp_path.replace(dest_path)
        finally:
            temp_path.unlink(missing_ok=True)

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