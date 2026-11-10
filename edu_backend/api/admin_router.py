"""管理路由：系统健康、文档管理、入库控制、检索监控、审计日志。"""
from __future__ import annotations

import asyncio
import os
import re
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import create_engine, text

from api.auth import require_admin_auth, require_teacher_auth
from config.settings import get_settings
from ingestion.task_manager import (
    create_task,
    get_task,
    list_tasks,
    run_task,
)
from observability.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


def _validate_kb_version_name(kb_version: str) -> str:
    """校验知识库版本名：字母开头，仅字母/数字/下划线，长度 2-64。"""
    kb = (kb_version or "").strip()
    if not kb:
        raise HTTPException(status_code=400, detail="知识库版本名不能为空")
    if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_]{1,63}", kb):
        raise HTTPException(
            status_code=400,
            detail="知识库版本名需以字母开头，仅含字母/数字/下划线，长度 2-64",
        )
    return kb


# ──────────────────────────────────────────────────────────────
# 系统健康
# ──────────────────────────────────────────────────────────────

@router.get("/admin/health")
async def health():
    settings = get_settings()
    components: dict = {}
    overall = "healthy"

    for name, check in [
        ("mysql", _check_mysql),
        ("redis", _check_redis),
        ("milvus", _check_milvus),
    ]:
        try:
            latency, ok = check(settings)
            components[name] = {"healthy": ok, "latency_ms": latency}
            if not ok:
                overall = "degraded"
        except Exception:
            components[name] = {"healthy": False, "latency_ms": 0}
            overall = "degraded"

    return {"status": overall, "components": components}


def _check_mysql(settings):
    start = time.perf_counter()
    engine = create_engine(settings.mysql_sync_uri)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    engine.dispose()
    return (time.perf_counter() - start) * 1000, True


def _check_redis(settings):
    import redis
    start = time.perf_counter()
    client = redis.from_url(settings.redis_url)
    client.ping()
    return (time.perf_counter() - start) * 1000, True


def _check_milvus(settings):
    from pymilvus import connections, utility
    start = time.perf_counter()
    connections.connect(alias="health", uri=settings.milvus_uri)
    utility.list_collections(using="health")
    return (time.perf_counter() - start) * 1000, True


# ──────────────────────────────────────────────────────────────
# 知识库统计
# ──────────────────────────────────────────────────────────────

@router.get("/admin/knowledge-base/stats")
async def knowledge_base_stats(user=Depends(require_admin_auth)):
    """返回所有 Milvus Collection 的统计信息。"""
    try:
        from vector_store.milvus_client import get_milvus_store

        store = get_milvus_store()
        collections = store.list_collections()
        stats = []
        for name in collections:
            stat = store.get_collection_stats(name)
            stats.append({
                "collection_name": name,
                "row_count": stat["row_count"],
                "index_status": stat["index_status"],
                "healthy": stat["healthy"],
            })
        return stats
    except Exception as exc:
        logger.error("kb_stats_error", error=str(exc))
        return []


# ──────────────────────────────────────────────────────────────
# 文档管理：上传 / 列表 / 删除
# ──────────────────────────────────────────────────────────────

async def _process_upload_file(
    file: UploadFile,
    kb_version: str,
    settings,
) -> dict:
    """处理单个上传文件，返回结果字典（成功含文件信息，失败含 error）。"""
    from ingestion.file_registry import compute_file_hash
    from ingestion.validator import ALLOWED_EXTENSIONS, validate_file_type
    from storage.db_engine import get_engine
    from sqlalchemy import text

    # 1. 文件名安全处理：仅取 basename，避免路径穿越
    filename = Path(file.filename or "").name
    if not filename:
        return {"file_name": "", "error": "文件名不能为空"}

    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        return {
            "file_name": filename,
            "error": f"不支持的文件类型 {suffix or '(无扩展名)'}，"
                     f"支持 {sorted(ALLOWED_EXTENSIONS)}",
        }

    # 2. 读取内容并校验大小
    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > settings.upload_max_size_mb:
        return {
            "file_name": filename,
            "error": f"文件超过大小限制（{settings.upload_max_size_mb}MB，实际 {size_mb:.1f}MB）",
        }

    raw_dir = Path(__file__).resolve().parents[1] / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    target = raw_dir / filename

    # 3. 待入库目录同名检测
    if target.exists():
        return {
            "file_name": filename,
            "error": f"已在待入库目录中（同名文件：{filename}），可直接开始入库",
            "duplicate": True,
        }

    # 4. 写入临时文件，计算哈希并做类型校验（失败不留残留）
    tmp_path = raw_dir / f".upload_tmp_{int(time.time() * 1000)}_{filename}"
    tmp_path.write_bytes(content)
    try:
        file_hash = compute_file_hash(tmp_path)

        # 5. 已入库检测（跨版本相同内容视为重复）
        engine = get_engine()
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT file_path, kb_version FROM file_registry "
                    "WHERE file_hash = :h ORDER BY ingested_at DESC LIMIT 1"
                ),
                {"h": file_hash},
            ).fetchone()
        if row:
            return {
                "file_name": filename,
                "error": f"该文件已入库（版本 {row[1]}：{row[0]}）",
                "duplicate": True,
                "already_ingested": True,
            }

        type_result = validate_file_type(tmp_path)
        if not type_result.valid:
            return {"file_name": filename, "error": "; ".join(type_result.errors)}

        # 6. 校验通过后原子移动到正式文件名
        os.replace(tmp_path, target)
    finally:
        tmp_path.unlink(missing_ok=True)

    return {
        "file_path": str(target),
        "file_name": filename,
        "file_hash": file_hash,
        "size": len(content),
        "suffix": suffix,
        "kb_version": kb_version,
        "pending": True,
        "message": "已上传至待入库目录",
    }


@router.post("/admin/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    kb_version: str | None = Query(default=None),
    user=Depends(require_admin_auth),
):
    """上传单个文档到待入库目录（data/raw），供"开始入库"直接处理。"""
    settings = get_settings()
    kb_version = kb_version or settings.default_kb_version
    return await _process_upload_file(file, kb_version, settings)


@router.post("/admin/documents/upload-batch")
async def upload_documents_batch(
    files: list[UploadFile] = File(...),
    kb_version: str | None = Query(default=None),
    user=Depends(require_admin_auth),
):
    """批量上传文档到待入库目录（一次请求处理多个文件，避免逐文件请求触发限流）。

    返回每个文件的独立结果，失败不影响其他文件。
    """
    settings = get_settings()
    kb_version = kb_version or settings.default_kb_version

    results = []
    for f in files:
        try:
            results.append(await _process_upload_file(f, kb_version, settings))
        except Exception as exc:
            results.append({
                "file_name": Path(f.filename or "").name,
                "error": f"处理异常: {str(exc)[:120]}",
            })

    success = sum(1 for r in results if not r.get("error"))
    return {
        "total": len(results),
        "success": success,
        "failed": len(results) - success,
        "results": results,
    }


@router.get("/admin/documents")
async def list_documents(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    kb_version: str | None = Query(default=None),
    user=Depends(require_admin_auth),
):
    """分页查询已入库文档列表。"""
    from ingestion.service import get_documents
    return get_documents(page=page, page_size=page_size, kb_version=kb_version)


@router.delete("/admin/documents/{file_hash}")
async def delete_document(
    file_hash: str,
    kb_version: str | None = Query(default=None),
    user=Depends(require_admin_auth),
):
    """从 Milvus 和 file_registry 中删除指定文档。"""
    from ingestion.service import delete_document as _delete
    kb_version = kb_version or get_settings().default_kb_version
    _delete(file_hash, kb_version)
    return {"deleted": True, "file_hash": file_hash}


# ──────────────────────────────────────────────────────────────
# 入库控制：触发 / 进度 / 任务
# ──────────────────────────────────────────────────────────────

@router.get("/admin/ingestion/pending-files")
async def list_pending_files(
    user=Depends(require_admin_auth),
) -> dict[str, Any]:
    """列出待入库目录中符合格式的文件（用于前端入库前校验）。"""
    from ingestion.validator import ALLOWED_EXTENSIONS

    data_dir = Path(__file__).resolve().parents[1] / "data" / "raw"
    if not data_dir.exists():
        return {"total": 0, "files": []}

    files = [
        f
        for f in sorted(data_dir.rglob("*"))
        if f.is_file() and f.suffix.lower() in ALLOWED_EXTENSIONS
    ]
    return {
        "total": len(files),
        "files": [
            {
                "name": f.name,
                "path": str(f),
                "size": f.stat().st_size,
            }
            for f in files[:50]
        ],
    }


@router.post("/admin/ingestion")
async def trigger_ingestion(
    mode: str = Query(default="full"),
    kb_version: str | None = Query(default=None),
    course_id: str | None = Query(default=None),
    input_dir: str | None = Query(default=None),
    user=Depends(require_admin_auth),
):
    """触发异步入库任务，返回 task_id。

    同一时刻仅允许一个入库任务运行：已有进行中任务时返回 409，
    避免并发任务重复处理同一批文件、竞争资源。
    """
    from ingestion.task_manager import has_running_task

    if has_running_task():
        raise HTTPException(
            status_code=409,
            detail="已有入库任务正在进行，请等待完成后再试",
        )

    settings = get_settings()
    course_id = course_id or settings.default_course_id
    kb_version = kb_version or settings.default_kb_version
    data_dir = input_dir or str(
        Path(__file__).resolve().parents[1] / "data" / "raw"
    )
    if not Path(data_dir).exists():
        Path(data_dir).mkdir(parents=True, exist_ok=True)

    task_id = create_task(kb_version, mode)
    asyncio.create_task(
        run_task(task_id, Path(data_dir), course_id, kb_version, mode)
    )
    return {"task_id": task_id, "mode": mode, "kb_version": kb_version}


