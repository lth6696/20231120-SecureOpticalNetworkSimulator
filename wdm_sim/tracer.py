from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from event.flow import Flow


@dataclass
class Tracer:
    path: Path | None = None
    records: list[dict[str, Any]] = field(default_factory=list)

    def record(self, event_type: str, time: float, flow: Flow, **details: Any) -> None:
        record = {
            "time": time,
            "event": event_type,
            "flow_id": flow.id,
            "src": flow.src,
            "dst": flow.dst,
            "rate": flow.rate,
            **details,
        }
        self.records.append(record)

    def close(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as fh:
            for record in self.records:
                fh.write(json.dumps(record, sort_keys=True) + "\n")
