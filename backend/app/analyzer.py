"""统计分析模块：频次、遗漏、冷热、连号、奇偶/大小/区间比、和值、AC 值。

设计要点：
- 纯函数：输入按开奖期号升序（旧 → 新）的 StatDraw 列表，输出可直接 JSON 序列化的 dict
- 不依赖数据库，便于用 known-good 用例逐项验证
- 统计结果按 (彩种, 窗口, 库版本) 做小型 LRU 缓存，同步后主动失效
"""

from __future__ import annotations

import math
import threading
from collections import Counter, OrderedDict
from dataclasses import dataclass
from datetime import date

# 缓存条目上限：3 个彩种 × 3 种窗口，再留余量
_CACHE_MAXSIZE = 32
_cache: "OrderedDict[tuple, dict]" = OrderedDict()
_cache_lock = threading.Lock()


@dataclass(frozen=True)
class StatDraw:
    """统计分析所需的最小开奖结构（与 ORM 解耦）。"""

    issue: str
    reds: tuple[int, ...]
    blue: int
    draw_date: date | None = None


# ---------------- 缓存 ----------------


def cache_get(key: tuple):
    with _cache_lock:
        value = _cache.get(key)
        if value is None:
            return None
        _cache.move_to_end(key)
        return value


def cache_put(key: tuple, value: dict) -> None:
    with _cache_lock:
        _cache[key] = value
        _cache.move_to_end(key)
        while len(_cache) > _CACHE_MAXSIZE:
            _cache.popitem(last=False)


def invalidate(lottery_type: str | None = None) -> None:
    """开奖数据更新后清空缓存；不传彩种则全部清空。"""
    with _cache_lock:
        if lottery_type is None:
            _cache.clear()
            return
        for key in [k for k in _cache if k[0] == lottery_type]:
            _cache.pop(key, None)


# ---------------- 单项统计 ----------------


def _freq(values: list[int], lo: int, hi: int) -> list[dict]:
    counter = Counter(values)
    return [{"number": n, "count": int(counter.get(n, 0))} for n in range(lo, hi + 1)]


def _omission(sequences: list[list[int]], lo: int, hi: int) -> list[dict]:
    """当前遗漏：距最近一次出现的期数。最新一期出现 = 0，从未出现 = len(sequences)。"""
    n = len(sequences)
    last_index: dict[int, int] = {}
    for i, seq in enumerate(sequences):
        for num in seq:
            last_index[num] = i
    return [
        {
            "number": num,
            "omission": (n - 1 - last_index[num]) if num in last_index else n,
        }
        for num in range(lo, hi + 1)
    ]


def _hot_cold(items: list[dict], top: int) -> tuple[list[dict], list[dict]]:
    """按频次排序：热号降序、冷号升序；次数相同按号码升序，保证结果确定。"""
    if not items:
        return [], []
    hot = sorted(items, key=lambda x: (-x["count"], x["number"]))[:top]
    cold = sorted(items, key=lambda x: (x["count"], x["number"]))[:top]
    return (
        [{"number": x["number"], "count": x["count"]} for x in hot],
        [{"number": x["number"], "count": x["count"]} for x in cold],
    )


def _small_max(red_min: int, red_max: int) -> int:
    """大小分界：号码区间前一半为小。1–33 → 1–16 为小、17–33 为大。"""
    span = red_max - red_min + 1
    return red_min + span // 2 - 1


def _zone_bounds(red_min: int, red_max: int) -> list[tuple[int, int]]:
    """三区间划分：1–11 / 12–22 / 23–33（整除时等宽，末区间吃掉余数）。"""
    span = red_max - red_min + 1
    width = span // 3
    bounds: list[tuple[int, int]] = []
    start = red_min
    for i in range(3):
        end = red_max if i == 2 else start + width - 1
        bounds.append((start, end))
        start = end + 1
    return bounds


def _distribution(counter: Counter, labels: list[str], parts: dict[str, list[int]] | None = None) -> list[dict]:
    result: list[dict] = []
    for label in labels:
        item = {"label": label, "count": int(counter.get(label, 0))}
        if parts is not None:
            item["parts"] = parts.get(label, [0, 0])
        result.append(item)
    return result


