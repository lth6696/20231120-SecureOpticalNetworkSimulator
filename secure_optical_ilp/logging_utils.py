from __future__ import annotations

import logging
import logging.config
from pathlib import Path


def setup_logging(config_path: str | Path = "logconfig.ini") -> Path:
    """从 INI 配置文件初始化日志。

    输入：
        config_path: ``fileConfig`` 格式的日志配置文件路径。

    输出：
        已加载配置文件的绝对路径。

    说明：
        ``logging.config.fileConfig`` 会从 INI 文件中读取
        handler/formatter/logger 的定义。它比 ``basicConfig`` 少见，
        但适合把日志输出位置和格式放到配置文件里统一管理。
    """
    resolved_path = Path(config_path).resolve()
    if not resolved_path.exists():
        raise FileNotFoundError(f"Logging config file not found: {resolved_path}")

    logging.config.fileConfig(
        resolved_path,
        disable_existing_loggers=False,
    )
    logging.getLogger(__name__).info("Logging initialized from %s", resolved_path)
    return resolved_path
