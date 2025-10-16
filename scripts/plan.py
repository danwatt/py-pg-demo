# filepath: c:\Users\danwa\PycharmProjects\pg-demo\scripts\plan.py
import json
import re
from typing import Any, Dict, List, Tuple, Optional

import psycopg2  # switched from pg8000 to psycopg2

from scripts.config import PG_USER, PG_PASSWORD, PG_HOST, PG_PORT
from scripts.sql import split_sql_statements
from scripts.table import render_html_table


def _format_float(v: Any) -> str:
    try:
        return f"{float(v):.2f}"
    except Exception:
        return str(v)


def _mm_escape_label(s: str) -> str:
    # Mermaid flowchart label inside ["..."] supports <br/> for newlines. Escape quotes/brackets.
    return (
        (s or "")
        .replace("\n", "<br/>")
        .replace("[", "(")
        .replace("]", ")")
        .replace("\"", "&quot;")
    )


def _node_label(n: Dict[str, Any]) -> str:
    nt = n.get("Node Type", "Node")
    rel = n.get("Relation Name")
    join_type = n.get("Join Type")
    head = f"{join_type + ' ' if join_type else ''}{nt}"
    if rel:
        head += f" on {rel}"
    rows = n.get("Plan Rows") if n.get("Plan Rows") is not None else n.get("Actual Rows")
    cost = n.get("Total Cost")
    index = n.get("Index Name")
    parts = [head]
    if rows is not None:
        parts.append(f"rows={rows}")
    if cost is not None:
        parts.append(f"cost={_format_float(cost)}")
    if index is not None:
        parts.append(f"index={index}")
    return _mm_escape_label("\n".join(parts))


def _build_flowchart(plan_root: Dict[str, Any], orientation: str = "LR") -> str:
    # Depth-first traversal to build nodes and edges
    direction = orientation if orientation in {"TB", "TD", "LR", "RL"} else "TB"
    lines: List[str] = [
        "---",
        "config:",
        "  look: neo",
        "  theme: neo",
        "---",
        f"flowchart {direction}"
    ]
    counter = [0]

    # Track node "Total Cost" and per-link styles in traversal order
    node_cost: Dict[str, float] = {}
    link_styles: List[str] = []

    def next_id() -> str:
        counter[0] += 1
        return f"n{counter[0]}"

    def parse_cost(n: Dict[str, Any]) -> float:
        v = n.get("Total Cost")
        try:
            return float(v) if v is not None else 0.0
        except Exception:
            return 0.0

    def edge_width_px(parent_cost: float, child_cost: float) -> int:
        # Map child/base (root) cost ratio to a stroke width in px
        MIN_W, MAX_W = 1, 10
        if parent_cost <= 0 or child_cost <= 0:
            return MIN_W
        ratio = child_cost / parent_cost
        ratio = max(ratio, 0)
        ratio = min(ratio, 1)
        width = round(MIN_W + ratio * (MAX_W - MIN_W))
        width = max(width, MIN_W)
        width = min(width, MAX_W)
        return int(width)

    # Capture root plan cost once; use as baseline for all edge thickness calculations
    root_cost = parse_cost(plan_root)

    def walk(n: Dict[str, Any]) -> Tuple[str, List[str]]:
        node_id = next_id()
        # Record node cost for later edge scaling
        node_cost[node_id] = parse_cost(n)
        label = _node_label(n)
        node_line = f'{node_id}["{label}"]'
        out_lines = [node_line]
        for ch in n.get("Plans", []) or []:
            child_id, child_lines = walk(ch)
            out_lines.extend(child_lines)
            out_lines.append(f"{node_id} --> {child_id}")
            # Determine link style index by current number of links emitted
            idx = len(link_styles)
            # Use root_cost as baseline to make thickness relative to total plan cost
            width = edge_width_px(root_cost, node_cost.get(child_id, 0.0))
            link_styles.append(f"linkStyle {idx} stroke-width:{width}px")
        return node_id, out_lines

    _, body_lines = walk(plan_root)
    lines.extend(body_lines)
    # Append per-link style directives after edges; Mermaid counts links in declaration order
    if link_styles:
        lines.extend(link_styles)
    return "\n".join(lines)


