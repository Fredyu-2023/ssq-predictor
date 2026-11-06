"""统计分析测试：known-good 数值、边界用例、属性恒等式。

验证原则（PROJECT_PLAN §11.2）：
- 频次和恒等：N 期 → 红球总频次 = N × 6
- 遗漏值：逐号断言（含最新期出现 = 0、从未出现 = N）
- 奇偶/大小/区间/和值：手造号码逐一核对
- AC 值：用两两差值去重后减 (个数-1) 的解析定义交叉验证
- 空数据：不崩溃，返回全 0 / 空列表
"""

from __future__ import annotations

import random

import numpy as np

from app import analyzer
from app.analyzer import StatDraw, ac_value

DEFAULTS = dict(red_count=6, red_min=1, red_max=33, blue_min=1, blue_max=16)


def d(issue: str, reds: list[int], blue: int = 1) -> StatDraw:
    return StatDraw(issue=issue, reds=tuple(reds), blue=blue)


def by_number(items: list[dict], number: int) -> dict:
    return next(item for item in items if item["number"] == number)


def by_label(items: list[dict], label: str) -> dict:
    return next(item for item in items if item["label"] == label)


# ---------------- 频次 ----------------


def test_red_frequency_sum_matches_draws() -> None:
    draws = [
        d("2026001", [1, 2, 3, 4, 5, 6], 1),
        d("2026002", [1, 2, 7, 8, 9, 10], 2),
        d("2026003", [1, 11, 12, 13, 14, 15], 1),
        d("2026004", [16, 17, 18, 19, 20, 21], 3),
        d("2026005", [22, 23, 24, 25, 26, 27], 4),
    ]
    out = analyzer.analyze(draws, **DEFAULTS)

    assert out["window"] == 5
    assert len(out["red_freq"]) == 33
    assert len(out["blue_freq"]) == 16
    assert sum(x["count"] for x in out["red_freq"]) == 5 * 6
    assert sum(x["count"] for x in out["blue_freq"]) == 5
    assert by_number(out["red_freq"], 1)["count"] == 3
    assert by_number(out["red_freq"], 33)["count"] == 0
    assert by_number(out["blue_freq"], 2)["count"] == 1


# ---------------- 遗漏 ----------------


def test_omission_known_sequence() -> None:
    draws = [
        d("2026001", [1, 2, 3, 4, 5, 6], 1),
        d("2026002", [1, 7, 8, 9, 10, 11], 2),
        d("2026003", [2, 7, 12, 13, 14, 15], 1),
    ]
    out = analyzer.analyze(draws, **DEFAULTS)

    # 最新一期（索引 2）出现的号 → 遗漏 0
    assert by_number(out["red_omission"], 2)["omission"] == 0
    assert by_number(out["red_omission"], 7)["omission"] == 0
    # 索引 1 出现 → 遗漏 1
    assert by_number(out["red_omission"], 1)["omission"] == 1
    # 索引 0 出现 → 遗漏 2
    assert by_number(out["red_omission"], 3)["omission"] == 2
    # 从未出现 → 遗漏 = 期数
    assert by_number(out["red_omission"], 33)["omission"] == 3

    assert by_number(out["blue_omission"], 1)["omission"] == 0
    assert by_number(out["blue_omission"], 2)["omission"] == 1
    assert by_number(out["blue_omission"], 3)["omission"] == 3


# ---------------- 奇偶 / 大小 / 区间 ----------------


def test_odd_even_ratio_exact() -> None:
    draws = [d("2026001", [1, 2, 3, 4, 5, 6], 1)]
    out = analyzer.analyze(draws, **DEFAULTS)

    assert len(out["odd_even"]) == 7
    assert by_label(out["odd_even"], "3:3")["count"] == 1
    assert by_label(out["odd_even"], "3:3")["parts"] == [3, 3]
    assert sum(x["count"] for x in out["odd_even"]) == 1
    assert by_label(out["odd_even"], "6:0")["count"] == 0


def test_odd_even_all_even() -> None:
    out = analyzer.analyze([d("2026001", [2, 4, 6, 8, 10, 12], 1)], **DEFAULTS)
    assert by_label(out["odd_even"], "0:6")["count"] == 1


