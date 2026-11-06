"""内置策略：random / hot / cold / balanced / mixed。

所有随机性都可通过 params["seed"] 固定，便于测试复现。
"""

from __future__ import annotations

import math
import random
from collections import Counter

from .base import BaseStrategy, ball_params


def _rng(params: dict) -> random.Random:
    seed = params.get("seed")
    if seed is None:
        return random.SystemRandom()
    return random.Random(int(seed))


def _window(history: list, params: dict) -> list:
    window = int(params.get("window", 30))
    if window <= 0 or window >= len(history):
        return history
    return history[-window:]


def _weighted_sample(rng: random.Random, population: list[int], weights: list[float], k: int) -> list[int]:
    """按权重不放回抽样；权重全 0 时退化为均匀抽样。"""
    pool = list(population)
    pool_weights = [float(w) for w in weights]
    chosen: list[int] = []
    for _ in range(k):
        total = math.fsum(pool_weights)
        if total <= 0:
            index = rng.randrange(len(pool))
        else:
            target = rng.random() * total
            index = 0
            acc = 0.0
            for i, w in enumerate(pool_weights):
                acc += w
                if target <= acc:
                    index = i
                    break
        chosen.append(pool.pop(index))
        pool_weights.pop(index)
    return chosen


def _small_max(red_min: int, red_max: int) -> int:
    span = red_max - red_min + 1
    return red_min + span // 2 - 1


def _zone_bounds(red_min: int, red_max: int) -> list[tuple[int, int]]:
    span = red_max - red_min + 1
    width = span // 3
    bounds = []
    start = red_min
    for i in range(3):
        end = red_max if i == 2 else start + width - 1
        bounds.append((start, end))
        start = end + 1
    return bounds


class RandomStrategy(BaseStrategy):
    name = "random"
    description = "纯随机基线：等概率抽样，用于对照其他策略"

    def generate(self, history: list, count: int = 1, **params) -> list[list[int]]:
        cfg = ball_params(params)
        rng = _rng(params)
        bets = []
        for _ in range(count):
            reds = sorted(rng.sample(range(cfg["red_min"], cfg["red_max"] + 1), cfg["red_count"]))
            bets.append([*reds, rng.randint(cfg["blue_min"], cfg["blue_max"])])
        return bets


class HotStrategy(BaseStrategy):
    name = "hot"
    description = "热号策略：按近 N 期红/蓝球频次加权抽样"

    def generate(self, history: list, count: int = 1, **params) -> list[list[int]]:
        cfg = ball_params(params)
        rng = _rng(params)
        rows = _window(history, params)
        red_freq = Counter(n for row in rows for n in row.reds)
        blue_freq = Counter(row.blue for row in rows)

        red_numbers = list(range(cfg["red_min"], cfg["red_max"] + 1))
        red_weights = [red_freq.get(n, 0) + 1.0 for n in red_numbers]
        blue_numbers = list(range(cfg["blue_min"], cfg["blue_max"] + 1))
        blue_weights = [blue_freq.get(n, 0) + 1.0 for n in blue_numbers]

        bets = []
        for _ in range(count):
            reds = sorted(_weighted_sample(rng, red_numbers, red_weights, cfg["red_count"]))
            blue = _weighted_sample(rng, blue_numbers, blue_weights, 1)[0]
            bets.append([*reds, blue])
        return bets


