from typing import List, Tuple


def render_html_table(cols: List[str], rows: List[Tuple]) -> str:
    thead = '<thead><tr>' + ''.join(f'<th>{escape_html(c)}</th>' for c in cols) + '</tr></thead>'
    tbody_rows = []
    for r in rows:
        tds = ''.join(f'<td>{escape_html(str(v))}</td>' for v in r)
        tbody_rows.append(f'<tr>{tds}</tr>')
    tbody = '<tbody>' + ''.join(tbody_rows) + '</tbody>'
    return f"\n\n<div class=\"sql-output\">\n<table>\n{thead}\n{tbody}\n</table>\n</div>\n\n"


def escape_html(s: str) -> str:
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace('"', "&quot;")
         .replace("'", "&#39;")
    )
