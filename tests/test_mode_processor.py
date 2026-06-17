from smartvoice.processing.cleanup import ModeProcessor


def test_raw_transcript_only_trims():
    processor = ModeProcessor({"raw_transcript": {"prefix": "", "suffix": ""}})

    assert processor.process("  um keep this  ", "raw_transcript") == "um keep this"


def test_coding_prompt_cleans_and_formats():
    processor = ModeProcessor({"coding_prompt": {"prefix": "Task: ", "suffix": ""}})

    assert processor.process("um add tests for config loader", "coding_prompt") == (
        "Task: Add tests for config loader."
    )


def test_commit_message_mode_formats_lowercase_subject():
    processor = ModeProcessor({"commit_message": {"prefix": "chore: ", "suffix": ""}})

    assert processor.process("Update voice history.", "commit_message") == "chore: update voice history"
