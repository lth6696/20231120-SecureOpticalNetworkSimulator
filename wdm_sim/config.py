from __future__ import annotations

import json
import tomllib
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .exceptions import ConfigurationError


@dataclass(frozen=True, slots=True)
class CallTypeConfig:
    rate: int
    weight: float
    cos: int = 0
    security_required: bool = False
    key_rate: int = 0


@dataclass(frozen=True, slots=True)
class PairWeightConfig:
    src: int
    dst: int
    weight: float


@dataclass(frozen=True, slots=True)
class TrafficConfig:
    calls: int
    load: float
    mean_holding_time: float
    max_rate: int
    call_types: list[CallTypeConfig]
    seed: int | None = None
    pairs: list[PairWeightConfig] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class SimulationConfig:
    algorithm: str
    topology_path: Path
    traffic: TrafficConfig
    k_paths: int = 3
    trace_path: Path | None = None


def load_simulation_config(path: str | Path) -> SimulationConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise ConfigurationError(f"configuration file does not exist: {config_path}")

    suffix = config_path.suffix.lower()
    if suffix == ".json":
        data = json.loads(config_path.read_text(encoding="utf-8"))
    elif suffix == ".toml":
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    elif suffix == ".xml":
        data = _load_config_xml(config_path)
    else:
        raise ConfigurationError(f"unsupported config format {suffix!r}")

    return _simulation_config_from_mapping(data, config_path.parent)


def _simulation_config_from_mapping(data: dict[str, Any], base_dir: Path) -> SimulationConfig:
    try:
        traffic_data = data["traffic"]
        topology_path = Path(data.get("topology_path", data.get("topology")))
        algorithm = str(data["algorithm"])
    except KeyError as exc:
        raise ConfigurationError(f"missing required config key: {exc.args[0]}") from exc

    if not topology_path.is_absolute():
        topology_path = base_dir / topology_path
    trace_path_raw = data.get("trace_path")
    trace_path = Path(trace_path_raw) if trace_path_raw else None
    if trace_path is not None and not trace_path.is_absolute():
        trace_path = base_dir / trace_path

    call_types = [
        CallTypeConfig(
            rate=int(item["rate"]),
            weight=float(item.get("weight", 1.0)),
            cos=int(item.get("cos", 0)),
            security_required=_as_bool(item.get("security_required", item.get("securityRequired", False))),
            key_rate=int(item.get("key_rate", item.get("keyRate", 0))),
        )
        for item in traffic_data.get("call_types", traffic_data.get("calls_types", traffic_data.get("callTypes", [])))
    ]
    if not call_types:
        raise ConfigurationError("traffic.call_types must contain at least one call type")

    pairs = [
        PairWeightConfig(
            src=int(item["src"]),
            dst=int(item["dst"]),
            weight=float(item.get("weight", 1.0)),
        )
        for item in traffic_data.get("pairs", traffic_data.get("pair_weights", []))
    ]

    traffic = TrafficConfig(
        calls=int(traffic_data.get("calls", traffic_data.get("num_flows", 0))),
        load=float(traffic_data["load"]),
        mean_holding_time=float(
            traffic_data.get("mean_holding_time", traffic_data.get("meanHoldingTime"))
        ),
        max_rate=int(traffic_data.get("max_rate", traffic_data.get("maxRate"))),
        seed=int(traffic_data["seed"]) if "seed" in traffic_data else None,
        call_types=call_types,
        pairs=pairs,
    )
    if traffic.calls <= 0:
        raise ConfigurationError("traffic.calls must be positive")
    if traffic.load <= 0:
        raise ConfigurationError("traffic.load must be positive")
    if traffic.mean_holding_time <= 0:
        raise ConfigurationError("traffic.mean_holding_time must be positive")
    if traffic.max_rate <= 0:
        raise ConfigurationError("traffic.max_rate must be positive")

    return SimulationConfig(
        algorithm=algorithm,
        topology_path=topology_path,
        traffic=traffic,
        k_paths=int(data.get("k_paths", data.get("kPaths", 3))),
        trace_path=trace_path,
    )


def _load_config_xml(path: Path) -> dict[str, Any]:
    root = ET.parse(path).getroot()
    traffic_el = root.find("traffic")
    if traffic_el is None:
        raise ConfigurationError("XML config must contain <traffic>")
    call_types = [dict(call.attrib) for call in traffic_el.findall("call")]
    pairs = [dict(pair.attrib) for pair in traffic_el.findall("pair")]
    return {
        "algorithm": root.attrib.get("algorithm"),
        "topology_path": root.attrib.get("topology", root.attrib.get("topology_path")),
        "k_paths": root.attrib.get("k_paths", root.attrib.get("kPaths", 3)),
        "trace_path": root.attrib.get("trace_path"),
        "traffic": {
            **traffic_el.attrib,
            "call_types": call_types,
            "pairs": pairs,
        },
    }


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes", "y"}
    return bool(value)

