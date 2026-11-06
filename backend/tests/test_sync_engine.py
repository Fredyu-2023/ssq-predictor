"""同步引擎测试：UPSERT 幂等、增量起点、坏数据跳过、日志、互斥锁。"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import func, select

from app import sync_engine
from app.fetchers.base import BaseFetcher, RawDraw
from app.fetchers.ssq_fetcher import SSQFetcher
from app.models import Draw, SyncLog

def make_draw(issue: str, reds=None, blues=None, sales=None) -> RawDraw:
    return RawDraw(
        lottery_type="ssq",
        issue=issue,
        draw_date=date(2026, 11, 5),
        reds=reds or [1, 2, 3, 4, 5, 6],
        blues=blues or [7],
        sales_amount=sales,
    )


class FakeFetcher(BaseFetcher):
    lottery_type = "ssq"
    name = "双色球"
    ball_config = SSQFetcher.ball_config

    def __init__(self, draws: list[RawDraw], fail: bool = False, ignore_since: bool = False) -> None:
        self.draws = draws
        self.fail = fail
        self.ignore_since = ignore_since
        self.since_calls: list[str | None] = []
        self.skipped: list[str] = []
        self.interval = 0

    def fetch(self, since: str | None = None) -> list[RawDraw]:
        self.since_calls.append(since)
        if self.fail:
            raise RuntimeError("模拟数据源故障")
        if self.ignore_since:
            return list(self.draws)
        return [d for d in self.draws if since is None or d.issue > since]

    def fetch_latest(self):
        return self.draws[-1] if self.draws else None


def _count(session) -> int:
    return session.execute(select(func.count()).select_from(Draw)).scalar_one()


def test_sync_inserts_and_is_idempotent(session) -> None:
    draws = [make_draw("2026001"), make_draw("2026002"), make_draw("2026003")]

    r1 = sync_engine.sync_lottery("ssq", fetcher=FakeFetcher(draws), wait=False)
    assert r1.status == "success"
    assert r1.fetched_count == 3
    assert r1.inserted_count == 3
    assert r1.latest_issue == "2026003"
    assert _count(session) == 3

    r2 = sync_engine.sync_lottery("ssq", fetcher=FakeFetcher(draws), wait=False)
    assert r2.inserted_count == 0
    assert _count(session) == 3, "重复同步不得产生重复行"


def test_incremental_uses_last_issue(session) -> None:
    draws = [make_draw("2026001"), make_draw("2026002")]
    sync_engine.sync_lottery("ssq", fetcher=FakeFetcher(draws), wait=False)

    fetcher = FakeFetcher(draws + [make_draw("2026003")])
    r = sync_engine.sync_lottery("ssq", fetcher=fetcher, wait=False)

    assert fetcher.since_calls == ["2026002"], "第二次同步应以最后一期为增量起点"
    assert r.inserted_count == 1
    assert r.latest_issue == "2026003"


def test_upsert_updates_existing_row(session) -> None:
    sync_engine.sync_lottery("ssq", fetcher=FakeFetcher([make_draw("2026001", sales=100)]), wait=False)

    r = sync_engine.sync_lottery(
        "ssq",
        fetcher=FakeFetcher([make_draw("2026001", sales=200)], ignore_since=True),
        wait=False,
    )
    assert r.inserted_count == 0
    row = session.get(Draw, ("ssq", "2026001"))
    assert row is not None
    assert row.sales_amount == 200, "UPSERT 应更新已有行的字段"


def test_invalid_draw_is_skipped_not_fatal(session) -> None:
    bad = make_draw("2026002", reds=[1, 1, 2, 3, 4, 5])  # 红球重复
    draws = [make_draw("2026001"), bad, make_draw("2026003")]

    r = sync_engine.sync_lottery("ssq", fetcher=FakeFetcher(draws), wait=False)

    assert r.status == "partial"
    assert r.skipped_count == 1
    assert r.inserted_count == 2
    assert "2026002" in (r.error_msg or "")
    assert _count(session) == 2, "坏数据不得入库"


def test_sync_log_success_recorded(session) -> None:
    sync_engine.sync_lottery("ssq", fetcher=FakeFetcher([make_draw("2026001")]), wait=False)

    logs = session.execute(select(SyncLog)).scalars().all()
    assert len(logs) == 1
    log = logs[0]
    assert log.status == "success"
    assert log.fetched_count == 1
    assert log.inserted_count == 1
    assert log.finished_at is not None


def test_sync_log_failure_recorded(session) -> None:
    r = sync_engine.sync_lottery("ssq", fetcher=FakeFetcher([], fail=True), wait=False)

    assert r.status == "failed"
    assert "模拟数据源故障" in (r.error_msg or "")
    logs = session.execute(select(SyncLog)).scalars().all()
    assert len(logs) == 1
    assert logs[0].status == "failed"
    assert logs[0].error_msg


def test_duplicate_issue_in_batch_single_row(session) -> None:
    """同一批里出现重复期号（数据源异常）→ 最终仍只有一行。"""
    draws = [make_draw("2026001"), make_draw("2026001"), make_draw("2026002")]
    r = sync_engine.sync_lottery("ssq", fetcher=FakeFetcher(draws), wait=False)

    assert _count(session) == 2
    # 两条 2026001 都算“新增”，但落库只有一行
    assert r.inserted_count == 3


def test_composite_primary_key_across_lotteries(session) -> None:
    """不同彩种允许相同期号（联合主键）。"""
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert

    rows = [
        dict(lottery_type="ssq", issue="2026001", draw_date=date(2026, 1, 1),
             red1=1, red2=2, red3=3, red4=4, red5=5, red6=6, blue=7),
        dict(lottery_type="dlt", issue="2026001", draw_date=date(2026, 1, 1),
             red1=1, red2=2, red3=3, red4=4, red5=5, red6=6, blue=7),
    ]
    session.execute(sqlite_insert(Draw).values(rows))
    session.commit()
    assert _count(session) == 2


def test_busy_lock_rejects_second_sync(session) -> None:
    lock = sync_engine._get_lock("ssq")
    assert lock.acquire(blocking=False)
    try:
        with pytest.raises(sync_engine.SyncBusyError):
            sync_engine.sync_lottery(
                "ssq", fetcher=FakeFetcher([make_draw("2026001")]), wait=False
            )
    finally:
        lock.release()


def test_get_status_and_logs(session) -> None:
    sync_engine.sync_lottery(
        "ssq",
        fetcher=FakeFetcher([make_draw("2026001"), make_draw("2026002")]),
        wait=False,
    )
    status = sync_engine.get_status(session)
    assert len(status) == 1
    item = status[0]
    assert item["type"] == "ssq"
    assert item["latest_issue"] == "2026002"
    assert item["total_count"] == 2
    assert item["last_sync_status"] == "success"
    assert item["latest_date"] == date(2026, 11, 5)

    logs = sync_engine.get_logs(session, "ssq", 10)
    assert len(logs) == 1


def test_full_sync_ignores_since_and_backfills(session) -> None:
    """全量模式忽略增量起点：先缺一期，再由 full 同步补齐。"""
    sync_engine.sync_lottery(
        "ssq",
        fetcher=FakeFetcher([make_draw("2026001"), make_draw("2026003")]),
        wait=False,
    )
    fetcher = FakeFetcher(
        [make_draw("2026001"), make_draw("2026002"), make_draw("2026003")],
        ignore_since=True,
    )
    r = sync_engine.sync_lottery("ssq", fetcher=fetcher, wait=False, full=True)

    assert fetcher.since_calls == [None], "full 模式不得传增量起点"
    assert r.inserted_count == 1
    assert _count(session) == 3


def test_extra_blue_stored_separately(session) -> None:
    """派奖期两个蓝球：主蓝球入 blue，第二个入 extra_blues。"""
    sync_engine.sync_lottery(
        "ssq", fetcher=FakeFetcher([make_draw("2015011", blues=[15, 12])]), wait=False
    )
    row = session.get(Draw, ("ssq", "2015011"))
    assert row is not None
    assert row.blue == 15
    assert row.extra_blues == [12]
    assert row.blues == [15, 12]


def test_cleanup_stale_running_logs(session) -> None:
    """服务重启：遗留的 running 日志应被标记为 failed。"""
    session.add(SyncLog(lottery_type="ssq", status="running"))
    session.add(SyncLog(lottery_type="ssq", status="success"))
    session.commit()

    cleaned = sync_engine.cleanup_stale_logs(session)
    assert cleaned == 1
    statuses = [log.status for log in session.execute(select(SyncLog)).scalars().all()]
    assert sorted(statuses) == ["failed", "success"]


def test_large_batch_insert_across_sqlite_variable_limit(session) -> None:
    """300 期一次性入库：验证分批写入，规避 SQLite 参数上限。"""
    draws = [make_draw(f"2026{i:03d}") for i in range(1, 301)]
    r = sync_engine.sync_lottery("ssq", fetcher=FakeFetcher(draws), wait=False)

    assert r.status == "success"
    assert r.inserted_count == 300
    assert _count(session) == 300


def test_empty_fetch_keeps_state(session) -> None:
    sync_engine.sync_lottery("ssq", fetcher=FakeFetcher([make_draw("2026001")]), wait=False)
    r = sync_engine.sync_lottery("ssq", fetcher=FakeFetcher([]), wait=False)

    assert r.status == "success"
    assert r.inserted_count == 0
    assert r.latest_issue == "2026001", "无新增时期号应回落到库内最后一期"
    assert _count(session) == 1
