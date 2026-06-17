from __future__ import annotations

import json
import re
from pathlib import Path


class ModeProcessor:
    def __init__(self, templates: dict) -> None:
        self.templates = templates

    @classmethod
    def from_resource(cls) -> "ModeProcessor":
        path = Path(__file__).resolve().parents[2] / "resources" / "mode_templates.json"
        with path.open("r", encoding="utf-8") as file:
            return cls(json.load(file))

    def process(self, raw_text: str, mode: str) -> str:
        text = raw_text.strip()
        if not text:
            return ""
        if mode == "raw_transcript":
            return text

        text = self._clean_text(text)
        if mode in {
            "documentation",
            "coding_prompt",
            "terminal_command_explanation",
            "competitive_programming_explanation",
        }:
            text = self._sentence_case(text)
        elif mode == "commit_message":
            text = self._commit_case(text)

        template = self.templates.get(mode, {"prefix": "", "suffix": ""})
        return f"{template.get('prefix', '')}{text}{template.get('suffix', '')}".strip()

    def _clean_text(self, text: str) -> str:
        text = re.sub(r"\b(um|uh|like|you know)\b[, ]*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _sentence_case(self, text: str) -> str:
        if not text:
            return text
        text = text[0].upper() + text[1:]
        if text[-1] not in ".!?`":
            text += "."
        return text

    def _commit_case(self, text: str) -> str:
        text = text.strip()
        if not text:
            return text
        text = text[0].lower() + text[1:]
        return text.rstrip(".")
