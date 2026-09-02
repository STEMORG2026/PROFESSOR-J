"""Tests for the Plotly chart-generator tool (Phase 5)."""

from __future__ import annotations

import json

import pytest

from app.guardrails.policy import SafetyPolicy
from app.tools.charts import ChartGenerator
from app.tools.executor import ToolExecutor


@pytest.fixture(scope="module")
def gen() -> ChartGenerator:
    return ChartGenerator()


def test_supported_types_listed() -> None:
    assert set(ChartGenerator.SUPPORTED) == {"line", "scatter", "bar", "pie", "histogram"}


def test_line_chart_spec(gen: ChartGenerator) -> None:
    out = gen.build(
        "line",
        x=[1, 2, 3],
        y=[4, 5, 6],
        title="Velocity vs time",
        x_label="time (s)",
        y_label="velocity (m/s)",
    )
    assert out["success"] is True
    assert out["chart_type"] == "line"
    # plotly_json must parse and be injectable into the webapp ```plotly``` block.
    spec = json.loads(out["plotly_json"])
    assert spec["data"][0]["type"] == "scatter"
    assert spec["data"][0]["x"] == [1, 2, 3]
    assert spec["data"][0]["y"] == [4, 5, 6]
    assert spec["layout"]["title"]["text"] == "Velocity vs time"
    assert spec["layout"]["xaxis"]["title"]["text"] == "time (s)"
    assert spec["layout"]["yaxis"]["title"]["text"] == "velocity (m/s)"


def test_bar_and_pie(gen: ChartGenerator) -> None:
    bar = gen.build("bar", x=["a", "b"], y=[10, 20], title="Counts")
    assert bar["success"] is True
    assert json.loads(bar["plotly_json"])["data"][0]["type"] == "bar"

    pie = gen.build("pie", labels=["Algebra", "Geometry"], values=[60, 40], hole="0.35")
    assert pie["success"] is True
    p = json.loads(pie["plotly_json"])
    assert p["data"][0]["type"] == "pie"
    assert p["data"][0]["labels"] == ["Algebra", "Geometry"]


def test_histogram(gen: ChartGenerator) -> None:
    out = gen.build("histogram", x=[1, 2, 2, 3, 3, 3], bins=5)
    assert out["success"] is True
    assert json.loads(out["plotly_json"])["data"][0]["type"] == "histogram"


def test_unknown_chart_type_fails_gracefully(gen: ChartGenerator) -> None:
    out = gen.build("surface3d")
    assert out["success"] is False
    assert "unknown chart type" in out["error"]


def test_missing_required_field_fails_gracefully(gen: ChartGenerator) -> None:
    out = gen.build("line", y=[1, 2])  # missing x
    assert out["success"] is False
    assert "missing required field(s): x" in out["error"]


def test_deterministic_output(gen: ChartGenerator) -> None:
    a = gen.build("line", x=[1, 2], y=[3, 4])
    b = gen.build("line", x=[1, 2], y=[3, 4])
    assert a["plotly_json"] == b["plotly_json"]


def test_registered_as_safe_tool() -> None:
    executor = ToolExecutor(SafetyPolicy(approval_callback=None))
    executor.register_chart_tools()
    assert executor.has_tool("make_chart")
    tools = executor.list_tools()
    chart = next(t for t in tools if t["name"] == "make_chart")
    assert chart["tier"] == "safe"
    assert "Plotly" in chart["description"]


def test_make_chart_via_executor() -> None:
    executor = ToolExecutor(SafetyPolicy(approval_callback=None))
    executor.register_chart_tools()

    import asyncio

    result = asyncio.run(
        executor.execute(
            "make_chart", {"chart_type": "pie", "labels": ["x", "y"], "values": [3, 7]}
        )
    )
    assert result["success"] is True
    assert result["chart_type"] == "pie"
    assert json.loads(result["plotly_json"])["data"][0]["type"] == "pie"


def test_chart_tool_registered_in_composition_root() -> None:
    import app.bootstrap  # exercises the import graph incl. plotly

    root = app.bootstrap.build_root()
    assert root.tools.has_tool("make_chart")
