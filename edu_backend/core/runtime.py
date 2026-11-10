"""运行时配置加载（生产级增强：环境变量插值）。"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

from observability.logger import get_logger

logger = get_logger(__name__)

# 匹配 ${VAR_NAME} 格式的环境变量引用
_ENV_VAR_PATTERN = re.compile(r"\$\{(\w+)\}")


def _resolve_env_vars(value: Any) -> Any:
    """递归解析配置中的 ${VAR_NAME} 环境变量引用。

    入参：
        value：配置值（可能是 str/dict/list）

    返回：
        解析后的配置值
    """
    if isinstance(value, str):
        def _replace(match):
            var_name = match.group(1)
            env_value = os.environ.get(var_name, "")
            if not env_value:
                logger.warning("env_var_not_set", var_name=var_name)
            return env_value

        return _ENV_VAR_PATTERN.sub(_replace, value)
    elif isinstance(value, dict):
        return {k: _resolve_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_resolve_env_vars(item) for item in value]
    return value


def load_config(path: str | None = None) -> dict[str, Any]:
    """读取 config.yaml 并解析环境变量。

    入参：
        path：配置文件路径（默认 config/config.yaml）

    返回：
        配置字典
    """
    config_path = (
        Path(path) if path
        else Path(__file__).resolve().parents[1] / "config" / "config.yaml"
    )

    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在：{config_path}")

    with config_path.open("r", encoding="utf-8") as handle:
        raw_config = yaml.safe_load(handle)

    # 解析环境变量引用
    config = _resolve_env_vars(raw_config)

    logger.info("config_loaded", path=str(config_path), keys=list(config.keys()))
    return config