@router.get("/admin/ingestion/progress")
async def ingestion_progress(
    kb_version: str | None = Query(default=None),
    user=Depends(require_admin_auth),
):
    """查询入库进度详情。"""
    from ingestion.service import get_ingestion_progress
    kb_version = kb_version or get_settings().default_kb_version
    return get_ingestion_progress(kb_version)


@router.get("/admin/ingestion/tasks")
async def ingestion_tasks(user=Depends(require_admin_auth)):
    """列出所有入库任务。"""
    return {"tasks": list_tasks()}


@router.get("/admin/ingestion/tasks/{task_id}")
async def ingestion_task_detail(task_id: str, user=Depends(require_admin_auth)):
    """查询单个入库任务状态。"""
    task = get_task(task_id)
    if task is None:
        return {"error": "task not found", "task_id": task_id}
    return task


# ──────────────────────────────────────────────────────────────
# 检索质量监控
# ──────────────────────────────────────────────────────────────

@router.get("/admin/retrieval-logs")
async def retrieval_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user=Depends(require_admin_auth),
):
    """分页查询检索日志。"""
    settings = get_settings()
    engine = create_engine(settings.mysql_sync_uri)
    offset = (page - 1) * page_size
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT id, session_id, query, intent, channel, "
                    "hit_count, top_score, elapsed_ms, trace_id, created_at "
                    "FROM retrieval_logs "
                    "ORDER BY id DESC LIMIT :lim OFFSET :off"
                ),
                {"lim": page_size, "off": offset},
            )
            logs = [
                {
                    "id": r[0],
                    "session_id": r[1],
                    "query": r[2][:200] if r[2] else "",
                    "intent": r[3],
                    "channel": r[4],
                    "hit_count": r[5],
                    "top_score": round(r[6], 4) if r[6] else None,
                    "elapsed_ms": r[7],
                    "trace_id": r[8],
                    "created_at": str(r[9]) if r[9] else "",
                }
                for r in result
            ]
            total = conn.execute(
                text("SELECT COUNT(*) FROM retrieval_logs")
            ).scalar() or 0
        return {"logs": logs, "total": total}
    except Exception as exc:
        logger.error("retrieval_logs_query_error", error=str(exc))
        return {"logs": [], "total": 0}
    finally:
        engine.dispose()


@router.get("/admin/retrieval-stats")
async def retrieval_stats(user=Depends(require_teacher_auth)):
    """检索质量统计：总数、平均命中率、平均耗时、渠道分布。"""
    settings = get_settings()
    engine = create_engine(settings.mysql_sync_uri)
    try:
        with engine.connect() as conn:
            total = conn.execute(
                text("SELECT COUNT(*) FROM retrieval_logs")
            ).scalar() or 0

            avg_hit = conn.execute(
                text("SELECT AVG(hit_count) FROM retrieval_logs")
            ).scalar() or 0

            avg_elapsed = conn.execute(
                text("SELECT AVG(elapsed_ms) FROM retrieval_logs")
            ).scalar() or 0

            zero_hit = conn.execute(
                text(
                    "SELECT COUNT(*) FROM retrieval_logs WHERE hit_count = 0"
                )
            ).scalar() or 0

            channel_rows = conn.execute(
                text(
                    "SELECT channel, COUNT(*) as cnt, AVG(hit_count) as avg_hit "
                    "FROM retrieval_logs GROUP BY channel"
                )
            )
            channels = [
                {"channel": r[0], "count": r[1], "avg_hit": round(r[2] or 0, 2)}
                for r in channel_rows
            ]

        return {
            "total": total,
            "avg_hit_count": round(avg_hit, 2),
            "avg_elapsed_ms": round(avg_elapsed, 0),
            "zero_hit_count": zero_hit,
            "zero_hit_rate": round(zero_hit / total, 4) if total else 0,
            "channels": channels,
        }
    except Exception as exc:
        logger.error("retrieval_stats_error", error=str(exc))
        return {
            "total": 0,
            "avg_hit_count": 0,
            "avg_elapsed_ms": 0,
            "zero_hit_count": 0,
            "zero_hit_rate": 0,
            "channels": [],
        }
    finally:
        engine.dispose()


# ──────────────────────────────────────────────────────────────
# 用户反馈分析
# ──────────────────────────────────────────────────────────────

@router.get("/admin/feedbacks")
async def list_feedbacks(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    rating: str | None = Query(default=None),
    user=Depends(require_teacher_auth),
):
    """分页查询用户反馈。"""
    settings = get_settings()
    engine = create_engine(settings.mysql_sync_uri)
    offset = (page - 1) * page_size
    where = "WHERE rating = :r" if rating else ""
    params: dict[str, Any] = {"lim": page_size, "off": offset}
    if rating:
        params["r"] = rating
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    f"SELECT id, session_id, course_id, question, answer, "
                    f"rating, comment, created_at FROM qa_feedback "
                    f"{where} ORDER BY id DESC LIMIT :lim OFFSET :off"
                ),
                params,
            )
            feedbacks = [
                {
                    "id": r[0],
                    "session_id": r[1],
                    "course_id": r[2],
                    "question": (r[3] or "")[:200],
                    "answer": (r[4] or "")[:200],
                    "rating": r[5],
                    "comment": r[6],
                    "created_at": str(r[7]) if r[7] else "",
                }
                for r in result
            ]
            total = conn.execute(
                text(f"SELECT COUNT(*) FROM qa_feedback {where}"), params
            ).scalar() or 0
        return {"feedbacks": feedbacks, "total": total}
    except Exception as exc:
        logger.error("feedbacks_query_error", error=str(exc))
        return {"feedbacks": [], "total": 0}
    finally:
        engine.dispose()


@router.get("/admin/feedbacks/stats")
async def feedback_stats(user=Depends(require_teacher_auth)):
    """反馈统计：总数、有用率、无用率。"""
    settings = get_settings()
    engine = create_engine(settings.mysql_sync_uri)
    try:
        with engine.connect() as conn:
            total = conn.execute(
                text("SELECT COUNT(*) FROM qa_feedback")
            ).scalar() or 0
            useful = conn.execute(
                text("SELECT COUNT(*) FROM qa_feedback WHERE rating = 'useful'")
            ).scalar() or 0
            not_useful = conn.execute(
                text(
                    "SELECT COUNT(*) FROM qa_feedback WHERE rating = 'not_useful'"
                )
            ).scalar() or 0
        return {
            "total": total,
            "useful": useful,
            "not_useful": not_useful,
            "useful_rate": round(useful / total, 4) if total else 0,
        }
    except Exception as exc:
        logger.error("feedback_stats_error", error=str(exc))
        return {"total": 0, "useful": 0, "not_useful": 0, "useful_rate": 0}
    finally:
        engine.dispose()


# ──────────────────────────────────────────────────────────────
# 审计日志
# ──────────────────────────────────────────────────────────────

@router.get("/admin/audit-logs")
async def audit_logs(
    page: int = Query(default=1),
    page_size: int = Query(default=20),
    user=Depends(require_admin_auth),
):
    try:
        from api.audit import get_audit_logger
        audit = get_audit_logger()
        offset = (page - 1) * page_size
        with audit.engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT id, operator_id, action, resource, response_status, "
                    "ip, trace_id, created_at FROM audit_logs "
                    "ORDER BY id DESC LIMIT :lim OFFSET :off"
                ),
                {"lim": page_size, "off": offset},
            )
            logs = [dict(r._mapping) for r in result]
            total = conn.execute(text("SELECT COUNT(*) FROM audit_logs")).scalar()
        return {"logs": logs, "total": total or 0}
    except Exception:
        return {"logs": [], "total": 0}


# ──────────────────────────────────────────────────────────────
# P1: 仪表盘统计
# ──────────────────────────────────────────────────────────────

@router.get("/admin/dashboard/stats")
async def dashboard_stats(user=Depends(require_teacher_auth)):
    """仪表盘聚合统计：检索趋势、命中率、反馈率、用户数。"""
    settings = get_settings()
    engine = create_engine(settings.mysql_sync_uri)
    try:
        with engine.connect() as conn:
            total_queries = conn.execute(
                text("SELECT COUNT(*) FROM retrieval_logs")
            ).scalar() or 0

            total_feedback = conn.execute(
                text("SELECT COUNT(*) FROM qa_feedback")
            ).scalar() or 0

            useful_feedback = conn.execute(
                text("SELECT COUNT(*) FROM qa_feedback WHERE rating = 'useful'")
            ).scalar() or 0

            total_users = conn.execute(
                text("SELECT COUNT(*) FROM users WHERE is_active = 1")
            ).scalar() or 0

            total_docs = conn.execute(
                text("SELECT COUNT(*) FROM file_registry")
            ).scalar() or 0

            avg_hit = conn.execute(
                text("SELECT AVG(hit_count) FROM retrieval_logs")
            ).scalar() or 0

            zero_hit = conn.execute(
                text("SELECT COUNT(*) FROM retrieval_logs WHERE hit_count = 0")
            ).scalar() or 0

            trend_rows = conn.execute(
                text(
                    "SELECT DATE(created_at) as d, COUNT(*) as cnt, "
                    "AVG(hit_count) as avg_hit "
                    "FROM retrieval_logs "
                    "WHERE created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY) "
                    "GROUP BY DATE(created_at) ORDER BY d"
                )
            )
            trend = [
                {
                    "date": str(r[0]),
                    "count": r[1],
                    "avg_hit": round(r[2] or 0, 2),
                }
                for r in trend_rows
            ]

        return {
            "total_queries": total_queries,
            "total_feedback": total_feedback,
            "total_users": total_users,
            "total_docs": total_docs,
            "avg_hit_count": round(avg_hit, 2),
            "zero_hit_rate": round(zero_hit / total_queries, 4) if total_queries else 0,
            "feedback_rate": round(total_feedback / total_queries, 4) if total_queries else 0,
            "useful_rate": round(useful_feedback / total_feedback, 4) if total_feedback else 0,
            "query_trend": trend,
        }
    except Exception as exc:
        logger.error("dashboard_stats_error", error=str(exc))
        return {
            "total_queries": 0, "total_feedback": 0, "total_users": 0,
            "total_docs": 0, "avg_hit_count": 0, "zero_hit_rate": 0,
            "feedback_rate": 0, "useful_rate": 0, "query_trend": [],
        }
    finally:
        engine.dispose()


