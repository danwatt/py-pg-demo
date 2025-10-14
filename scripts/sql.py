from typing import List, Tuple

import psycopg2

from scripts.config import PG_USER, PG_PASSWORD, PG_HOST, PG_PORT


def split_sql_statements(sql_text: str) -> List[str]:
    # naive split on semicolons outside of strings; good enough for demos
    stmts = []
    buf = []
    in_single = False
    in_double = False
    prev = ''
    for ch in sql_text:
        if ch == "'" and prev != "\\" and not in_double:
            in_single = not in_single
        elif ch == '"' and prev != "\\" and not in_single:
            in_double = not in_double
        if ch == ';' and not in_single and not in_double:
            stmts.append(''.join(buf).strip())
            buf = []
        else:
            buf.append(ch)
        prev = ch
    tail = ''.join(buf).strip()
    if tail:
        stmts.append(tail)
    return [s for s in (stmt.strip() for stmt in stmts) if s]


def exec_sql_block(dbname: str, sql_text: str, offline: bool = False) -> List[Tuple[List[str], List[Tuple]]]:
    if offline:
        return []
    results = []
    conn = psycopg2.connect(user=PG_USER, password=PG_PASSWORD, host=PG_HOST, port=PG_PORT, dbname=dbname)
    try:
        conn.autocommit = True
        cur = conn.cursor()
        for stmt in split_sql_statements(sql_text):
            cur.execute(stmt)
            # If the statement produced a result set, cursor.description is populated
            if cur.description:
                cols = [d[0] for d in cur.description]
                rows = cur.fetchall()
                results.append((cols, rows))
        cur.close()
    except Exception as e:
        print(f"Error executing SQL block: {e}")
        raise
    finally:
        conn.close()
    return results
