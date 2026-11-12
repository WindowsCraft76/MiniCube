import tkinter as tk


class ScrollingButton(tk.Button):
    _SCROLL_INTERVAL_MS = 120
    _SCROLL_PAUSE_MS = 1000

    def __init__(self, *args, **kwargs):
        self._scroll_ready = False
        self._full_text = ""
        self._scroll_position = 0
        self._scroll_direction = -1
        self._scroll_after_id = None
        super().__init__(*args, **kwargs)

        self._full_text = str(self.cget("text"))
        self._scroll_ready = True
        self.bind("<Configure>", self._refresh_scroll, add="+")
        self.bind("<Destroy>", self._on_destroy, add="+")
        self.after_idle(self._refresh_scroll)

    def configure(self, cnf=None, **kwargs):
        text = kwargs.get("text")
        if text is None and isinstance(cnf, dict):
            text = cnf.get("text")

        result = super().configure(cnf, **kwargs)
        if text is not None and self._scroll_ready:
            self._full_text = str(text)
            self._scroll_position = 0
            self._cancel_scroll()
            self.after_idle(self._refresh_scroll)
        return result

    config = configure

    def _available_text_width(self, widget_width=None):
        width = self.winfo_width() if widget_width is None else widget_width
        if width <= 1:
            return None
        padding = (
            2 * self.winfo_pixels(self.cget("padx"))
            + 2 * self.winfo_pixels(self.cget("borderwidth"))
            + 2 * self.winfo_pixels(self.cget("highlightthickness"))
        )
        return max(0, width - padding)

    def _text_width(self, text):
        return int(self.tk.call("font", "measure", self.cget("font"), text))

    def _refresh_scroll(self, event=None):
        if not self._scroll_ready:
            return

        available = self._available_text_width(event.width if event is not None else None)
        if available is None:
            return
        if not self._full_text or self._text_width(self._full_text) <= available:
            self._cancel_scroll()
            self._scroll_position = 0
            self._scroll_direction = -1
            if self.cget("text") != self._full_text:
                super().configure(text=self._full_text)
            return

        if self._scroll_after_id is None:
            self._animate_scroll()

    def _max_start(self, available):
        start = len(self._full_text) - 1
        while start > 0 and self._text_width(self._full_text[start - 1:]) <= available:
            start -= 1
        return start

    def _animate_scroll(self):
        self._scroll_after_id = None
        if not self.winfo_exists():
            return

        available = self._available_text_width()
        if available is None:
            self._scroll_after_id = self.after(50, self._animate_scroll)
            return
        if self._text_width(self._full_text) <= available:
            self._scroll_position = 0
            self._scroll_direction = -1
            super().configure(text=self._full_text)
            return

        max_start = self._max_start(available)
        pos = max(0, min(self._scroll_position, max_start))

        end = pos
        while end < len(self._full_text) and self._text_width(self._full_text[pos:end + 1]) <= available:
            end += 1
        if end == pos:
            if available <= 0:
                self._scroll_after_id = self.after(50, self._animate_scroll)
                return
            end += 1
        super().configure(text=self._full_text[pos:end])

        if self._scroll_direction == 1 and pos >= max_start:
            self._scroll_direction = -1
            delay = self._SCROLL_PAUSE_MS
        elif self._scroll_direction == -1 and pos <= 0:
            self._scroll_direction = 1
            delay = self._SCROLL_PAUSE_MS
        else:
            pos += self._scroll_direction
            delay = self._SCROLL_INTERVAL_MS

        self._scroll_position = pos
        self._scroll_after_id = self.after(delay, self._animate_scroll)

    def _cancel_scroll(self):
        if self._scroll_after_id is not None:
            self.after_cancel(self._scroll_after_id)
            self._scroll_after_id = None

    def _on_destroy(self, event):
        if event.widget is self:
            self._cancel_scroll()