# ──────────────────────────────────────────────────────────────
# P1: 用户管理 CRUD
# ──────────────────────────────────────────────────────────────

@router.get("/admin/users")
async def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    role: str | None = Query(default=None),
    user=Depends(require_admin_auth),
):
    """分页查询用户列表。"""
    settings = get_settings()
    engine = create_engine(settings.mysql_sync_uri)
    offset = (page - 1) * page_size
    where = "WHERE role = :r" if role else ""
    params: dict[str, Any] = {"lim": page_size, "off": offset}
    if role:
        params["r"] = role
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    f"SELECT id, user_id, username, role, course_ids, "
                    f"display_name, is_active, created_at, updated_at "
                    f"FROM users {where} ORDER BY id DESC LIMIT :lim OFFSET :off"
                ),
                params,
            )
            users = [
                {
                    "id": r[0],
                    "user_id": r[1],
                    "username": r[2],
                    "role": r[3],
                    "course_ids": r[4].split(",") if r[4] else [],
                    "display_name": r[5],
                    "is_active": bool(r[6]),
                    "created_at": str(r[7]) if r[7] else "",
                    "updated_at": str(r[8]) if r[8] else "",
                }
                for r in result
            ]
            total = conn.execute(
                text(f"SELECT COUNT(*) FROM users {where}"), params
            ).scalar() or 0
        return {"users": users, "total": total}
    except Exception as exc:
        logger.error("list_users_error", error=str(exc))
        return {"users": [], "total": 0}
    finally:
        engine.dispose()


class UserCreateRequest(BaseModel):
    username: str
    password: str
    role: str = "student"
    course_ids: str = ""
    display_name: str | None = None


@router.post("/admin/users")
async def create_user(req: UserCreateRequest, user=Depends(require_admin_auth)):
    """创建新用户。"""
    import bcrypt as _bcrypt
    settings = get_settings()
    engine = create_engine(settings.mysql_sync_uri)
    user_id = f"{req.role}_{int(time.time())}_{os.urandom(3).hex()}"
    password_hash = _bcrypt.hashpw(
        req.password.encode(), _bcrypt.gensalt()
    ).decode()
    try:
        with engine.connect() as conn:
            existing = conn.execute(
                text("SELECT id FROM users WHERE username = :u"),
                {"u": req.username},
            ).fetchone()
            if existing:
                return {"error": "用户名已存在"}
            conn.execute(
                text(
                    "INSERT INTO users (user_id, username, password_hash, role, "
                    "course_ids, display_name, is_active) "
                    "VALUES (:uid, :un, :ph, :r, :ci, :dn, 1)"
                ),
                {
                    "uid": user_id, "un": req.username, "ph": password_hash,
                    "r": req.role, "ci": req.course_ids, "dn": req.display_name,
                },
            )
            conn.commit()
        return {"user_id": user_id, "username": req.username, "role": req.role}
    except Exception as exc:
        logger.error("create_user_error", error=str(exc))
        return {"error": str(exc)[:200]}
    finally:
        engine.dispose()


class UserUpdateRequest(BaseModel):
    role: str | None = None
    course_ids: str | None = None
    display_name: str | None = None
    is_active: bool | None = None
    password: str | None = None


@router.put("/admin/users/{user_id}")
async def update_user(
    user_id: str,
    req: UserUpdateRequest,
    user=Depends(require_admin_auth),
):
    """编辑用户信息（角色/课程/显示名/启用状态/密码）。"""
    import bcrypt as _bcrypt
    settings = get_settings()
    engine = create_engine(settings.mysql_sync_uri)
    try:
        with engine.connect() as conn:
            sets: list[str] = []
            params: dict[str, Any] = {"uid": user_id}
            if req.role is not None:
                sets.append("role = :role")
                params["role"] = req.role
            if req.course_ids is not None:
                sets.append("course_ids = :ci")
                params["ci"] = req.course_ids
            if req.display_name is not None:
                sets.append("display_name = :dn")
                params["dn"] = req.display_name
            if req.is_active is not None:
                sets.append("is_active = :ia")
                params["ia"] = 1 if req.is_active else 0
            if req.password is not None:
                sets.append("password_hash = :ph")
                params["ph"] = _bcrypt.hashpw(
                    req.password.encode(), _bcrypt.gensalt()
                ).decode()
            if not sets:
                return {"updated": False, "message": "无更新字段"}
            conn.execute(
                text(f"UPDATE users SET {', '.join(sets)} WHERE user_id = :uid"),
                params,
            )
            conn.commit()
        return {"updated": True, "user_id": user_id}
    except Exception as exc:
        logger.error("update_user_error", error=str(exc))
        return {"error": str(exc)[:200]}
    finally:
        engine.dispose()


@router.delete("/admin/users/{user_id}")
async def disable_user(user_id: str, user=Depends(require_admin_auth)):
    """禁用用户（软删除）。"""
    settings = get_settings()
    engine = create_engine(settings.mysql_sync_uri)
    try:
        with engine.connect() as conn:
            conn.execute(
                text("UPDATE users SET is_active = 0 WHERE user_id = :uid"),
                {"uid": user_id},
            )
            conn.commit()
        return {"disabled": True, "user_id": user_id}
    except Exception as exc:
        logger.error("disable_user_error", error=str(exc))
        return {"error": str(exc)[:200]}
    finally:
        engine.dispose()


# ──────────────────────────────────────────────────────────────
# P1: 课程管理 CRUD
# ──────────────────────────────────────────────────────────────

@router.get("/admin/courses")
async def list_courses(
    user=Depends(require_teacher_auth),
):
    """查询所有课程列表。"""
    settings = get_settings()
    engine = create_engine(settings.mysql_sync_uri)
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT course_id, title, description, "
                    "active_kb_version, is_deleted, created_at "
                    "FROM courses "
                    "WHERE is_deleted = 0 AND course_id != '' "
                    "ORDER BY course_id"
                )
            )
            courses = [
                {
                    "course_id": r[0],
                    "title": r[1],
                    "description": r[2] or "",
                    "active_kb_version": r[3],
                    "created_at": str(r[5]) if r[5] else "",
                }
                for r in result
            ]
        return {"courses": courses}
    except Exception as exc:
        logger.error("list_courses_error", error=str(exc))
        return {"courses": []}
    finally:
        engine.dispose()


class CourseCreateRequest(BaseModel):
    course_id: str
    title: str
    description: str = ""
    active_kb_version: str | None = None
    # 同时创建知识库版本（可选）：提供后自动创建版本并激活绑定到该课程
    create_kb_version: str | None = None
    kb_description: str = ""


@router.post("/admin/courses")
async def create_course(req: CourseCreateRequest, user=Depends(require_admin_auth)):
    """创建课程，可选地同时创建并激活对应知识库版本，避免操作割裂。"""
    if not req.course_id or not req.course_id.strip():
        raise HTTPException(status_code=400, detail="课程 ID 不能为空")

    new_kb = _validate_kb_version_name(req.create_kb_version) if req.create_kb_version else None

    settings = get_settings()
    engine = create_engine(settings.mysql_sync_uri)
    try:
        with engine.connect() as conn:
            if new_kb:
                exists = conn.execute(
                    text(
                        "SELECT 1 FROM kb_versions "
                        "WHERE course_id = :ci AND kb_version = :kb"
                    ),
                    {"ci": req.course_id, "kb": new_kb},
                ).fetchone()
                if exists:
                    raise HTTPException(status_code=409, detail=f"版本已存在: {new_kb}")

            conn.execute(
                text(
                    "INSERT INTO courses (course_id, title, description, "
                    "active_kb_version) VALUES (:ci, :t, :d, :kb)"
                ),
                {"ci": req.course_id, "t": req.title, "d": req.description,
                 "kb": new_kb or req.active_kb_version or settings.default_kb_version},
            )

            if new_kb:
                conn.execute(
                    text(
                        "INSERT INTO kb_versions (course_id, kb_version, version_seq, status, "
                        "description, doc_collection, faq_collection, question_collection) "
                        "VALUES (:ci, :kb, :seq, 'active', :desc, :doc, :faq, :question)"
                    ),
                    {
                        "ci": req.course_id,
                        "kb": new_kb,
                        "seq": int(time.time()),
                        "desc": req.kb_description,
                        "doc": f"edu_doc_hybrid_{new_kb}",
                        "faq": f"edu_faq_hybrid_{new_kb}",
                        "question": f"edu_question_hybrid_{new_kb}",
                    },
                )
            conn.commit()
    except HTTPException:
        raise
    except Exception as exc:
        return {"error": str(exc)[:200]}
    finally:
        engine.dispose()

    if new_kb:
        try:
            from vector_store.milvus_client import get_milvus_store

            store = get_milvus_store()
            for name in (
                f"edu_doc_hybrid_{new_kb}",
                f"edu_faq_hybrid_{new_kb}",
                f"edu_question_hybrid_{new_kb}",
            ):
                store.ensure_collection(name)
        except Exception as exc:
            logger.warning("create_course_kb_collection_failed", kb_version=new_kb, error=str(exc))

    return {
        "course_id": req.course_id,
        "title": req.title,
        "kb_version": new_kb or req.active_kb_version or settings.default_kb_version,
        "kb_created": bool(new_kb),
    }


class CourseUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    active_kb_version: str | None = None


@router.put("/admin/courses/{course_id}")
async def update_course(
    course_id: str,
    req: CourseUpdateRequest,
    user=Depends(require_admin_auth),
):
    settings = get_settings()
    engine = create_engine(settings.mysql_sync_uri)
    try:
        with engine.connect() as conn:
            sets: list[str] = []
            params: dict[str, Any] = {"ci": course_id}
            if req.title is not None:
                sets.append("title = :t")
                params["t"] = req.title
            if req.description is not None:
                sets.append("description = :d")
                params["d"] = req.description
            if req.active_kb_version is not None:
                sets.append("active_kb_version = :kb")
                params["kb"] = req.active_kb_version
            if not sets:
                return {"updated": False}
            conn.execute(
                text(f"UPDATE courses SET {', '.join(sets)} WHERE course_id = :ci"),
                params,
            )
            conn.commit()
        return {"updated": True, "course_id": course_id}
    except Exception as exc:
        return {"error": str(exc)[:200]}
    finally:
        engine.dispose()


@router.delete("/admin/courses/{course_id}")
async def delete_course(course_id: str, user=Depends(require_admin_auth)):
    if not course_id or not course_id.strip():
        raise HTTPException(status_code=400, detail="课程 ID 不能为空")
    settings = get_settings()
    engine = create_engine(settings.mysql_sync_uri)
    try:
        with engine.connect() as conn:
            conn.execute(
                text("UPDATE courses SET is_deleted = 1 WHERE course_id = :ci"),
                {"ci": course_id},
            )
            conn.commit()
        return {"deleted": True, "course_id": course_id}
    except Exception as exc:
        return {"error": str(exc)[:200]}
    finally:
        engine.dispose()


# ──────────────────────────────────────────────────────────────
# P1: FAQ 管理 CRUD
# ──────────────────────────────────────────────────────────────

@router.get("/admin/faqs")
async def list_faqs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    course_id: str | None = Query(default=None),
    user=Depends(require_admin_auth),
):
    settings = get_settings()
    engine = create_engine(settings.mysql_sync_uri)
    offset = (page - 1) * page_size
    where = "WHERE is_deleted = 0 AND course_id = :ci" if course_id else "WHERE is_deleted = 0"
    params: dict[str, Any] = {"lim": page_size, "off": offset}
    if course_id:
        params["ci"] = course_id
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    f"SELECT faq_id, course_id, question, answer, source, "
                    f"created_at FROM faqs {where} "
                    f"ORDER BY faq_id DESC LIMIT :lim OFFSET :off"
                ),
                params,
            )
            faqs = [
                {
                    "faq_id": r[0],
                    "course_id": r[1],
                    "question": (r[2] or "")[:200],
                    "answer": (r[3] or "")[:200],
                    "source": r[4],
                    "created_at": str(r[5]) if r[5] else "",
                }
                for r in result
            ]
            total = conn.execute(
                text(f"SELECT COUNT(*) FROM faqs {where}"), params
            ).scalar() or 0
        return {"faqs": faqs, "total": total}
    except Exception as exc:
        logger.error("list_faqs_error", error=str(exc))
        return {"faqs": [], "total": 0}
    finally:
        engine.dispose()


class FaqCreateRequest(BaseModel):
    course_id: str
    question: str
    answer: str
    source: str = ""


@router.post("/admin/faqs")
async def create_faq(req: FaqCreateRequest, user=Depends(require_admin_auth)):
    settings = get_settings()
    engine = create_engine(settings.mysql_sync_uri)
    faq_id = f"faq_{int(time.time())}_{os.urandom(3).hex()}"
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "INSERT INTO faqs (faq_id, course_id, question, answer, source) "
                    "VALUES (:fid, :ci, :q, :a, :s)"
                ),
                {"fid": faq_id, "ci": req.course_id, "q": req.question, "a": req.answer, "s": req.source},
            )
            conn.commit()
        return {"faq_id": faq_id}
    except Exception as exc:
        return {"error": str(exc)[:200]}
    finally:
        engine.dispose()


@router.delete("/admin/faqs/{faq_id}")
async def delete_faq(faq_id: str, user=Depends(require_admin_auth)):
    settings = get_settings()
    engine = create_engine(settings.mysql_sync_uri)
    try:
        with engine.connect() as conn:
            conn.execute(
                text("UPDATE faqs SET is_deleted = 1 WHERE faq_id = :fid"),
                {"fid": faq_id},
            )
            conn.commit()
        return {"deleted": True, "faq_id": faq_id}
    except Exception as exc:
        return {"error": str(exc)[:200]}
    finally:
        engine.dispose()


# ──────────────────────────────────────────────────────────────
# P1: 审计日志增强（筛选 + CSV 导出）
# ──────────────────────────────────────────────────────────────

@router.get("/admin/audit-logs/filtered")
async def audit_logs_filtered(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    operator_id: str | None = Query(default=None),
    action: str | None = Query(default=None),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    user=Depends(require_admin_auth),
):
    """带筛选条件的审计日志查询。"""
    settings = get_settings()
    engine = create_engine(settings.mysql_sync_uri)
    offset = (page - 1) * page_size
    conditions = []
    params: dict[str, Any] = {"lim": page_size, "off": offset}
    if operator_id:
        conditions.append("operator_id = :oid")
        params["oid"] = operator_id
    if action:
        conditions.append("action = :act")
        params["act"] = action
    if start_date:
        conditions.append("created_at >= :sd")
        params["sd"] = start_date
    if end_date:
        conditions.append("created_at <= :ed")
        params["ed"] = end_date
    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    f"SELECT id, operator_id, action, resource, "
                    f"response_status, ip, trace_id, created_at "
                    f"FROM audit_logs {where} "
                    f"ORDER BY id DESC LIMIT :lim OFFSET :off"
                ),
                params,
            )
            logs = [dict(r._mapping) for r in result]
            total = conn.execute(
                text(f"SELECT COUNT(*) FROM audit_logs {where}"), params
            ).scalar() or 0
        return {"logs": logs, "total": total}
    except Exception as exc:
        logger.error("audit_filtered_error", error=str(exc))
        return {"logs": [], "total": 0}
    finally:
        engine.dispose()


# ──────────────────────────────────────────────────────────────
# P1: 配置管理
# ──────────────────────────────────────────────────────────────

@router.get("/admin/config")
async def get_config(user=Depends(require_admin_auth)):
    """返回系统配置（敏感字段脱敏）。"""
    settings = get_settings()
    return {
        "llm_model": settings.llm_model,
        "llm_fallback_model": settings.llm_fallback_model,
        "embedding_model_path": settings.embedding_model_path,
        "reranker_model_path": settings.reranker_model_path,
        "milvus_uri": settings.milvus_uri,
        "redis_url": "***REDIS***",
        "mysql_host": settings.mysql_host,
        "mysql_database": settings.mysql_database,
        "doc_top_k": settings.doc_top_k,
        "faq_top_k": settings.faq_top_k,
        "rerank_top_n": settings.rerank_top_n,
        "embedding_batch_size": settings.embedding_batch_size,
        "min_chunk_chars": settings.min_chunk_chars,
        "chunk_dedup_jaccard_threshold": settings.chunk_dedup_jaccard_threshold,
        "rag_min_score_threshold": settings.rag_min_score_threshold,
    }


class ConfigUpdateRequest(BaseModel):
    doc_top_k: int | None = None
    faq_top_k: int | None = None
    rerank_top_n: int | None = None
    rag_min_score_threshold: float | None = None


@router.put("/admin/config")
async def update_config(
    req: ConfigUpdateRequest,
    user=Depends(require_admin_auth),
):
    """热更新检索参数（写入运行时覆盖）。"""
    settings = get_settings()
    updated = []
    if req.doc_top_k is not None:
        settings.doc_top_k = req.doc_top_k
        updated.append(f"doc_top_k={req.doc_top_k}")
    if req.faq_top_k is not None:
        settings.faq_top_k = req.faq_top_k
        updated.append(f"faq_top_k={req.faq_top_k}")
    if req.rerank_top_n is not None:
        settings.rerank_top_n = req.rerank_top_n
        updated.append(f"rerank_top_n={req.rerank_top_n}")
    if req.rag_min_score_threshold is not None:
        settings.rag_min_score_threshold = req.rag_min_score_threshold
        updated.append(f"rag_min_score_threshold={req.rag_min_score_threshold}")
    return {"updated": updated}


# ──────────────────────────────────────────────────────────────
# P2: KB 版本管理
# ──────────────────────────────────────────────────────────────

@router.get("/admin/kb-versions")
async def list_kb_versions(
    course_id: str | None = Query(default=None),
    user=Depends(require_admin_auth),
):
    """查询知识库版本列表。"""
    settings = get_settings()
    engine = create_engine(settings.mysql_sync_uri)
    where = "WHERE is_deleted = 0 AND course_id = :ci" if course_id else "WHERE is_deleted = 0"
    params: dict[str, Any] = {}
    if course_id:
        params["ci"] = course_id
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    f"SELECT course_id, kb_version, version_seq, status, "
                    f"description, doc_collection, faq_collection, "
                    f"question_collection, created_at, updated_at "
                    f"FROM kb_versions {where} ORDER BY version_seq DESC"
                ),
                params,
            )
            versions = [
                {
                    "course_id": r[0],
                    "kb_version": r[1],
                    "version_seq": r[2],
                    "status": r[3],
                    "description": r[4] or "",
                    "doc_collection": r[5],
                    "faq_collection": r[6],
                    "question_collection": r[7],
                    "created_at": str(r[8]) if r[8] else "",
                    "updated_at": str(r[9]) if r[9] else "",
                }
                for r in result
            ]
        return {"versions": versions, "total": len(versions)}
    except Exception as exc:
        logger.error("list_kb_versions_error", error=str(exc))
        return {"versions": [], "total": 0}
    finally:
        engine.dispose()


