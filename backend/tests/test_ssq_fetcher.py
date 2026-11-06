"""双色球 Fetcher 测试：known-good 解析、球号校验、增量拉取、失败重试。"""

from __future__ import annotations

from datetime import date

import httpx
import pytest

from app.fetchers.base import BallConfig, RawDraw
from app.fetchers.ssq_fetcher import SSQFetcher

SSQ_CONFIG = SSQFetcher.ball_config

# 真实接口返回结构的抽样（2026127 期）
SAMPLE_ITEM = {
    "name": "双色球",
    "code": "2026127",
    "date": "2026-11-05(四)",
    "red": "13,14,19,25,29,32",
    "blue": "12",
    "blue2": "",
    "sales": "346422846",
    "poolmoney": "1129731594",
    "prizegrades": [
        {"type": 1, "typenum": "3", "typemoney": "10000000"},
        {"type": 2, "typenum": "79", "typemoney": "360377"},
        {"type": 3, "typenum": "812", "typemoney": "3000"},
    ],
}


def _payload(issues: list[str], page_no: int = 1, pages: int = 1) -> dict:
    items = []
    for i, issue in enumerate(issues):
        items.append(
            {
                "code": issue,
                "date": f"2026-11-{5 + i:02d}(四)",
                "red": "01,02,03,04,05,06",
                "blue": "07",
                "blue2": "",
                "sales": "100",
                "poolmoney": "200",
                "prizegrades": [{"type": 1, "typenum": "1", "typemoney": "5000000"}],
            }
        )
    return {"result": items, "pageNo": page_no, "pageNum": pages, "total": 0}


def test_parse_item_known_good() -> None:
    """固定 JSON → 期号/日期/红蓝球/销售额/奖池完全匹配。"""
    fetcher = SSQFetcher(client=httpx.Client(transport=httpx.MockTransport(lambda r: None)))
    draw = fetcher.parse_item(SAMPLE_ITEM)

    assert draw.lottery_type == "ssq"
    assert draw.issue == "2026127"
    assert draw.draw_date == date(2026, 11, 5)
    assert draw.reds == [13, 14, 19, 25, 29, 32]
    assert draw.blues == [12]
    assert draw.sales_amount == 346422846
    assert draw.pool_balance == 1129731594
    assert draw.prize1_count == 3
    assert [g["type"] for g in draw.prize_details["levels"]] == [1, 2, 3]


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("2026-11-05(四)", date(2026, 11, 5)),
        ("2026-11-05", date(2026, 11, 5)),
        ("2003-02-23(日)", date(2003, 2, 23)),
    ],
)
def test_parse_date_variants(raw: str, expected: date) -> None:
    assert SSQFetcher.parse_date(raw) == expected


def test_parse_item_tolerates_annotation_in_money() -> None:
    """真实数据存在 '5490089（含派奖172413）' 这种带备注的金额 → 取前导整数。"""
    item = dict(
        SAMPLE_ITEM,
        prizegrades=[{"type": 1, "typenum": "3", "typemoney": "5490089（含派奖172413）"}],
    )
    draw = SSQFetcher().parse_item(item)
    assert draw.prize_details["levels"][0]["money"] == 5490089
    assert draw.prize1_count == 3


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("5490089（含派奖172413）", 5490089),
        ("12,345", 12345),
        ("316,122,624", 316122624),
        ("", None),
        (None, None),
        ("abc", None),
    ],
)
def test_to_int_variants(raw, expected) -> None:
    assert SSQFetcher._to_int(raw) == expected


def test_parse_item_reds_are_sorted() -> None:
    """无序红球入库前统一升序，保证 Draw.reds ≥ 后续算法假设。"""
    item = dict(SAMPLE_ITEM, red="32,13,25,14,29,19")
    draw = SSQFetcher().parse_item(item)
    assert draw.reds == [13, 14, 19, 25, 29, 32]


@pytest.mark.parametrize(
    "reds,blues,reason",
    [
        ([1, 2, 3, 4, 5], [1], "红球个数应为 6"),
        ([1, 2, 3, 4, 5, 5], [1], "红球存在重复"),
        ([1, 2, 3, 4, 5, 34], [1], "红球 34 超出范围"),
        ([0, 1, 2, 3, 4, 5], [1], "红球 0 超出范围"),
        ([1, 2, 3, 4, 5, 6], [17], "蓝球 17 超出范围"),
        ([1, 2, 3, 4, 5, 6], [], "蓝球个数应为 1"),
        ([1, 2, 3, 4, 5, 6], [1, 2, 3], "蓝球个数应为 1-2"),
    ],
)
def test_ball_validation_rejects(reds, blues, reason) -> None:
    with pytest.raises(ValueError, match=reason):
        SSQ_CONFIG.validate(reds, blues)


