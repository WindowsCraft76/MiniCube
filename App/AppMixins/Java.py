import platform
import zipfile
from pathlib import Path
from Config import (
    API_AZUL_URL,
    JAVA_DIR,
    LIBRARIES_DIR,
    NATIVES_DIR
)
from AppMixins.Exceptions import _AbortLaunch


class JavaMixin:

    def get_required_java_version(self, version_data):

        java_info = version_data.get("javaVersion")
        if not java_info:
            return 8
        return java_info.get("majorVersion", 8)

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