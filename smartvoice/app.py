from __future__ import annotations

from dataclasses import dataclass

from smartvoice.audio.recorder import SoundDeviceRecorder
from smartvoice.core.workflow import SmartVoiceWorkflow
from smartvoice.hotkeys.listener import HotkeyListener
from smartvoice.injection.clipboard import ClipboardInjector, NoopInjector
from smartvoice.processing.cleanup import ModeProcessor
from smartvoice.storage.config_store import ConfigStore
from smartvoice.storage.history_store import HistoryStore
from smartvoice.transcription.factory import build_transcriber


@dataclass
class SmartVoiceApp:
    config: dict
    workflow: SmartVoiceWorkflow
    hotkeys: HotkeyListener

    def warmup(self) -> None:
        self.workflow.warmup()


def build_app(
    *,
    inject: bool = True,
    mode: str | None = None,
    config_override: dict | None = None,
    audio_debug_path: str | None = None,
) -> SmartVoiceApp:
    config_store = ConfigStore()
    config = config_store.load()
    if config_override:
        config = config_store.merge(config, config_override)
    active_mode = mode or config["modes"]["default"]
    recorder = SoundDeviceRecorder(config["audio"], config["app"]["max_recording_seconds"])
    transcription_config = dict(config["transcription"])
    transcription_config["vad_enabled"] = config["audio"].get("vad_enabled", True)
    transcriber = build_transcriber(transcription_config, config["privacy"])
    processor = ModeProcessor.from_resource()
    injector = ClipboardInjector(config["injection"], config["privacy"]) if inject else NoopInjector()
    history = HistoryStore(limit=config["privacy"]["history_limit"])
    workflow = SmartVoiceWorkflow(
        recorder=recorder,
        transcriber=transcriber,
        processor=processor,
        injector=injector,
        history=history,
        default_mode=active_mode,
        audio_debug_path=audio_debug_path,
    )
    hotkeys = HotkeyListener(config["hotkeys"], workflow, config["modes"])
    return SmartVoiceApp(config=config, workflow=workflow, hotkeys=hotkeys)
