from __future__ import annotations

import logging
import time


class HotkeyListener:
    def __init__(self, hotkey_config: dict, workflow, modes_config: dict | None = None) -> None:
        self.hotkey_config = hotkey_config
        self.workflow = workflow
        self.modes = list((modes_config or {}).get("available", []))
        self._recording_started_by_hotkey = False

    def run_forever(self) -> None:
        import keyboard

        push_to_talk = self.hotkey_config["push_to_talk"]
        trigger_key = push_to_talk.split("+")[-1]
        keyboard.on_press_key(trigger_key, self._on_press, suppress=False)
        keyboard.on_release_key(trigger_key, self._on_release, suppress=False)
        keyboard.add_hotkey(self.hotkey_config["cancel"], self.workflow.cancel_recording)
        keyboard.add_hotkey(self.hotkey_config["retry_injection"], self.workflow.retry_injection)
        if "cycle_mode" in self.hotkey_config:
            keyboard.add_hotkey(self.hotkey_config["cycle_mode"], self.cycle_mode)

        while True:
            time.sleep(0.25)

    def _on_press(self, event) -> None:
        import keyboard

        del event
        if self._recording_started_by_hotkey:
            return
        if self._push_to_talk_is_pressed(keyboard):
            self._recording_started_by_hotkey = True
            self.workflow.start_recording()

    def _on_release(self, event) -> None:
        del event
        if self._recording_started_by_hotkey and self.workflow.state == "recording":
            self._recording_started_by_hotkey = False
            self.workflow.stop_and_process()
        else:
            self._recording_started_by_hotkey = False

    def _push_to_talk_is_pressed(self, keyboard_module) -> bool:
        keys = self.hotkey_config["push_to_talk"].split("+")
        return all(keyboard_module.is_pressed(key) for key in keys[:-1])

    def cycle_mode(self) -> None:
        if not self.modes:
            return
        try:
            index = self.modes.index(self.workflow.mode)
        except ValueError:
            index = -1
        next_mode = self.modes[(index + 1) % len(self.modes)]
        self.workflow.set_mode(next_mode)
        logging.info("Mode changed to %s", next_mode)
