import hashlib
import json
import zipfile
from Config import (
    INDEXES_DIR,
    LIBRARIES_DIR,
    LIBRARIES_MC_URL,
    VERSIONS_DIR
)
from AppMixins.Exceptions import _AbortLaunch


class VersionDataMixin:

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