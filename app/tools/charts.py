"""ChartGenerator — Plotly figure generation as a safety-gated tool.

Produces a Plotly figure *spec* (JSON) for chart types a STEM tutor commonly
needs (line, scatter, bar, pie, histogram). The output is a plain dict whose
``plotly_json`` member drops straight into the webapp's Plotly renderer (the
`` ```plotly {json} ```  `` block consumed by ``frontend/src/components/
MessageContent.tsx``).

The tool is intentionally **deterministic and side-effect free**: it never
writes files or evaluates code, so it registers as :class:`SafetyTier.SAFE` and
needs no sandbox. The model provides tidy data; validation and rounding keep
figure JSON clean for the renderer.
"""

from __future__ import annotations

import json
from typing import Any

from app.domain.tool import SafetyTier

try:  # plotly is a declared runtime dep (requirements.txt); degrade gracefully.
    import plotly.graph_objects as go  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - exercised only in dependency-light envs
    go = None

_LINE_STYLES = frozenset({"solid", "dash", "dot", "dashdot"})
_PIE_HOLES = ("0", "0.35", "0.5")


class ChartGenerator:
    """Build Plotly figure specs from structured, validated arguments."""

    #: Figure types the generator can emit, mapped to factories.
    SUPPORTED = ("line", "scatter", "bar", "pie", "histogram")

    def build(self, chart_type: str, **kwargs: Any) -> dict[str, Any]:
        """Return a Plotly figure spec (``to_plotly_json``) for ``chart_type``.

        Returns ``{"success": False, "error": ...}`` for unknown chart types or
        invalid payloads so failures surface as tool output rather than raising.
        """
        if go is None:
            return {"success": False, "error": "plotly not available"}
        chart_type = (chart_type or "").lower().strip()
        if chart_type not in self.SUPPORTED:
            supported = ", ".join(self.SUPPORTED)
            return {
                "success": False,
                "error": f"unknown chart type '{chart_type}'; supported: {supported}",
            }
        try:
            factory = getattr(self, f"_build_{chart_type}")
            fig = factory(**kwargs)
        except (TypeError, ValueError, KeyError) as exc:
            return {"success": False, "error": str(exc)}
        spec = fig.to_plotly_json()
        return {
            "success": True,
            "chart_type": chart_type,
            "title": kwargs.get("title"),
            "spec": spec,
            "plotly_json": json.dumps(spec, separators=(",", ":")),
        }

    # -- widget factories -----------------------------------------------------

    def _build_line(self, **kw: Any) -> Any:
        _require(kw, "x", "y")
        go_: Any = _go()
        trace = go_.Scatter(
            x=kw["x"],
            y=kw["y"],
            mode=kw.get("mode", "lines+markers"),
            name=kw.get("series_name") or kw.get("name"),
            line={"dash": kw.get("line_style", "solid")}
            if kw.get("line_style") in _LINE_STYLES
            else None,
        )
        return go_.Figure(data=[trace], layout=_layout(kw))

    def _build_scatter(self, **kw: Any) -> Any:
        _require(kw, "x", "y")
        go_: Any = _go()
        trace = go_.Scatter(
            x=kw["x"],
            y=kw["y"],
            mode="markers",
            name=kw.get("series_name") or kw.get("name"),
            marker={
                "size": _safe_number(kw.get("size"), default=8),
                "color": kw.get("color") or None,
            },
        )
        return go_.Figure(data=[trace], layout=_layout(kw))

    def _build_bar(self, **kw: Any) -> Any:
        _require(kw, "x", "y")
        go_: Any = _go()
        trace = go_.Bar(
            x=kw["x"],
            y=kw["y"],
            name=kw.get("series_name") or kw.get("name"),
            marker={"color": kw.get("color") or None},
        )
        return go_.Figure(data=[trace], layout=_layout(kw))

    def _build_pie(self, **kw: Any) -> Any:
        _require(kw, "labels", "values")
        labels = kw["labels"]
        values = [_safe_number(v, default=0) for v in kw["values"]]
        hole = kw.get("hole", "0")
        if hole not in _PIE_HOLES:
            hole = "0"
        go_: Any = _go()
        trace = go_.Pie(
            labels=labels,
            values=values,
            hole=float(hole) if hole != "0" else 0.0,
        )
        layout = _layout(kw)
        layout["showlegend"] = kw.get("show_legend", True)
        return go_.Figure(data=[trace], layout=layout)

    def _build_histogram(self, **kw: Any) -> Any:
        if not kw.get("x"):
            raise ValueError("'x' (list of observations) is required")
        go_: Any = _go()
        trace = go_.Histogram(
            x=kw["x"],
            nbinsx=kw.get("bins"),
            name=kw.get("series_name") or kw.get("name"),
        )
        return go_.Figure(data=[trace], layout=_layout(kw))


def _go() -> Any:
    if go is None:
        raise RuntimeError("plotly is not available")
    return go


def _require(kw: dict[str, Any], *fields: str) -> None:
    missing = [f for f in fields if not kw.get(f)]
    if missing:
        raise ValueError(f"missing required field(s): {', '.join(missing)}")


def _safe_number(value: Any, *, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _layout(kw: dict[str, Any]) -> dict[str, Any]:
    layout: dict[str, Any] = {}
    if kw.get("title"):
        layout["title"] = {"text": str(kw["title"])}
    if kw.get("x_label"):
        layout["xaxis"] = {"title": {"text": str(kw["x_label"])}}
    if kw.get("y_label"):
        layout["yaxis"] = {"title": {"text": str(kw["y_label"])}}
    if kw.get("plot_bgcolor"):
        layout["plot_bgcolor"] = kw["plot_bgcolor"]
    if kw.get("paper_bgcolor"):
        layout["paper_bgcolor"] = kw["paper_bgcolor"]
    return layout


__all__ = ["ChartGenerator", "SafetyTier"]
