"""回测引擎测试：卡方生存函数、命中概率、滑动窗口指标与确定性。"""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

from app.backtest import chi2_sf, red_hit_probability, run_backtest
from app.strategies.builtin import HotStrategy, RandomStrategy
from app.strategies.base import BaseStrategy

TOTAL_RED = math.comb(33, 6)


def _draw(reds: list[int], blue: int, issue: str) -> SimpleNamespace:
    return SimpleNamespace(reds=list(reds), blue=blue, blues=[blue], issue=issue)


def _history(count: int = 200, fixed: bool = False) -> list[SimpleNamespace]:
    draws = []
    for i in range(count):
        reds = [1, 2, 3, 4, 5, 6] if fixed else sorted(((i + k) % 33) + 1 for k in range(6))
        blue = 1 if fixed else (i % 16) + 1
        draws.append(_draw(reds, blue, f"2024{i:03d}"))
    return draws


class FixedStrategy(BaseStrategy):
    name = "fixed_test"
    description = "测试固定号码"

    def generate(self, history, count=1, **params):
        return [[1, 2, 3, 4, 5, 6, 1]] * count


class BadStrategy(BaseStrategy):
    name = "bad_test"
    description = "返回非法号码"

    def generate(self, history, count=1, **params):
        return [[1, 2, 3, 4, 5, 6, 99]]


@pytest.mark.parametrize(
    ("statistic", "df"),
    [
        (3.841459, 1),
        (5.991465, 2),
        (7.814728, 3),
        (46.194, 32),
    ],
)
def test_chi2_sf_known_values(statistic: float, df: int) -> None:
    assert chi2_sf(statistic, df) == pytest.approx(0.05, abs=1e-5)


def test_chi2_sf_edges() -> None:
    assert chi2_sf(0.0, 3) == 1.0
    assert chi2_sf(1e-12, 1) == pytest.approx(1.0, abs=1e-6)
    assert 0.0 <= chi2_sf(100.0, 6) <= 1.0
    with pytest.raises(ValueError):
        chi2_sf(-1.0, 2)
    with pytest.raises(ValueError):
        chi2_sf(1.0, 0)


def test_red_hit_probability_distribution() -> None:
    probs = [red_hit_probability(k) for k in range(7)]
    assert sum(probs) == pytest.approx(1.0, rel=1e-12)
    assert probs[0] == pytest.approx(296010 / TOTAL_RED, rel=1e-12)
    assert probs[1] == pytest.approx(484380 / TOTAL_RED, rel=1e-12)
    assert probs[6] == pytest.approx(1 / TOTAL_RED, rel=1e-12)
    assert max(probs) == probs[1]  # 随机选号最可能命中 1 个红球


def test_backtest_perfect_matches() -> None:
    history = _history(200, fixed=True)
    result = run_backtest(history, FixedStrategy(), window=50, periods=100)
    assert result["samples"] == 100
    assert result["red_hits"][6]["count"] == 100
    assert result["blue_hits"] == 100
    assert result["blue_hit_rate"] == 1.0
    assert result["prize_levels"][0]["actual"] == 100  # 全部 6+1 一等奖
    assert result["avg_red_hits"] == 6.0
    assert result["from_issue"] == history[100].issue
    assert result["to_issue"] == history[199].issue


def test_backtest_metrics_are_internally_consistent() -> None:
    history = _history(300)
    result = run_backtest(history, FixedStrategy(), window=50, periods=200)
    hits = sum(item["count"] for item in result["red_hits"])
    prizes = sum(item["actual"] for item in result["prize_levels"])
    assert hits == result["samples"] == 200
    assert 0 <= prizes <= result["samples"]
    assert sum(item["ratio"] for item in result["red_hits"]) == pytest.approx(1.0)
    assert 0.0 <= result["chi_square"]["p_value"] <= 1.0
    assert result["chi_square"]["df"] == 3
    expected_total = sum(item["expected"] for item in result["chi_square"]["buckets"])
    assert expected_total == pytest.approx(200, rel=1e-9)
    assert "p =" in result["chi_square"]["conclusion"]
    assert result["disclaimer"]


def test_backtest_insufficient_history() -> None:
    with pytest.raises(ValueError, match="历史数据不足"):
        run_backtest(_history(10), FixedStrategy(), window=50, periods=1)
    with pytest.raises(ValueError, match="暂无历史"):
        run_backtest([], FixedStrategy())


def test_backtest_rejects_invalid_output() -> None:
    with pytest.raises(ValueError, match="蓝球"):
        run_backtest(_history(60), BadStrategy(), window=10, periods=5)


def test_backtest_seed_is_deterministic() -> None:
    history = _history(200)
    first = run_backtest(history, HotStrategy(), window=50, periods=100, seed=7)
    second = run_backtest(history, HotStrategy(), window=50, periods=100, seed=7)
    assert first["red_hits"] == second["red_hits"]
    assert first["blue_hits"] == second["blue_hits"]
    assert first["chi_square"]["statistic"] == second["chi_square"]["statistic"]


def test_backtest_random_is_close_to_baseline() -> None:
    """500 期样本下随机策略的命中分布应接近理论值（卡方 p 通常 > 0.05）。"""
    result = run_backtest(
        _history(600), RandomStrategy(), window=50, periods=500, seed=42
    )
    probs = [red_hit_probability(k) for k in range(7)]
    for item in result["red_hits"]:
        assert item["ratio"] == pytest.approx(probs[item["hits"]], abs=0.06)
