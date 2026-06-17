from __future__ import annotations

import tempfile
from pathlib import Path

from smartvoice.audio.recorder import save_wav
from smartvoice.core.models import AudioBuffer
from smartvoice.transcription.credentials import get_openai_api_key


class OpenAITranscriptionEngine:
    def __init__(self, config: dict, *, api_key: str | None = None, client=None) -> None:
        self.config = config
        self.api_key = api_key
        self._client = client

    @property
    def client(self):
        if self._client is None:
            api_key = self.api_key or get_openai_api_key()
            if not api_key:
                raise RuntimeError("OPENAI_API_KEY is required for OpenAI transcription.")
            try:
                from openai import OpenAI
            except ModuleNotFoundError as exc:
                raise RuntimeError("Install the openai package to use OpenAI transcription.") from exc
            self._client = OpenAI(api_key=api_key)
        return self._client

    def transcribe(self, audio: AudioBuffer) -> str:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            temp_path = Path(tmp.name)
        try:
            save_wav(audio, temp_path)
            with temp_path.open("rb") as audio_file:
                response = self.client.audio.transcriptions.create(
                    model=self.config.get("openai_model", "gpt-4o-transcribe"),
                    file=audio_file,
                )
            if isinstance(response, dict):
                return str(response.get("text", "")).strip()
            return str(getattr(response, "text", "")).strip()
        finally:
            temp_path.unlink(missing_ok=True)

    def warmup(self) -> None:
        return None