def test_ball_validation_accepts_edges() -> None:
    SSQ_CONFIG.validate([1, 2, 3, 32, 33, 6], [16])
    SSQ_CONFIG.validate([1, 2, 3, 4, 5, 6], [1])
    # 派奖期的「幸运蓝球」：主蓝球 + 第二个蓝球合法
    SSQ_CONFIG.validate([1, 2, 3, 4, 5, 6], [16, 1])


def test_fetch_incremental_stops_at_since() -> None:
    """已有 2026123 → 只拉取更新的 4 条，且请求到第 2 页即停止。"""
    pages = {
        1: _payload(["2026127", "2026126", "2026125"], page_no=1, pages=3),
        2: _payload(["2026124", "2026123", "2026122"], page_no=2, pages=3),
        3: _payload(["2026121"], page_no=3, pages=3),
    }
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["pageNo"])
        calls.append(page)
        return httpx.Response(200, json=pages[page])

    fetcher = SSQFetcher(
        client=httpx.Client(transport=httpx.MockTransport(handler)), interval=0
    )
    draws = fetcher.fetch(since="2026123")

    assert [d.issue for d in draws] == ["2026124", "2026125", "2026126", "2026127"]
    assert calls == [1, 2], "命中 since 后应停止翻页"


def test_fetch_full_history_boundary() -> None:
    """since=None → 拉完所有页；空结果页立即停止。"""
    pages = {
        1: _payload(["2026127"], page_no=1, pages=2),
        2: _payload(["2026126"], page_no=2, pages=2),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["pageNo"])
        return httpx.Response(200, json=pages.get(page, {"result": [], "pageNum": 2}))

    fetcher = SSQFetcher(
        client=httpx.Client(transport=httpx.MockTransport(handler)), interval=0
    )
    draws = fetcher.fetch()
    assert [d.issue for d in draws] == ["2026126", "2026127"]


def test_fetch_skips_malformed_items() -> None:
    """单条坏数据不中断整页，计入 skipped。"""
    payload = {
        "result": [
            dict(SAMPLE_ITEM),
            {"code": "", "date": "2026-11-05", "red": "01,02,03,04,05,06", "blue": "01"},
            {"code": "2026125", "date": "bad-date", "red": "01,02,03,04,05,06", "blue": "01"},
        ],
        "pageNum": 1,
        "pageNo": 1,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    fetcher = SSQFetcher(
        client=httpx.Client(transport=httpx.MockTransport(handler)), interval=0
    )
    draws = fetcher.fetch()
    assert [d.issue for d in draws] == ["2026127"]
    assert len(fetcher.skipped) == 2


def test_fetch_retries_then_succeeds() -> None:
    """前两次请求失败，第三次成功。"""
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] < 3:
            return httpx.Response(500, text="server error")
        return httpx.Response(200, json=_payload(["2026127"]))

    fetcher = SSQFetcher(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        interval=0,
        max_retries=3,
    )
    draws = fetcher.fetch()
    assert attempts["n"] == 3
    assert [d.issue for d in draws] == ["2026127"]


def test_fetch_latest_returns_newest() -> None:
    fetcher = SSQFetcher(
        client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=_payload(["2026127", "2026126"]))))
    )
    latest = fetcher.fetch_latest()
    assert latest is not None
    assert latest.issue == "2026127"


def test_rawdraw_defaults() -> None:
    draw = RawDraw(
        lottery_type="ssq", issue="2026127", draw_date=date(2026, 11, 5), reds=[1], blues=[2]
    )
    assert draw.sales_amount is None
    assert draw.prize_details is None


def test_ball_config_dict_roundtrip() -> None:
    assert SSQ_CONFIG.as_dict() == {
        "red_count": 6,
        "red_min": 1,
        "red_max": 33,
        "blue_count": 1,
        "blue_min": 1,
        "blue_max": 16,
        "blue_count_max": 2,
    }
    assert BallConfig(**SSQ_CONFIG.as_dict()) == SSQ_CONFIG


# ---------------- 历史回补（500 彩票网，2003–2012） ----------------

# 500 网历史页真实行结构抽样：
# 03001 含「快乐星期天」第二蓝球 10；12154 该列为空（&nbsp;）
BACKFILL_ROW_2003 = (
    '<tr class="t_tr1"><!--<td>1</td>--><td>03001</td>'
    '<td class="t_cfont2">10</td><td class="t_cfont2">11</td><td class="t_cfont2">12</td>'
    '<td class="t_cfont2">13</td><td class="t_cfont2">26</td><td class="t_cfont2">28</td>'
    '<td class="t_cfont4">11</td><td class="t_cfont4">10&nbsp;</td>'
    '<td>2,097,070</td><td>0</td><td>0</td><td>1</td><td>898,744</td>'
    '<td>10,307,806</td><td>2003-02-23</td></tr>'
)
BACKFILL_ROW_2012 = (
    '<tr class="t_tr1"><!--<td>2</td>--><td>12154</td>'
    '<td class="t_cfont2">05</td><td class="t_cfont2">07</td><td class="t_cfont2">12</td>'
    '<td class="t_cfont2">16</td><td class="t_cfont2">28</td><td class="t_cfont2">32</td>'
    '<td class="t_cfont4">04</td><td class="t_cfont4">&nbsp;</td>'
    '<td>72,256,070</td><td>5</td><td>6,000,000</td><td>137</td><td>210,394</td>'
    '<td>349,475,260</td><td>2012-12-30</td></tr>'
)


