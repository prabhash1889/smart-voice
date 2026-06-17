from smartvoice.hotkeys.listener import HotkeyListener


class FakeKeyboard:
    def __init__(self, pressed):
        self.pressed = set(pressed)

    def is_pressed(self, key):
        return key in self.pressed


class FakeWorkflow:
    def __init__(self):
        self.state = "idle"
        self.mode = "raw_transcript"
        self.started = 0
        self.stopped = 0

    def start_recording(self):
        self.state = "recording"
        self.started += 1

    def stop_and_process(self):
        self.state = "idle"
        self.stopped += 1

    def set_mode(self, mode):
        self.mode = mode


def test_push_to_talk_requires_modifiers():
    workflow = FakeWorkflow()
    listener = HotkeyListener({"push_to_talk": "ctrl+alt+space"}, workflow)

    assert listener._push_to_talk_is_pressed(FakeKeyboard(["ctrl"])) is False
    assert listener._push_to_talk_is_pressed(FakeKeyboard(["ctrl", "alt"])) is True


def test_press_release_starts_and_stops_once(monkeypatch):
    workflow = FakeWorkflow()
    listener = HotkeyListener({"push_to_talk": "ctrl+alt+space"}, workflow)

    import smartvoice.hotkeys.listener as listener_module

    class KeyboardModule:
        @staticmethod
        def is_pressed(key):
            return key in {"ctrl", "alt"}

    monkeypatch.setitem(__import__("sys").modules, "keyboard", KeyboardModule)

    listener._on_press(None)
    listener._on_press(None)
    listener._on_release(None)

    assert workflow.started == 1
    assert workflow.stopped == 1


def test_cycle_mode():
    workflow = FakeWorkflow()
    listener = HotkeyListener(
        {"push_to_talk": "ctrl+alt+space"},
        workflow,
        {"available": ["raw_transcript", "coding_prompt"]},
    )

    listener.cycle_mode()

    assert workflow.mode == "coding_prompt"
