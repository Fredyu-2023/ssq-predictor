"""选号策略测试：输出合法性、约束精确性、随机均匀性、冷热偏向、确定性。"""

from __future__ import annotations

import math
import random
from collections import Counter
from dataclasses import dataclass

import numpy as np
import pytest

from app.strategies import base, builtin, get_strategy, list_strategies, load_errors
from app.strategies.base import validate_bets


@dataclass
class FakeDraw:
    issue: str
    reds: list[int]
    blue: int


def make_history(n: int = 120, seed: int = 1) -> list[FakeDraw]:
    rng = random.Random(seed)
    return [
        FakeDraw(
            issue=f"2026{i:03d}",
            reds=sorted(rng.sample(range(1, 34), 6)),
            blue=rng.randint(1, 16),
        )
        for i in range(n)
    ]


def chi2_sf_even(x: float, df: int) -> float:
    """偶数自由度的卡方生存函数（Erlang 精确式），用于不引入 scipy 依赖的交叉验证。

    P(X > x) = exp(-x/2) * Σ_{i=0}^{df/2-1} (x/2)^i / i!
    """
    assert df % 2 == 0
    half = df // 2
    term = 1.0
    total = 0.0
    for i in range(half):
        if i > 0:
            term *= (x / 2) / i
        total += term
    return math.exp(-x / 2) * total


def test_chi2_sf_known_good() -> None:
    # 卡方分布 df=32 的 95% 临界值 46.194 → 生存函数应约为 0.05
    assert abs(chi2_sf_even(46.194, 32) - 0.05) < 5e-4


def test_registry_lists_all_builtins() -> None:
    items = {item["name"]: item for item in list_strategies()}
    assert set(items) == {"random", "hot", "cold", "balanced", "mixed"}
    for name in items:
        assert items[name]["source"] == "builtin"
        assert items[name]["description"]
    assert load_errors() == []


def test_unknown_strategy_raises() -> None:
    with pytest.raises(KeyError):
        get_strategy("not_exists")


@pytest.mark.parametrize("name", ["random", "hot", "cold", "balanced", "mixed"])
def test_every_strategy_output_is_valid(name: str) -> None:
    history = make_history()
    strategy = get_strategy(name)
    bets = strategy.generate(history, 20, window=30, seed=20261106)
    normalized = validate_bets(bets, expected_count=20)
    assert len(normalized) == 20


def test_random_uniformity_chi_square() -> None:
    bets = builtin.RandomStrategy().generate([], 10000, seed=20261106)
    counts = Counter(n for bet in bets for n in bet[:6])
    expected = len(bets) * 6 / 33
    chi2 = sum((counts.get(n, 0) - expected) ** 2 / expected for n in range(1, 34))
    p_value = chi2_sf_even(chi2, 32)
    assert p_value > 0.01, f"随机策略分布不均匀：chi2={chi2:.3f}, p={p_value:.4f}"


def test_balanced_constraints_exact() -> None:
    bets = builtin.BalancedStrategy().generate([], 300, seed=42)
    for bet in bets:
        reds = bet[:6]
        odd = sum(1 for n in reds if n % 2 == 1)
        big = sum(1 for n in reds if n >= 17)
        zone = [
            sum(1 for n in reds if 1 <= n <= 11),
            sum(1 for n in reds if 12 <= n <= 22),
            sum(1 for n in reds if 23 <= n <= 33),
        ]
        assert odd == 3
        assert big == 3
        assert zone == [2, 2, 2]


def test_hot_and_cold_biases() -> None:
    # 30 期中 1 号每期出现、33 号从未出现
    history = [
        FakeDraw(issue=f"2026{i:03d}", reds=[1, 2, 3, 4, 5, 6 + (i % 20)], blue=1)
        for i in range(30)
    ]
    # 保证 33 号确实从未出现（上面的号码最大 26）
    hot_counts = Counter(
        n
        for bet in builtin.HotStrategy().generate(history, 1000, window=30, seed=1)
        for n in bet[:6]
    )
    cold_counts = Counter(
        n
        for bet in builtin.ColdStrategy().generate(history, 1000, window=30, seed=2)
        for n in bet[:6]
    )
    assert hot_counts[1] > hot_counts[33]
    assert cold_counts[33] > cold_counts[1]


@pytest.mark.parametrize("name", ["random", "hot", "cold", "balanced", "mixed"])
def test_seed_determinism(name: str) -> None:
    history = make_history()
    strategy = get_strategy(name)
    first = strategy.generate(history, 8, window=30, seed=99)
    second = strategy.generate(history, 8, window=30, seed=99)
    assert first == second


def test_mixed_unique_and_valid() -> None:
    history = make_history()
    bets = builtin.MixedStrategy().generate(history, 10, window=30, seed=7)
    assert len({tuple(bet) for bet in bets}) == 10
    validate_bets(bets, expected_count=10)


def test_empty_history_is_safe() -> None:
    for name in ["random", "hot", "cold", "balanced", "mixed"]:
        bets = get_strategy(name).generate([], 5, window=30, seed=3)
        validate_bets(bets, expected_count=5)


def test_validate_bets_rejects_invalid_output() -> None:
    with pytest.raises(ValueError):
        validate_bets([[1, 2, 3, 4, 5, 6, 7]], expected_count=2)  # 注数不符

    bad_bets = [
        [1, 2, 3, 4, 5, 5, 7],  # 红球重复
        [1, 2, 3, 4, 5, 34, 7],  # 红球越界
        [1, 2, 3, 4, 5, 6, 17],  # 蓝球越界
        [6, 5, 4, 3, 2, 1, 7],  # 未升序
        [1, 2, 3, 4, 5, 6],  # 缺少蓝球
        [1, 2, 3, 4, 5, 6, 7, 8],  # 长度错误
        [1, 2, 3, 4, 5, 6, 7.5],  # 蓝球非整数
    ]
    for bet in bad_bets:
        with pytest.raises(ValueError):
            validate_bets([bet], expected_count=1)


def test_validate_bets_normalizes_numpy_ints() -> None:
    bets = [[np.int64(1), np.int64(2), np.int64(3), np.int64(4), np.int64(5), np.int64(6), np.int64(7)]]
    normalized = validate_bets(bets, expected_count=1)
    assert normalized == [[1, 2, 3, 4, 5, 6, 7]]
    assert all(isinstance(n, int) for n in normalized[0])


def test_ball_params_defaults() -> None:
    assert base.ball_params({}) == base.DEFAULT_BALLS
    assert base.ball_params({"red_count": 6})["red_count"] == 6
