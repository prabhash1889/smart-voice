from smartvoice.core.models import AudioBuffer
from smartvoice.core.workflow import SmartVoiceWorkflow


class FakeRecorder:
    def start(self):
        self.started = True

    def stop(self):
        return AudioBuffer(samples=[0.05] * 16000, sample_rate=16000)

    def cancel(self):
        self.cancelled = True


class FakeTranscriber:
    def transcribe(self, audio):
        return "write tests"

    def warmup(self):
        self.warmed = True


class FakeProcessor:
    def process(self, raw_text, mode):
        return f"{mode}:{raw_text}"


class FakeInjector:
    def __init__(self):
        self.text = None

    def inject(self, text):
        self.text = text


class FakeHistory:
    def __init__(self):
        self.saved = []

    def save(self, result):
        self.saved.append(result)

    def latest_success(self):
        for result in reversed(self.saved):
            if result.error is None and result.final_text:
                return {"final_text": result.final_text}
        return None


class SilentRecorder(FakeRecorder):
    def stop(self):
        return AudioBuffer(samples=[0.0] * 16000, sample_rate=16000)


def test_workflow_records_transcribes_processes_injects_and_saves():
    injector = FakeInjector()
    history = FakeHistory()
    workflow = SmartVoiceWorkflow(
        recorder=FakeRecorder(),
        transcriber=FakeTranscriber(),
        processor=FakeProcessor(),
        injector=injector,
        history=history,
        default_mode="coding_prompt",
    )

    workflow.start_recording()
    result = workflow.stop_and_process()

    assert result.final_text == "coding_prompt:write tests"
    assert injector.text == "coding_prompt:write tests"
    assert history.saved[-1].final_text == "coding_prompt:write tests"


def test_workflow_rejects_silent_recording():
    injector = FakeInjector()
    history = FakeHistory()
    workflow = SmartVoiceWorkflow(
        recorder=SilentRecorder(),
        transcriber=FakeTranscriber(),
        processor=FakeProcessor(),
        injector=injector,
        history=history,
        default_mode="coding_prompt",
    )

    workflow.start_recording()
    result = workflow.stop_and_process()

    assert result.error == "Recording level is too low. Check the selected microphone."
    assert injector.text is None


def test_audio_buffer_reports_levels():
    audio = AudioBuffer(samples=[0.0, 0.5, -0.25], sample_rate=16000)

    assert audio.peak == 0.5
    assert audio.rms > 0


def test_retry_uses_history_after_restart():
    injector = FakeInjector()
    history = FakeHistory()
    history.save_result = None
    workflow = SmartVoiceWorkflow(
        recorder=FakeRecorder(),
        transcriber=FakeTranscriber(),
        processor=FakeProcessor(),
        injector=injector,
        history=history,
        default_mode="coding_prompt",
    )
    workflow.start_recording()
    workflow.stop_and_process()
    workflow.last_result = None

    workflow.retry_injection()

    assert injector.text == "coding_prompt:write tests"
