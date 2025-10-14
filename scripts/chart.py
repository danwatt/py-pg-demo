import json
import uuid
from typing import Tuple, List


def render_chart_from_results(chart_info: dict, first_result: Tuple[List[str], List[Tuple]]) -> str:
    chart_type = chart_info.get("type")
    x_col = chart_info.get("x")
    y_col = chart_info.get("y")
    title = chart_info.get("title") or f"{y_col} by {x_col}"
    cols, rows = first_result
    if not rows:
        return ""
    try:
        x_idx = cols.index(x_col)
        y_idx = cols.index(y_col)
    except ValueError:
        return ""
    labels = [str(r[x_idx]) for r in rows]
    data = []
    for r in rows:
        v = r[y_idx]
        try:
            data.append(float(v))
        except Exception:
            # skip non-numeric; if any skip, bail out
            return ""
    canvas_id = f"chart_{uuid.uuid4().hex[:8]}"
    cfg = {
        "type": chart_info.get("type") if chart_type in ("bar", "line", "pie") else "bar",
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "label": title,
                    "data": data,
                    "backgroundColor": "rgba(54, 162, 235, 0.5)",
                    "borderColor": "rgb(54, 162, 235)",
                    "borderWidth": 1,
                }
            ],
        },
        "options": {
            "responsive": True,
            "plugins": {"legend": {"display": True}},
            "scales": {"y": {"beginAtZero": True}},
        },
    }
    cfg_js = json.dumps(cfg)
    # Use doubled braces only for the IIFE wrapper; all config is injected via JSON
    return (
        f'<div class="sql-chart">\n<canvas id="{canvas_id}" height="220"></canvas>\n'
        f'</div>\n<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>\n'
        f'<script>(function(){{\n  var ctx = document.getElementById("{canvas_id}").getContext("2d");\n'
        f'  var cfg = {cfg_js};\n  new Chart(ctx, cfg);\n}})();</script>\n'
    )
