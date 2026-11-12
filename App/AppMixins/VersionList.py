import json
from tkinter import messagebox
from Config import (
    VERSION_MANIFEST_URL,
    VERSIONS_DIR
)
from AppMixins.Exceptions import _AbortLaunch
from i18n import t


class VersionListMixin:

    _STATE_KEYS = {
        "loading": "version_list.state.loading",
        "empty": "version_list.state.empty",
        "error": "version_list.state.error",
    }

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
        if self.version_state != "ready":
            self.version_menu.config(state="disabled")
        else:
            self.version_menu.config(state="disabled" if self._ui_locked else "readonly")

    def _set_version_state(self, state):
        self.version_state = state
        self.version_var.set(t(self._STATE_KEYS[state]))

    def _set_version_list(self, values, error=False):
        self.version_menu["values"] = values
        if error:
            self._set_version_state("error")
        elif values:
            self.version_state = "ready"
            self.version_var.set(values[0])
        else:
            self._set_version_state("empty")
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

    def _has_valid_version(self):
        return self.version_state == "ready"

    def _apply_installed_version_list(self):
        try:
            profiles = self.profile_manager.get_all_profiles()
        except Exception as e:
            self.log(f"Error loading installed profiles! {e}", "error")
            self._set_version_list([], error=True)
            return

        installed_profiles = [
            (profile.get("lastUsed", "") or "", profile.get("lastVersionId", key))
            for key, profile in profiles.items()
            if profile.get("type") == "custom"
        ]
        installed_profiles.sort(reverse=True)
        self.installed_profiles_map = {
            version_id: version_id
            for _, version_id in installed_profiles
        }

        self._set_version_list(list(self.installed_profiles_map.keys()))

    def _get_selected_version_id(self):
        if not self._has_valid_version():
            return None
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
        except _AbortLaunch:
            self.log("Manifest fetch canceled.", "info")
            return False
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror(t("version_list.error_box.fetch_manifest.title"), t("version_list.error_box.fetch_manifest.detail")))
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

        items.sort(key=lambda version: version["releaseTime"], reverse=True)
        version_ids = [v["id"] for v in items]

        self._set_version_list(version_ids)