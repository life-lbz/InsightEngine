"""JWT 认证：学员 Token 签发与校验。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config.settings import get_settings

security_scheme = HTTPBearer(auto_error=False)


def create_access_token(
    user_id: str,
    course_ids: list[str] | None = None,
    role: str = "student",
) -> str:
    """签发 JWT Access Token。

    入参：
        user_id：学员 ID
        course_ids：可访问的课程 ID 列表
        role：角色（student/admin）

    返回：
        JWT Token 字符串
    """
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_expire_minutes
    )
    payload: dict[str, Any] = {
        "sub": user_id,
        "role": role,
        "course_ids": course_ids or [],
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token(user_id: str) -> str:
    """签发 JWT Refresh Token（有效期 7 天）。"""
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.jwt_refresh_expire_days
    )
    payload = {
        "sub": user_id,
        "type": "refresh",
        "exp": expire,
    }
    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def verify_token(token: str) -> dict[str, Any]:
    """校验 JWT Token。

    入参：
        token：JWT Token 字符串

    返回：
        解码后的 Payload 字典

    异常：
        HTTPException 401：Token 无效或过期
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 已过期，请重新登录",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 无效",
        )


async def require_student_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> dict[str, Any]:
    """学员认证依赖：校验 JWT 并返回用户信息。

    返回：
        {"user_id": str, "role": str, "course_ids": list[str]}

    异常：
        HTTPException 401：未提供 Token 或 Token 无效
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请提供认证 Token",
        )
    payload = verify_token(credentials.credentials)
    return {
        "user_id": payload.get("sub", ""),
        "role": payload.get("role", "student"),
        "course_ids": payload.get("course_ids", []),
    }


async def require_admin_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> dict[str, Any]:
    """管理员认证依赖：校验 JWT 且 role 必须为 admin。"""
    user_info = await require_student_auth(credentials)
    if user_info["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return user_info


async def require_teacher_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> dict[str, Any]:
    """教师认证依赖：校验 JWT 且 role 为 teacher 或 admin。"""
    user_info = await require_student_auth(credentials)
    if user_info["role"] not in ("teacher", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要教师或管理员权限",
        )
    return user_info