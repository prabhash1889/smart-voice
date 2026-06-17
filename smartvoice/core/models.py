from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class AudioBuffer:
    samples: Any
    sample_rate: int

    @property
    def duration_ms(self) -> int:
        try:
            sample_count = len(self.samples)
        except TypeError:
            return 0
        return int(sample_count / self.sample_rate * 1000) if self.sample_rate else 0

    @property
    def rms(self) -> float:
        try:
            import numpy as np

            if len(self.samples) == 0:
                return 0.0
            return float(np.sqrt(np.mean(np.square(self.samples))))
        except Exception:
            return 0.0

    @property
    def peak(self) -> float:
        try:
            import numpy as np

            if len(self.samples) == 0:
                return 0.0
            return float(np.max(np.abs(self.samples)))
        except Exception:
            return 0.0


@dataclass(frozen=True)
class WorkflowResult:
    mode: str
    raw_text: str = ""
    final_text: str = ""
    audio_duration_ms: int = 0
    error: str | None = None
    created_at: datetime = datetime.now(timezone.utc)
