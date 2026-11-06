"""可视化框架测试：清单完整、占位状态、注册与特征提取。"""

from __future__ import annotations

import pytest

from app.visualizers import BaseVisualizer, VisualizationData, get_visualizer, list_visualizers, register
from app.visualizers import registry as viz_registry


def test_catalog_contains_all_planned_algorithms() -> None:
    items = list_visualizers()
    assert len(items) == 18
    assert [item["code"] for item in items] == list("ABCDEFGHIJKLMNOPQR")
    assert all(item["status"] == "planned" for item in items)
    assert {item["category"] for item in items} == {
        "频域", "轨迹", "动力系统", "图论", "螺旋", "塌陷", "伸展收缩", "组合"
    }
    assert all(item["dimension"] in {"2D", "3D", "2D/3D"} for item in items)
    assert len({item["name"] for item in items}) == 18
    assert all(item["title"] and item["mapping"] and item["description"] for item in items)


def test_planned_visualizer_cannot_render() -> None:
    visualizer = get_visualizer("spiral_fourier")
    assert visualizer.code == "G"
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
