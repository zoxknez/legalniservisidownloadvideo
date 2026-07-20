"""Shared types for the media pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class Stage(str, Enum):
    INIT = "init"
    KEYS = "keys"
    FRAGMENTS = "fragments"
    DECRYPT = "decrypt"
    MUX = "mux"
    DONE = "done"

    @classmethod
    def order(cls) -> List["Stage"]:
        return [cls.INIT, cls.KEYS, cls.FRAGMENTS, cls.DECRYPT, cls.MUX, cls.DONE]

    def index(self) -> int:
        return self.order().index(self)

    def reached(self, other: "Stage") -> bool:
        """True if self is at or past *other*."""
        return self.index() >= other.index()


@dataclass
class TrackPolicy:
    """Quality / language preferences applied after manifest parse."""

    max_height: Optional[int] = None
    codecs: Optional[List[str]] = None
    audio_langs: Optional[List[str]] = None
    prefer_hdr: bool = False
    l3_cap: bool = True


@dataclass
class PipelineResult:
    output_path: Path
    stage: Stage = Stage.DONE
    job_id: str = ""
    resumed: bool = False
    keys_count: int = 0
    meta: Dict[str, Any] = field(default_factory=dict)
