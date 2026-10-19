import os
import re
import subprocess
import threading
import time
from tkinter import messagebox
from Config import (
    ASSETS_DIR,
    GAME_DIR,
    LIBRARIES_DIR,
    VERSIONS_DIR
)
from VersionManager import read_local_version
from MicrosoftAuth import MicrosoftAuth
from AppMixins.Exceptions import _AbortLaunch


class LaunchMixin:

    launcher_version = read_local_version()

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
            self._cancel_event.clear()
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

    def _build_jvm_and_game_args(self, version_data, version_id, natives_dir, cp_str, active_user, uuid, token, launcher_version):
        substitutions = {
            "natives_directory": str(natives_dir),
            "launcher_name": "MiniCube",
            "launcher_version": f"{launcher_version}",
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

        self._cancel_event.clear()
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
            version_data, version_id, natives_dir, cp_str, active_user, uuid, token, launcher_version=self.launcher_version
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