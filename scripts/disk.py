from html import escape
from typing import List, Dict

import psycopg2

from scripts.config import PG_USER, PG_PASSWORD, PG_HOST, PG_PORT


def _fmt_size(bytes_val: int) -> str:
    try:
        b = float(bytes_val or 0)
    except Exception:
        b = 0.0
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while b >= 1024 and i < len(units) - 1:
        b /= 1024.0
        i += 1
    if i <= 1:
        return f"{b:.0f} {units[i]}"
    return f"{b:.2f} {units[i]}"


def _fetch_disk_usage(dbname: str) -> List[Dict[str, object]]:
    """
    Return records of disk usage across non-system schemas in the current database.
    Each record: {schema, table, name, kind, size_bytes}
    - A 'table' kind entry represents only the table heap (pg_relation_size(table)).
    - For each index on a table, include an 'index' kind entry with its size.
    """
    conn = psycopg2.connect(user=PG_USER, password=PG_PASSWORD, host=PG_HOST, port=PG_PORT, dbname=dbname)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            WITH tables AS (
              SELECT c.oid AS table_oid, n.nspname AS schema, c.relname AS table_name
              FROM pg_class c
              JOIN pg_namespace n ON n.oid = c.relnamespace
              WHERE c.relkind = 'r' -- ordinary tables
                AND n.nspname NOT IN ('pg_catalog','information_schema','pg_toast')
            )
            SELECT t.schema,
                   t.table_name,
                   'table' AS kind,
                   t.table_name AS name,
                   pg_relation_size(t.table_oid) AS size_bytes
            FROM tables t
            UNION ALL
            SELECT t.schema,
                   t.table_name,
                   'index' AS kind,
                   i.relname AS name,
                   pg_relation_size(i.oid) AS size_bytes
            FROM tables t
            JOIN pg_index ix ON ix.indrelid = t.table_oid
            JOIN pg_class i ON i.oid = ix.indexrelid
            ORDER BY 1, 2, 3, 4
            """
        )
        rows = cur.fetchall()
        cur.close()
    finally:
        conn.close()
    result: List[Dict[str, object]] = []
    for schema, table, kind, name, size_bytes in rows:
        result.append({
            "schema": schema,
            "table": table,
            "kind": kind,
            "name": name if kind == "index" else "(table data)",
            "size_bytes": int(size_bytes or 0),
        })
    return result


# Minimal CSS for the table view
essential_table_css = """
<style>
.sql-disk-summary{margin:8px 0;padding:8px;border:1px solid #e5e5e5;border-radius:6px;background:#fff}
.sql-disk-summary .legend{font-size:.9em;color:#444;margin:0 0 6px 0}
.sql-disk-summary table{width:100%;border-collapse:collapse;font-size:.95em}
.sql-disk-summary th,.sql-disk-summary td{padding:6px 8px;border-bottom:1px solid #eee}
.sql-disk-summary th{text-align:left;color:#444;background:#fafafa}
.sql-disk-summary td.num{text-align:right;white-space:nowrap}
.sql-disk-summary tr.sub td:first-child{padding-left:24px;color:#444}
</style>
"""


def render_disk_treemap(dbname: str) -> str:
    """
    Render a simple HTML table of disk usage.
    Tables are listed with their total size, and their indexes are nested beneath
    showing each index's size and the percentage of the table's total they consume.
    """
    data = _fetch_disk_usage(dbname)
    if not data:
        return ""

    # Group data by (schema, table)
    tables: Dict[tuple, Dict[str, object]] = {}
    for rec in data:
        schema = str(rec.get("schema") or "")
        table = str(rec.get("table") or "")
        kind = str(rec.get("kind") or "")
        name = str(rec.get("name") or "")
        size_b = int(rec.get("size_bytes") or 0)

        key = (schema, table)
        if key not in tables:
            tables[key] = {"heap": 0, "indexes": []}  # type: ignore[assignment]
        if kind == "table":
            tables[key]["heap"] = size_b  # type: ignore[index]
        elif kind == "index":
            tables[key]["indexes"].append({"name": name, "size": size_b})  # type: ignore[index]

    # Build HTML rows
    def pct(part: int, whole: int) -> str:
        if whole <= 0:
            return "0%"
        return f"{(part / whole) * 100:.1f}%"

    # Sort by schema, then table name
    sorted_keys = sorted(tables.keys(), key=lambda k: (k[0], k[1]))

    rows_html: List[str] = []
    for (schema, table) in sorted_keys:
        heap = int(tables[(schema, table)]["heap"])  # type: ignore[index]
        idx_list = list(tables[(schema, table)]["indexes"])  # type: ignore[index]
        # Total size for the table = heap + indexes
        total = heap + sum(i["size"] for i in idx_list)

        # Table total row
        fq_name = f"{schema}.{table}" if schema else table
        rows_html.append(
            f"<tr class=\"table\"><td><strong>{escape(fq_name)}</strong></td><td class=\"num\"><strong>{_fmt_size(total)}</strong></td><td class=\"num\">100%</td></tr>"
        )
        # Heap (table data) row
        rows_html.append(
            f"<tr class=\"sub\"><td>(table data)</td><td class=\"num\">{_fmt_size(heap)}</td><td class=\"num\">&ndash;</td></tr>"
        )
        # Index rows (largest first)
        for idx in sorted(idx_list, key=lambda x: x["size"], reverse=True):
            rows_html.append(
                f"<tr class=\"sub\"><td>{escape(str(idx['name']))}</td><td class=\"num\">{_fmt_size(idx['size'])}</td><td class=\"num\">{pct(idx['size'], total)}</td></tr>"
            )

    html = f"""
{essential_table_css}
<div class=\"sql-disk-summary\">
  <div class=\"legend\">Index percentages are relative to their table's total size (heap + all indexes).</div>
  <table>
    <thead>
      <tr><th>Object</th><th>Size</th><th>% of table</th></tr>
    </thead>
    <tbody>
      {''.join(rows_html)}
    </tbody>
  </table>
</div>
"""
    return html

