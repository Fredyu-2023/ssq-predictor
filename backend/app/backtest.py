"""回测引擎：滑动窗口模拟策略历史表现，并与随机基线做卡方检验。

诚实性原则：内置策略长期表现与随机等价，因此 p-value 结论必须原样展示。
"""

from __future__ import annotations

import math

from .strategies.base import DISCLAIMER, validate_bets


def _gamma_q(a: float, x: float) -> float:
    """正则化上不完全伽马函数 Q(a, x) = 1 - P(a, x)。"""
    if a <= 0 or x < 0:
        raise ValueError("gamma_q 参数非法")
    if x == 0:
        return 1.0
    if x < a + 1.0:
        return 1.0 - _gamma_p_series(a, x)
    return _gamma_q_contfrac(a, x)


def _gamma_p_series(a: float, x: float) -> float:
    ap = a
    summ = 1.0 / a
    delta = summ
    for _ in range(200):
        ap += 1.0
        delta *= x / ap
        summ += delta
        if abs(delta) < abs(summ) * 1e-15:
            break
    return summ * math.exp(-x + a * math.log(x) - math.lgamma(a))


def _gamma_q_contfrac(a: float, x: float) -> float:
    tiny = 1e-300
    b = x + 1.0 - a
    c = 1.0 / tiny
    d = 1.0 / b if abs(b) > tiny else 1.0 / tiny
    h = d
    for i in range(1, 200):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-15:
            break
    return math.exp(-x + a * math.log(x) - math.lgamma(a)) * h


def chi2_sf(statistic: float, df: int) -> float:
    """卡方分布生存函数（右尾概率），支持任意正自由度。"""
    if df <= 0:
        raise ValueError("df 必须为正")
    if statistic < 0:
        raise ValueError("statistic 不能为负")
    return _gamma_q(df / 2.0, statistic / 2.0)


def red_hit_probability(k: int, red_count: int = 6, red_pool: int = 33) -> float:
    """随机选号命中 k 个红球的超几何分布概率。"""
    total = math.comb(red_pool, red_count)
    return math.comb(red_count, k) * math.comb(red_pool - red_count, red_count - k) / total


def _prize_level(red_hits: int, blue_hit: bool) -> int:
    if red_hits == 6:
        return 1 if blue_hit else 2
    if red_hits == 5:
        return 3 if blue_hit else 4
    if red_hits == 4:
        return 4 if blue_hit else 5
    if red_hits == 3:
        return 5 if blue_hit else 0
    if blue_hit:
        return 6
    return 0


def _prize_probabilities(red_count: int, red_pool: int, blue_pool: int) -> list[float]:
    """各奖级理论概率（p[0] 对应一等奖，p[5] 对应六等奖）。"""
    p_blue = 1.0 / blue_pool
    p_other = 1.0 - p_blue
    r = [red_hit_probability(k, red_count, red_pool) for k in range(red_count + 1)]
    return [
        r[6] * p_blue,
        r[6] * p_other,
        r[5] * p_blue,
        r[5] * p_other + r[4] * p_blue,
        r[4] * p_other + r[3] * p_blue,
        (r[0] + r[1] + r[2]) * p_blue,
    ]


def _draw_reds(draw) -> list[int]:
    return list(draw.reds)


def _draw_blue(draw) -> int:
    blues = getattr(draw, "blues", None)
    if blues:
        return int(blues[0])
    return int(draw.blue)