class KbVersionCreateRequest(BaseModel):
    course_id: str
    kb_version: str
    description: str = ""
    activate: bool = False


@router.post("/admin/kb-versions")
async def create_kb_version(req: KbVersionCreateRequest, user=Depends(require_admin_auth)):
    """创建知识库版本：登记 kb_versions 并预创建三个 Collection。

    kb_version 即知识库名，会映射为 `edu_doc_hybrid_{kb_version}`、
    `edu_faq_hybrid_{kb_version}`、`edu_question_hybrid_{kb_version}` 三个
    Collection，实现不同课程/年级文档的向量隔离。
    """
    kb = _validate_kb_version_name(req.kb_version)

    settings = get_settings()
    engine = create_engine(settings.mysql_sync_uri)
    try:
        with engine.connect() as conn:
            course = conn.execute(
                text(
                    "SELECT course_id FROM courses "
                    "WHERE course_id = :ci AND is_deleted = 0"
                ),
                {"ci": req.course_id},
            ).fetchone()
            if course is None:
                raise HTTPException(status_code=404, detail=f"课程不存在: {req.course_id}")

            exists = conn.execute(
                text(
                    "SELECT 1 FROM kb_versions "
                    "WHERE course_id = :ci AND kb_version = :kb"
                ),
                {"ci": req.course_id, "kb": kb},
            ).fetchone()
            if exists:
                raise HTTPException(status_code=409, detail=f"版本已存在: {kb}")

            conn.execute(
                text(
                    "INSERT INTO kb_versions (course_id, kb_version, version_seq, status, "
                    "description, doc_collection, faq_collection, question_collection) "
                    "VALUES (:ci, :kb, :seq, :status, :desc, :doc, :faq, :question)"
                ),
                {
                    "ci": req.course_id,
                    "kb": kb,
                    "seq": int(time.time()),
                    "status": "active" if req.activate else "inactive",
                    "desc": req.description,
                    "doc": f"edu_doc_hybrid_{kb}",
                    "faq": f"edu_faq_hybrid_{kb}",
                    "question": f"edu_question_hybrid_{kb}",
                },
            )

            if req.activate:
                conn.execute(
                    text(
                        "UPDATE courses SET active_kb_version = :kb "
                        "WHERE course_id = :ci AND is_deleted = 0"
                    ),
                    {"kb": kb, "ci": req.course_id},
                )
                conn.execute(
                    text(
                        "UPDATE kb_versions SET status = 'archived' "
                        "WHERE course_id = :ci AND kb_version != :kb AND is_deleted = 0"
                    ),
                    {"ci": req.course_id, "kb": kb},
                )
            conn.commit()
    finally:
        engine.dispose()

    # 预创建三个 Collection（幂等）
    try:
        from vector_store.milvus_client import get_milvus_store

        store = get_milvus_store()
        for name in (
            f"edu_doc_hybrid_{kb}",
            f"edu_faq_hybrid_{kb}",
            f"edu_question_hybrid_{kb}",
        ):
            store.ensure_collection(name)
    except Exception as exc:
        logger.warning("create_kb_version_collection_failed", kb_version=kb, error=str(exc))

    return {
        "created": True,
        "course_id": req.course_id,
        "kb_version": kb,
        "doc_collection": f"edu_doc_hybrid_{kb}",
        "faq_collection": f"edu_faq_hybrid_{kb}",
        "question_collection": f"edu_question_hybrid_{kb}",
        "activated": req.activate,
    }


@router.put("/admin/kb-versions/{kb_version}/activate")
async def activate_kb_version(
    kb_version: str,
    course_id: str = Query(...),
    user=Depends(require_admin_auth),
):
    """激活指定知识库版本：更新课程活跃版本 + 预加载 Collection。"""
    settings = get_settings()
    engine = create_engine(settings.mysql_sync_uri)
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "UPDATE courses SET active_kb_version = :kb "
                    "WHERE course_id = :ci AND is_deleted = 0"
                ),
                {"kb": kb_version, "ci": course_id},
            )
            conn.execute(
                text(
                    "UPDATE kb_versions SET status = 'active' "
                    "WHERE kb_version = :kb AND course_id = :ci"
                ),
                {"kb": kb_version, "ci": course_id},
            )
            conn.execute(
                text(
                    "UPDATE kb_versions SET status = 'archived' "
                    "WHERE kb_version != :kb AND course_id = :ci AND is_deleted = 0"
                ),
                {"kb": kb_version, "ci": course_id},
            )
            conn.commit()

        try:
            from vector_store.collection_lifecycle import CollectionLifecycleManager
            mgr = CollectionLifecycleManager()
            mgr.preload_active_collections({course_id: kb_version})
        except Exception as exc:
            logger.warning("preload_after_activate_failed", error=str(exc))

        return {"activated": True, "kb_version": kb_version, "course_id": course_id}
    except Exception as exc:
        logger.error("activate_kb_version_error", error=str(exc))
        return {"error": str(exc)[:200]}
    finally:
        engine.dispose()


# ──────────────────────────────────────────────────────────────
# P2: 索引重建
# ──────────────────────────────────────────────────────────────

@router.post("/admin/indexes/rebuild")
async def rebuild_index(
    collection: str = Query(...),
    dry_run: bool = Query(default=False),
    user=Depends(require_admin_auth),
):
    """重建 Milvus Collection 的 HNSW 索引。"""
    try:
        from pymilvus import Collection, connections, utility

        settings = get_settings()
        if not connections.has_connection("default"):
            connections.connect(alias="default", uri=settings.milvus_uri)

        if not utility.has_collection(collection):
            return {"error": f"Collection '{collection}' 不存在"}

        col = Collection(collection)

        if dry_run:
            try:
                idx_info = col.indexes
                return {
                    "dry_run": True,
                    "collection": collection,
                    "row_count": col.num_entities,
                    "indexes": [
                        {"field_name": idx.field_name, "index_type": getattr(idx, 'index_type', 'N/A')}
                        for idx in idx_info
                    ],
                }
            except Exception:
                return {"dry_run": True, "collection": collection, "row_count": col.num_entities}

        col.release()
        for idx in list(col.indexes):
            try:
                col.drop_index(index_name=idx.field_name)
            except Exception:
                pass

        try:
            from pymilvus import IndexParams
            idx_params = IndexParams()
            idx_params.add_index(
                field_name="embedding",
                index_type="HNSW",
                metric_type="IP",
                params={"M": 32, "efConstruction": 256},
            )
            col.create_index(idx_params)
        except Exception as exc:
            logger.warning("create_hnsw_index_failed", error=str(exc))

        col.load()
        return {
            "rebuilt": True,
            "collection": collection,
            "row_count": col.num_entities,
        }
    except Exception as exc:
        logger.error("rebuild_index_error", error=str(exc))
        return {"error": str(exc)[:200]}


# ──────────────────────────────────────────────────────────────
# P2: 章节管理 CRUD
# ──────────────────────────────────────────────────────────────

@router.get("/admin/courses/{course_id}/chapters")
async def list_chapters(
    course_id: str,
    user=Depends(require_admin_auth),
):
    """查询指定课程的章节列表。"""
    settings = get_settings()
    engine = create_engine(settings.mysql_sync_uri)
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT chapter_id, course_id, chapter_no, title, summary, "
                    "created_at, updated_at FROM chapters "
                    "WHERE course_id = :ci AND is_deleted = 0 "
                    "ORDER BY chapter_no"
                ),
                {"ci": course_id},
            )
            chapters = [
                {
                    "chapter_id": r[0],
                    "course_id": r[1],
                    "chapter_no": r[2],
                    "title": r[3],
                    "summary": r[4] or "",
                    "created_at": str(r[5]) if r[5] else "",
                    "updated_at": str(r[6]) if r[6] else "",
                }
                for r in result
            ]
        return {"chapters": chapters, "total": len(chapters)}
    except Exception as exc:
        logger.error("list_chapters_error", error=str(exc))
        return {"chapters": [], "total": 0}
    finally:
        engine.dispose()


class ChapterCreateRequest(BaseModel):
    chapter_no: int
    title: str
    summary: str = ""


@router.post("/admin/courses/{course_id}/chapters")
async def create_chapter(
    course_id: str,
    req: ChapterCreateRequest,
    user=Depends(require_admin_auth),
):
    """创建章节。"""
    settings = get_settings()
    engine = create_engine(settings.mysql_sync_uri)
    chapter_id = f"chap_{int(time.time())}_{os.urandom(3).hex()}"
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "INSERT INTO chapters (chapter_id, course_id, chapter_no, title, summary) "
                    "VALUES (:cid, :ci, :cn, :t, :s)"
                ),
                {"cid": chapter_id, "ci": course_id, "cn": req.chapter_no, "t": req.title, "s": req.summary},
            )
            conn.commit()
        return {"chapter_id": chapter_id, "title": req.title}
    except Exception as exc:
        return {"error": str(exc)[:200]}
    finally:
        engine.dispose()


class ChapterUpdateRequest(BaseModel):
    chapter_no: int | None = None
    title: str | None = None
    summary: str | None = None


