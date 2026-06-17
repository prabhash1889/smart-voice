from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path

from smartvoice.audio.recorder import diagnose_audio, list_input_devices
from smartvoice.app import build_app
from smartvoice.storage.config_store import ConfigStore
from smartvoice.storage.history_store import HistoryStore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SmartVoice push-to-talk prototype")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Record once after Enter, transcribe, process, and paste.",
    )
    parser.add_argument(
        "--no-inject",
        action="store_true",
        help="Print final text without pasting it.",
    )
    parser.add_argument(
        "--mode",
        default=None,
        help="Mode to use for this run. Defaults to config modes.default.",
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="List available microphone input devices and exit.",
    )
    parser.add_argument(
        "--device",
        type=int,
        default=None,
        help="Microphone input device id to use for this run.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="faster-whisper model for this run, e.g. base.en, small.en, medium.en.",
    )
    parser.add_argument(
        "--beam-size",
        type=int,
        default=None,
        help="Whisper beam size for this run. Higher can improve accuracy but is slower.",
    )
    parser.add_argument(
        "--vad",
        choices=["on", "off"],
        default=None,
        help="Enable or disable faster-whisper VAD for this run.",
    )
    parser.add_argument(
        "--engine",
        choices=["faster_whisper", "openai"],
        default=None,
        help="Transcription engine for this run.",
    )
    parser.add_argument(
        "--openai-model",
        default=None,
        help="OpenAI transcription model for this run. Defaults to gpt-4o-transcribe.",
    )
    parser.add_argument(
        "--allow-cloud-transcription",
        action="store_true",
        help="Allow this run to send audio to the configured cloud transcription engine.",
    )
    parser.add_argument(
        "--diagnose-audio",
        action="store_true",
        help="Record 5 seconds, report RMS/peak, save a WAV, and exit.",
    )
    parser.add_argument(
        "--save-audio",
        action="store_true",
        help="Save the last recording to .smartvoice/last_recording.wav for debugging.",
    )
    parser.add_argument(
        "--history",
        type=int,
        nargs="?",
        const=10,
        default=None,
        help="Show recent transcript history and exit. Defaults to 10 rows.",
    )
    parser.add_argument(
        "--show-config",
        action="store_true",
        help="Print the merged SmartVoice configuration and exit.",
    )
    parser.add_argument(
        "--copy-last",
        action="store_true",
        help="Copy the most recent successful transcript to the clipboard and exit.",
    )
    parser.add_argument(
        "--clear-history",
        action="store_true",
        help="Delete local transcript history and exit.",
    )
    parser.add_argument(
        "--set-defaults",
        action="store_true",
        help="Persist --device, --model, --beam-size, --mode, --vad, --engine, --openai-model, and cloud opt-in as defaults.",
    )
    parser.add_argument(
        "--no-warmup",
        action="store_true",
        help="Skip startup model warmup. Useful for config/history/debug commands.",
    )
    parser.add_argument(
        "--tray",
        action="store_true",
        help="Run the optional PySide6 tray app.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    logging.basicConfig(level=getattr(logging, args.log_level), format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("huggingface_hub").setLevel(logging.WARNING)

    if args.list_devices:
        for device in list_input_devices():
            print(
                f"{device['id']}: {device['name']} "
                f"({device['channels']} ch, {device['default_sample_rate']} Hz)"
            )
        return 0

    config_store = ConfigStore()

    if args.show_config:
        print(json.dumps(config_store.load(), indent=2))
        return 0

    if args.history is not None:
        for row in HistoryStore().recent(args.history):
            status = "error" if row["error"] else "ok"
            text = row["final_text"] or row["error"] or ""
            print(f"{row['id']} | {row['created_at']} | {status} | {row['mode']} | {text}")
        return 0

    if args.clear_history:
        HistoryStore().clear()
        print("History cleared.")
        return 0

    if args.copy_last:
        row = HistoryStore().latest_success()
        if not row:
            print("No successful transcript found.")
            return 1
        import pyperclip

        pyperclip.copy(row["final_text"])
        print(row["final_text"])
        return 0

    default_override = {}
    if args.device is not None:
        default_override.setdefault("audio", {})["input_device_id"] = args.device
    if args.vad is not None and args.set_defaults:
        default_override.setdefault("audio", {})["vad_enabled"] = args.vad == "on"
    if args.model is not None and args.set_defaults:
        default_override.setdefault("transcription", {})["model"] = args.model
    if args.beam_size is not None and args.set_defaults:
        default_override.setdefault("transcription", {})["beam_size"] = args.beam_size
    if args.engine is not None and args.set_defaults:
        default_override.setdefault("transcription", {})["engine"] = args.engine
    if args.openai_model is not None and args.set_defaults:
        default_override.setdefault("transcription", {})["openai_model"] = args.openai_model
    if args.mode is not None and args.set_defaults:
        default_override.setdefault("modes", {})["default"] = args.mode
    if args.allow_cloud_transcription and args.set_defaults:
        default_override.setdefault("privacy", {})["allow_cloud_transcription"] = True
    if default_override:
        config_store.update(default_override)
        logging.info("Saved default settings.")

    override = {}
    if args.device is not None:
        override.setdefault("audio", {})["input_device_id"] = args.device
    if args.vad is not None:
        override.setdefault("audio", {})["vad_enabled"] = args.vad == "on"
    if args.model is not None:
        override.setdefault("transcription", {})["model"] = args.model
    if args.beam_size is not None:
        override.setdefault("transcription", {})["beam_size"] = args.beam_size
    if args.engine is not None:
        override.setdefault("transcription", {})["engine"] = args.engine
    if args.openai_model is not None:
        override.setdefault("transcription", {})["openai_model"] = args.openai_model
    if args.allow_cloud_transcription:
        override.setdefault("privacy", {})["allow_cloud_transcription"] = True

    if args.diagnose_audio:
        config = config_store.load()
        if override:
            config = config_store.merge(config, override)
        output_path = Path.cwd() / ".smartvoice" / "audio_diagnostic.wav"
        report = diagnose_audio(config["audio"], duration_seconds=5, output_path=output_path)
        print(f"Saved WAV: {report['path']}")
        print(f"Duration: {report['duration_ms'] / 1000:.2f}s")
        print(f"RMS: {report['rms']:.5f}")
        print(f"Peak: {report['peak']:.5f}")
        print(f"Sample rate: {report['sample_rate']} Hz")
        return 0

    audio_debug_path = None
    if args.save_audio:
        audio_debug_path = str(Path.cwd() / ".smartvoice" / "last_recording.wav")

    app = build_app(
        inject=not args.no_inject,
        mode=args.mode,
        config_override=override,
        audio_debug_path=audio_debug_path,
    )
    if args.tray:
        from smartvoice.ui.tray import run_tray

        return run_tray(app)

    if not args.no_warmup:
        app.warmup()

    if args.once:
        input("Press Enter to start recording, then Enter again to stop.")
        app.workflow.start_recording()
        input("Recording. Press Enter to stop.")
        result = app.workflow.stop_and_process()
        if result.final_text:
            print(result.final_text)
        elif result.error:
            print(f"Error: {result.error}")
        else:
            print("No transcript produced.")
        return 0 if result.error is None else 1

    logging.info("SmartVoice is running. Hold %s to record.", app.config["hotkeys"]["push_to_talk"])
    logging.info("Press Ctrl+C to quit.")
    app.hotkeys.run_forever()
    return 0
