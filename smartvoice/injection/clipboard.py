from __future__ import annotations

import logging
import time


class ClipboardInjector:
    def __init__(self, injection_config: dict, privacy_config: dict) -> None:
        self.injection_config = injection_config
        self.privacy_config = privacy_config

    def inject(self, text: str) -> None:
        import keyboard
        import pyperclip

        if self.injection_config.get("strip_trailing_newline", True):
            text = text.rstrip("\r\n")

        previous = pyperclip.paste()
        pyperclip.copy(text)
        time.sleep(self.injection_config.get("paste_delay_ms", 80) / 1000)
        keyboard.press_and_release("ctrl+v")
        time.sleep(self.injection_config.get("restore_delay_ms", 200) / 1000)

        if self.privacy_config.get("restore_clipboard_after_paste", True):
            pyperclip.copy(previous)
        logging.info("Injected %s characters via clipboard paste.", len(text))


class PrintInjector:
    def inject(self, text: str) -> None:
        print(text)


class NoopInjector:
    def inject(self, text: str) -> None:
        logging.info("No-inject mode: skipped paste of %s characters.", len(text))
