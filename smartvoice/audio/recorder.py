from __future__ import annotations

import time
import wave
from pathlib import Path

import numpy as np

from smartvoice.core.models import AudioBuffer


class SoundDeviceRecorder:
    def __init__(self, audio_config: dict, max_recording_seconds: int) -> None:
        self.audio_config = audio_config
        self.max_recording_seconds = max_recording_seconds
        self.sample_rate = int(audio_config.get("sample_rate", 16000))
        self.channels = int(audio_config.get("channels", 1))
        self.input_device_id = audio_config.get("input_device_id")
        self.stop_tail_ms = int(audio_config.get("stop_tail_ms", 350))
        self._frames: list[np.ndarray] = []
        self._stream = None
        self._started_at = 0.0

    def start(self) -> None:
        import sounddevice as sd

        self._frames = []
        self._started_at = time.monotonic()
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="float32",
            device=self.input_device_id,
            callback=self._on_audio,
        )
        self._stream.start()

    def _on_audio(self, indata, frames, callback_time, status) -> None:
        del frames, callback_time
        if status:
            # Keep recording; sounddevice statuses are often recoverable.
            pass
        if time.monotonic() - self._started_at <= self.max_recording_seconds:
            self._frames.append(indata.copy())

    def stop(self) -> AudioBuffer:
        if self._stream is not None and self.stop_tail_ms > 0:
            time.sleep(self.stop_tail_ms / 1000)
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        if not self._frames:
            samples = np.zeros((0,), dtype=np.float32)
        else:
            samples = np.concatenate(self._frames, axis=0)
            if samples.ndim == 2:
                samples = samples[:, 0]
        return AudioBuffer(samples=samples.astype(np.float32), sample_rate=self.sample_rate)

    def cancel(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        self._frames = []


def list_input_devices() -> list[dict]:
    import sounddevice as sd

    devices = []
    for index, device in enumerate(sd.query_devices()):
        if int(device.get("max_input_channels", 0)) > 0:
            devices.append(
                {
                    "id": index,
                    "name": device["name"],
                    "channels": int(device["max_input_channels"]),
                    "default_sample_rate": int(device["default_samplerate"]),
                }
            )
    return devices


def save_wav(audio: AudioBuffer, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    samples = np.clip(audio.samples, -1.0, 1.0)
    int_samples = (samples * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(audio.sample_rate)
        wav_file.writeframes(int_samples.tobytes())


def diagnose_audio(audio_config: dict, *, duration_seconds: int = 5, output_path: Path) -> dict:
    recorder = SoundDeviceRecorder(audio_config, max_recording_seconds=duration_seconds)
    recorder.start()
    time.sleep(duration_seconds)
    audio = recorder.stop()
    save_wav(audio, output_path)
    return {
        "path": str(output_path),
        "duration_ms": audio.duration_ms,
        "rms": audio.rms,
        "peak": audio.peak,
        "sample_rate": audio.sample_rate,
    }