@router.put("/admin/chapters/{chapter_id}")
async def update_chapter(
    chapter_id: str,
    req: ChapterUpdateRequest,
    user=Depends(require_admin_auth),
):
    """编辑章节。"""
    settings = get_settings()
    engine = create_engine(settings.mysql_sync_uri)
    try:
        with engine.connect() as conn:
            sets: list[str] = []
            params: dict[str, Any] = {"cid": chapter_id}
            if req.chapter_no is not None:
                sets.append("chapter_no = :cn")
                params["cn"] = req.chapter_no
            if req.title is not None:
                sets.append("title = :t")
                params["t"] = req.title
            if req.summary is not None:
                sets.append("summary = :s")
                params["s"] = req.summary
            if not sets:
                return {"updated": False}
            conn.execute(
                text(f"UPDATE chapters SET {', '.join(sets)} WHERE chapter_id = :cid"),
                params,
            )
            conn.commit()
        return {"updated": True, "chapter_id": chapter_id}
    except Exception as exc:
        return {"error": str(exc)[:200]}
    finally:
        engine.dispose()


@router.delete("/admin/chapters/{chapter_id}")
async def delete_chapter(chapter_id: str, user=Depends(require_admin_auth)):
    """删除章节（软删除）。"""
    settings = get_settings()
    engine = create_engine(settings.mysql_sync_uri)
    try:
        with engine.connect() as conn:
            conn.execute(
                text("UPDATE chapters SET is_deleted = 1 WHERE chapter_id = :cid"),
                {"cid": chapter_id},
            )
            conn.commit()
        return {"deleted": True, "chapter_id": chapter_id}
    except Exception as exc:
        return {"error": str(exc)[:200]}
    finally:
        engine.dispose()


# ──────────────────────────────────────────────────────────────
# P2: 题库管理 CRUD
# ──────────────────────────────────────────────────────────────

@router.get("/admin/questions")
async def list_questions(
    course_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user=Depends(require_admin_auth),
):
    """分页查询题库。"""
    settings = get_settings()
    engine = create_engine(settings.mysql_sync_uri)
    offset = (page - 1) * page_size
    conditions = ["is_deleted = 0"]
    params: dict[str, Any] = {"lim": page_size, "off": offset}
    if course_id:
        conditions.append("course_id = :ci")
        params["ci"] = course_id
    where = "WHERE " + " AND ".join(conditions)
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    f"SELECT question_id, course_id, chapter_id, point_id, "
                    f"question_type, difficulty, question_text, answer, "
                    f"explanation, source, created_at "
                    f"FROM questions {where} ORDER BY question_id DESC LIMIT :lim OFFSET :off"
                ),
                params,
            )
            questions = [
                {
                    "question_id": r[0],
                    "course_id": r[1],
                    "chapter_id": r[2],
                    "point_id": r[3],
                    "question_type": r[4],
                    "difficulty": r[5],
                    "question_text": (r[6] or "")[:300],
                    "answer": (r[7] or "")[:200],
                    "explanation": (r[8] or "")[:200],
                    "source": r[9],
                    "created_at": str(r[10]) if r[10] else "",
                }
                for r in result
            ]
            total = conn.execute(
                text(f"SELECT COUNT(*) FROM questions {where}"), params
            ).scalar() or 0
        return {"questions": questions, "total": total}
    except Exception as exc:
        logger.error("list_questions_error", error=str(exc))
        return {"questions": [], "total": 0}
    finally:
        engine.dispose()


class QuestionCreateRequest(BaseModel):
    course_id: str
    chapter_id: str | None = None
    point_id: str | None = None
    question_type: str = "single_choice"
    difficulty: str = "medium"
    question_text: str
    answer: str = ""
    explanation: str = ""
    source: str = ""


@router.post("/admin/questions")
async def create_question(req: QuestionCreateRequest, user=Depends(require_admin_auth)):
    """创建题目。"""
    settings = get_settings()
    engine = create_engine(settings.mysql_sync_uri)
    question_id = f"q_{int(time.time())}_{os.urandom(3).hex()}"
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "INSERT INTO questions (question_id, course_id, chapter_id, "
                    "point_id, question_type, difficulty, question_text, answer, "
                    "explanation, source) "
                    "VALUES (:qid, :ci, :chid, :pid, :qt, :df, :qt_text, :ans, :exp, :src)"
                ),
                {
                    "qid": question_id, "ci": req.course_id, "chid": req.chapter_id,
                    "pid": req.point_id, "qt": req.question_type, "df": req.difficulty,
                    "qt_text": req.question_text, "ans": req.answer, "exp": req.explanation, "src": req.source,
                },
            )
            conn.commit()
        return {"question_id": question_id}
    except Exception as exc:
        return {"error": str(exc)[:200]}
    finally:
        engine.dispose()


class QuestionUpdateRequest(BaseModel):
    chapter_id: str | None = None
    point_id: str | None = None
    question_type: str | None = None
    difficulty: str | None = None
    question_text: str | None = None
    answer: str | None = None
    explanation: str | None = None


@router.put("/admin/questions/{question_id}")
async def update_question(
    question_id: str,
    req: QuestionUpdateRequest,
    user=Depends(require_admin_auth),
):
    """编辑题目。"""
    settings = get_settings()
    engine = create_engine(settings.mysql_sync_uri)
    try:
        with engine.connect() as conn:
            sets: list[str] = []
            params: dict[str, Any] = {"qid": question_id}
            if req.chapter_id is not None:
                sets.append("chapter_id = :chid")
                params["chid"] = req.chapter_id
            if req.point_id is not None:
                sets.append("point_id = :pid")
                params["pid"] = req.point_id
            if req.question_type is not None:
                sets.append("question_type = :qt")
                params["qt"] = req.question_type
            if req.difficulty is not None:
                sets.append("difficulty = :df")
                params["df"] = req.difficulty
            if req.question_text is not None:
                sets.append("question_text = :qt_text")
                params["qt_text"] = req.question_text
            if req.answer is not None:
                sets.append("answer = :ans")
                params["ans"] = req.answer
            if req.explanation is not None:
                sets.append("explanation = :exp")
                params["exp"] = req.explanation
            if not sets:
                return {"updated": False}
            conn.execute(
                text(f"UPDATE questions SET {', '.join(sets)} WHERE question_id = :qid"),
                params,
            )
            conn.commit()
        return {"updated": True, "question_id": question_id}
    except Exception as exc:
        return {"error": str(exc)[:200]}
    finally:
        engine.dispose()


@router.delete("/admin/questions/{question_id}")
async def delete_question(question_id: str, user=Depends(require_admin_auth)):
    """删除题目（软删除）。"""
    settings = get_settings()
    engine = create_engine(settings.mysql_sync_uri)
    try:
        with engine.connect() as conn:
            conn.execute(
                text("UPDATE questions SET is_deleted = 1 WHERE question_id = :qid"),
                {"qid": question_id},
            )
            conn.commit()
        return {"deleted": True, "question_id": question_id}
    except Exception as exc:
        return {"error": str(exc)[:200]}
    finally:
        engine.dispose()


# ──────────────────────────────────────────────────────────────
# P2: 学员进度查询
# ──────────────────────────────────────────────────────────────

@router.get("/admin/students/progress")
async def list_student_progress(
    course_id: str | None = Query(default=None),
    user=Depends(require_teacher_auth),
):
    """查询所有学员进度概览。"""
    settings = get_settings()
    engine = create_engine(settings.mysql_sync_uri)
    where = "WHERE 1=1"
    params: dict[str, Any] = {}
    if course_id:
        where = "WHERE sp.course_id = :ci"
        params["ci"] = course_id
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    f"SELECT sp.user_id, sp.course_id, sp.current_chapter_id, "
                    f"sp.mastered_points, sp.updated_at, "
                    f"u.username, u.display_name "
                    f"FROM student_progress sp "
                    f"LEFT JOIN users u ON sp.user_id = u.user_id "
                    f"{where} ORDER BY sp.updated_at DESC"
                ),
                params,
            )
            progress = [
                {
                    "user_id": r[0],
                    "course_id": r[1],
                    "current_chapter_id": r[2] or "",
                    "mastered_points": r[3] or "",
                    "updated_at": str(r[4]) if r[4] else "",
                    "username": r[5] or "",
                    "display_name": r[6] or "",
                }
                for r in result
            ]
        return {"progress": progress, "total": len(progress)}
    except Exception as exc:
        logger.error("list_student_progress_error", error=str(exc))
        return {"progress": [], "total": 0}
    finally:
        engine.dispose()


@router.get("/admin/students/{user_id}/progress")
async def get_student_progress(
    user_id: str,
    course_id: str | None = Query(default=None),
    user=Depends(require_teacher_auth),
):
    """查询单个学员的详细进度。"""
    settings = get_settings()
    engine = create_engine(settings.mysql_sync_uri)
    where = "WHERE sp.user_id = :uid"
    params: dict[str, Any] = {"uid": user_id}
    if course_id:
        where += " AND sp.course_id = :ci"
        params["ci"] = course_id
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    f"SELECT sp.user_id, sp.course_id, sp.current_chapter_id, "
                    f"sp.mastered_points, sp.updated_at, "
                    f"u.username, u.display_name "
                    f"FROM student_progress sp "
                    f"LEFT JOIN users u ON sp.user_id = u.user_id "
                    f"{where}"
                ),
                params,
            )
            rows = [
                {
                    "user_id": r[0],
                    "course_id": r[1],
                    "current_chapter_id": r[2] or "",
                    "mastered_points": r[3] or "",
                    "updated_at": str(r[4]) if r[4] else "",
                    "username": r[5] or "",
                    "display_name": r[6] or "",
                }
                for r in result
            ]
        return {"progress": rows}
    except Exception as exc:
        logger.error("get_student_progress_error", error=str(exc))
        return {"progress": []}
    finally:
        engine.dispose()


# ──────────────────────────────────────────────────────────────
# P2: 对话回放
# ──────────────────────────────────────────────────────────────

