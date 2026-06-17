from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Protocol

from smartvoice.core.models import AudioBuffer, WorkflowResult


class Recorder(Protocol):
    def start(self) -> None: ...
    def stop(self) -> AudioBuffer: ...
    def cancel(self) -> None: ...


class Transcriber(Protocol):
    def transcribe(self, audio: AudioBuffer) -> str: ...
    def warmup(self) -> None: ...


class Processor(Protocol):
    def process(self, raw_text: str, mode: str) -> str: ...


class Injector(Protocol):
    def inject(self, text: str) -> None: ...


class History(Protocol):
    def save(self, result: WorkflowResult) -> None: ...
    def latest_success(self) -> dict | None: ...


class SmartVoiceWorkflow:
    def __init__(
        self,
        *,
        recorder: Recorder,
        transcriber: Transcriber,
        processor: Processor,
        injector: Injector,
        history: History,
        default_mode: str,
        min_recording_ms: int = 300,
        audio_debug_path: str | None = None,
    ) -> None:
        self.recorder = recorder
        self.transcriber = transcriber
        self.processor = processor
        self.injector = injector
        self.history = history
        self.mode = default_mode
        self.min_recording_ms = min_recording_ms
        self.state = "idle"
        self.last_result: WorkflowResult | None = None
        self.audio_debug_path = audio_debug_path

    def warmup(self) -> None:
        if self.state != "idle":
            return
        self.state = "loading_model"
        logging.info("Loading transcription model...")
        try:
            self.transcriber.warmup()
            logging.info("Transcription model ready.")
        finally:
            self.state = "idle"

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        logging.info("Mode: %s", mode)

    def start_recording(self) -> None:
        if self.state != "idle":
            logging.debug("Ignoring record request while state=%s", self.state)
            return
        self.state = "recording"
        logging.info("Recording...")
        self.recorder.start()

    def cancel_recording(self) -> None:
        if self.state != "recording":
            return
        self.recorder.cancel()
        self.state = "idle"
        logging.info("Recording cancelled.")

    def stop_and_process(self) -> WorkflowResult:
        if self.state != "recording":
            return WorkflowResult(mode=self.mode, error=f"Cannot stop from state {self.state}")

        try:
            audio = self.recorder.stop()
            logging.info(
                "Audio level: rms=%.5f peak=%.5f duration=%.2fs",
                audio.rms,
                audio.peak,
                audio.duration_ms / 1000,
            )
            if self.audio_debug_path:
                from pathlib import Path

                from smartvoice.audio.recorder import save_wav

                save_wav(audio, Path(self.audio_debug_path))
                logging.info("Saved debug audio: %s", self.audio_debug_path)
            if audio.duration_ms < self.min_recording_ms:
                result = WorkflowResult(
                    mode=self.mode,
                    audio_duration_ms=audio.duration_ms,
                    error="Recording too short.",
                    created_at=datetime.now(timezone.utc),
                )
                self._finish(result)
                return result
            if audio.rms < 0.001 and audio.peak < 0.01:
                result = WorkflowResult(
                    mode=self.mode,
                    audio_duration_ms=audio.duration_ms,
                    error="Recording level is too low. Check the selected microphone.",
                    created_at=datetime.now(timezone.utc),
                )
                self._finish(result)
                return result

            self.state = "transcribing"
            logging.info("Transcribing...")
            raw_text = self.transcriber.transcribe(audio).strip()

            self.state = "processing"
            final_text = self.processor.process(raw_text, self.mode)
            if final_text:
                logging.info("Transcript: %s", final_text)
            else:
                logging.info("No transcript produced.")

            self.state = "injecting"
            if final_text:
                self.injector.inject(final_text)

            result = WorkflowResult(
                mode=self.mode,
                raw_text=raw_text,
                final_text=final_text,
                audio_duration_ms=audio.duration_ms,
                created_at=datetime.now(timezone.utc),
            )
            self._finish(result)
            logging.info("Done.")
            return result
        except Exception as exc:
            logging.exception("SmartVoice workflow failed.")
            result = WorkflowResult(
                mode=self.mode,
                error=str(exc),
                created_at=datetime.now(timezone.utc),
            )
            self._finish(result)
            return result

    def retry_injection(self) -> None:
        if self.last_result and self.last_result.final_text:
            self.injector.inject(self.last_result.final_text)
            logging.info("Re-injected last in-memory transcript.")
            return
        row = self.history.latest_success()
        if row and row.get("final_text"):
            self.injector.inject(row["final_text"])
            logging.info("Re-injected latest transcript from history.")

    def _finish(self, result: WorkflowResult) -> None:
        self.last_result = result
        self.history.save(result)
        self.state = "idle"
