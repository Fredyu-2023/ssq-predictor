"""同步相关 API：状态查询、手动触发、同步日志。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import db, sync_engine
from ..schemas import SyncLogOut, SyncRunResult, SyncStatusItem, SyncStatusResponse

router = APIRouter(prefix="/sync", tags=["sync"])


@router.get("/status", response_model=SyncStatusResponse)
def sync_status(session: Session = Depends(db.get_db)) -> SyncStatusResponse:
    sync_engine.sync_lottery_configs(session)
    items = [SyncStatusItem(**item) for item in sync_engine.get_status(session)]
    return SyncStatusResponse(lotteries=items)


@router.post("/run", response_model=SyncRunResult)
def sync_run(
    type: str | None = Query(default=None, description="彩种标识，不传则同步全部"),
    full: bool = Query(default=False, description="true=全量扫描并补齐历史缺口"),
    session: Session = Depends(db.get_db),
) -> SyncRunResult:
    if type:
        try:
            result = sync_engine.sync_lottery(type, wait=False, full=full)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except sync_engine.SyncBusyError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    else:
        results = sync_engine.sync_all(wait=False, full=full)
        if not results:
            raise HTTPException(status_code=404, detail="没有已注册的彩种")
        # 只同步一个彩种时返回它；多个彩种时返回第一个的结果概要
        result = results[0]
    return SyncRunResult(**result.as_dict())


@router.get("/logs", response_model=list[SyncLogOut])
def sync_logs(
    type: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    session: Session = Depends(db.get_db),
) -> list[SyncLogOut]:
    logs = sync_engine.get_logs(session, type, limit)
    return [SyncLogOut.model_validate(log) for log in logs]
