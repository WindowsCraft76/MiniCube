import contextlib
import threading
import tkinter as tk
from tkinter import messagebox


class LifecycleMixin:

    def _listen_for_instance_signal(self):
        while True:
            try:
                conn, _ = self._instance_socket.accept()
            except OSError:
                return
            try:
                data = conn.recv(16)
                if data == b"SHOW":
                    self.root.after(0, self._restore_window)
            except Exception:
                pass
            finally:
                with contextlib.suppress(Exception):
                    conn.close()

    def _restore_window(self):
        try:
            self._hidden_in_background = False
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
            self.root.attributes("-topmost", True)
            self.root.after(200, lambda: self.root.attributes("-topmost", False))
        except Exception:
            pass

    def _minecraft_running(self):
        return self.game_process is not None and self.game_process.poll() is None

    def _on_close_request(self):
        if self._minecraft_running() and self.keep_open_var.get():
            self._hidden_in_background = True
            self.root.withdraw()
        else:
            self._shutdown_app()

    def _on_launch_button(self):
        if self._minecraft_running():
            self.stop_game()
            return
        if self.version_var.get() == "Loading...":
            messagebox.showwarning("Launch", "Version list is still loading.\nPlease wait a moment and try again.")
            return
        if self.version_var.get() == "No version available":
            messagebox.showwarning("Launch", "No version available to launch.\nPlease check your settings and try again.")
            return
        if self.version_var.get() == "Error":
            messagebox.showwarning("Launch", "An error occurred while checking version availability.\nPlease check your settings and try again.")
            return
        self.save_settings()
        self.update_progress("Starting...")
        self.launch_game()

    def _cancel_or_stop(self):
        if self._minecraft_running():
            self.stop_game()
            return
        if self.download_thread and self.download_thread.is_alive():
            self._cancel_event.set()
            self.log("Cancellation requested!", "warn")
            self.update_progress("Canceling...")

    def stop_game(self):
        process = self.game_process
        if not process or process.poll() is not None:
            return
        self.log(f"Stop requested for Java process! (PID {process.pid})", "warn")
        self._game_stop_requested = True
        self.update_progress("Stopping game...")
        try:
            process.terminate()
        except OSError as error:
            self.log(f"Unable to stop Java process: {error}", "error")

    def _shutdown_app(self):
        with contextlib.suppress(Exception):
            self.save_settings()
        try:
            if self.rpc:
                self.rpc.stop_rpc()
        except Exception:
            pass
        try:
            if self._instance_socket:
                self._instance_socket.close()
        except Exception:
            pass
        if self.debug:
            print("Closing!")
        with contextlib.suppress(Exception):
            self.root.destroy()

    def start_launch_sequence(self):
        threading.Thread(target=self._launch_sequence_worker, daemon=True).start()

    def _launch_sequence_worker(self):
        self.log("Starting up...", "info")

        if self.no_internet:
            self.log("No internet connection!", "warn")
            self.root.after(0, self._enter_offline_ui)
        else:
            self._run_online_tasks()

        self.root.after(0, self._schedule_connectivity_check)

        self.log("Startup checks complete.", "info")

    def _run_online_tasks(self, previous_version=None):
        def run_update_check():
            try:
                self.check_version_mismatch()
            except Exception as e:
                with contextlib.suppress(Exception):
                    self.log(f"Error checking for updates! ({e})", "error")

        def run_manifest_fetch():
            try:
                if self._fetch_version_manifest():
                    self.root.after(0, lambda: self._apply_version_list_keeping(previous_version))
                else:
                    self.root.after(0, lambda: self._set_version_list([], error=True))
            except Exception as e:
                with contextlib.suppress(Exception):
                    self.log(f"Error loading versions! ({e})", "error")
                self.root.after(0, lambda: self._set_version_list([], error=True))

        threads = [
            threading.Thread(target=run_update_check, daemon=True),
            threading.Thread(target=run_manifest_fetch, daemon=True),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    def _on_first_map(self, event):
        if self._ui_ready:
            return
        self._ui_ready = True
        self.root.unbind("<Map>")
        self.root.after(50, self._right_align_notifications)
        if self._pending_no_internet_popup:
            self._pending_no_internet_popup = False
            self._show_no_internet_info()
        if self._pending_update_version:
            remote_version, remote_numeric, remote_type = self._pending_update_version
            self._pending_update_version = None
            self._show_update_popup(remote_version, remote_numeric, remote_type)

    def _hide_all_windows(self):
        self._hidden_windows = []
        for w in self.root.winfo_children():
            if isinstance(w, tk.Toplevel) and w.winfo_viewable():
                w.withdraw()
                self._hidden_windows.append(w)
        self.root.withdraw()

    def _restore_all_windows(self):
        self.root.deiconify()
        for w in getattr(self, "_hidden_windows", []):
            with contextlib.suppress(Exception):
                if w.winfo_exists():
                    w.deiconify()
        self._hidden_windows = []