def run_backtest(
    history: list,
    strategy,
    *,
    window: int = 100,
    periods: int = 100,
    red_count: int = 6,
    red_min: int = 1,
    red_max: int = 33,
    blue_min: int = 1,
    blue_max: int = 16,
    seed: int | None = None,
) -> dict:
    """滑动窗口回测。history 按时间从旧到新排列。

    对每个被测期 i：用 history[i-window:i] 生成 1 注，与实际开奖比对。
    """
    if not history:
        raise ValueError("暂无历史开奖数据")
    if window < 1:
        raise ValueError("window 必须 >= 1")
    if window >= len(history):
        raise ValueError(f"历史数据不足：window={window}，仅有 {len(history)} 期")
    if periods < 1:
        raise ValueError("periods 必须 >= 1")

    periods = min(periods, len(history) - window)
    start = len(history) - periods
    red_pool = red_max - red_min + 1
    ball_args = {
        "red_count": red_count,
        "red_min": red_min,
        "red_max": red_max,
        "blue_min": blue_min,
        "blue_max": blue_max,
    }

    red_counts = [0] * (red_count + 1)
    prize_counts = [0] * 7  # 0 = 未中奖, 1-6 = 奖级
    blue_hits = 0
    red_total = 0

    for offset in range(periods):
        index = start + offset
        train = history[max(0, index - window):index]
        actual = history[index]
        params = {"window": window, **ball_args}
        if seed is not None:
            params["seed"] = int(seed) * 1000 + offset
        raw = strategy.generate(train, 1, **params)
        bet = validate_bets(raw, expected_count=1, **ball_args)[0]

        pred_reds = set(bet[:red_count])
        hits = len(pred_reds.intersection(_draw_reds(actual)))
        blue_hit = bet[-1] == _draw_blue(actual)

        red_counts[hits] += 1
        red_total += hits
        if blue_hit:
            blue_hits += 1
        prize_counts[_prize_level(hits, blue_hit)] += 1

    samples = periods
    first_issue = str(getattr(history[start], "issue", ""))
    last_issue = str(getattr(history[start + periods - 1], "issue", ""))

    red_hits = [
        {
            "hits": k,
            "count": red_counts[k],
            "ratio": round(red_counts[k] / samples, 6),
        }
        for k in range(red_count + 1)
    ]

    prize_probs = _prize_probabilities(red_count, red_pool, blue_max - blue_min + 1)
    names = ["一等奖", "二等奖", "三等奖", "四等奖", "五等奖", "六等奖"]
    conditions = ["6+1", "6+0", "5+1", "5+0 / 4+1", "4+0 / 3+1", "蓝球（红球 ≤2）"]
    prizes = [
        {
            "level": level + 1,
            "name": names[level],
            "condition": conditions[level],
            "actual": prize_counts[level + 1],
            "expected": round(samples * prize_probs[level], 6),
            "probability": round(prize_probs[level], 10),
        }
        for level in range(6)
    ]

    # 卡方检验：红球命中分桶 [0, 1, 2, ≥3]，期望频数均 ≥5（500 期样本下 ≥3 桶约 32 次）
    observed = [red_counts[0], red_counts[1], red_counts[2], sum(red_counts[3:])]
    probs = [
        red_hit_probability(0, red_count, red_pool),
        red_hit_probability(1, red_count, red_pool),
        red_hit_probability(2, red_count, red_pool),
        sum(red_hit_probability(k, red_count, red_pool) for k in range(3, red_count + 1)),
    ]
    expected = [samples * p for p in probs]
    statistic = math.fsum((o - e) ** 2 / e for o, e in zip(observed, expected)) if samples else 0.0
    df = len(observed) - 1
    p_value = chi2_sf(statistic, df)

    if p_value > 0.05:
        conclusion = (
            f"p = {p_value:.4f} > 0.05：该策略红球命中分布与随机基线无显著差异（符合预期，"
            "任何号码选择方式都不会改变中奖概率）。"
        )
    else:
        conclusion = (
            f"p = {p_value:.4f} ≤ 0.05：样本期内出现统计显著偏差，通常源于随机波动，"
            "不代表策略具备预测能力。"
        )

    return {
        "strategy": strategy.name,
        "window": window,
        "periods": periods,
        "samples": samples,
        "from_issue": first_issue,
        "to_issue": last_issue,
        "red_hits": red_hits,
        "avg_red_hits": round(red_total / samples, 6),
        "blue_hits": blue_hits,
        "blue_hit_rate": round(blue_hits / samples, 6),
        "blue_expected_rate": round(1 / (blue_max - blue_min + 1), 6),
        "prize_levels": prizes,
        "chi_square": {
            "statistic": round(statistic, 6),
            "df": df,
            "p_value": round(p_value, 6),
            "buckets": [
                {
                    "label": label,
                    "observed": o,
                    "expected": round(e, 4),
                }
                for label, o, e in zip(["0 个", "1 个", "2 个", "≥3 个"], observed, expected)
            ],
            "conclusion": conclusion,
        },
        "disclaimer": DISCLAIMER,
    }
