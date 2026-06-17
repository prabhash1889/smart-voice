from types import SimpleNamespace

from smartvoice.core.models import AudioBuffer
from smartvoice.transcription.credentials import get_openai_api_key
from smartvoice.transcription.factory import build_transcriber
from smartvoice.transcription.faster_whisper_engine import FasterWhisperEngine
from smartvoice.transcription.openai_engine import OpenAITranscriptionEngine


class Segment:
    def __init__(self, text):
        self.text = text


class FakeWhisperModel:
    def __init__(self):
        self.calls = []

    def transcribe(self, samples, **kwargs):
        del samples
        self.calls.append(kwargs)
        if kwargs["vad_filter"]:
            return [], None
        return [Segment("hello world")], None


def test_faster_whisper_respects_vad_off():
    engine = FasterWhisperEngine({"vad_enabled": False, "language": "en", "beam_size": 5})
    engine._model = FakeWhisperModel()

    text = engine.transcribe(AudioBuffer(samples=[0.05] * 16000, sample_rate=16000))

    assert text == "hello world"
    assert [call["vad_filter"] for call in engine._model.calls] == [False]


def test_faster_whisper_retries_without_vad_when_enabled():
    engine = FasterWhisperEngine({"vad_enabled": True, "language": "en", "beam_size": 5})
    engine._model = FakeWhisperModel()

    text = engine.transcribe(AudioBuffer(samples=[0.05] * 16000, sample_rate=16000))

    assert text == "hello world"
    assert [call["vad_filter"] for call in engine._model.calls] == [True, False]


def test_openai_engine_requires_cloud_opt_in():
    try:
        build_transcriber({"engine": "openai"}, {"allow_cloud_transcription": False})
    except RuntimeError as exc:
        assert "allow_cloud_transcription" in str(exc)
    else:
        raise AssertionError("OpenAI transcription should require explicit cloud opt-in")


def test_openai_api_key_comes_from_environment(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    assert get_openai_api_key() == "test-key"


def test_openai_engine_uses_mocked_api_response():
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(text="mock transcript")

    client = SimpleNamespace(audio=SimpleNamespace(transcriptions=SimpleNamespace(create=create)))
    engine = OpenAITranscriptionEngine(
        {"openai_model": "gpt-4o-transcribe"},
        client=client,
    )

    text = engine.transcribe(AudioBuffer(samples=[0.05] * 16000, sample_rate=16000))

    assert text == "mock transcript"
    assert calls[0]["model"] == "gpt-4o-transcribe"
    assert calls[0]["file"].name.endswith(".wav")