def _render_tabs(flowchart_diagram: str, plan_json_pretty: str, results_html: Optional[str] = None) -> str:
    # Minimal tabs CSS/JS, no external deps
    style = (
        "<style>"
        ".plan-tabs{border:1px solid #ddd;border-radius:6px;overflow:hidden;margin:0.4rem 0;background:#fff;}"
        ".plan-tabs .tab-bar{display:flex;border-bottom:1px solid #ddd;background:#f6f8fa;}"
        ".plan-tabs .tab{padding:6px 10px;cursor:pointer;font-size:.95em;border-right:1px solid #e5e5e5;user-select:none;}"
        ".plan-tabs .tab.active{background:#fff;font-weight:600;}"
        ".plan-tabs .tab-panel{display:none;padding:8px;}"
        ".plan-tabs .tab-panel.active{display:block;}"
        ".plan-tabs pre{white-space:pre-wrap;word-break:break-word;background:#fafafa;border:1px solid #eee;border-radius:4px;padding:8px;margin:0;}"
        "</style>"
    )
    visual_panel = (
        f"<div class=\"tab-panel active\">"
        f"<div class=\"mermaid\">{flowchart_diagram}</div>"
        f"</div>"
    )
    raw_panel = (
        f"<div class=\"tab-panel\"><pre>{plan_json_pretty}</pre></div>"
    )
    results_panel = (
        f"<div class=\"tab-panel\">{results_html}</div>" if results_html else ""
    )
    # Build tabs and panels conditionally
    tab_bar = (
        f"<div class=\"tab-bar\">"
        f"  <div class=\"tab active\" data-tab=\"visual\">Visual</div>"
        + (f"  <div class=\"tab\" data-tab=\"results\">Results</div>" if results_html else "") +
        f"  <div class=\"tab\" data-tab=\"raw\">Raw (JSON)</div>"
        f"</div>"
    )
    panels = (
        f"<div class=\"panels\">"
        f"  <div class=\"panel visual\">{visual_panel}</div>"
        + (f"  <div class=\"panel results\">{results_panel}</div>" if results_html else "") +
        f"  <div class=\"panel raw\">{raw_panel}</div>"
        f"</div>"
    )
    tabs = (
        f"<div class=\"plan-tabs\">{style}"
        f"{tab_bar}"
        f"{panels}"
        f"</div>"
        f"<script src=\"https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js\"></script>"
        f"<script>(function(){{\n"
        f"  try {{ mermaid.initialize({{ startOnLoad: true }}); }} catch (e) {{}}\n"
        f"  var root = document.currentScript.previousElementSibling;\n"
        f"  // Find nearest .plan-tabs (previous sibling may be the script tag)\n"
        f"  while (root && !root.classList.contains('plan-tabs')) root = root.previousElementSibling;\n"
        f"  if (!root) root = document.querySelector('.plan-tabs');\n"
        f"  if (root) {{\n"
        f"    var tabs = root.querySelectorAll('.tab-bar .tab');\n"
        f"    var panels = {{}};\n"
        f"    ['visual','results','raw'].forEach(function(name){{\n"
        f"      var p = root.querySelector('.panel.'+name+' .tab-panel');\n"
        f"      if (p) panels[name] = p;\n"
        f"    }});\n"
        f"    function activate(which) {{\n"
        f"      tabs.forEach(function(t){{ t.classList.toggle('active', t.dataset.tab===which); }});\n"
        f"      Object.keys(panels).forEach(function(name){{ panels[name].classList.toggle('active', name===which); }});\n"
        f"      if (which==='visual') {{ try {{ mermaid.init(); }} catch(e) {{}} }}\n"
        f"    }}\n"
        f"    tabs.forEach(function(t){{ t.addEventListener('click', function(){{ activate(t.dataset.tab); }}); }});\n"
        f"  }}\n"
        f"}})();</script>"
    )
    return tabs


def render_explain_plan(dbname: str, sql_text: str) -> str:
    # Use the first statement; wrap with EXPLAIN (FORMAT JSON)
    stmts = split_sql_statements(sql_text)
    if not stmts:
        return ""
    original_stmt = stmts[0].strip().rstrip(';')

    explain_re = re.compile(r"^\s*explain(\s*\((?P<opts>[^)]*)\))?\s+(?P<body>.*)$", re.IGNORECASE | re.DOTALL)
    m = explain_re.match(original_stmt)
    results_stmt = None
    if m:
        opts = m.group('opts') or ''
        body = (m.group('body') or '').strip()
        # Keep a copy of the body for results if it's a row-returning statement
        results_stmt = body
        if 'format json' not in (opts or '').lower():
            opts = (opts + ', FORMAT JSON') if opts else 'FORMAT JSON'
        # Add verbosity and costs unless already present
        add_opts = []
        lo = (opts or '').lower()
        if 'verbose' not in lo:
            add_opts.append('VERBOSE')
        if 'costs' not in lo:
            add_opts.append('COSTS')
        if add_opts:
            opts = opts + ', ' + ', '.join(add_opts)
        stmt = f"EXPLAIN ({opts}) {body}"
    else:
        results_stmt = original_stmt
        stmt = f"EXPLAIN (ANALYZE, COSTS, VERBOSE, BUFFERS, FORMAT JSON) {original_stmt}"

    # Decide if we should attempt to fetch a result set (SELECT/WITH/VALUES)
    results_html: Optional[str] = None
    def is_row_returning(s: Optional[str]) -> bool:
        if not s:
            return False
        return re.match(r"^\s*(select|with|values)\b", s, re.IGNORECASE) is not None

    conn = psycopg2.connect(user=PG_USER, password=PG_PASSWORD, host=PG_HOST, port=PG_PORT, dbname=dbname)
    try:
        conn.autocommit = True
        cur = conn.cursor()
        # First, run EXPLAIN ... FORMAT JSON
        cur.execute(stmt)
        row = cur.fetchone()
        # Optionally, run the original row-returning statement to fetch results
        if is_row_returning(results_stmt):
            try:
                cur.execute(results_stmt)
                if cur.description:
                    cols = [d[0] for d in cur.description]
                    rows = cur.fetchall()
                    results_html = render_html_table(cols, rows)
            except Exception:
                # If the results query fails, leave the results tab empty
                results_html = None
        cur.close()
    finally:
        conn.close()

    if not row:
        return ""
    plan_val = row[0]
    try:
        if isinstance(plan_val, (str, bytes)):
            plan_json = json.loads(plan_val)
        else:
            plan_json = plan_val
    except Exception:
        return f"<pre class=\"explain-text\">{str(plan_val)}</pre>"

    try:
        top = plan_json[0] if isinstance(plan_json, list) else plan_json
        plan_root = top.get("Plan") if isinstance(top, dict) else None
        if not isinstance(plan_root, dict):
            return f"<pre class=\"explain-text\">{json.dumps(plan_json, indent=2)}</pre>"
        flow = _build_flowchart(plan_root, orientation="TB")
        pretty = json.dumps(plan_json, indent=2)
        return _render_tabs(flow, pretty, results_html)
    except Exception:
        return f"<pre class=\"explain-text\">{json.dumps(plan_json, indent=2)}</pre>"
