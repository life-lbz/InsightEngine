"""安全配置校验器：生产环境启动时拦截不合规配置。"""
from __future__ import annotations

from config.settings import Settings


class SecurityConfigError(Exception):
    """安全配置校验失败异常。"""


# 占位符黑名单：这些值不允许出现在生产环境
PLACEHOLDER_VALUES = {
    "replace-with-real-key",
    "replace-with-random-token",
    "replace-with-jwt-secret",
    "root123",
    "",
}


def validate_security_config(settings: Settings) -> None:
    """校验生产环境安全配置。

    入参：
        settings：已加载的 Settings 实例

    异常：
        SecurityConfigError：当关键安全配置不合规时抛出

    边界条件：
        - 仅在 app_env == "prod" 时执行严格校验
        - dev/staging 环境仅输出告警日志
    """
    if not settings.is_production:
        return

    errors: list[str] = []

    # LLM API Key 不能为占位符
    if settings.llm_api_key in PLACEHOLDER_VALUES:
        errors.append(
            "LLM_API_KEY 在生产环境不允许使用占位符，"
            "请通过环境变量 PROJECT_DEEPSEEK_API_KEY 设置真实密钥"
        )

    # Admin Token 长度校验
    if len(settings.admin_api_token) < 32:
        errors.append(
            f"ADMIN_API_TOKEN 长度不足（当前 {len(settings.admin_api_token)} 字符），"
            "生产环境要求至少 32 字符"
        )

    # JWT Secret 不能为占位符
    if settings.jwt_secret_key in PLACEHOLDER_VALUES:
        errors.append(
            "JWT_SECRET_KEY 在生产环境不允许使用占位符，"
            "请通过环境变量设置至少 32 字符的随机密钥"
        )

    # MySQL 密码不能为默认值
    if settings.mysql_password in {"root123", "root", ""}:
        errors.append(
            "MYSQL_PASSWORD 在生产环境不允许使用默认密码"
        )

    # Redis 密码不能为空
    if not settings.redis_password:
        errors.append(
            "REDIS_PASSWORD 在生产环境不允许为空"
        )

    if errors:
        error_msg = "\n".join(f"  [{i + 1}] {e}" for i, e in enumerate(errors))
        raise SecurityConfigError(
            f"生产环境安全配置校验失败（共 {len(errors)} 项）：\n{error_msg}\n"
            "请修复以上配置后重新启动"
        )