@router.get("/admin/sessions")
async def list_sessions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user=Depends(require_teacher_auth),
):
    """查询最近的会话列表（去重 session_id）。"""
    settings = get_settings()
    engine = create_engine(settings.mysql_sync_uri)
    offset = (page - 1) * page_size
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT session_id, COUNT(*) as msg_count, "
                    "MIN(id) as first_id, MAX(id) as last_id "
                    "FROM chat_messages "
                    "WHERE session_id IS NOT NULL AND session_id != '' "
                    "GROUP BY session_id "
                    "ORDER BY last_id DESC LIMIT :lim OFFSET :off"
                ),
                {"lim": page_size, "off": offset},
            )
            sessions = [
                {
                    "session_id": r[0],
                    "message_count": r[1],
                }
                for r in result
            ]
            total = conn.execute(
                text(
                    "SELECT COUNT(DISTINCT session_id) FROM chat_messages "
                    "WHERE session_id IS NOT NULL AND session_id != ''"
                )
            ).scalar() or 0
        return {"sessions": sessions, "total": total}
    except Exception as exc:
        logger.error("list_sessions_error", error=str(exc))
        return {"sessions": [], "total": 0}
    finally:
        engine.dispose()


@router.get("/admin/sessions/{session_id}/replay")
async def session_replay(
    session_id: str,
    user=Depends(require_teacher_auth),
):
    """对话回放：按 session_id 关联聊天消息和检索日志。"""
    settings = get_settings()
    engine = create_engine(settings.mysql_sync_uri)
    try:
        with engine.connect() as conn:
            msg_result = conn.execute(
                text(
                    "SELECT id, session_id, message FROM chat_messages "
                    "WHERE session_id = :sid ORDER BY id"
                ),
                {"sid": session_id},
            )
            messages = [
                {
                    "id": r[0],
                    "session_id": r[1],
                    "message": r[2] or "",
                }
                for r in msg_result
            ]

            ret_result = conn.execute(
                text(
                    "SELECT id, session_id, query, intent, channel, "
                    "hit_count, top_score, elapsed_ms, trace_id, created_at "
                    "FROM retrieval_logs "
                    "WHERE session_id = :sid ORDER BY id"
                ),
                {"sid": session_id},
            )
            retrieval_logs = [
                {
                    "id": r[0],
                    "session_id": r[1],
                    "query": r[2] or "",
                    "intent": r[3],
                    "channel": r[4],
                    "hit_count": r[5],
                    "top_score": round(r[6], 4) if r[6] else None,
                    "elapsed_ms": r[7],
                    "trace_id": r[8],
                    "created_at": str(r[9]) if r[9] else "",
                }
                for r in ret_result
            ]

            fb_result = conn.execute(
                text(
                    "SELECT id, question, answer, rating, comment, created_at "
                    "FROM qa_feedback WHERE session_id = :sid ORDER BY id"
                ),
                {"sid": session_id},
            )
            feedbacks = [
                {
                    "id": r[0],
                    "question": (r[1] or "")[:200],
                    "answer": (r[2] or "")[:200],
                    "rating": r[3],
                    "comment": r[4],
                    "created_at": str(r[5]) if r[5] else "",
                }
                for r in fb_result
            ]

        return {
            "session_id": session_id,
            "messages": messages,
            "retrieval_logs": retrieval_logs,
            "feedbacks": feedbacks,
        }
    except Exception as exc:
        logger.error("session_replay_error", error=str(exc))
        return {
            "session_id": session_id,
            "messages": [],
            "retrieval_logs": [],
            "feedbacks": [],
        }
    finally:
        engine.dispose()


# ──────────────────────────────────────────────────────────────
# P2: 负反馈惩罚管理
# ──────────────────────────────────────────────────────────────

@router.get("/admin/feedback-penalties")
async def list_feedback_penalties(user=Depends(require_teacher_auth)):
    """查看所有 chunk 惩罚分值（Redis）。"""
    try:
        import redis as _redis
        settings = get_settings()
        client = _redis.from_url(settings.redis_url)
        keys = list(client.scan_iter("chunk_penalty:*"))
        penalties = []
        for key in keys:
            chunk_id = key.decode().replace("chunk_penalty:", "")
            raw = client.get(key)
            ttl = client.ttl(key)
            try:
                score = float(raw) if raw else 0.0
            except (ValueError, TypeError):
                score = 0.0
            penalties.append({
                "chunk_id": chunk_id,
                "penalty_score": score,
                "ttl_seconds": ttl,
            })
        penalties.sort(key=lambda x: x["penalty_score"])
        return {"penalties": penalties, "total": len(penalties)}
    except Exception as exc:
        logger.error("list_penalties_error", error=str(exc))
        return {"penalties": [], "total": 0}


@router.delete("/admin/feedback-penalties/{chunk_id}")
async def reset_feedback_penalty(chunk_id: str, user=Depends(require_teacher_auth)):
    """重置指定 chunk 的惩罚分值。"""
    try:
        import redis as _redis
        settings = get_settings()
        client = _redis.from_url(settings.redis_url)
        key = f"chunk_penalty:{chunk_id}"
        deleted = client.delete(key)
        return {"reset": deleted > 0, "chunk_id": chunk_id}
    except Exception as exc:
        return {"error": str(exc)[:200]}


# ──────────────────────────────────────────────────────────────
# P3: 限流监控
# ──────────────────────────────────────────────────────────────

@router.get("/admin/rate-limits")
async def list_rate_limits(user=Depends(require_admin_auth)):
    """查询各端点的限流状态（Redis 滑动窗口统计）。"""
    try:
        import redis as _redis
        settings = get_settings()
        client = _redis.from_url(settings.redis_url)
        keys = list(client.scan_iter("ratelimit:*"))
        limits = []
        api_limit = settings.api_rate_limit_per_minute
        admin_limit = settings.admin_rate_limit_per_minute
        for key in keys:
            identifier = key.decode().replace("ratelimit:", "")
            current = client.zcard(key)
            is_admin = "admin" in identifier.lower()
            limit_val = admin_limit if is_admin else api_limit
            blocked_key = f"blocked:{identifier}"
            try:
                blocked_today = int(client.get(blocked_key) or 0)
            except Exception:
                blocked_today = 0
            limits.append({
                "endpoint": identifier,
                "current_count": current,
                "limit": limit_val,
                "window_seconds": 60,
                "blocked_count_today": blocked_today,
            })
        limits.sort(key=lambda x: x["current_count"], reverse=True)
        return {"rate_limits": limits, "total": len(limits)}
    except Exception as exc:
        logger.error("list_rate_limits_error", error=str(exc))
        return {"rate_limits": [], "total": 0}


# ──────────────────────────────────────────────────────────────
# P3: 插件健康检查面板
# ──────────────────────────────────────────────────────────────

@router.get("/admin/plugins/health")
async def plugins_health(user=Depends(require_admin_auth)):
    """插件健康检查面板：使用已初始化单例进行实时健康检查。"""
    plugins: list[dict[str, Any]] = []

    # 1. 向量库（Milvus）— 直接连通性检查
    try:
        settings = get_settings()
        latency, healthy = _check_milvus(settings)
        plugins.append({
            "name": "vector_store",
            "healthy": healthy,
            "latency_ms": int(latency),
            "error": "",
        })
    except Exception as exc:
        plugins.append({
            "name": "vector_store",
            "healthy": False,
            "latency_ms": 0,
            "error": str(exc)[:200],
        })

    # 2. LLM — 检查 API Key 配置 + 探测连通性
    try:
        settings = get_settings()
        api_key = os.environ.get("LLM_API_KEY", "") or getattr(settings, "llm_api_key", "")
        if not api_key or api_key in ("your-api-key-here", "sk-xxx"):
            plugins.append({
                "name": "llm",
                "healthy": False,
                "latency_ms": 0,
                "error": "LLM API Key 未配置，请在环境变量 LLM_API_KEY 中设置",
            })
        else:
            import yaml
            from factory.component_factory import create_llm

            config_path = Path(__file__).resolve().parents[1] / "config" / "config.yaml"
            with open(config_path, encoding="utf-8") as f:
                config = yaml.safe_load(f)
            if "llm" in config:
                config["llm"]["api_key"] = api_key
            llm = create_llm(config)
            llm_status = llm.health_check()
            plugins.append({
                "name": "llm",
                "healthy": llm_status.get("healthy", False),
                "latency_ms": llm_status.get("latency_ms", 0),
                "error": llm_status.get("error", ""),
            })
    except Exception as exc:
        plugins.append({
            "name": "llm",
            "healthy": False,
            "latency_ms": 0,
            "error": str(exc)[:200],
        })

    # 3. Redis — 连通性检查
    try:
        import redis as _redis
        settings = get_settings()
        client = _redis.from_url(settings.redis_url)
        start = time.perf_counter()
        client.ping()
        latency = int((time.perf_counter() - start) * 1000)
        plugins.append({
            "name": "redis",
            "healthy": True,
            "latency_ms": latency,
            "error": "",
        })
    except Exception as exc:
        plugins.append({
            "name": "redis",
            "healthy": False,
            "latency_ms": 0,
            "error": str(exc)[:200],
        })

    # 4. MySQL — 连通性检查
    try:
        settings = get_settings()
        engine = create_engine(settings.mysql_sync_uri)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        plugins.append({
            "name": "mysql",
            "healthy": True,
            "latency_ms": 0,
            "error": "",
        })
    except Exception as exc:
        plugins.append({
            "name": "mysql",
            "healthy": False,
            "latency_ms": 0,
            "error": str(exc)[:200],
        })

    overall = all(p["healthy"] for p in plugins)
    return {
        "overall": overall,
        "plugins": plugins,
        "total": len(plugins),
    }


