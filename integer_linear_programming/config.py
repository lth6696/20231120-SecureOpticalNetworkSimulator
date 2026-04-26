from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

from .data_model import CostParameters

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
    try:
        import tomli as tomllib
    except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "TOML config support requires Python 3.11+ or the `tomli` package. "
            "Run `python -m pip install -r requirements.txt`."
        ) from exc





def load_app_config(path: str | Path = "config.toml") -> AppConfig:
    """Load all user-provided experiment parameters from a TOML file."""
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with config_path.open("rb") as file:
        raw_config = tomllib.load(file)

    base_dir = config_path.resolve().parent
    config = AppConfig(
        logging=_read_logging_config(raw_config, base_dir),
        topology=_read_topology_config(raw_config, base_dir),
        request_generation=_read_dataclass(
            RequestGenerationConfig,
            raw_config.get("request_generation", {}),
        ),
        network_resources=_read_dataclass(
            NetworkResourceConfig,
            raw_config.get("network_resources", {}),
        ),
        costs=_read_dataclass(CostParameters, raw_config.get("costs", {})),
        solver=_read_dataclass(SolverConfig, raw_config.get("solver", {})),
        outputs=_read_output_config(raw_config, base_dir),
    )
    _validate_config(config)
    return config


def _read_logging_config(raw_config: dict[str, Any], base_dir: Path) -> LoggingConfig:
    section = raw_config.get("logging", {})
    return LoggingConfig(config_path=_resolve_path(section, "config_path", base_dir))


def _read_topology_config(raw_config: dict[str, Any], base_dir: Path) -> TopologyConfig:
    section = raw_config.get("topology", {})
    return TopologyConfig(path=_resolve_path(section, "path", base_dir))


def _read_output_config(raw_config: dict[str, Any], base_dir: Path) -> OutputConfig:
    section = raw_config.get("outputs", {})
    return OutputConfig(
        directory=_resolve_path(section, "directory", base_dir),
        solution_filename=section.get("solution_filename", "solution.json"),
        report_filename=section.get("report_filename", "solution_report.md"),
        enable_visualization=section.get("enable_visualization", True),
    )


def _read_dataclass(cls, values: dict[str, Any]):
    """
    【核心功能】将字典数据 严格转换为 数据类实例（校验字段，拒绝非法配置）
    :param cls: 代表数据类本身（比如 AppConfig 类）
    :param values: 字典数据, 键：字符串, 值：任意类型（Any）
    :return: 数据类的实例对象
    """
    # 1. 获取数据类中【定义好的合法字段】
    allowed_fields = {field.name for field in fields(cls)}  # fields(cls) 获取数据类定义的所有字段
    unexpected = set(values) - allowed_fields
    if unexpected:
        names = ", ".join(sorted(unexpected))
        raise ValueError(f"Unknown keys in [{_section_name(cls)}]: {names}")
    return cls(**values)


def _resolve_path(section: dict[str, Any], key: str, base_dir: Path) -> Path:
    default_value = getattr(_path_defaults(key), key)
    raw_path = Path(section.get(key, default_value))
    if raw_path.is_absolute():
        return raw_path
    return base_dir / raw_path


def _path_defaults(key: str):
    if key == "config_path":
        return LoggingConfig()
    if key == "path":
        return TopologyConfig()
    if key == "directory":
        return OutputConfig()
    raise KeyError(key)


def _section_name(cls) -> str:
    mapping = {
        CostParameters: "costs",
        NetworkResourceConfig: "network_resources",
        RequestGenerationConfig: "request_generation",
        SolverConfig: "solver",
    }
    return mapping.get(cls, cls.__name__)


def _validate_config(config: AppConfig) -> None:
    requests = config.request_generation
    resources = config.network_resources
    solver = config.solver
    costs = config.costs

    if requests.count <= 0:
        raise ValueError("request_generation.count must be positive.")
    if requests.bandwidth_min <= 0 or requests.bandwidth_max < requests.bandwidth_min:
        raise ValueError(
            "request_generation bandwidth range must be positive and ordered."
        )
    if requests.security_level_min < 0:
        raise ValueError("request_generation.security_level_min cannot be negative.")
    if requests.security_level_max < requests.security_level_min:
        raise ValueError("request_generation security_level range must be ordered.")
    if resources.wavelengths <= 0:
        raise ValueError("network_resources.wavelengths must be positive.")
    if resources.lightpaths_per_pair <= 0:
        raise ValueError("network_resources.lightpaths_per_pair must be positive.")
    if resources.logical_bandwidth_capacity <= 0:
        raise ValueError(
            "network_resources.logical_bandwidth_capacity must be positive."
        )
    if resources.logical_key_capacity <= 0:
        raise ValueError("network_resources.logical_key_capacity must be positive.")
    for field in fields(CostParameters):
        value = getattr(costs, field.name)
        if value < 0:
            raise ValueError(f"costs.{field.name} cannot be negative.")
    if solver.time_limit_seconds is not None and solver.time_limit_seconds <= 0:
        raise ValueError("solver.time_limit_seconds must be positive when set.")
    if not config.outputs.solution_filename:
        raise ValueError("outputs.solution_filename cannot be empty.")
    if not config.outputs.report_filename:
        raise ValueError("outputs.report_filename cannot be empty.")
