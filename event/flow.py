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
    sec: int = 0
    kgr: int = 0