def test_big_small_ratio_exact() -> None:
    # 1–16 为小，17–33 为大
    out_small = analyzer.analyze([d("2026001", [1, 2, 3, 4, 5, 6], 1)], **DEFAULTS)
    assert by_label(out_small["big_small"], "0:6")["count"] == 1
    assert by_label(out_small["big_small"], "0:6")["parts"] == [0, 6]

    out_big = analyzer.analyze([d("2026001", [17, 20, 25, 28, 30, 33], 1)], **DEFAULTS)
    assert by_label(out_big["big_small"], "6:0")["count"] == 1

    # 分界值 16 属于小、17 属于大
    out_edge = analyzer.analyze([d("2026001", [16, 17, 18, 19, 20, 21], 1)], **DEFAULTS)
    assert by_label(out_edge["big_small"], "5:1")["count"] == 1


def test_zone_ratio_exact() -> None:
    out = analyzer.analyze([d("2026001", [1, 11, 12, 22, 23, 33], 1)], **DEFAULTS)
    assert out["zone_ratio"][0]["label"] == "2:2:2"
    assert out["zone_ratio"][0]["count"] == 1
    assert out["zone_ratio"][0]["parts"] == [2, 2, 2]

    out_low = analyzer.analyze([d("2026001", [1, 2, 3, 4, 5, 6], 1)], **DEFAULTS)
    assert by_label(out_low["zone_ratio"], "6:0:0")["count"] == 1
    assert sum(x["count"] for x in out_low["zone_ratio"]) == 1


# ---------------- 连号 ----------------


def test_consecutive_pairs() -> None:
    out = analyzer.analyze([d("2026001", [1, 2, 3, 4, 5, 6], 1)], **DEFAULTS)
    pairs = {item["pair"]: item["count"] for item in out["consecutive"]}
    assert pairs == {"1-2": 1, "2-3": 1, "3-4": 1, "4-5": 1, "5-6": 1}
    assert [item["pair"] for item in out["consecutive"]] == [
        "1-2",
        "2-3",
        "3-4",
        "4-5",
        "5-6",
    ]

    # 无连号 → 空列表
    out_none = analyzer.analyze([d("2026001", [1, 3, 5, 8, 13, 21], 1)], **DEFAULTS)
    assert out_none["consecutive"] == []


# ---------------- 和值 ----------------


def test_sum_stats_and_buckets() -> None:
    out = analyzer.analyze([d("2026001", [1, 2, 3, 4, 5, 6], 1)], **DEFAULTS)
    assert out["sum_stats"]["min"] == 21
    assert out["sum_stats"]["max"] == 21
    assert np.isclose(out["sum_stats"]["mean"], 21.0, rtol=1e-9, atol=1e-12)
    assert by_label(out["sum_distribution"], "20-29")["count"] == 1

    two = analyzer.analyze(
        [d("2026001", [1, 2, 3, 4, 5, 6], 1), d("2026002", [28, 29, 30, 31, 32, 33], 1)],
        **DEFAULTS,
    )
    assert two["sum_stats"]["max"] == 183
    assert np.isclose(two["sum_stats"]["mean"], (21 + 183) / 2, rtol=1e-9, atol=1e-12)
    assert by_label(two["sum_distribution"], "20-29")["count"] == 1
    assert by_label(two["sum_distribution"], "180-189")["count"] == 1


# ---------------- AC 值 ----------------


def test_ac_value_known_good() -> None:
    assert ac_value([1, 2, 3, 4, 5, 6]) == 0  # 差值只有 1..5，共 5 个
    assert ac_value([1, 2, 3, 4, 5, 7]) == 1  # 差值 1..6，共 6 个
    assert ac_value([1, 5, 10, 15, 20, 25]) == 4  # 9 个不同差值 − 5
    # 解析定义交叉验证
    reds = [3, 8, 13, 18, 23, 28]
    diffs = {abs(b - a) for i, a in enumerate(reds) for b in reds[i + 1 :]}
    assert ac_value(reds) == len(diffs) - 5


def test_ac_distribution_and_average() -> None:
    draws = [
        d("2026001", [1, 2, 3, 4, 5, 6], 1),   # AC = 0
        d("2026002", [1, 2, 3, 4, 5, 7], 1),   # AC = 1
    ]
    out = analyzer.analyze(draws, **DEFAULTS)
    assert len(out["ac_distribution"]) == 11
    assert by_label(out["ac_distribution"], "0")["count"] == 1
    assert by_label(out["ac_distribution"], "1")["count"] == 1
    assert np.isclose(out["ac_avg"], 0.5, rtol=1e-9, atol=1e-12)


# ---------------- 冷热号 ----------------


