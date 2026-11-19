"""Headless stand-ins for the keyboard and clipboard."""

class DummyKeyboard:
    """Fallback dummy keyboard for testing and headless environments without display."""

    def __init__(self):
        self.pressed_keys = []
        self.tapped_keys = []

    def press(self, key):
        self.pressed_keys.append(key)

    def release(self, key):
        if key in self.pressed_keys:
            self.pressed_keys.remove(key)

    def tap(self, key):
        self.tapped_keys.append(key)


class DummyClipboard:
    """Fallback dummy clipboard for testing and headless environments."""

    def __init__(self, initial_text: str = ""):
        self._text = initial_text

    def paste(self) -> str:
        return self._text

    def copy(self, text: str):
        self._text = text
