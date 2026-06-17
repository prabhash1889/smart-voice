from __future__ import annotations

from smartvoice.transcription.faster_whisper_engine import FasterWhisperEngine
from smartvoice.transcription.openai_engine import OpenAITranscriptionEngine


def build_transcriber(transcription_config: dict, privacy_config: dict):
    engine = transcription_config.get("engine", "faster_whisper")
    if engine == "faster_whisper":
        return FasterWhisperEngine(transcription_config)
    if engine == "openai":
        if not privacy_config.get("allow_cloud_transcription", False):
            raise RuntimeError(
                "OpenAI transcription is disabled. Set privacy.allow_cloud_transcription=true to send audio to the cloud."
            )
        return OpenAITranscriptionEngine(transcription_config)
    raise ValueError(f"Unsupported transcription engine: {engine}")
