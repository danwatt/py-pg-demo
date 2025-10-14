# PG Demo Showcase

This project showcases PostgreSQL functionality through a set of demos built from Markdown. SQL blocks inside the Markdown are executed against per-demo databases in a Dockerized Postgres, and any result sets are rendered as HTML tables after the code block.

## Prerequisites

- Docker Desktop
- [uv](https://github.com/astral-sh/uv) (Python package/dependency manager)

> PowerShell note: Use new lines or `;` to separate commands. Avoid `&&` if your PowerShell version doesn’t support it.

## Quick start (PowerShell)

- Start Postgres in Docker:

```powershell
docker compose up -d postgres
```

- Build the site offline (no DB needed; SQL blocks are not executed):

```powershell
uv run python scripts\build.py --offline
```

- Build the site with Postgres (SQL blocks executed, results rendered):

```powershell
uv run python scripts\build.py
```

- Serve locally for live preview:

```powershell
uv run python -m mkdocs serve
```

The static site will be written to `build/site`.

## Project layout

- `demos/` — Each subfolder is a demo. Markdown files are processed in alphabetical order.
- `scripts/build.py` — Orchestrates Docker availability, executes SQL code blocks, writes processed Markdown to `build/staging`, and runs MkDocs to render HTML.
- `mkdocs.yml` — MkDocs configuration targeting the staging directory.

## Writing demos

- Put your demo files under `demos/<demo-name>/`.
- Use fenced code blocks labeled `sql` or `postgresql`:

````
```sql
SELECT 1 AS n;
```
````

Any statements that produce rows will be rendered as a table after the block, in the order they run.

Each demo maps to a separate PostgreSQL database named after the demo folder (sanitized).

### Optional: quick charts

Add an HTML comment on the line immediately before a SQL block to render a Chart.js chart from the first result set:

```markdown
<!-- chart:bar x=name y=age title="Age by Person" -->
```sql
SELECT name, age FROM people ORDER BY age;
```

### Optional: schema diagram (Mermaid)

Add an HTML comment on the line immediately before a SQL block to render a Mermaid ER diagram of the current database schema (after the SQL runs):

```markdown
<!-- schemadiagram -->
```sql
-- create or alter tables here
CREATE TABLE people (
  id serial PRIMARY KEY,
  name text NOT NULL,
  age int
);
```
```

Notes:
- The diagram is generated from the `public` schema using information_schema (tables, columns, primary keys, and foreign keys).
- The output is injected as a Mermaid `erDiagram` block and rendered via the Mermaid CDN script. No extra plugins needed.
- In offline builds, the diagram is skipped with a short note.

### New: Fake data seeding with YAML + Faker

You can insert N rows of fake data using a YAML block powered by [Faker](https://faker.readthedocs.io/) and optional references to existing rows. Place the directive `<!-- fakeseed -->` immediately before a fenced block labeled `yaml`.

Example:

```markdown
<!-- fakeseed -->
```yaml
seed: 42              # optional, for reproducible data
table: pets           # required: table name
rows: 5               # required: number of rows to insert
fields:               # required: mapping of column -> value spec
  person_id:          # choose an existing id from another table
    ref: { table: people, column: id }
  name:               # use a Faker provider
    faker: first_name
  species:            # pick randomly from a list
    oneof: ["cat", "dog", "penguin"]
```
```

Supported field specs:
- Scalar values (string/number/bool/null) are inserted as-is.
- `oneof: [..]` randomly picks one of the provided values.
- `faker: <provider>` calls a Faker provider, e.g. `first_name`, `last_name`, `email`, etc. Optional `kwargs: { ... }` can be passed.
- `ref:` may be:
  - `{ table: <table>, column: <column> }` to randomly pick an existing value from that column.
  - `{ sql: "SELECT id FROM some_table WHERE ..." }` to pick from a custom query (first column used).

Notes:
- The YAML block is executed at build time like SQL blocks, and a short summary is shown after it.
- In offline builds, fakeseed execution is skipped with a note (no inserts performed).

### New: visual EXPLAIN plan

Add `<!-- plan -->` on the line immediately before a SQL block to render a Mermaid flowchart of the PostgreSQL planner output.

Example:

```markdown
<!-- plan -->
```sql
SELECT COUNT(*) FROM people;
```
```

Notes:
- The builder runs `EXPLAIN (FORMAT JSON, VERBOSE, COSTS)` on your query and renders a Mermaid flowchart (top-down) of the plan tree.
- Each node label includes the node type (and relation when present), plus `rows=` and `cost=`.
- It does not use `ANALYZE`, so the query is not executed.
- If you already wrote `EXPLAIN (...)`, the builder ensures `FORMAT JSON` is present and preserves your other options.
- In offline builds, the plan is skipped and a short note is shown.

## Notes

- Configure connection parameters via env vars: `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`.
- The offline build is useful for quick iteration on content and layout without Docker.

## Next ideas

- Charts: detect more chart types and styling options.
- MkDocs plugin: move the pre-processing into a custom plugin that hooks into `on_page_markdown` to avoid a staging dir.
