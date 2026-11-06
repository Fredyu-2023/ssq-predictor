"""custom_algorithm 插件加载器测试：自动注册、忽略下划线、坏文件隔离。"""

from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.strategies import registry
from app.strategies.base import validate_bets

CUSTOM_DIR = Path(registry.CUSTOM_DIR)


def _history(count: int = 10, red_count: int = 6) -> list[SimpleNamespace]:
    """最小历史样本：只需 reds/blues，足以覆盖插件算法读取频次的用法。"""
    draws = []
    for i in range(count):
        reds = sorted(((i + k) % 33) + 1 for k in range(red_count))
        draws.append(SimpleNamespace(reds=reds, blues=[(i % 16) + 1]))
    return draws


def _write_module(name: str, body: str) -> Path:
    CUSTOM_DIR.mkdir(parents=True, exist_ok=True)
    path = CUSTOM_DIR / f"{name}.py"
    path.write_text(body, encoding="utf-8")
    return path


def _cleanup(path: Path) -> None:
    path.unlink(missing_ok=True)
    for pyc in (CUSTOM_DIR / "__pycache__").glob(f"{path.stem}.*.pyc"):
        pyc.unlink(missing_ok=True)
    registry.reload()


def test_examples_are_ignored() -> None:
    registry.reload()
    names = {item["name"] for item in registry.list_strategies()}
    assert "example_random" not in names
    assert "example_freq" not in names
    assert {"random", "hot", "cold", "balanced", "mixed"} <= names
    assert registry.load_errors() == []


def test_custom_strategy_registered_and_usable() -> None:
    token = uuid.uuid4().hex[:8]
    module_name = f"tmp_algo_{token}"
    class_name = f"TmpAlgo{token}"
    path = _write_module(
        module_name,
        f'''"""临时测试算法。"""
from app.strategies.base import BaseStrategy, ball_params


class {class_name}(BaseStrategy):
    name = "{module_name}"
    description = "测试用自定义策略"

    def generate(self, history, count=1, **params):
        cfg = ball_params(params)
        reds = list(range(cfg["red_min"], cfg["red_min"] + cfg["red_count"]))
        return [[*reds, cfg["blue_min"]] for _ in range(count)]
''',
    )
    try:
        registry.reload()
        entries = {item["name"]: item for item in registry.list_strategies()}
        assert module_name in entries
        assert entries[module_name]["source"] == "custom"

        strategy = registry.get_strategy(module_name)
        bets = strategy.generate(_history(), 3, **{"window": 10})
        assert validate_bets(bets, expected_count=3) == [[1, 2, 3, 4, 5, 6, 1]] * 3
    finally:
        _cleanup(path)


def test_broken_file_does_not_block_others() -> None:
    good_token = uuid.uuid4().hex[:8]
    bad_token = uuid.uuid4().hex[:8]
    good_module = f"tmp_good_{good_token}"
    bad_module = f"tmp_bad_{bad_token}"
    good_path = _write_module(
        good_module,
        f'''from app.strategies.base import BaseStrategy


class Good{bad_token}(BaseStrategy):
    name = "{good_module}"
    description = "同批次正常策略"

    def generate(self, history, count=1, **params):
        return [[1, 2, 3, 4, 5, 6, 7]] * count
''',
    )
    bad_path = _write_module(bad_module, "raise RuntimeError('故意写坏的算法文件')\n")
    try:
        registry.reload()
        names = {item["name"] for item in registry.list_strategies()}
        assert good_module in names
        assert any(bad_module in message for message in registry.load_errors())
    finally:
        _cleanup(good_path)
        _cleanup(bad_path)


@pytest.mark.parametrize(
    ("bets", "message"),
    [
        ([[1, 2, 3, 4, 5, 6]], "长度"),
        ([[1, 2, 3, 4, 5, 6, 40]], "蓝球"),
    ],
)
def test_custom_output_is_validated(bets: list[list[int]], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        validate_bets(bets, expected_count=1)
