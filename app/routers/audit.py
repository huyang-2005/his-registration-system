"""审计日志查询页面与接口。"""
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request

from app import db, web
from app.deps import require_roles

router = APIRouter()


def _filtered(user_id, action, start, end, limit=200):
    sql = (
        "SELECT * FROM audit_log WHERE 1=1 "
    )
    params = []
    if user_id:
        sql += " AND user_id = ?"
        params.append(int(user_id))
    if action:
        sql += " AND action = ?"
        params.append(action)
    if start:
        sql += " AND date(created_at) >= ?"
        params.append(start)
    if end:
        sql += " AND date(created_at) <= ?"
        params.append(end)
    sql += " ORDER BY log_id DESC LIMIT ?"
    params.append(limit)
    return db.query(sql, params)


@router.get("/audit")
def audit_page(
    request: Request,
    user_id: str = Query(""),
    action: str = Query(""),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    user=Depends(require_roles("admin")),
):
    rows = _filtered(user_id, action, start, end)
    users = db.query("SELECT DISTINCT user_id, username FROM audit_log WHERE user_id IS NOT NULL")
    actions = db.query("SELECT DISTINCT action FROM audit_log ORDER BY action")
    return web.render(
        request, "audit.html", logs=rows, users=users, actions=actions,
        user_id=user_id, action=action, start=start or "", end=end or "",
    )


@router.get("/api/audit")
def audit_api(
    user_id: str = Query(""),
    action: str = Query(""),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    user=Depends(require_roles("admin")),
):
    rows = _filtered(user_id, action, start, end, limit)
    return {
        "count": len(rows),
        "items": [dict(row) for row in rows],
    }
