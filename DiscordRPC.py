# Discord rpc class, used to manage the discord rpc presence of the app

import time
from pypresence import Presence
from Config import CLIENT_ID_RPC
from VersionsManager import get_info_version

class DiscordRPC:
    def __init__(self, app=None):
        self.app = app
        self.rpc = None
        self.start_time = None

    def _update(self, details: str):
        if not self.rpc:
            return
        try:
            self.rpc.update(
                large_image="logo_1024x1024",
                large_text=f"Mini Cube - {get_info_version()}",
                details=details,
                start=self.start_time,
                buttons=[{"label": "Download Mini Cube", "url": "https://github.com/WindowsCraft76/mini-cube/releases"}]
            )
        except Exception:
            pass

    def start_rpc(self):
        if self.rpc:
            return
        try:
            self.rpc = Presence(CLIENT_ID_RPC)
            self.rpc.connect()
            self.start_time = time.time()
            self._update(details="In the launcher")
            if self.app:
                self.app.log("Successfully connected to Discord RPC", "success")
        except Exception as e:
            if self.app:
                self.app.log(f"Failed to connect to Discord RPC!", "error")
            self.rpc = None

    def update_details(self, details: str):
        self._update(details=details)

    def is_running(self):
        return self.rpc is not None

    def stop_rpc(self):
        if not self.rpc:
            return
        try:
            self.rpc.clear()
            self.rpc.close()
        except Exception:
            if self.app:
                self.app.log("Failed to close Discord RPC!", "error")
        finally:
            self.rpc = None
            self.start_time = None
            if self.app:
                self.app.log("Discord RPC disconnected.", "info")