def _sum_buckets(sums: list[int], width: int = 10) -> list[dict]:
    if not sums:
        return []
    start = (min(sums) // width) * width
    end = (max(sums) // width) * width
    labels = [f"{s}-{s + width - 1}" for s in range(start, end + 1, width)]
    counter = Counter(f"{(v // width) * width}-{(v // width) * width + width - 1}" for v in sums)
    return _distribution(counter, labels)


def ac_value(reds: list[int] | tuple[int, ...]) -> int:
    """AC 值（算术复杂度）：两两差值的不同个数 − (红球个数 − 1)。

    6 个红球时，两两差值最多 15 个，故 AC ∈ [0, 10]。
    """
    diffs = {abs(b - a) for i, a in enumerate(reds) for b in reds[i + 1 :]}
    return len(diffs) - (len(reds) - 1)


def _consecutive(reds_seq: list[list[int]]) -> list[dict]:
    counter: Counter = Counter()
    for reds in reds_seq:
        present = set(reds)
        for n in reds:
            if n + 1 in present:
                counter[(n, n + 1)] += 1
    items = [
        {"pair": f"{a}-{b}", "count": int(c), "parts": [a, b]}
        for (a, b), c in counter.items()
        if c > 0
    ]
    items.sort(key=lambda x: (-x["count"], x["parts"][0]))
    return items


# ---------------- 主入口 ----------------


def analyze(
    draws: list[StatDraw],
    *,
    red_count: int = 6,
    red_min: int = 1,
    red_max: int = 33,
    blue_min: int = 1,
    blue_max: int = 16,
) -> dict:
    """计算全部统计维度。draws 必须按开奖期号升序（旧 → 新）。"""
    n = len(draws)
    reds_seq = [list(d.reds) for d in draws]
    blues_seq = [[d.blue] for d in draws]

    red_freq = _freq([x for seq in reds_seq for x in seq], red_min, red_max)
    blue_freq = _freq([x for seq in blues_seq for x in seq], blue_min, blue_max)
    red_omission = _omission(reds_seq, red_min, red_max)
    blue_omission = _omission(blues_seq, blue_min, blue_max)
    hot_red, cold_red = _hot_cold(red_freq, 5) if n else ([], [])
    hot_blue, cold_blue = _hot_cold(blue_freq, 3) if n else ([], [])

    # 奇偶比：奇数 : 偶数
    odd_counter: Counter = Counter()
    for reds in reds_seq:
        odd = sum(1 for x in reds if x % 2 == 1)
        odd_counter[f"{odd}:{len(reds) - odd}"] += 1
    odd_labels = [f"{o}:{red_count - o}" for o in range(red_count, -1, -1)]
    odd_parts = {label: [int(label.split(":")[0]), int(label.split(":")[1])] for label in odd_labels}

    # 大小比：大 : 小
    small_max = _small_max(red_min, red_max)
    size_counter: Counter = Counter()
    for reds in reds_seq:
        small = sum(1 for x in reds if x <= small_max)
        size_counter[f"{len(reds) - small}:{small}"] += 1
    size_labels = [f"{b}:{red_count - b}" for b in range(red_count, -1, -1)]
    size_parts = {label: [int(label.split(":")[0]), int(label.split(":")[1])] for label in size_labels}

    # 区间比：1–11 / 12–22 / 23–33
    zones = _zone_bounds(red_min, red_max)
    zone_counter: Counter = Counter()
    zone_parts: dict[str, list[int]] = {}
    for reds in reds_seq:
        counts = [sum(1 for x in reds if lo <= x <= hi) for lo, hi in zones]
        label = ":".join(str(c) for c in counts)
        zone_counter[label] += 1
        zone_parts[label] = counts
    zone_items = [
        {"label": label, "count": int(c), "parts": zone_parts[label]}
        for label, c in zone_counter.items()
    ]
    zone_items.sort(key=lambda x: (-x["count"], x["label"]))

    # 和值
    sums = [sum(reds) for reds in reds_seq]
    sum_stats = {
        "min": int(min(sums)) if sums else 0,
        "max": int(max(sums)) if sums else 0,
        "mean": float(math.fsum(sums) / n) if n else 0.0,
    }

    # AC 值
    acs = [ac_value(reds) for reds in reds_seq]
    ac_counter = Counter(str(v) for v in acs)
    ac_labels = [str(v) for v in range(0, 11)]

    return {
        "window": n,
        "first_issue": draws[0].issue if draws else None,
        "last_issue": draws[-1].issue if draws else None,
        "red_freq": red_freq,
        "blue_freq": blue_freq,
        "red_omission": red_omission,
        "blue_omission": blue_omission,
        "hot_red": hot_red,
        "cold_red": cold_red,
        "hot_blue": hot_blue,
        "cold_blue": cold_blue,
        "consecutive": _consecutive(reds_seq),
        "odd_even": _distribution(odd_counter, odd_labels, odd_parts),
        "big_small": _distribution(size_counter, size_labels, size_parts),
        "zone_ratio": zone_items,
        "sum_distribution": _sum_buckets(sums),
        "sum_stats": sum_stats,
        "ac_distribution": _distribution(ac_counter, ac_labels),
        "ac_avg": float(math.fsum(acs) / n) if n else 0.0,
    }
