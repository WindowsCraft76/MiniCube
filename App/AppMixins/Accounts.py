import contextlib
import threading
import tkinter as tk
from tkinter import messagebox
from Config import (
    ASSETS,
    CACHE_DIR
)
from MicrosoftAuth import MicrosoftAuth
from SplashScreen import center_window


class AccountsMixin:

    def _on_account_selected(self, event=None):
        username = self.selected_account_var.get()
        if not username or username == "No account":
            return

        account_data = self.account_manager.get_account_by_name(username)
        if account_data and account_data.get("uuid"):
            self._update_account_prefs(last_used_account=account_data["uuid"])

    def toggle_accounts_manager_window(self):
        if getattr(self, "acc_win", None) and self.acc_win.winfo_exists():
            try:
                self.acc_win.deiconify()
                self.acc_win.lift()
                self.acc_win.focus_force()
            except Exception:
                pass
            return
        
        self.acc_win = tk.Toplevel(self.root)
        self.acc_win.title("Accounts Manager")
        self.acc_win.iconbitmap(str(ASSETS / "icon" / "icon_64x64.ico"))
        self.acc_win.resizable(False, False)
        center_window(self.acc_win, 300, 250)

        self.acc_list_container = tk.Frame(self.acc_win, relief=tk.SUNKEN, bd=1, bg="white")
        self.acc_list_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=1)

        self.acc_rows_frame = tk.Frame(self.acc_list_container, bg="white")
        self.acc_rows_frame.place(x=0, y=0, relwidth=1, relheight=1)

        self.acc_empty_label = tk.Label(
            self.acc_list_container,
            text="No account available",
            fg="gray"
        )

        self.acc_head_images = {}
        self.acc_row_widgets = {}
        self.selected_account_row = None

        btn_frame = tk.Frame(self.acc_win)
        btn_frame.pack(pady=10)

        self.add_account_btn = tk.Button(btn_frame, text="Add account", command=self.add_microsoft_account)
        self.add_account_btn.pack(side=tk.LEFT, padx=5)
        self._sync_online_widgets()

        self.refresh_account_listbox()

        self.acc_win.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        with contextlib.suppress(Exception):
            self.acc_win.destroy()
        self.acc_win = None

    def add_microsoft_account(self):
        if self.no_internet:
            messagebox.showwarning("Add account", "You are offline.\nAdding an account requires an internet connection.")
            return

        if hasattr(self, "add_account_btn"):
            self.add_account_btn.config(state="disabled")

        self._show_connecting_popup()

        def worker():
            ms_auth = MicrosoftAuth(app=self)
            account_data = ms_auth.login()
            self.root.after(0, lambda: self._on_login_finished(account_data))

        threading.Thread(target=worker, daemon=True).start()

    def _show_connecting_popup(self):
        self.connecting_win = tk.Toplevel(self.acc_win)
        self.connecting_win.title("Connecting...")
        self.connecting_win.resizable(False, False)
        with contextlib.suppress(Exception):
            self.connecting_win.iconbitmap(str(ASSETS / "icon" / "icon_64x64.ico"))
        center_window(self.connecting_win, 280, 90)
        self.connecting_win.transient(self.acc_win)
        self.connecting_win.protocol("WM_DELETE_WINDOW", lambda: None)

        tk.Label(
            self.connecting_win,
            text="Connecting to Microsoft...\nPlease continue in your browser.",
            justify="center",
            padx=15,
            pady=25
        ).pack()

        self.connecting_win.grab_set()

    def _on_login_finished(self, account_data):
        if getattr(self, "connecting_win", None) and self.connecting_win.winfo_exists():
            try:
                self.connecting_win.grab_release()
                self.connecting_win.destroy()
            except Exception:
                pass
        self.connecting_win = None

        if hasattr(self, "add_account_btn"):
            self.add_account_btn.config(state=self._online_only_state())

        if account_data:
            self.account_manager.add_account(account_data)
            self.refresh_account_listbox()
            self.refresh_accounts_ui()

    def refresh_accounts_ui(self):
        accounts = self.account_manager.get_all_accounts()

        if not accounts:
            self.account_menu['values'] = ["No account"]
            self.selected_account_var.set("No account")
            self.account_menu.config(state="disabled")
        else:
            names = [acc['username'] for acc in accounts]
            usernames_by_uuid = {acc.get('uuid'): acc['username'] for acc in accounts}
            self.account_menu['values'] = names

            if self.default_account in usernames_by_uuid:
                chosen = usernames_by_uuid[self.default_account]
            elif self.last_used_account in usernames_by_uuid:
                chosen = usernames_by_uuid[self.last_used_account]
            else:
                chosen = names[0]

            self.selected_account_var.set(chosen)
            self.account_menu.config(state="readonly")

        self.toggle_account_mode()

    def _get_head_photoimage(self, uuid, size=25):
        if not uuid:
            return None

        head_path = CACHE_DIR / f"{uuid}.png"
        if not head_path.exists():
            return None

        try:
            img = tk.PhotoImage(file=str(head_path))
            factor = max(1, img.width() // size)
            if factor > 1:
                img = img.subsample(factor, factor)
            return img
        except Exception:
            return None

    def _select_account_row(self, username):
        self.selected_account_row = username
        for uname, row in self.acc_row_widgets.items():
            color = "#cde6ff" if uname == username else "white"
            try:
                row.config(bg=color)
                for child in row.winfo_children():
                    child.config(bg=color)
            except Exception:
                pass

    def refresh_account_listbox(self):
        if not getattr(self, "acc_rows_frame", None):
            return

        try:
            if not self.acc_rows_frame.winfo_exists():
                return
        except tk.TclError:
            return

        for widget in self.acc_rows_frame.winfo_children():
            widget.destroy()
        self.acc_row_widgets = {}
        self.acc_head_images = {}

        accounts = self.account_manager.get_all_accounts()
        accounts = sorted(
            accounts,
            key=lambda acc: 0 if acc.get("uuid") == self.default_account else 1
        )

        if not accounts:
            self.acc_empty_label.place(relx=0.5, rely=0.5, anchor="center")
            self.selected_account_row = None
            return

        self.acc_empty_label.place_forget()

        for acc in accounts:
            username = acc.get("username")
            uuid = acc.get("uuid")

            row = tk.Frame(self.acc_rows_frame, height=40, cursor="hand2", bg="white")
            row.pack(fill=tk.X)
            row.pack_propagate(False)

            head_img = self._get_head_photoimage(uuid)
            if head_img is not None:
                self.acc_head_images[username] = head_img
                icon_label = tk.Label(row, image=head_img, bg="white")
            else:
                icon_label = tk.Label(row, width=4, bg="white")
            icon_label.pack(side=tk.LEFT, padx=(10, 4))

            options_btn = tk.Button(
                row, text="⋮", bg="white", relief=tk.FLAT,
                font=("Segoe UI", 12, "bold"), width=2,
                command=lambda u=username, uid=uuid: self._open_account_options_menu(u, uid)
            )
            options_btn.pack(side=tk.RIGHT, padx=(4, 10))

            star_label = tk.Label(
                row, text="★" if uuid == self.default_account else "",
                bg="white", fg="#f4b400", font=("Segoe UI", 12, "bold"), width=2
            )
            star_label.pack(side=tk.RIGHT)

            name_label = tk.Label(
                row, text=username, bg="white",
                font=("Segoe UI", 10), anchor="center"
            )
            name_label.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            for widget in (row, icon_label, name_label):
                widget.bind("<Button-1>", lambda e, u=username: self._select_account_row(u))

            self.acc_row_widgets[username] = row

        if self.selected_account_row in self.acc_row_widgets:
            self._select_account_row(self.selected_account_row)

    def _open_account_options_menu(self, username, uuid):
        self._select_account_row(username)
        is_default = (uuid == self.default_account)

        menu = tk.Menu(self.acc_win, tearoff=0)
        menu.add_command(
            label="Refresh token",
            state="disabled" if self.no_internet else "normal",
            command=lambda: self._refresh_selected_account_token(username),
        )
        if is_default:
            menu.add_command(label="Remove default account", command=lambda: self._unset_default_account(uuid))
        else:
            menu.add_command(label="Set as default account", command=lambda: self._set_default_account(uuid))
        menu.add_command(label="Delete account", command=lambda: self._delete_account(username))

        try:
            x = self.acc_win.winfo_pointerx()
            y = self.acc_win.winfo_pointery()
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _set_default_account(self, uuid):
        self._update_account_prefs(default_account=uuid)
        self.refresh_account_listbox()

    def _unset_default_account(self, uuid):
        if self.default_account == uuid:
            self._update_account_prefs(default_account=None)
        self.refresh_account_listbox()

    def _refresh_selected_account_token(self, username):
        if self.no_internet:
            messagebox.showwarning("Refresh token", "You are offline.\nRefreshing a token requires an internet connection.")
            return

        account_data = self.account_manager.get_account_by_name(username)
        if not account_data:
            return

        def worker():
            auth = MicrosoftAuth(app=self)
            refreshed = auth.refresh_token(account_data, force=True)

            def finish():
                if refreshed:
                    self.account_manager.update_account(refreshed)
                    if getattr(self, "acc_win", None) and self.acc_win.winfo_exists():
                        self.refresh_account_listbox()
                    self.refresh_accounts_ui()
                else:
                    messagebox.showerror(
                        "Authentication Error",
                        f"Failed to refresh token for {username}.\nPlease log in again."
                    )

            self.root.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def _delete_account(self, username):
        if self._minecraft_running() and username == self._playing_username:
            messagebox.showwarning(
                "Delete account",
                f"{username} is currently playing.\nStop the game before deleting this account."
            )
            return

        if not messagebox.askyesno("Delete account", f"Delete account {username}?"):
            return

        account_data = self.account_manager.get_account_by_name(username)
        uuid = account_data.get("uuid") if account_data else None

        self.account_manager.remove_account(username)
        if self.selected_account_row == username:
            self.selected_account_row = None

        updates = {}
        if uuid and self.default_account == uuid:
            updates["default_account"] = None
        if uuid and self.last_used_account == uuid:
            updates["last_used_account"] = None
        if updates:
            self._update_account_prefs(**updates)

        self.refresh_account_listbox()
        self.refresh_accounts_ui()

    def toggle_account_mode(self):
        has_official = len(self.account_manager.get_all_accounts()) > 0

        for widget in self.account_frame.winfo_children():
            widget.pack_forget()

        if self.is_offline_var.get():
            if not has_official:
                self.is_offline_var.set(False)
                self.toggle_account_mode()
                messagebox.showwarning(
                    "Warning",
                    "Connect at least one Microsoft account to unlock Offline mode."
                )
                return
            
            self.offline_label.pack(pady=(0, 2))
            self.offline_entry.pack(pady=(0, 0))
            self.log("Switching to offline mode.", "info")
        else:
            self.account_label.pack(pady=(0, 2))
            self.account_menu.pack(pady=(0, 0))
            self.log("Switching to online mode.", "info")