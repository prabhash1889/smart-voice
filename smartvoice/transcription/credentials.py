from __future__ import annotations

import os


def get_openai_api_key() -> str | None:
    key = os.environ.get("OPENAI_API_KEY")
    if key:
        return key
    return None
