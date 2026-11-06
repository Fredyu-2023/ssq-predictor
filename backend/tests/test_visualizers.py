"""可视化框架测试：清单完整、占位状态、注册与特征提取。"""

from __future__ import annotations

import math
from datetime import date

import pytest

from app.visualizers import BaseVisualizer, VisualizationData, get_visualizer, list_visualizers, register
from app.visualizers import registry as viz_registry


class FakeDraw:
    """构造一期开奖，供算法直接消费（不依赖数据库模型）。"""

    def __init__(self, reds: list[int], blue: int, issue: str = "2026127") -> None:
        self.reds = reds
        self.blues = [blue]
        self.issue = issue
        self.draw_date = date(2026, 11, 5)


def test_catalog_contains_all_algorithms_and_g_is_implemented() -> None:
    items = list_visualizers()
    assert len(items) == 18
    assert [item["code"] for item in items] == list("ABCDEFGHIJKLMNOPQR")
    assert sum(1 for item in items if item["status"] == "planned") == 17
    by_name = {item["name"]: item for item in items}
    assert by_name["spiral_fourier"]["status"] == "implemented"
    assert by_name["spiral_fourier"]["code"] == "G"
    assert {item["category"] for item in items} == {
        "频域", "轨迹", "动力系统", "图论", "螺旋", "塌陷", "伸展收缩", "组合"
    }
    assert all(item["dimension"] in {"2D", "3D", "2D/3D"} for item in items)
    assert len({item["name"] for item in items}) == 18
    assert all(item["title"] and item["mapping"] and item["description"] for item in items)


def test_planned_visualizer_cannot_render() -> None:
    visualizer = get_visualizer("fourier_curve")
    assert visualizer.code == "A"
    assert visualizer.status == "planned"
    with pytest.raises(NotImplementedError, match="开发中"):
        visualizer.render([])


def test_unknown_visualizer() -> None:
    with pytest.raises(KeyError, match="未知可视化算法"):
        get_visualizer("not_exists")


class FakeVisualizer(BaseVisualizer):
    name = "fake_viz"
    code = "Z"
    title = "测试实现"
    category = "组合"
    dimension = "2D"
    status = "implemented"
    description = "测试用"
    mapping = "无"

    def render(self, draws: list, **params) -> VisualizationData:
        return VisualizationData(
            type="curve_2d",
            data={"points": [[1, 2], [3, 4]]},
            metadata={"color": "#38bdf8"},
        )

    def extract_features(self, data: VisualizationData) -> dict:
        return {"area": 2.0, "centroid": [2.0, 3.0]}


def test_register_and_extract_features() -> None:
    register(FakeVisualizer())
    try:
        items = {item["name"]: item for item in list_visualizers()}
        assert items["fake_viz"]["status"] == "implemented"
        visualizer = get_visualizer("fake_viz")
        data = visualizer.render([])
        assert data.type == "curve_2d"
        assert data.data["points"] == [[1, 2], [3, 4]]
        assert visualizer.extract_features(data) == {"area": 2.0, "centroid": [2.0, 3.0]}
    finally:
        viz_registry._REGISTRY.pop("fake_viz", None)


def test_register_requires_name() -> None:
    class NoName(BaseVisualizer):
        def render(self, draws: list, **params) -> VisualizationData:
            return VisualizationData(type="points_2d")

    with pytest.raises(ValueError, match="name"):
        register(NoName())


# ---------------- G. 螺旋骨架傅里叶 ----------------

REDS = [3, 11, 17, 22, 28, 33]


def test_spiral_fourier_maps_red_to_harmonics() -> None:
    visualizer = get_visualizer("spiral_fourier")
    data = visualizer.render([FakeDraw(REDS, 9)])
    assert data.type == "spiral_fourier"
    assert visualizer.status == "implemented"

    payload = data.data
    points = payload["points"]
    assert len(points) == 1440
    assert all(math.isfinite(x) and math.isfinite(y) for x, y in points)
    # 归一化后所有点都落在单位圆内，且最大半径恰好为 1
    assert max(math.hypot(x, y) for x, y in points) == pytest.approx(1.0, abs=1e-5)

    assert payload["issue"] == "2026127"
    assert payload["reds"] == REDS
    assert payload["blue"] == 9
    assert [item["order"] for item in payload["harmonics"]] == [1, 2, 3, 4, 5, 6]
    assert [item["number"] for item in payload["harmonics"]] == REDS
    # 振幅 = 红球号 / 红球上限，权重之和为 1
    for item in payload["harmonics"]:
        assert item["amplitude"] == pytest.approx(item["number"] / 33, abs=1e-6)
    assert sum(item["weight"] for item in payload["harmonics"]) == pytest.approx(1.0, abs=1e-5)


def test_spiral_fourier_blue_controls_tightness() -> None:
    visualizer = get_visualizer("spiral_fourier")
    loose = visualizer.render([FakeDraw(REDS, 1)]).data
    tight = visualizer.render([FakeDraw(REDS, 16)]).data

    assert loose["tightness"] == pytest.approx(1 / 16, abs=1e-6)
    assert tight["tightness"] == pytest.approx(1.0, abs=1e-6)
    # 蓝球越大 → 螺距越小 → 圈数越多
    assert tight["pitch"] < loose["pitch"]
    assert tight["turns"] > loose["turns"]


def test_spiral_fourier_uses_latest_draw_and_params() -> None:
    visualizer = get_visualizer("spiral_fourier")
    first = FakeDraw([1, 2, 3, 4, 5, 6], 1, issue="100")
    last = FakeDraw(REDS, 9, issue="200")
    data = visualizer.render([first, last], samples=480, gain=0.0, pitch=0.2).data

    assert data["issue"] == "200"
    assert data["reds"] == last.reds
    assert len(data["points"]) == 480
    assert data["gain"] == 0.0
    # pitch 是蓝球最小时的基准螺距，实际螺距还会按紧密度收紧
    assert data["pitch"] == pytest.approx(0.2 * (1 - 0.6 * 9 / 16), abs=1e-6)


def test_spiral_fourier_is_deterministic() -> None:
    visualizer = get_visualizer("spiral_fourier")
    draw = FakeDraw(REDS, 9)
    assert visualizer.render([draw]).data == visualizer.render([draw]).data


def test_spiral_fourier_rejects_empty_draws() -> None:
    visualizer = get_visualizer("spiral_fourier")
    with pytest.raises(ValueError, match="至少需要一期"):
        visualizer.render([])


def test_spiral_fourier_extract_features() -> None:
    visualizer = get_visualizer("spiral_fourier")
    data = visualizer.render([FakeDraw(REDS, 9)])
    features = visualizer.extract_features(data)

    assert set(features) == {
        "turns", "tightness", "pitch", "gain", "harmonic_centroid", "dominant_harmonic",
        "mean_radius", "radius_std", "arc_length", "curvature_energy", "wave_amplitude",
        "wave_energy", "end_radius", "end_angle_deg",
    }
    assert features["dominant_harmonic"] == 6
    assert 1 < features["harmonic_centroid"] <= 6
    # 均匀采样的闭合转角总和 ≈ 圈数 × 2π
    assert features["curvature_energy"] == pytest.approx(
        data.data["turns"] * 2 * math.pi, rel=1e-5
    )
    # 波形振幅不超过算法设定的 gain
    assert features["wave_amplitude"] <= data.data["gain"] + 1e-4
    assert features["arc_length"] > 0
    assert features["mean_radius"] > 0
    assert features["radius_std"] > 0
    assert 0.0 <= features["end_angle_deg"] < 360.0
    assert features["end_radius"] <= 1.0 + 1e-6
