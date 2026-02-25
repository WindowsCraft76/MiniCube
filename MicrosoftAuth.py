import webbrowser
import http.server
import socketserver
import threading
import urllib.parse
import time
import requests
from tkinter import messagebox
from Config import CLIENT_ID, REDIRECT_URI, SCOPE


class MicrosoftAuth:
    HTML_SUCCESS = """
    <html>
        <head><title>Connection successful !</title></head>
        <body style="font-family:sans-serif; text-align:center; margin-top:50px;">
            <img src="data:image/png;base64,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" alt="Icon" style="width:100px;height:100px;">
            <h1 style="color:green;">Connection successful !</h1>
            <p>You can close this window.</p>
        </body>
    </html>
    """

    HTML_ERROR = """
    <html>
        <head><title>Authentication error</title></head>
        <body style="font-family:sans-serif; text-align:center; margin-top:50px;">
            <img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAALQAAAC0CAYAAAA9zQYyAAAHQ0lEQVR4nOzdv4scZRjA8Wd0rXKYkIDEQiFgOgXFxvJstJf8AZaChY12Qi5oaWufPyCBFAFBLBaLpAhoTCwkRIJ4xEgulwvcGS9q1tu92+SZzb678+N9Z973eb/fZt6dnZtpPix7M+/sDISC9fn1D9bGy1Ehp0WKYTEqzoxff/nGuaFQkAohr5URuwJ3qADtoWqIXYHbZ4BuWDvErsDdNkDXKAxiV+BuEqCX1C1iV+CuGqDnFAdiV+BeFKAPihuxK3DPljXoNBG7Ave47EDbQuwqX9xZgM4Dsau8cJsFnTdiV/ZxmwIN4jrZxJ08aBD7yA7uJEGDOGRp404G9Pn7Z9YmA4X4h/WfhPx3ZGXlYFQM5QD3ZyfODiWBogY9D7ErcLfrKWJXaeCODnQdxK7AXa3liF3FizsK0D4QuwJ3ueaIXcWFuzfQIRG7yhW3f8Su+sfdKeg+ELuyjrs7xK76wR0cdEyIXVnB3T9iV93hDgI6BcSuUsMdL2JXYXF7A50yYlex4k4PsSv/uFuBtojYVd+47SB25Qd3bdA5IXbVFW77iF01x10JNIjd+cadL2JX9XA7QYO4fk1xg7hqy3GXQIPYX8twg7ht83EXIA7fjbu/yuAFoWDt4x7DLj4Zvj86snJYXj3+yt6nxotCftv8537p9dbOppC/th+elOs/XpTLl3+R0ah4dzBeubX9QLZuPphsAO72zSLWHTl09MkY3M3SiGcbzK4Ad7MWIXYF7uotQqwbLHoT3ItrgtgVuJ+tKmLdoOqG4N7PJ2JXOeNuglhXGbQuN9xdIHaVA+62iHWNQOus4u4TsStLuH0i1rUGrUsdd4yIXaWIOxRinVfQulRwp4TYVcy4u0CsCwZaFxtuC4hdxYC7a8S6TkDr+sJtGbGrLnH3iVjXOWhdaNw5InYVAncsiHW9gtb5wg3i5bXBHSNiXTSgdXVxg7h5VXDHjlgXJWidCzeI/adxr28cSwaxLnrQuinuK5duyfGXj8lbb5/cWx4V8tPW9gm5du2CfH/pqjz667GkWFKgdXf+uCffXLw3GYO7eRqxhZIFrQN3vawh1pkArQP3/Cwj1pkDrcsddy6IdaZB63LBnSNiXTagddZw545YlyVoXaq4QTy/7EHrYscN4uUB2lEsuEFcL0BXqGvcIG4eoGsWCjeI/QToFrXFDWL/AdpTVXGDOGyADtA83Ddu/Q7iDgJ04Ma4L1y4Ixs7W0LhAzSZCtBkKkCTqQBNpgI0mQrQZCpAk6kATaYCNJkK0GQqQJOpAE2mAjSZCtBkKkCTqQBNpgI0mQrQZCpAk6kATaYCNJkK0GQqQJOpAE2mAjSZCtBkKkCTqQBNpgI0mWpw7OsHk8G9jw8LUYq9dO6/ybIYqU/oKexx4KbYmyKebe5XDnBTjLkQ65Z+hwY39VkVxLpa/xSCm7qoLmJd47Mc4CaftUGs83LaDtzUJF+Idd7PQ4ObFhUCsS7ohRVw07jQiHWdXSkEd151iVjXy6VvcNusL8S63udygDvtYkCsi2pyErjTKDbEumhn24E7rmJGrEti+qjGvbnyr8hJocAd/+15eXzlkaRWcvOhj24P5PVvD03GP7+3I+S3184Xk+XGTnqYxyU9wX8Kexy4mzdFbCEzd6yAu16WEOtM3oIF7vlZRawzf09h7rhzQKzL6ibZXHDnhliX7V3f1nDnjFjHzxhIurhB/GyAnil23CBeHKAXFAtuEFcP0BXrGjeImwXoBoXCDeL2AbplbXGD2G+A9lhV3CAOF6ADpXE/3P1bbt8FcRcBmkwFaDIVoMlUgCZTAZpMBWgyFaDJVIAmUwGaTAVoMhWgyVSAJlMBmkwFaDIVoMlUgCZTAZpMBWgyFaDJVIAmUwGaTAVoMhWgyVSAJlMBmkwFaDIVoMlUgCZTAZpM9VwhMhSixCsKOTNZTld8ceqd1b1Xp0ciqxJ563d3JaX2f073T0mpFB5eP0V89fb22pN18zaMHTegwxcr6HmIS+8v20GMuAEdvphAL0Nc2lZqFAtuQIevb9B1EJf+ThrWJ25Ah68P0E0Rl/YhHuoaN6DD1xVoH4hL+xPPdYEb0OELCdo34tK+JWChcAM6fL5Bh0RcOo50lE/cgA6fD9BdIS4dU3qoLW5Ah68p6D4Ql44vPdcEN6DDVwd034h1UT3etCpuQIdvGeiYEOuifV7vItyADt880LEi1iXxAOpZ3IAO3xR0Coh1yT1RfYx7fWM3iVmB01IDvYdigvi7m5trkljJgdZ9tPrm6kiK6HGnADplxLqkQetixh0raCuIdWZA62LDHRNoi4h1JkHrYsDdN2jriHXmQev6wt0H6JwQ67ICresSd1egc0Wsyxa0LjTukKBBXA7QM4XA7Rs0iN0BekG+cPsADeJqAbpibXA3BQ3i+gG6QXVx1wEN4nYBumVVcC8DDWJ/AdpjLtzzQIM4TIAOlMY9BQ3i8AG6g059+OnqubNfDYWC9z8AAAD//6iv/VQAAAAGSURBVAMA1UFDv1Y6d+kAAAAASUVORK5CYII=" alt="Icon" style="width:100px;height:100px;">
            <h1 style="color:red;">Authentication failed</h1>
            <p>{error}</p>
        </body>
    </html>
    """

    def __init__(self, app=None):
        self.app = app
        self.auth_code = None
        self.auth_failed = False

    def login(self):
        self.auth_code = None
        self.auth_failed = False

        params = {
            "client_id": CLIENT_ID,
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPE,
            "response_mode": "query"
        }

        auth_url = "https://login.live.com/oauth20_authorize.srf?" + urllib.parse.urlencode(params)
        webbrowser.open(auth_url)

        self._start_local_server()

        if self.app:
            self.app.log("Waiting for Microsoft login in browser...", "info")

        start = time.time()
        while self.auth_code is None and not self.auth_failed and time.time() - start < 120:
            time.sleep(0.5)

        if self.auth_failed or not self.auth_code:
            if self.app:
                self.app.log("Authentication failed or canceled.", "error")
            return None

        try:
            ms_access, ms_refresh = self._get_microsoft_token(self.auth_code)
            xbl_token = self._get_xbox_live_token(ms_access)
            xsts_token, uhs = self._get_xsts_token(xbl_token)
            mc_token = self._get_minecraft_token(xsts_token, uhs)
            profile = self._get_minecraft_profile(mc_token)

            if self.app:
                self.app.log(f"Authentication successful! Welcome {profile['name']}", "success")

            return {
                "username": profile["name"],
                "uuid": profile["id"],
                "access_token": mc_token,
                "refresh_token": ms_refresh
            }

        except Exception as e:
            self.auth_failed = True
            if self.app:
                self.app.log(f"Authentication failed!: {e}", "error")
                messagebox.showerror("Authentication Failed", str(e))
            return None

    def _start_local_server(self):
        auth = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                query = urllib.parse.parse_qs(
                    urllib.parse.urlparse(self.path).query
                )

                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()

                if "error" in query:
                    auth.auth_failed = True
                    error_msg = query.get("error_description", ["Unknown error"])[0]
                    html = auth.HTML_ERROR.format(error=error_msg)
                    self.wfile.write(html.encode("utf-8"))

                    if auth.app:
                        auth.app.log(f"Authentication failed: {error_msg}", "error")

                elif "code" in query:
                    auth.auth_code = query["code"][0]
                    self.wfile.write(auth.HTML_SUCCESS.encode("utf-8"))

                else:
                    auth.auth_failed = True
                    html = auth.HTML_ERROR.format(error="Invalid request.")
                    self.wfile.write(html.encode("utf-8"))

            def log_message(self, format, *args):
                pass

        def run_server():
            socketserver.TCPServer.allow_reuse_address = True
            with socketserver.TCPServer(("localhost", 8080), Handler) as httpd:
                httpd.handle_request()

        threading.Thread(target=run_server, daemon=True).start()

    # ---------------- MICROSOFT TOKEN ----------------
    def _get_microsoft_token(self, code):
        url = "https://login.live.com/oauth20_token.srf"
        data = {
            "client_id": CLIENT_ID,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPE
        }

        r = requests.post(url, data=data)
        r.raise_for_status()
        js = r.json()

        return js["access_token"], js.get("refresh_token", "")

    # ---------------- XBOX LIVE ----------------
    def _get_xbox_live_token(self, ms_access):
        url = "https://user.auth.xboxlive.com/user/authenticate"
        payload = {
            "Properties": {
                "AuthMethod": "RPS",
                "SiteName": "user.auth.xboxlive.com",
                "RpsTicket": f"d={ms_access}"
            },
            "RelyingParty": "http://auth.xboxlive.com",
            "TokenType": "JWT"
        }

        r = requests.post(url, json=payload)
        r.raise_for_status()
        return r.json()["Token"]

    # ---------------- XSTS ----------------
    def _get_xsts_token(self, xbl_token):
        url = "https://xsts.auth.xboxlive.com/xsts/authorize"
        payload = {
            "Properties": {
                "SandboxId": "RETAIL",
                "UserTokens": [xbl_token]
            },
            "RelyingParty": "rp://api.minecraftservices.com/",
            "TokenType": "JWT"
        }

        r = requests.post(url, json=payload)
        r.raise_for_status()
        js = r.json()

        uhs = js["DisplayClaims"]["xui"][0]["uhs"]
        return js["Token"], uhs

    # ---------------- MINECRAFT TOKEN ----------------
    def _get_minecraft_token(self, xsts_token, uhs):
        url = "https://api.minecraftservices.com/authentication/login_with_xbox"
        payload = {
            "identityToken": f"XBL3.0 x={uhs};{xsts_token}"
        }

        r = requests.post(url, json=payload)
        r.raise_for_status()
        return r.json()["access_token"]

    # ---------------- PROFILE ----------------
    def _get_minecraft_profile(self, mc_token):
        headers = {
            "Authorization": f"Bearer {mc_token}"
        }

        r = requests.get(
            "https://api.minecraftservices.com/minecraft/profile",
            headers=headers
        )
        r.raise_for_status()
        return r.json()