def _backfill_fetcher(html_by_start: dict[str, str]) -> SSQFetcher:
    """按 start 参数返回对应年份的 HTML；未提供的年份返回空页。"""

    def handler(request: httpx.Request) -> httpx.Response:
        start = request.url.params.get("start", "")
        html = html_by_start.get(start, "<table></table>")
        return httpx.Response(200, content=html.encode("gb18030", errors="replace"))

    return SSQFetcher(
        client=httpx.Client(transport=httpx.MockTransport(handler)), interval=0
    )


def test_backfill_parse_known_good() -> None:
    """固定 HTML → 期号归一化（5 位 → 7 位）、红蓝球、金额、日期完全匹配。"""
    fetcher = _backfill_fetcher({"03001": BACKFILL_ROW_2003, "12001": BACKFILL_ROW_2012})
    draws = fetcher.fetch_backfill()

    assert [d.issue for d in draws] == ["2003001", "2012154"]

    first = draws[0]
    assert first.draw_date == date(2003, 2, 23)
    assert first.reds == [10, 11, 12, 13, 26, 28]
    assert first.blues == [11, 10]  # 主蓝球 11 + 快乐星期天 10（→ extra_blues）
    assert first.pool_balance == 2097070
    assert first.sales_amount == 10307806
    assert first.prize1_count == 0
    assert [g["type"] for g in first.prize_details["levels"]] == [1, 2]

    last = draws[1]
    assert last.blues == [4]  # 快乐星期天列为空 → 只有主蓝球
    assert last.prize1_count == 5
    assert last.draw_date == date(2012, 12, 30)

    # 回补结果必须通过既有球号校验（含双蓝球边界）
    for draw in draws:
        SSQ_CONFIG.validate(draw.reds, draw.blues)


def test_backfill_until_filters_overlap() -> None:
    """until 用于避开官网已覆盖的期：2003002 起只保留 2003001。"""
    fetcher = _backfill_fetcher({"03001": BACKFILL_ROW_2003})
    draws = fetcher.fetch_backfill(until="2003002")
    assert [d.issue for d in draws] == ["2003001"]


def test_backfill_bad_row_recorded_not_raised() -> None:
    """坏行（列数不足）不中断整页，原因计入 skipped。"""
    bad_row = '<tr class="t_tr1"><td>03001</td><td>10</td></tr>'
    fetcher = _backfill_fetcher({"03001": BACKFILL_ROW_2003 + bad_row})
    draws = fetcher.fetch_backfill()
    assert [d.issue for d in draws] == ["2003001"]
    assert any("列数" in reason for reason in fetcher.skipped)


def test_backfill_happy_sunday_zero_is_placeholder() -> None:
    """真实数据：非周日开奖的「快乐星期天」列填 0 占位，不得当成第二蓝球。"""
    row_03002 = (
        '<tr class="t_tr1"><!--<td>2</td>--><td>03002</td>'
        '<td class="t_cfont2">04</td><td class="t_cfont2">09</td><td class="t_cfont2">19</td>'
        '<td class="t_cfont2">20</td><td class="t_cfont2">21</td><td class="t_cfont2">26</td>'
        '<td class="t_cfont4">12</td><td class="t_cfont4">0&nbsp;</td>'
        '<td>8,330,621</td><td>0</td><td>0</td><td>2</td><td>264,332</td>'
        '<td>7,398,870</td><td>2003-02-27</td></tr>'
    )
    fetcher = _backfill_fetcher({"03001": row_03002})
    draws = fetcher.fetch_backfill()
    assert draws[0].issue == "2003002"
    assert draws[0].blues == [12]  # 0 占位被忽略，只有主蓝球
    SSQ_CONFIG.validate(draws[0].reds, draws[0].blues)


def test_backfill_network_failure_raises() -> None:
    """任一年请求失败即抛 RuntimeError（由 sync_engine 捕获并记为 partial）。"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="server error")

    fetcher = SSQFetcher(
        client=httpx.Client(transport=httpx.MockTransport(handler)), interval=0, max_retries=2
    )
    with pytest.raises(RuntimeError, match="历史回补失败"):
        fetcher.fetch_backfill()