class ColdStrategy(BaseStrategy):
    name = "cold"
    description = "冷号策略：按遗漏期数加权，遗漏越久权重越高"

    def generate(self, history: list, count: int = 1, **params) -> list[list[int]]:
        cfg = ball_params(params)
        rng = _rng(params)
        rows = _window(history, params)
        n = len(rows)

        last_red: dict[int, int] = {}
        last_blue: dict[int, int] = {}
        for i, row in enumerate(rows):
            for num in row.reds:
                last_red[num] = i
            last_blue[row.blue] = i

        red_numbers = list(range(cfg["red_min"], cfg["red_max"] + 1))
        red_weights = [
            (n - 1 - last_red[num] if num in last_red else n) + 1.0 for num in red_numbers
        ]
        blue_numbers = list(range(cfg["blue_min"], cfg["blue_max"] + 1))
        blue_weights = [
            (n - 1 - last_blue[num] if num in last_blue else n) + 1.0 for num in blue_numbers
        ]

        bets = []
        for _ in range(count):
            reds = sorted(_weighted_sample(rng, red_numbers, red_weights, cfg["red_count"]))
            blue = _weighted_sample(rng, blue_numbers, blue_weights, 1)[0]
            bets.append([*reds, blue])
        return bets


class BalancedStrategy(BaseStrategy):
    name = "balanced"
    description = "均衡策略：强制奇偶 3:3、大小 3:3、区间 2:2:2"

    def generate(self, history: list, count: int = 1, **params) -> list[list[int]]:
        cfg = ball_params(params)
        rng = _rng(params)
        red_count = cfg["red_count"]
        zones = _zone_bounds(cfg["red_min"], cfg["red_max"])
        per_zone = red_count // 3
        odd_target = red_count // 2
        small_max = _small_max(cfg["red_min"], cfg["red_max"])

        bets = []
        for _ in range(count):
            reds = self._balanced_reds(rng, zones, per_zone, red_count, odd_target, small_max)
            blue = rng.randint(cfg["blue_min"], cfg["blue_max"])
            bets.append([*reds, blue])
        return bets

    @staticmethod
    def _balanced_reds(
        rng: random.Random,
        zones: list[tuple[int, int]],
        per_zone: int,
        red_count: int,
        odd_target: int,
        small_max: int,
    ) -> list[int]:
        for _ in range(4000):
            reds: list[int] = []
            for lo, hi in zones:
                reds.extend(rng.sample(range(lo, hi + 1), per_zone))
            if len(reds) < red_count:
                reds.extend(
                    rng.sample(
                        [n for n in range(zones[0][0], zones[-1][1] + 1) if n not in reds],
                        red_count - len(reds),
                    )
                )
            odd = sum(1 for n in reds if n % 2 == 1)
            small = sum(1 for n in reds if n <= small_max)
            if odd == odd_target and small == red_count // 2:
                return sorted(reds)
        raise RuntimeError("均衡策略在 4000 次尝试内未构造出满足约束的号码")


class MixedStrategy(BaseStrategy):
    name = "mixed"
    description = "混合策略：random/hot/cold/balanced 轮流出号，合并后按注去重"

    def generate(self, history: list, count: int = 1, **params) -> list[list[int]]:
        pool = [RandomStrategy(), HotStrategy(), ColdStrategy(), BalancedStrategy()]
        base_seed = params.get("seed")
        bets: list[list[int]] = []
        seen: set[tuple[int, ...]] = set()

        for i in range(count):
            sub_params = dict(params)
            if base_seed is not None:
                sub_params["seed"] = int(base_seed) * 1000 + i
            bet = pool[i % len(pool)].generate(history, 1, **sub_params)[0]
            key = tuple(bet)
            if key not in seen:
                seen.add(key)
                bets.append(bet)

        # 去重后不足 count 注时，用随机策略补足并尽量保持唯一
        fallback = RandomStrategy()
        attempts = 0
        while len(bets) < count and attempts < 2000:
            sub_params = dict(params)
            if base_seed is not None:
                sub_params["seed"] = int(base_seed) * 1000 + 500 + attempts
            bet = fallback.generate(history, 1, **sub_params)[0]
            key = tuple(bet)
            if key not in seen:
                seen.add(key)
                bets.append(bet)
            attempts += 1
        while len(bets) < count:
            bets.append(fallback.generate(history, 1, **params)[0])
        return bets


BUILTIN_STRATEGIES: list[BaseStrategy] = [
    RandomStrategy(),
    HotStrategy(),
    ColdStrategy(),
    BalancedStrategy(),
    MixedStrategy(),
]
