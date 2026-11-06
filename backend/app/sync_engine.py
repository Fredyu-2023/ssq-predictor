"""同步引擎：统一调度 → 球号校验 → UPSERT → 写 sync_log。

并发控制：每个彩种一把互斥锁，启动同步与手动同步共用，避免并发写库。
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session, sessionmaker

from . import analyzer, config, db
from .fetchers import RawDraw, get_fetcher, list_fetchers
from .models import Draw, LotteryConfig, SyncLog

_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()

MAX_ERROR_ITEMS = 10  # sync_log 里最多保留的错误明细条数


class SyncBusyError(RuntimeError):
    """同一彩种已有同步在跑。"""


@dataclass
class SyncResult:
    lottery_type: str
    status: str  # success / failed / partial / busy
    fetched_count: int = 0
    inserted_count: int = 0
    skipped_count: int = 0
    latest_issue: str | None = None
    error_msg: str | None = None
    elapsed_ms: int = 0

    def as_dict(self) -> dict:
        return {
            "lottery_type": self.lottery_type,
            "status": self.status,
            "fetched_count": self.fetched_count,
            "inserted_count": self.inserted_count,
            "skipped_count": self.skipped_count,
            "latest_issue": self.latest_issue,
            "error_msg": self.error_msg,
            "elapsed_ms": self.elapsed_ms,
        }


def _get_lock(lottery_type: str) -> threading.Lock:
    with _locks_guard:
        lock = _locks.get(lottery_type)
        if lock is None:
            lock = threading.Lock()
            _locks[lottery_type] = lock
        return lock


def is_syncing(lottery_type: str) -> bool:
    lock = _get_lock(lottery_type)
    return lock.locked()


def _session_factory() -> sessionmaker[Session]:
    if db.SessionLocal is None:
        db.init_db()
    assert db.SessionLocal is not None
    return db.SessionLocal


# ---------------- 彩种配置 -----------------------------


def sync_lottery_configs(session: Session) -> None:
    """把已注册 Fetcher 的球号规则写入 lottery_config（幂等）。"""
    for cls in list_fetchers():
        cfg = cls.ball_config
        row = session.get(LotteryConfig, cls.lottery_type)
        if row is None:
            row = LotteryConfig(lottery_type=cls.lottery_type, name=cls.name, enabled=True)
            session.add(row)
        row.name = cls.name
        row.red_count = cfg.red_count
        row.red_min = cfg.red_min
        row.red_max = cfg.red_max
        row.blue_count = cfg.blue_count
        row.blue_min = cfg.blue_min
        row.blue_max = cfg.blue_max
    session.commit()


# ---------------- 入库 ----------


def _to_row(draw: RawDraw) -> dict:
    reds = draw.reds
    blues = draw.blues
    return {
        "lottery_type": draw.lottery_type,
        "issue": draw.issue,
        "draw_date": draw.draw_date,
        "red1": reds[0],
        "red2": reds[1],
        "red3": reds[2],
        "red4": reds[3],
        "red5": reds[4],
        "red6": reds[5],
        "blue": blues[0],
        "extra_blues": blues[1:] or None,
        "sales_amount": draw.sales_amount,
        "pool_balance": draw.pool_balance,
        "prize1_count": draw.prize1_count,
        "prize_details": draw.prize_details,
    }


def _upsert_draws(session: Session, lottery_type: str, draws: list[RawDraw]) -> int:
    """按 (lottery_type, issue) UPSERT，返回新增（原本不存在）的条数。"""
    if not draws:
        return 0

    issues = [d.issue for d in draws]
    existing: set[str] = set()
    for i in range(0, len(issues), 500):  # 规避 SQLite IN 参数上限
        chunk = issues[i : i + 500]
        stmt = select(Draw.issue).where(
            Draw.lottery_type == lottery_type, Draw.issue.in_(chunk)
        )
        existing.update(session.execute(stmt).scalars().all())

    rows = [_to_row(d) for d in draws]
    update_cols = {
        c: getattr(sqlite_insert(Draw).excluded, c)
        for c in (
            "draw_date",
            "red1",
            "red2",
            "red3",
            "red4",
            "red5",
            "red6",
            "blue",
            "extra_blues",
            "sales_amount",
            "pool_balance",
            "prize1_count",
            "prize_details",
        )
    }
    # 分批写入：规避 SQLite 单条语句的参数个数上限
    chunk_size = 50
    for i in range(0, len(rows), chunk_size):
        session.execute(
            sqlite_insert(Draw)
            .values(rows[i : i + chunk_size])
            .on_conflict_do_update(index_elements=["lottery_type", "issue"], set_=update_cols)
        )
    session.commit()
    return sum(1 for d in draws if d.issue not in existing)


# ---------------- 主流程 ----------


def sync_lottery(
    lottery_type: str,
    *,
    fetcher=None,
    wait: bool = True,
    interval_override: float | None = None,
    full: bool = False,
) -> SyncResult:
    """同步单个彩种。

    full=True：忽略增量起点、全量扫描（用于启动自愈，补齐历史缺口）；
    full=False：从库内最后一期开始增量拉取。

    wait=True：等待锁（最多 SYNC_LOCK_WAIT 秒），超时抛 SyncBusyError；
    wait=False：拿不到锁直接抛 SyncBusyError（API 用这种方式，避免长时间挂起）。
    """
    lock = _get_lock(lottery_type)
    acquired = lock.acquire(timeout=config.SYNC_LOCK_WAIT) if wait else lock.acquire(blocking=False)
    if not acquired:
        raise SyncBusyError(f"彩种 {lottery_type} 正在同步中，请稍后重试")

    factory = _session_factory()
    started = datetime.now()
    t0 = time.perf_counter()
    log_id: int | None = None
    result = SyncResult(lottery_type=lottery_type, status="failed")

    try:
        if fetcher is None:
            fetcher = get_fetcher(lottery_type)
        if interval_override is not None and hasattr(fetcher, "interval"):
            fetcher.interval = interval_override

        with factory() as session:
            log = SyncLog(lottery_type=lottery_type, started_at=started, status="running")
            session.add(log)
            session.commit()
            log_id = log.id

            since = None
            if not full:
                since = session.execute(
                    select(func.max(Draw.issue)).where(Draw.lottery_type == lottery_type)
                ).scalar_one_or_none()

            draws = fetcher.fetch(since=since)

            skipped_reasons = list(getattr(fetcher, "skipped", []))
            valid: list[RawDraw] = []
            for draw in draws:
                try:
                    fetcher.ball_config.validate(draw.reds, draw.blues)
                except ValueError as exc:
                    skipped_reasons.append(f"期号 {draw.issue} 校验失败：{exc}")
                    continue
                valid.append(draw)

            inserted = _upsert_draws(session, lottery_type, valid)
            # 数据可能被 UPSERT 更新，统计缓存一律失效
            analyzer.invalidate(lottery_type)
            latest = valid[-1].issue if valid else since

            status = "partial" if skipped_reasons else "success"
            error_msg = "；".join(skipped_reasons[:MAX_ERROR_ITEMS]) or None

            log.status = status
            log.finished_at = datetime.now()
            log.fetched_count = len(draws)
            log.inserted_count = inserted
            log.error_msg = error_msg
            session.commit()

            result = SyncResult(
                lottery_type=lottery_type,
                status=status,
                fetched_count=len(draws),
                inserted_count=inserted,
                skipped_count=len(skipped_reasons),
                latest_issue=latest,
                error_msg=error_msg,
            )
    except Exception as exc:  # 同步失败只落日志，不抛给启动流程（API 层再转 500）
        error_msg = f"{type(exc).__name__}: {exc}"
        if log_id is not None:
            with factory() as session:
                log = session.get(SyncLog, log_id)
                if log is not None:
                    log.status = "failed"
                    log.finished_at = datetime.now()
                    log.error_msg = error_msg[:2000]
                    session.commit()
        result = SyncResult(lottery_type=lottery_type, status="failed", error_msg=error_msg)
    finally:
        result.elapsed_ms = int((time.perf_counter() - t0) * 1000)
        lock.release()

    return result


def cleanup_stale_logs(session: Session) -> int:
    """服务重启后，把上次进程中断遗留的 running 日志标记为 failed，避免前端误显示“同步中”。"""
    rows = session.execute(select(SyncLog).where(SyncLog.status == "running")).scalars().all()
    now = datetime.now()
    for row in rows:
        row.status = "failed"
        row.finished_at = now
        row.error_msg = "同步进程中断（服务重启）"
    session.commit()
    return len(rows)


def get_status(session: Session) -> list[dict]:
    """各彩种同步状态：最新期号/日期、总条数、上次同步时间与结果。"""
    items: list[dict] = []
    for cls in list_fetchers():
        lottery_type = cls.lottery_type
        total = session.execute(
            select(func.count()).select_from(Draw).where(Draw.lottery_type == lottery_type)
        ).scalar_one()
        latest = session.execute(
            select(Draw)
            .where(Draw.lottery_type == lottery_type)
            .order_by(Draw.issue.desc())
            .limit(1)
        ).scalar_one_or_none()
        last_log = session.execute(
            select(SyncLog)
            .where(SyncLog.lottery_type == lottery_type)
            .order_by(SyncLog.id.desc())
            .limit(1)
        ).scalar_one_or_none()

        items.append(
            {
                "type": lottery_type,
                "name": cls.name,
                "latest_issue": latest.issue if latest else None,
                "latest_date": latest.draw_date if latest else None,
                "total_count": int(total),
                "last_sync_at": (last_log.finished_at or last_log.started_at)
                if last_log
                else None,
                "last_sync_status": last_log.status if last_log else None,
                "syncing": is_syncing(lottery_type),
            }
        )
    return items


def get_logs(
    session: Session, lottery_type: str | None = None, limit: int = 20
) -> list[SyncLog]:
    stmt = select(SyncLog).order_by(SyncLog.id.desc()).limit(max(1, min(limit, 200)))
    if lottery_type:
        stmt = stmt.where(SyncLog.lottery_type == lottery_type)
    return list(session.execute(stmt).scalars().all())


def sync_all(*, wait: bool = True, full: bool = False) -> list[SyncResult]:
    """同步全部已注册彩种（顺序执行，单个失败不影响其他）。"""
    results: list[SyncResult] = []
    for cls in list_fetchers():
        try:
            results.append(sync_lottery(cls.lottery_type, wait=wait, full=full))
        except SyncBusyError:
            results.append(SyncResult(lottery_type=cls.lottery_type, status="busy"))
        except Exception as exc:  # 兜底，保证逐个彩种都返回结果
            results.append(
                SyncResult(
                    lottery_type=cls.lottery_type,
                    status="failed",
                    error_msg=f"{type(exc).__name__}: {exc}",
                )
            )
    return results
