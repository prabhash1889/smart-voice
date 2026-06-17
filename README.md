# SmartVoice

Windows-first push-to-talk dictation prototype for developer workflows.

Current prototype flow:

1. Hold `Ctrl+Alt+Space`.
2. Speak.
3. Release the hotkey.
4. SmartVoice transcribes locally with `faster-whisper`.
5. The processed text is pasted into the focused app.
6. A local history row is saved.

## Setup

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

For the first run, `faster-whisper` downloads the configured model. The default model is `small.en`.

SmartVoice records microphone audio directly as an in-memory waveform. On Windows systems where
Application Control blocks PyAV's native DLLs, the app bypasses PyAV and still feeds microphone
audio to `faster-whisper`.

## Run

```powershell
python -m smartvoice
```

Useful development mode without pasting:

```powershell
python -m smartvoice --once --no-inject
```

Show microphones and persist the working device:

```powershell
python -m smartvoice --list-devices
python -m smartvoice --device 15 --set-defaults --no-warmup
python -m smartvoice --show-config
```

Compare local VAD behavior or record a 5 second microphone diagnostic:

```powershell
python -m smartvoice --once --no-inject --vad off
python -m smartvoice --diagnose-audio --device 15
```

Use optional OpenAI transcription. This sends recorded audio to OpenAI and is blocked unless
cloud transcription is explicitly allowed:

```powershell
$env:OPENAI_API_KEY = "..."
python -m smartvoice --once --no-inject --engine openai --allow-cloud-transcription
```

Use the optional tray UI:

```powershell
python -m pip install -r requirements-ui.txt
python -m smartvoice --tray
```

Inspect or recover recent transcripts:

```powershell
python -m smartvoice --history 10
python -m smartvoice --copy-last
python -m smartvoice --clear-history
```

## Test

```powershell
python -m pytest -q
```

## Package

```powershell
.\scripts\package_windows.ps1
```

## Privacy Defaults

- Local transcription is the default path.
- Audio is not retained by the app.
- Cloud transcription is blocked unless `privacy.allow_cloud_transcription` is true or
  `--allow-cloud-transcription` is passed for the current run.
- API keys are read from `OPENAI_API_KEY` and are never written to config or history.
- LLM cleanup is not implemented in this first pass.
- Clipboard content is restored after paste by default.
