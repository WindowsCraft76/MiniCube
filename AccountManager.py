import json
from Config import ACCOUNTS_FILE

class AccountManager:
    def __init__(self, app=None):
        self.app = app
        self.accounts = []
        self.load_accounts()

    def load_accounts(self):
        if ACCOUNTS_FILE.exists():
            try:
                with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                    self.accounts = json.load(f)
            except Exception as e:
                if self.app: self.app.log(f"Error loading accounts: {e}", "error")
                self.accounts = []
        else:
            self.accounts = []

    def save_accounts(self):
        try:
            with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.accounts, f, indent=4)
        except Exception as e:
            if self.app: self.app.log(f"Error saving accounts: {e}", "error")

    def add_account(self, account_data: dict):
        for acc in self.accounts:
            if acc.get("username") == account_data.get("username"):
                if self.app: self.app.log(f"Account {account_data.get('username')} already exists.", "warn")
                return

        self.accounts.append(account_data)
        self.save_accounts()
        if self.app: self.app.log(f"Account {account_data.get('username')} added to manager.", "success")

    def remove_account(self, username: str):
        self.accounts = [acc for acc in self.accounts if acc.get("username") != username]
        self.save_accounts()
        if self.app: self.app.log(f"Account {username} removed.", "info")

    def get_all_accounts(self):
        return self.accounts

    def get_account_by_name(self, username: str):
        for acc in self.accounts:
            if acc.get("username") == username:
                return acc
        return None