"""双色球数据适配器（主数据源：中国福利彩票官网公开查询接口）。

说明：计划书原文写的是「体彩网 gameNo=85」，实测该参数返回的是超级大乐透；
双色球属于中国福利彩票，官方接口为 cwl.gov.cn 的 findDrawNotice。

覆盖范围（2003-001 首期至今）：
- 2013-001 起：官网接口 findDrawNotice 分页提供（实测 2085 期）；
- 2003-001 至 2012 年末：官网接口不含该段，由 500 彩票网历史页回补
  （fetch_backfill()，仅在全量同步 full=True 时触发，逐年请求）。
"""

from __future__ import annotations

import re
import time
from datetime import date

import httpx

from .. import config
from .base import BallConfig, BaseFetcher, RawDraw

API_URL = "https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice"

# 历史回补源：500 彩票网历史页（覆盖 2003-001 起；官网接口只到 2013-001）
BACKFILL_URL = "https://datachart.500.com/ssq/history/newinc/history.php"
BACKFILL_YEAR_RANGE = range(2003, 2013)  # 2003（首期年）到 2012（官网覆盖前一年）

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Referer": "https://www.cwl.gov.cn/",
    "Accept": "application/json, text/javascript, */*; q=0.01",
}


class SSQFetcher(BaseFetcher):
    lottery_type = "ssq"
    name = "双色球"
    ball_config = BallConfig(
        red_count=6,
        red_min=1,
        red_max=33,
        blue_count=1,
        blue_min=1,
        blue_max=16,
        blue_count_max=2,  # 少数派奖期存在「幸运蓝球」，第二个存入 extra_blues
    )

    def __init__(
        self,
        client: httpx.Client | None = None,
        page_size: int = config.SYNC_PAGE_SIZE,
        interval: float = config.SYNC_REQUEST_INTERVAL,
        max_retries: int = config.SYNC_MAX_RETRIES,
    ) -> None:
        self.page_size = page_size
        self.interval = interval
        self.max_retries = max_retries
        self._client = client
        # 本次 fetch 中被跳过的坏数据（用于写 sync_log）
        self.skipped: list[str] = []

    # ---------- HTTP ----------

    def _get_page(self, page_no: int) -> dict:
        """拉取一页，失败按 max_retries 次重试（指数退避）。"""
        params = {
            "name": "ssq",
            "pageNo": page_no,
            "pageSize": self.page_size,
            "systemType": "PC",
        }
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                if self._client is not None:
                    resp = self._client.get(API_URL, params=params)
                else:
                    with httpx.Client(
                        timeout=config.HTTP_TIMEOUT, headers=DEFAULT_HEADERS, follow_redirects=True
                    ) as client:
                        resp = client.get(API_URL, params=params)
                resp.raise_for_status()
                data = resp.json()
                if not isinstance(data, dict) or "result" not in data:
                    raise ValueError(f"接口返回结构异常：{str(data)[:120]}")
                return data
            except (httpx.HTTPError, ValueError) as exc:  # 网络错误 / JSON 解析失败
                last_error = exc
                if attempt < self.max_retries:
                    time.sleep(self.interval * (2 ** (attempt - 1)))
        raise RuntimeError(f"第 {page_no} 页拉取失败（重试 {self.max_retries} 次）：{last_error}")

    # ---------- 解析 ----------

    @staticmethod
    def parse_date(raw: str) -> date:
        """'2026-11-05(四)' → date(2026, 11, 5)。"""
        text = raw.strip()
        head = text.split("(")[0].strip()
        return date.fromisoformat(head)

    @staticmethod
    def _to_int(value: object) -> int | None:
        """容错解析金额/注数：接口存在 '5490089（含派奖172413）' 这类带备注的值。"""
        if value is None:
            return None
        text = str(value).strip().replace(",", "")
        if not text:
            return None
        match = re.match(r"-?\d+", text)
        if not match:
            return None
        return int(match.group())

    def parse_item(self, item: dict) -> RawDraw:
        """把接口单条 JSON 解析为 RawDraw（只做结构解析，合法性由 sync_engine 校验）。"""
        issue = str(item.get("code") or item.get("issue") or "").strip()
        if not issue:
            raise ValueError("缺少期号")

        red_text = str(item.get("red") or "")
        reds = [int(x) for x in red_text.split(",") if x.strip()]
        blobs: list[int] = []
        blue_main = str(item.get("blue") or "").strip()
        if blue_main:
            blobs.append(int(blue_main))
        blue2 = str(item.get("blue2") or "").strip()
        if blue2:
            blobs.append(int(blue2))

        grades: list[dict] = []
        prize1_count: int | None = None
        for g in item.get("prizegrades") or []:
            try:
                level_type = int(g.get("type"))
            except (TypeError, ValueError):
                continue
            count = self._to_int(g.get("typenum"))
            money = self._to_int(g.get("typemoney"))
            grades.append({"type": level_type, "count": count, "money": money})
            if level_type == 1:
                prize1_count = count

        return RawDraw(
            lottery_type=self.lottery_type,
            issue=issue,
            draw_date=self.parse_date(str(item.get("date") or "")),
            reds=sorted(reds),
            blues=blobs,
            sales_amount=self._to_int(item.get("sales")),
            pool_balance=self._to_int(item.get("poolmoney")),
            prize_details={"levels": grades} if grades else None,
            prize1_count=prize1_count,
        )

    # ---------- 历史回补（500 彩票网，2003–2012） ----------

    def _get_backfill_page(self, year: int) -> str:
        """拉取某一年的回补页 HTML，失败按 max_retries 次重试（指数退避）。

        500 网期号为 5 位「yyNNN」，start/end 按年圈定，如 2003 年 → 03001–03999。
        页面为 GB 系编码，但我们只解析 ASCII 的数字与标签，解码错误可安全忽略。
        """
        yy = year % 100
        params = {"start": f"{yy:02d}001", "end": f"{yy:02d}999"}
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                if self._client is not None:
                    resp = self._client.get(BACKFILL_URL, params=params)
                else:
                    with httpx.Client(
                        timeout=config.HTTP_TIMEOUT, headers=DEFAULT_HEADERS, follow_redirects=True
                    ) as client:
                        resp = client.get(BACKFILL_URL, params=params)
                resp.raise_for_status()
                return resp.content.decode("gb18030", errors="replace")
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt < self.max_retries:
                    time.sleep(self.interval * (2 ** (attempt - 1)))
        raise RuntimeError(f"{year} 年历史回补失败（重试 {self.max_retries} 次）：{last_error}")

    def parse_backfill_html(self, html: str) -> list[RawDraw]:
        """解析 500 网历史页的全部数据行；单行解析失败计入 skipped，不中断整页。"""
        draws: list[RawDraw] = []
        for row in re.findall(r'<tr class="t_tr1">(.*?)</tr>', html, flags=re.S):
            try:
                draws.append(self._parse_backfill_row(row))
            except (ValueError, TypeError, IndexError) as exc:
                self.skipped.append(f"回补行解析失败：{exc}")
        return draws

    @staticmethod
    def _parse_backfill_row(row: str) -> RawDraw:
        """解析单行，共 16 列：

        期号 | 红球×6 | 蓝球 | 快乐星期天 | 奖池 | 一等奖(注数,奖金) | 二等奖(注数,奖金) | 总投注 | 日期
        「快乐星期天」是 2003–2004 周日开奖的加开蓝球，存入 extra_blues（blues[1]）。
        """
        # 首列序号写在 HTML 注释里，先删注释再抓 <td>，避免误匹配
        row = re.sub(r"<!--.*?-->", "", row, flags=re.S)
        cells = [
            re.sub(r"<[^>]+>", "", cell).replace("&nbsp;", "").strip()
            for cell in re.findall(r"<td[^>]*>(.*?)</td>", row, flags=re.S)
        ]
        if len(cells) != 16:
            raise ValueError(f"列数应为 16，实际 {len(cells)}")

        raw_issue = cells[0]
        if len(raw_issue) != 5 or not raw_issue.isdigit():
            raise ValueError(f"期号格式异常：{raw_issue!r}")
        # 期号归一化：500 网 5 位 yyNNN → 库内 7 位 yyyyNNN（03001 → 2003001）
        issue = f"20{raw_issue[:2]}{raw_issue[2:]}"

        blues = [int(cells[7])]
        # 快乐星期天：非周日开奖期该列填「0」占位，仅在 1–16 时才算真正的加开蓝球
        if cells[8].isdigit() and 1 <= int(cells[8]) <= 16:
            blues.append(int(cells[8]))

        prize1_count = SSQFetcher._to_int(cells[10])
        prize1_money = SSQFetcher._to_int(cells[11])
        prize2_count = SSQFetcher._to_int(cells[12])
        prize2_money = SSQFetcher._to_int(cells[13])
        levels: list[dict] = []
        if prize1_count is not None:
            levels.append({"type": 1, "count": prize1_count, "money": prize1_money})
        if prize2_count is not None:
            levels.append({"type": 2, "count": prize2_count, "money": prize2_money})

        return RawDraw(
            lottery_type="ssq",
            issue=issue,
            draw_date=date.fromisoformat(cells[15]),
            reds=sorted(int(c) for c in cells[1:7]),
            blues=blues,
            sales_amount=SSQFetcher._to_int(cells[14]),
            pool_balance=SSQFetcher._to_int(cells[9]),
            prize_details={"levels": levels} if levels else None,
            prize1_count=prize1_count,
        )

    def fetch_backfill(self, until: str | None = None) -> list[RawDraw]:
        """回补官网接口未覆盖的 2003–2012 历史期，按期号升序返回。

        until：只保留期号 < until 的记录（一般传官网覆盖的最早一期，避免重叠）；
        逐年请求（每年约 150 期），任一年失败直接抛错，由调用方决定如何处理。
        解析失败行的原因追加到 self.skipped（fetch() 重置后此处只增不清）。
        """
        draws: list[RawDraw] = []
        years = list(BACKFILL_YEAR_RANGE)
        for index, year in enumerate(years):
            html = self._get_backfill_page(year)
            for draw in self.parse_backfill_html(html):
                if until is None or draw.issue < until:
                    draws.append(draw)
            if self.interval > 0 and index < len(years) - 1:
                time.sleep(self.interval)
        draws.sort(key=lambda d: d.issue)
        return draws

    # ---------- 契约实现 ----------

    def fetch(self, since: str | None = None) -> list[RawDraw]:
        """分页拉取；遇到期号 ≤ since 的页即停止（增量同步）。"""
        self.skipped = []
        results: list[RawDraw] = []
        page_no = 1

        while True:
            data = self._get_page(page_no)
            items = data.get("result") or []
            if not items:
                break

            page_issues: list[str] = []
            for item in items:
                try:
                    draw = self.parse_item(item)
                except (ValueError, TypeError, KeyError) as exc:
                    self.skipped.append(f"第{page_no}页解析失败：{exc}")
                    continue
                page_issues.append(draw.issue)
                if since is None or draw.issue > since:
                    results.append(draw)

            if not page_issues:
                break

            # 已覆盖到 since 之前的数据 → 后续页都是更早的期，无需继续
            if since is not None and min(page_issues) <= since:
                break

            total_pages = int(data.get("pageNum") or 0)
            if page_no >= total_pages:
                break
            page_no += 1
            if self.interval > 0:
                time.sleep(self.interval)

        results.sort(key=lambda d: d.issue)
        return results

    def fetch_latest(self) -> RawDraw | None:
        data = self._get_page(1)
        items = data.get("result") or []
        for item in items:
            try:
                return self.parse_item(item)
            except (ValueError, TypeError, KeyError):
                continue
        return None
