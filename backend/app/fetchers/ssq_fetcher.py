"""双色球数据适配器（数据源：中国福利彩票官网公开查询接口）。

说明：计划书原文写的是「体彩网 gameNo=85」，实测该参数返回的是超级大乐透；
双色球属于中国福利彩票，官方接口为 cwl.gov.cn 的 findDrawNotice。
该接口覆盖 2013-001 至今（实测 2085 期），2003–2012 的历史期不在该接口内。
"""

from __future__ import annotations

import re
import time
from datetime import date

import httpx

from .. import config
from .base import BallConfig, BaseFetcher, RawDraw

API_URL = "https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice"

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
