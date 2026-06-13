import time
from pypresence import Presence
from Config import CLIENT_ID_RPC, PAGE_URL
from VersionsManager import get_info_version

class DiscordRPC:
    def __init__(self, app=None):
        self.app = app
        self.rpc = None
        self.start_time = None

    def _update(self, details: str, small_image: str = None, small_text: str = None):
        if not self.rpc:
            return
        try:
            payload = {
                "large_image": "logo_1024x1024",
                "large_text": f"Mini Cube - {get_info_version()}",
                "details": details,
                "start": self.start_time,
                "buttons": [{"label": "Download Mini Cube", "url": f"{PAGE_URL}/releases"}]
            }

            if small_image:
                payload["small_image"] = small_image
            if small_text:
                payload["small_text"] = small_text

            self.rpc.update(**payload)
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

    def update(self, details: str, small_image: str = None, small_text: str = None):
        self._update(details=details, small_image=small_image, small_text=small_text)
        if self.app:
            self.app.log("Updated Discord RPC presence", "info")

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