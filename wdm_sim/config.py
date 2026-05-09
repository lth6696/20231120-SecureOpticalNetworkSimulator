from __future__ import annotations

import logging
import tomllib
from dataclasses import dataclass, fields, field
from pathlib import Path
from typing import Any

from exceptions import ConfigurationError


@dataclass(frozen=True, slots=True)
class LoggingConfig:
    """Path and default level for the logging configuration."""

    path: str = "logconfig.ini"
    level: str = "INFO"


@dataclass(frozen=True, slots=True)
class ResourceConfig:
    """Global WDM defaults when a topology file omits resource details."""

    wavelengths: int = 0
    max_bandwidth: int = 0
    max_key_rate: int = 0


@dataclass(frozen=True, slots=True)
class TopologyConfig:
    """Topology source used to build the physical network model."""

    path: str = "graphml/Nsfnet.graphml"
    resource: ResourceConfig = None


@dataclass(frozen=True, slots=True)
class CallTypeConfig:
    """Weighted traffic profile for one class of generated requests."""

    rate: int
    weight: float
    cos: int = 0


@dataclass(frozen=True, slots=True)
class TrafficConfig:
    """Parameters that drive stochastic flow generation."""

    calls: int = 0
    load: float = 0.0
    mean_holding_time: float = 0.0
    seed: int | None = None
    max_bandwidth: int = 0
    min_bandwidth: int = 0
    max_key_rate: int = 4
    min_key_rate: int = 1
    max_security_level: int = 2
    min_security_level: int = 0
    call_types: list[CallTypeConfig] = field(default_factory=list)





@dataclass(frozen=True, slots=True)
class AlgorithmConfig:
    """Routing/allocation algorithm selection and tuning parameters."""

    name: str = ""
    k: int = 0


@dataclass(frozen=True, slots=True)
class SimulationConfig:
    """Top-level immutable container for one simulation experiment."""

    logging: LoggingConfig = LoggingConfig()
    topology: TopologyConfig = TopologyConfig()
    traffic: TrafficConfig = TrafficConfig()
    resource: ResourceConfig = ResourceConfig()
    algorithm: AlgorithmConfig = AlgorithmConfig()

    trace_path: Path | None = None


def load_simulation_config(path: str | Path) -> SimulationConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise ConfigurationError(f"configuration file does not exist: {config_path}")

    with config_path.open("rb") as file:
        raw_config = tomllib.load(file)

    # Parse each section into a dedicated dataclass so unsupported keys fail
    # early instead of leaking into the simulation at runtime.
    config = SimulationConfig(
        logging=_read_dataclass(LoggingConfig, raw_config.get("logging", {})),
        topology=_read_dataclass(TopologyConfig, raw_config.get("topology", {})),
        traffic=_read_dataclass(TrafficConfig, raw_config.get("traffic", {})),
        # resource=_read_dataclass(ResourceConfig, raw_config.get("resource", {})),
        algorithm=_read_dataclass(AlgorithmConfig, raw_config.get("algorithm", {})),
    )
    return config


def _read_dataclass(cls, values: dict[str, Any]):
    """Instantiate one config section and reject unknown keys up front."""

    allowed_fields = {f.name for f in fields(cls)}
    unexpected = set(values) - allowed_fields
    if unexpected:
        names = ", ".join(sorted(unexpected))
        raise ValueError(f"Unknown keys in [{_section_name(cls)}]: {names}")

    if cls is TrafficConfig and "call_types" in values:
        values["call_types"] = [
            item if isinstance(item, CallTypeConfig) else CallTypeConfig(**item)
            for item in values["call_types"]
        ]

    if cls is TopologyConfig:
        values["resource"] = ResourceConfig(**values["resource"])
    return cls(**values)


def _section_name(cls: type[Any]) -> str:
    mapping = {
        LoggingConfig: "logging",
        TopologyConfig: "topology",
        TrafficConfig: "traffic",
        ResourceConfig: "resource",
        AlgorithmConfig: "algorithm",
        # CostsConfig: "costs",
        # OutputsConfig: "outputs",
    }
    return mapping.get(cls, cls.__name__)
