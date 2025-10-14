from typing import Dict, List

import psycopg2

from scripts.config import PG_USER, PG_PASSWORD, PG_HOST, PG_PORT


def _map_pg_type_to_mermaid(pg_type: str) -> str:
    t = (pg_type or "").lower()
    if t in {"smallint", "integer", "int", "int2", "int4", "bigint", "int8", "serial", "bigserial", "smallserial"}:
        return "int"
    if t in {"numeric", "decimal", "real", "double precision", "float4", "float8"}:
        return "float"
    if t in {"boolean", "bool"}:
        return "bool"
    if t in {"date"}:
        return "date"
    if t.startswith("timestamp") or t.startswith("time"):
        # Mermaid ER doesn't have datetime; use string
        return "string"
    # common string-ish types
    if any(s in t for s in ["char", "text", "uuid", "json", "jsonb", "bytea", "xml", "inet", "citext"]):
        return "string"
    # default fallback
    return "string"


def render_schema_mermaid(dbname: str) -> str:
    # Introspect tables, columns, PKs, FKs from public schema and build a Mermaid ER diagram
    conn = psycopg2.connect(user=PG_USER, password=PG_PASSWORD, host=PG_HOST, port=PG_PORT, dbname=dbname)
    try:
        cur = conn.cursor()
        # Tables
        cur.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            ORDER BY table_name
            """
        )
        tables = [r[0] for r in cur.fetchall()]

        # Columns and PKs
        columns: Dict[str, List[Dict[str, str]]] = {}
        pks: Dict[str, List[str]] = {}
        for t in tables:
            cur.execute(
                """
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema='public' AND table_name=%s
                ORDER BY ordinal_position
                """,
                (t,)
            )
            cols = [{"name": r[0], "type": r[1], "nullable": r[2]} for r in cur.fetchall()]
            columns[t] = cols
            cur.execute(
                """
                SELECT kc.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kc
                  ON tc.constraint_name = kc.constraint_name
                 AND tc.table_schema = kc.table_schema
                 AND tc.table_name = kc.table_name
                WHERE tc.constraint_type='PRIMARY KEY'
                  AND tc.table_schema='public'
                  AND tc.table_name=%s
                ORDER BY kc.ordinal_position
                """,
                (t,)
            )
            pks[t] = [r[0] for r in cur.fetchall()]

        # Foreign keys
        cur.execute(
            """
            SELECT
              tc.table_name AS fk_table,
              kcu.column_name AS fk_column,
              ccu.table_name AS pk_table,
              ccu.column_name AS pk_column
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
            JOIN information_schema.referential_constraints AS rc
              ON tc.constraint_name = rc.constraint_name
             AND tc.table_schema = rc.constraint_schema
            JOIN information_schema.constraint_column_usage AS ccu
              ON ccu.constraint_name = rc.unique_constraint_name
             AND ccu.constraint_schema = rc.unique_constraint_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_schema = 'public'
            ORDER BY fk_table, fk_column
            """
        )
        fks = [(r[0], r[1], r[2], r[3]) for r in cur.fetchall()]
        cur.close()
    finally:
        conn.close()

    # Build Mermaid ER diagram text (Mermaid expects specific simple types)
    lines = ["erDiagram"]
    for t in tables:
        ent = t.upper()
        lines.append(f"  {ent} {{")
        pkset = set(pks.get(t, []))
        for col in columns.get(t, []):
            mtype = _map_pg_type_to_mermaid(col["type"])  # map PG type -> mermaid
            name = col["name"]
            suffix = " PK" if name in pkset else ""
            lines.append(f"    {mtype} {name}{suffix}")
        lines.append("  }")
    for (fk_table, fk_col, pk_table, pk_col) in fks:
        lines.append(f"  {pk_table.upper()} ||--o{{ {fk_table.upper()} : {fk_col}") # :  -> {pk_col}

    diagram = "\n".join(lines)

    # Use a div.mermaid block (preferred by Mermaid)
    mermaid_html = f"""
<div class=\"schema-diagram\">\n<div class=\"mermaid\">{diagram}</div>\n</div>\n<script src=\"https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js\"></script>\n<script>
  (function() {{
    try {{ mermaid.initialize({{ startOnLoad: true }}); }} catch (e) {{}}
  }})();
</script>
"""
    return mermaid_html
