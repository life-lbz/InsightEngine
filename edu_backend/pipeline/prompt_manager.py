"""Prompt 模板管理器：从 YAML 加载、变量注入、版本管理。"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from observability.logger import get_logger

logger = get_logger(__name__)

PROMPTS_FILE = Path(__file__).resolve().parents[1] / "config" / "prompts.yaml"


@lru_cache(maxsize=1)
def _load_prompts() -> dict[str, Any]:
    """加载 prompts.yaml 到内存（单例缓存）。"""
    if not PROMPTS_FILE.exists():
        logger.warning("prompts_file_not_found", path=str(PROMPTS_FILE))
        return {}
    data = yaml.safe_load(PROMPTS_FILE.read_text(encoding="utf-8"))
    logger.info("prompts_loaded", count=len(data), path=str(PROMPTS_FILE))
    return data


def get_prompt(name: str, **variables: str) -> tuple[str, str]:
    """获取指定名称的 Prompt 模板并注入变量。

    入参：
        name：Prompt 名称（对应 prompts.yaml 的 key）
        **variables：模板变量（如 context="...", question="..."）

    返回：
        (system_prompt, user_prompt) 元组

    异常：
        KeyError：Prompt 名称不存在
    """
    prompts = _load_prompts()
    template = prompts.get(name)
    if template is None:
        raise KeyError(f"Prompt '{name}' not found in {PROMPTS_FILE}")

    system = template.get("system", "")
    user = template.get("user", "")

    if variables:
        system = system.format(**variables) if "{" in system else system
        user = user.format(**variables) if "{" in user else user

    return system, user


def get_fallback_message() -> str:
    """获取降级兜底回复文本。"""
    prompts = _load_prompts()
    fb = prompts.get("fallback", {})
    return fb.get("template", "抱歉，服务暂时不可用，请稍后重试。")


def list_prompts() -> dict[str, str]:
    """列出所有可用 Prompt 及其版本。"""
    prompts = _load_prompts()
    return {name: p.get("version", "unknown") for name, p in prompts.items()}


def reload_prompts() -> None:
    """热重新加载 Prompt 配置。"""
    _load_prompts.cache_clear()
    _load_prompts()
    logger.info("prompts_reloaded")
