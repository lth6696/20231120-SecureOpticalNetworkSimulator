from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Flow:
    id: int
    src: int
    dst: int
    rate: int
    duration: float
    cos: int
    security_required: bool = False
    key_rate: int = 0