def test_hot_cold_ordering_and_ties() -> None:
    draws = [
        d("2026001", [1, 2, 3, 4, 5, 6], 5),
        d("2026002", [1, 2, 3, 4, 5, 32], 5),
        d("2026003", [1, 7, 8, 9, 10, 33], 1),
    ]
    out = analyzer.analyze(draws, **DEFAULTS)

    assert out["hot_red"][0] == {"number": 1, "count": 3}
    assert [x["number"] for x in out["hot_red"][1:]] == [2, 3, 4, 5]  # 同为 2 次时号码升序
    # 冷号 = 频次最低（未出现过的号频次为 0，属于最冷），次数相同按号码升序
    assert [x["number"] for x in out["cold_red"]] == [11, 12, 13, 14, 15]
    assert all(x["count"] == 0 for x in out["cold_red"])

    assert out["hot_blue"][0] == {"number": 5, "count": 2}
    assert [x["number"] for x in out["cold_blue"]] == [2, 3, 4]
    assert all(x["count"] == 0 for x in out["cold_blue"])


def test_hot_cold_limits() -> None:
    draws = [d(f"2026{i:03d}", [1, 2, 3, 4, 5, 6], 1) for i in range(1, 4)]
    out = analyzer.analyze(draws, **DEFAULTS)
    assert len(out["hot_red"]) == 5
    assert len(out["cold_red"]) == 5
    assert len(out["hot_blue"]) == 3
    assert len(out["cold_blue"]) == 3


# ---------------- 空数据 / 边界 ----------------


def test_empty_draws_returns_zeros() -> None:
    out = analyzer.analyze([], **DEFAULTS)

    assert out["window"] == 0
    assert out["first_issue"] is None
    assert out["last_issue"] is None
    assert len(out["red_freq"]) == 33
    assert all(x["count"] == 0 for x in out["red_freq"])
    assert len(out["blue_freq"]) == 16
    assert all(x["count"] == 0 for x in out["blue_freq"])
    assert all(x["omission"] == 0 for x in out["red_omission"])
    assert out["hot_red"] == [] and out["cold_red"] == []
    assert out["hot_blue"] == [] and out["cold_blue"] == []
    assert out["consecutive"] == []
    assert out["zone_ratio"] == []
    assert out["sum_distribution"] == []
    assert out["sum_stats"] == {"min": 0, "max": 0, "mean": 0.0}
    assert np.isclose(out["ac_avg"], 0.0, rtol=1e-9, atol=1e-12)
    assert len(out["odd_even"]) == 7
    assert all(x["count"] == 0 for x in out["odd_even"])


# ---------------- 属性测试 ----------------


def test_properties_on_random_draws() -> None:
    rng = random.Random(20261106)
    draws = []
    for i in range(120):
        reds = tuple(sorted(rng.sample(range(1, 34), 6)))
        draws.append(StatDraw(issue=f"2026{i:03d}", reds=reds, blue=rng.randint(1, 16)))

    out = analyzer.analyze(draws, **DEFAULTS)
    n = len(draws)

    assert out["window"] == n
    assert sum(x["count"] for x in out["red_freq"]) == 6 * n
    assert sum(x["count"] for x in out["blue_freq"]) == n
    assert all(0 <= x["omission"] <= n for x in out["red_omission"])
    assert all(0 <= x["omission"] <= n for x in out["blue_omission"])
    assert sum(x["count"] for x in out["odd_even"]) == n
    assert sum(x["count"] for x in out["big_small"]) == n
    assert sum(x["count"] for x in out["zone_ratio"]) == n
    assert sum(x["count"] for x in out["sum_distribution"]) == n
    assert sum(x["count"] for x in out["ac_distribution"]) == n
    assert all(0 <= int(x["label"]) <= 10 for x in out["ac_distribution"])
    assert 21 <= out["sum_stats"]["min"] <= out["sum_stats"]["max"] <= 183

    for item in out["odd_even"]:
        assert sum(item["parts"]) == 6
    for item in out["big_small"]:
        assert sum(item["parts"]) == 6
    for item in out["zone_ratio"]:
        assert sum(item["parts"]) == 6


def test_ac_range_property() -> None:
    rng = random.Random(7)
    for _ in range(500):
        reds = sorted(rng.sample(range(1, 34), 6))
        assert 0 <= ac_value(reds) <= 10


# ---------------- 缓存 ----------------


def test_cache_put_get_invalidate() -> None:
    key = ("ssq", "30", 100, "2026100")
    payload = {"window": 30}
    analyzer.cache_put(key, payload)
    assert analyzer.cache_get(key) is payload

    analyzer.invalidate("other")
    assert analyzer.cache_get(key) is payload, "其他彩种失效不得影响本彩种"

    analyzer.invalidate("ssq")
    assert analyzer.cache_get(key) is None

    analyzer.cache_put(key, payload)
    analyzer.invalidate()
    assert analyzer.cache_get(key) is None
