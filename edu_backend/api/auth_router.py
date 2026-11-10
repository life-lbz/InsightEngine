"""认证路由：登录、刷新令牌、用户信息、登出。"""
from __future__ import annotations

import time

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text

from api.auth import (
    create_access_token,
    create_refresh_token,
    require_student_auth,
    verify_token,
)
from config.settings import get_settings
from storage.db_engine import get_engine

router = APIRouter()

# 开发环境回退账号（生产环境通过 ENABLE_FALLBACK_USERS=false 关闭）
# 密码使用 bcrypt 哈希存储，避免源码泄露明文密码
_FALLBACK_USERS = {
    "admin": {
        "password_hash": bcrypt.hashpw(
            b"admin123", bcrypt.gensalt()
        ).decode(),
        "user_id": "admin-001",
        "role": "admin",
        "course_ids": ["default_course"],
    },
    "teacher": {
        "password_hash": bcrypt.hashpw(
            b"teacher123", bcrypt.gensalt()
        ).decode(),
        "user_id": "teacher-001",
        "role": "teacher",
        "course_ids": ["default_course"],
    },
    "student": {
        "password_hash": bcrypt.hashpw(
            b"student123", bcrypt.gensalt()
        ).decode(),
        "user_id": "student-001",
        "role": "student",
        "course_ids": ["default_course"],
    },
}


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


def _verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def _query_user(username: str) -> dict | None:
    """从 users 表查询用户，返回标准化字典。"""
    engine = get_engine()
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT user_id, username, password_hash, role, "
                    "course_ids, display_name, is_active "
                    "FROM users WHERE username = :u LIMIT 1"
                ),
                {"u": username},
            ).fetchone()
        if row is None:
            return None
        if not row[6]:
            return {"disabled": True}
        return {
            "user_id": row[0],
            "username": row[1],
            "password_hash": row[2],
            "role": row[3],
            "course_ids": row[4].split(",") if row[4] else [],
            "display_name": row[5],
        }
    except Exception:
        return None


@router.post("/auth/login")
async def login(req: LoginRequest):
    db_user = _query_user(req.username)

    if db_user and not db_user.get("disabled"):
        if _verify_password(req.password, db_user["password_hash"]):
            access_token = create_access_token(
                db_user["user_id"],
                db_user["course_ids"],
                db_user["role"],
            )
            refresh = create_refresh_token(db_user["user_id"])
            return {
                "access_token": access_token,
                "refresh_token": refresh,
                "user": {
                    "user_id": db_user["user_id"],
                    "role": db_user["role"],
                    "course_ids": db_user["course_ids"],
                    "display_name": db_user.get("display_name"),
                },
            }

    if db_user and db_user.get("disabled"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已被禁用，请联系管理员",
        )

    settings = get_settings()
    if settings.enable_fallback_users:
        fallback = _FALLBACK_USERS.get(req.username)
        if fallback and _verify_password(
            req.password, fallback["password_hash"]
        ):
            access_token = create_access_token(
                fallback["user_id"],
                fallback["course_ids"],
                fallback["role"],
            )
            refresh = create_refresh_token(fallback["user_id"])
            return {
                "access_token": access_token,
                "refresh_token": refresh,
                "user": {
                    "user_id": fallback["user_id"],
                    "role": fallback["role"],
                    "course_ids": fallback["course_ids"],
                },
            }

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="用户名或密码错误",
    )


@router.post("/auth/refresh")
async def refresh(req: RefreshRequest):
    payload = verify_token(req.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的 refresh token 类型",
        )
    user_id = payload.get("sub", "")
    access_token = create_access_token(user_id)
    return {"access_token": access_token}


@router.get("/auth/me")
async def me(user=Depends(require_student_auth)):
    return {
        "user_id": user["user_id"],
        "role": user["role"],
        "course_ids": user["course_ids"],
    }


@router.post("/auth/logout")
async def logout(user=Depends(require_student_auth)):
    """登出：将 access token 加入 Redis 黑名单。"""
    settings = get_settings()
    try:
        import redis
        client = redis.from_url(settings.redis_url, **settings.redis_pool_kwargs)
        token_key = f"jwt:blacklist:{user['user_id']}:{int(time.time())}"
        client.setex(token_key, settings.jwt_expire_minutes * 60, "1")
    except Exception:
        pass
    return {"detail": "已登出"}