# ──────────────────────────────────────────────────────────────
# P3: Prometheus 指标聚合
# ──────────────────────────────────────────────────────────────

@router.get("/admin/metrics/summary")
async def metrics_summary(user=Depends(require_admin_auth)):
    """Prometheus 指标聚合：返回关键指标的采样快照。"""
    try:
        from prometheus_client import REGISTRY

        def _collect_metric(metric) -> list[dict]:
            samples = []
            try:
                for sample in metric.collect():
                    for s in sample.samples:
                        samples.append({
                            "name": s.name,
                            "labels": dict(s.labels) if s.labels else {},
                            "value": round(s.value, 4) if isinstance(s.value, float) else s.value,
                        })
            except Exception:
                pass
            return samples

        metrics_data: dict[str, Any] = {}
        for collector in REGISTRY.collect():
            metric_name = collector.name
            samples = _collect_metric(collector)
            if samples:
                metrics_data[metric_name] = samples

        summary = {
            "rag_request_duration": metrics_data.get("rag_request_duration", []),
            "rag_first_token_latency": metrics_data.get("rag_first_token_latency", []),
            "milvus_search_duration": metrics_data.get("milvus_search_duration", []),
            "milvus_search_total": metrics_data.get("milvus_search_total", []),
            "llm_request_duration": metrics_data.get("llm_request_duration", []),
            "llm_token_usage": metrics_data.get("llm_token_usage", []),
            "llm_request_total": metrics_data.get("llm_request_total", []),
            "cache_hit_rate": metrics_data.get("cache_hit_rate", []),
            "degraded_request_total": metrics_data.get("degraded_request_total", []),
            "websocket_active_connections": metrics_data.get("websocket_active_connections", []),
            "hallucination_risk_total": metrics_data.get("hallucination_risk_total", []),
            "plugin_health_status": metrics_data.get("plugin_health_status", []),
            "feedback_rating_ratio": metrics_data.get("feedback_rating_ratio", []),
            "metric_count": len(metrics_data),
        }
        return summary
    except Exception as exc:
        logger.error("metrics_summary_error", error=str(exc))
        return {"error": str(exc)[:200], "metric_count": 0}


# ──────────────────────────────────────────────────────────────
# P3: 检索策略 A/B 测试框架
# ──────────────────────────────────────────────────────────────

_AB_TEST_DDL = """
CREATE TABLE IF NOT EXISTS ab_tests (
    test_id VARCHAR(128) PRIMARY KEY,
    name VARCHAR(256) NOT NULL,
    course_id VARCHAR(128) DEFAULT 'global',
    strategy_a VARCHAR(128) NOT NULL DEFAULT 'hybrid',
    strategy_b VARCHAR(128) NOT NULL DEFAULT 'dense_only',
    traffic_split INT NOT NULL DEFAULT 50,
    status VARCHAR(32) NOT NULL DEFAULT 'draft',
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    is_deleted TINYINT NOT NULL DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

_AB_RESULT_DDL = """
CREATE TABLE IF NOT EXISTS ab_test_results (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    test_id VARCHAR(128) NOT NULL,
    strategy VARCHAR(128) NOT NULL,
    session_id VARCHAR(256),
    feedback_rating VARCHAR(32),
    retrieval_score FLOAT,
    response_time_ms INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_test (test_id),
    INDEX idx_strategy (strategy)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""


def _ensure_ab_tables() -> None:
    """确保 A/B 测试表存在。"""
    settings = get_settings()
    engine = create_engine(settings.mysql_sync_uri)
    try:
        with engine.connect() as conn:
            conn.execute(text(_AB_TEST_DDL))
            conn.execute(text(_AB_RESULT_DDL))
            conn.commit()
    except Exception as exc:
        logger.warning("ensure_ab_tables_failed", error=str(exc))
    finally:
        engine.dispose()


@router.get("/admin/ab-tests")
async def list_ab_tests(
    status_filter: str | None = Query(default=None, alias="status"),
    user=Depends(require_admin_auth),
):
    """查询 A/B 测试列表。"""
    _ensure_ab_tables()
    settings = get_settings()
    engine = create_engine(settings.mysql_sync_uri)
    where = "WHERE is_deleted = 0"
    params: dict[str, Any] = {}
    if status_filter:
        where += " AND status = :st"
        params["st"] = status_filter
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    f"SELECT test_id, name, course_id, strategy_a, strategy_b, "
                    f"traffic_split, status, description, created_at, updated_at "
                    f"FROM ab_tests {where} ORDER BY created_at DESC"
                ),
                params,
            )
            tests = [
                {
                    "test_id": r[0],
                    "name": r[1],
                    "course_id": r[2],
                    "strategy_a": r[3],
                    "strategy_b": r[4],
                    "traffic_split": r[5],
                    "status": r[6],
                    "description": r[7] or "",
                    "created_at": str(r[8]) if r[8] else "",
                    "updated_at": str(r[9]) if r[9] else "",
                }
                for r in result
            ]
        return {"ab_tests": tests, "total": len(tests)}
    except Exception as exc:
        logger.error("list_ab_tests_error", error=str(exc))
        return {"ab_tests": [], "total": 0}
    finally:
        engine.dispose()


class AbTestCreateRequest(BaseModel):
    name: str
    course_id: str = "global"
    strategy_a: str = "hybrid"
    strategy_b: str = "dense_only"
    traffic_split: int = 50
    description: str = ""


@router.post("/admin/ab-tests")
async def create_ab_test(req: AbTestCreateRequest, user=Depends(require_admin_auth)):
    """创建 A/B 测试。"""
    _ensure_ab_tables()
    settings = get_settings()
    engine = create_engine(settings.mysql_sync_uri)
    test_id = f"abtest_{int(time.time())}_{os.urandom(3).hex()}"
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "INSERT INTO ab_tests (test_id, name, course_id, strategy_a, "
                    "strategy_b, traffic_split, status, description) "
                    "VALUES (:tid, :nm, :ci, :sa, :sb, :ts, 'draft', :desc)"
                ),
                {
                    "tid": test_id, "nm": req.name, "ci": req.course_id,
                    "sa": req.strategy_a, "sb": req.strategy_b,
                    "ts": req.traffic_split, "desc": req.description,
                },
            )
            conn.commit()
        return {"test_id": test_id, "name": req.name}
    except Exception as exc:
        return {"error": str(exc)[:200]}
    finally:
        engine.dispose()


class AbTestUpdateRequest(BaseModel):
    name: str | None = None
    traffic_split: int | None = None
    status: str | None = None
    description: str | None = None


@router.put("/admin/ab-tests/{test_id}")
async def update_ab_test(
    test_id: str,
    req: AbTestUpdateRequest,
    user=Depends(require_admin_auth),
):
    """更新 A/B 测试配置或状态。"""
    settings = get_settings()
    engine = create_engine(settings.mysql_sync_uri)
    try:
        with engine.connect() as conn:
            sets: list[str] = []
            params: dict[str, Any] = {"tid": test_id}
            if req.name is not None:
                sets.append("name = :nm")
                params["nm"] = req.name
            if req.traffic_split is not None:
                sets.append("traffic_split = :ts")
                params["ts"] = req.traffic_split
            if req.status is not None:
                sets.append("status = :st")
                params["st"] = req.status
            if req.description is not None:
                sets.append("description = :desc")
                params["desc"] = req.description
            if not sets:
                return {"updated": False}
            conn.execute(
                text(f"UPDATE ab_tests SET {', '.join(sets)} WHERE test_id = :tid"),
                params,
            )
            conn.commit()
        return {"updated": True, "test_id": test_id}
    except Exception as exc:
        return {"error": str(exc)[:200]}
    finally:
        engine.dispose()


@router.delete("/admin/ab-tests/{test_id}")
async def delete_ab_test(test_id: str, user=Depends(require_admin_auth)):
    """删除 A/B 测试（软删除）。"""
    settings = get_settings()
    engine = create_engine(settings.mysql_sync_uri)
    try:
        with engine.connect() as conn:
            conn.execute(
                text("UPDATE ab_tests SET is_deleted = 1 WHERE test_id = :tid"),
                {"tid": test_id},
            )
            conn.commit()
        return {"deleted": True, "test_id": test_id}
    except Exception as exc:
        return {"error": str(exc)[:200]}
    finally:
        engine.dispose()


@router.get("/admin/ab-tests/{test_id}/results")
async def ab_test_results(test_id: str, user=Depends(require_admin_auth)):
    """查询 A/B 测试的统计结果。"""
    _ensure_ab_tables()
    settings = get_settings()
    engine = create_engine(settings.mysql_sync_uri)
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT strategy, COUNT(*) as total, "
                    "SUM(CASE WHEN feedback_rating = 'useful' THEN 1 ELSE 0 END) as positive, "
                    "SUM(CASE WHEN feedback_rating = 'not_useful' THEN 1 ELSE 0 END) as negative, "
                    "AVG(retrieval_score) as avg_score, "
                    "AVG(response_time_ms) as avg_time "
                    "FROM ab_test_results WHERE test_id = :tid "
                    "GROUP BY strategy"
                ),
                {"tid": test_id},
            )
            stats = [
                {
                    "strategy": r[0],
                    "total_requests": r[1],
                    "positive_feedback": r[2] or 0,
                    "negative_feedback": r[3] or 0,
                    "avg_retrieval_score": round(r[4], 4) if r[4] else 0,
                    "avg_response_time_ms": round(r[5], 1) if r[5] else 0,
                }
                for r in result
            ]
        return {"test_id": test_id, "results": stats}
    except Exception as exc:
        logger.error("ab_test_results_error", error=str(exc))
        return {"test_id": test_id, "results": []}
    finally:
        engine.dispose()
