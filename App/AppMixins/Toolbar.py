import contextlib
import os


class ToolbarMixin:

    def _find_toolbar_index_by_label(self, label):
        try:
            end = self.toolbar.index("end")
            if end is None:
                return None
            for i in range(end + 1):
                try:
                    lbl = self.toolbar.entrycget(i, "label")
                    if lbl == label:
                        return i
                except Exception:
                    continue
        except Exception:
            return None
        return None

    def _set_notification(self, key, label, command):
        self._notifications = {key: (label, command)}
        self._render_notifications()

    def _clear_notification(self, key):
        if key in self._notifications:
            self._notifications = {}
            self._render_notifications()

    def _render_notifications(self):
        with contextlib.suppress(Exception):
            end = self.toolbar.index("end")
            for i in range(end, self._notif_anchor_index, -1):
                self.toolbar.delete(i)
            for label, command in self._notifications.values():
                self.toolbar.add_command(label=label, command=command)
        self._right_align_notifications()
        self.root.after(250, self._right_align_notifications)

    def _right_align_notifications(self):
        if os.name != "nt":
            return
        job = getattr(self, "_align_after_id", None)
        if job is not None:
            with contextlib.suppress(Exception):
                self.root.after_cancel(job)
        self._align_after_id = self.root.after(60, self._apply_right_align)

    def _resolve_root_hwnd(self):
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        GA_ROOT = 2
        user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        user32.GetAncestor.restype = wintypes.HWND
        user32.GetMenu.argtypes = [wintypes.HWND]
        user32.GetMenu.restype = wintypes.HMENU

        candidates = []
        with contextlib.suppress(Exception):
            frame = self.root.wm_frame()
            if frame:
                candidates.append(int(frame, 16))
        with contextlib.suppress(Exception):
            candidates.append(user32.GetAncestor(self.root.winfo_id(), GA_ROOT))

        for hwnd in candidates:
            if hwnd and user32.GetMenu(hwnd):
                return hwnd
        return candidates[0] if candidates else 0

    def _apply_right_align(self):
        self._align_after_id = None
        try:
            import ctypes
            from ctypes import wintypes

            class MENUITEMINFOW(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.UINT), ("fMask", wintypes.UINT),
                    ("fType", wintypes.UINT), ("fState", wintypes.UINT),
                    ("wID", wintypes.UINT), ("hSubMenu", wintypes.HMENU),
                    ("hbmpChecked", wintypes.HBITMAP), ("hbmpUnchecked", wintypes.HBITMAP),
                    ("dwItemData", ctypes.c_size_t), ("dwTypeData", wintypes.LPWSTR),
                    ("cch", wintypes.UINT), ("hbmpItem", wintypes.HBITMAP),
                ]

            user32 = ctypes.windll.user32
            user32.GetMenu.argtypes = [wintypes.HWND]
            user32.GetMenu.restype = wintypes.HMENU
            user32.GetMenuItemCount.argtypes = [wintypes.HMENU]
            user32.GetMenuItemInfoW.argtypes = [wintypes.HMENU, wintypes.UINT, wintypes.BOOL, ctypes.POINTER(MENUITEMINFOW)]
            user32.SetMenuItemInfoW.argtypes = [wintypes.HMENU, wintypes.UINT, wintypes.BOOL, ctypes.POINTER(MENUITEMINFOW)]
            user32.DrawMenuBar.argtypes = [wintypes.HWND]

            hwnd = self._resolve_root_hwnd()
            if not hwnd:
                if self.debug:
                    self.log("Notification align: no window handle found.", "debug")
                return
            hmenu = user32.GetMenu(hwnd)
            if not hmenu:
                if self.debug:
                    self.log("Notification align: GetMenu returned no native menu.", "debug")
                return

            MIIM_FTYPE = 0x00000100
            MFT_RIGHTJUSTIFY = 0x00004000
            item_count = user32.GetMenuItemCount(hmenu)
            if item_count <= self._notif_anchor_index:
                return

            applied = 0
            for pos in range(self._notif_anchor_index, item_count):
                info = MENUITEMINFOW()
                info.cbSize = ctypes.sizeof(MENUITEMINFOW)
                info.fMask = MIIM_FTYPE
                if not user32.GetMenuItemInfoW(hmenu, pos, True, ctypes.byref(info)):
                    continue
                info.fType |= MFT_RIGHTJUSTIFY
                if user32.SetMenuItemInfoW(hmenu, pos, True, ctypes.byref(info)):
                    applied += 1
            user32.DrawMenuBar(hwnd)
            if self.debug:
                self.log(f"Notification align: flagged {applied}/{item_count - self._notif_anchor_index} item(s).", "debug")
        except Exception as e:
            if self.debug:
                self.log(f"Notification align failed: {e}", "debug")