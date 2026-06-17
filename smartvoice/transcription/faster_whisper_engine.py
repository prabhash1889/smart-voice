from __future__ import annotations

import importlib
import importlib.machinery
import logging
import os
import sys
import types

from smartvoice.core.models import AudioBuffer


class FasterWhisperEngine:
    def __init__(self, config: dict) -> None:
        self.config = config
        self._model = None

    @property
    def model(self):
        if self._model is None:
            os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
            WhisperModel = self._load_whisper_model_class()

            model_name = self.config.get("model", "small.en")
            device = self.config.get("device", "auto")
            compute_type = self.config.get("compute_type", "auto")
            logging.info(
                "Loading faster-whisper model '%s'. First run may download model files.",
                model_name,
            )
            try:
                self._model = WhisperModel(model_name, device=device, compute_type=compute_type)
            except RuntimeError as exc:
                if "cublas" not in str(exc).lower() and "cuda" not in str(exc).lower():
                    raise
                logging.warning("CUDA runtime is unavailable; falling back to CPU int8.")
                self.config["device"] = "cpu"
                self.config["compute_type"] = "int8"
                self._model = WhisperModel(model_name, device="cpu", compute_type="int8")
        return self._model

    def _load_whisper_model_class(self):
        try:
            from faster_whisper import WhisperModel

            return WhisperModel
        except ImportError as exc:
            if "Application Control policy" not in str(exc) and "av" not in str(exc).lower():
                raise
            return self._load_whisper_model_without_pyav()

    def _load_whisper_model_without_pyav(self):
        package_path = self._find_faster_whisper_path()

        package = types.ModuleType("faster_whisper")
        package.__path__ = [package_path]
        package.__package__ = "faster_whisper"
        sys.modules["faster_whisper"] = package
        sys.modules["faster_whisper.audio"] = self._build_audio_stub()

        module = importlib.import_module("faster_whisper.transcribe")
        return module.WhisperModel

    def _find_faster_whisper_path(self) -> str:
        for entry in sys.path:
            spec = importlib.machinery.PathFinder.find_spec("faster_whisper", [entry])
            if spec and spec.submodule_search_locations:
                return list(spec.submodule_search_locations)[0]
        raise ModuleNotFoundError("Could not locate faster_whisper package")

    def _build_audio_stub(self):
        import numpy as np

        module = types.ModuleType("faster_whisper.audio")

        def decode_audio(input_file, sampling_rate: int = 16000, split_stereo: bool = False):
            del input_file, sampling_rate, split_stereo
            raise RuntimeError(
                "PyAV is blocked on this system, so SmartVoice can only pass in-memory "
                "microphone audio to faster-whisper. File decoding is unavailable."
            )

        def pad_or_trim(array, length: int = 3000, *, axis: int = -1):
            if array.shape[axis] > length:
                array = array.take(indices=range(length), axis=axis)
            if array.shape[axis] < length:
                pad_widths = [(0, 0)] * array.ndim
                pad_widths[axis] = (0, length - array.shape[axis])
                array = np.pad(array, pad_widths)
            return array

        module.decode_audio = decode_audio
        module.pad_or_trim = pad_or_trim
        return module

    def transcribe(self, audio: AudioBuffer) -> str:
        vad_enabled = bool(self.config.get("vad_enabled", True))
        text = self._transcribe_once(audio, vad_filter=vad_enabled)
        if vad_enabled and not text:
            logging.info("No speech detected after VAD; retrying without VAD.")
            text = self._transcribe_once(audio, vad_filter=False)
        return text

    def warmup(self) -> None:
        _model = self.model

    def _transcribe_once(self, audio: AudioBuffer, *, vad_filter: bool) -> str:
        segments, _info = self.model.transcribe(
            audio.samples,
            language=self.config.get("language", "en"),
            vad_filter=vad_filter,
            beam_size=int(self.config.get("beam_size", 5)),
        )
        return " ".join(segment.text.strip() for segment in segments).strip()
