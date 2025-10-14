import random
from typing import Dict, Any, List

import psycopg2
from psycopg2.extras import execute_values
import yaml
from faker import Faker

from scripts.config import PG_USER, PG_PASSWORD, PG_HOST, PG_PORT


def _generate_value(spec: Any, fk: Faker, conn, cache: Dict[str, List[Any]]):
    # Simple scalar
    if spec is None or isinstance(spec, (int, float, bool, str)):
        return spec
    if isinstance(spec, list):
        return random.choice(spec) if spec else None
    if not isinstance(spec, dict):
        return spec
    # oneof: [..]
    if "oneof" in spec:
        choices = spec.get("oneof")
        return random.choice(choices) if isinstance(choices, list) and choices else None
    # faker: provider with optional args
    if "faker" in spec:
        provider = spec.get("faker")
        kwargs = spec.get("kwargs") or {}
        fn = getattr(fk, provider, None)
        if callable(fn):
            try:
                return fn(**kwargs)
            except Exception:
                return fn()
        # fallback: unknown provider -> None
        return None
    # ref: table/column or raw sql
    if "ref" in spec:
        ref = spec["ref"]
        if isinstance(ref, dict):
            if "sql" in ref:
                sql = ref["sql"]
                key = f"sql::{sql}"
                if key not in cache:
                    cur = conn.cursor()
                    cur.execute(sql)
                    cache[key] = [row[0] for row in cur.fetchall()]
                    cur.close()
                vals = cache.get(key, [])
                return random.choice(vals) if vals else None
            table = ref.get("table")
            column = ref.get("column", "id")
            if table:
                key = f"{table}.{column}"
                if key not in cache:
                    cur = conn.cursor()
                    cur.execute(f"SELECT \"{column}\" FROM \"{table}\"")
                    cache[key] = [row[0] for row in cur.fetchall()]
                    cur.close()
                vals = cache.get(key, [])
                return random.choice(vals) if vals else None
    # default fallback
    return None



def seed_fake_data(dbname: str, yaml_text: str, offline: bool = False) -> str:
    spec = yaml.safe_load(yaml_text) or {}
    table = spec.get("table")
    rows = int(spec.get("rows", 1))
    fields: Dict[str, Any] = spec.get("fields") or {}
    seed = spec.get("seed")
    if not table or not isinstance(fields, dict) or rows <= 0:
        return "> Invalid fakeseed spec: requires 'table', positive 'rows', and 'fields' mapping.\n"
    if offline:
        return f"> (Offline build: would insert {rows} fake row(s) into {table})\n"

    fk = Faker()
    if isinstance(seed, int):
        Faker.seed(seed)
        random.seed(seed)

    conn = psycopg2.connect(user=PG_USER, password=PG_PASSWORD, host=PG_HOST, port=PG_PORT, dbname=dbname)
    try:
        # Use a single transaction for speed
        conn.autocommit = False
        cur = conn.cursor()
        cache: Dict[str, List[Any]] = {}
        cols = list(fields.keys())
        collist = ", ".join([f'"{c}"' for c in cols])
        print(f"Inserting {rows} fake row(s) into {table}...")
        insert_sql = f"INSERT INTO \"{table}\" ({collist}) VALUES %s"

        # Generate rows in chunks to limit memory and speed up insertion
        def _row_generator():
            for _ in range(rows):
                yield tuple(_generate_value(fields[c], fk, conn, cache) for c in cols)

        def _chunked(iterable, size: int):
            batch = []
            for item in iterable:
                batch.append(item)
                if len(batch) >= size:
                    yield batch
                    batch = []
            if batch:
                yield batch

        # Tuneable batch size; 1k is a solid default for execute_values
        BATCH_SIZE = 1000
        for chunk in _chunked(_row_generator(), BATCH_SIZE):
            execute_values(cur, insert_sql, chunk, page_size=BATCH_SIZE)
        cur.close()
        conn.commit()
        return f"> Inserted {rows} fake row(s) into {table}.\n"
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
