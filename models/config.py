from __future__ import annotations

import logging
import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Mapping

from models.common import AttrsMixin
from models.exceptions import ConfigurationError


@dataclass(frozen=True, slots=True)
class LoggingConfig:
    """Logging configuration loaded from config.toml."""

    level: str = "INFO"
    file: str | None = "Log"
    filemode: str = "w"
    format: str = "%(asctime)s - %(levelname)s - %(message)s"
    encoding: str = "utf-8"
    console: bool = False


@dataclass(frozen=True, slots=True)
class LinkResourceConfig(AttrsMixin):
    """Global WDM defaults when a topology file omits resource details."""

    wavelengths: int = 0
    max_bandwidth: int = 0

    attrs: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TopologyConfig(AttrsMixin):
    """Topology source used to build the physical network model."""

    path: str = "../graphml/Nsfnet.graphml"
    resource: LinkResourceConfig = None

    attrs: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CallTypeConfig(AttrsMixin):
    """Weighted traffic profile for one class of generated requests."""

    rate: int
    weight: float

    attrs: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TrafficConfig(AttrsMixin):
    """Parameters that drive stochastic flow generation."""

    calls: int = 0
    load: float = 0.0
    mean_holding_time: float = 0.0
    seed: int | None = None
    call_types: list[CallTypeConfig] = field(default_factory=list)
    max_bandwidth: int = 0

    attrs: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AlgorithmConfig(AttrsMixin):
    """Routing/allocation algorithm selection and tuning parameters."""

    name: str = ""
    k: int = 0

    attrs: Mapping[str, Any] = field(default_factory=dict)


@dataclass
class SimulationConfig(AttrsMixin):
    """Top-level immutable container for one simulation experiment."""

    logging: LoggingConfig = LoggingConfig()
    topology: TopologyConfig = TopologyConfig()
    traffic: TrafficConfig = TrafficConfig()
    resource: LinkResourceConfig = LinkResourceConfig()
    algorithm: AlgorithmConfig = AlgorithmConfig()

    attrs: Mapping[str, Any] = field(default_factory=dict)

    def load_config(self, path: str | Path) -> None:
        config_path = Path(path)
        if not config_path.exists():
            raise ConfigurationError(f"configuration file does not exist: {config_path}")

        with config_path.open("rb") as file:
            config = tomllib.load(file)

        # Parse each section into a dedicated dataclass so unsupported keys fail
        # early instead of leaking into the simulation at runtime.
        self.logging = self._read_dataclass(LoggingConfig, config.get("logging", {}))
        self.topology = self._read_dataclass(TopologyConfig, config.get("topology", {}))
        self.traffic = self._read_dataclass(TrafficConfig, config.get("traffic", {}))
        self.algorithm = self._read_dataclass(AlgorithmConfig, config.get("algorithm", {}))
        self.attrs = {
            key: values for key, values in config.items() if not hasattr(self, key)
        }

    def load_logging(self):
        handlers: list[logging.Handler] = []

        if self.logging.file:
            log_path = Path(self.logging.file)

            if not log_path.is_absolute():
                log_path = Path(Path.cwd()) / log_path

            log_path.parent.mkdir(parents=True, exist_ok=True)

            file_handler = logging.FileHandler(
                filename=log_path,
                mode=self.logging.filemode,
                encoding=self.logging.encoding
            )
            handlers.append(file_handler)

        if self.logging.console:
            console_handler = logging.StreamHandler()
            handlers.append(console_handler)

        logging.basicConfig(
            level=self.logging.level.upper(),
            format=self.logging.format,
            handlers=handlers,
            force=True
        )

    def _read_dataclass(self, cls, values: dict[str, Any]):
        """Instantiate one config section and reject unknown keys up front."""

        if cls is TrafficConfig and "call_types" in values:
            values["call_types"] = [
                self._read_dataclass(CallTypeConfig, item)
                for item in values["call_types"]
            ]
        elif cls is TopologyConfig:
            values["resource"] = self._read_dataclass(LinkResourceConfig, values["resource"])

        field_map = {f.name: f for f in fields(cls)}
        known_attrs = {}
        extra_attrs = {}

        for key, value in values.items():
            if key in field_map:
                known_attrs[key] = value
            else:
                extra_attrs[key] = value

        if extra_attrs:
            if "attrs" not in field_map:
                raise ValueError(
                    f"{cls.__name__} got unknown config key(s): {sorted(extra_attrs)}"
                )

            known_attrs["attrs"] = {**extra_attrs}
        return cls(**known_attrs)
