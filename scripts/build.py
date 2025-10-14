import re
import time
import shutil
import subprocess
from pathlib import Path
from typing import List, Dict, Any
import argparse
import sys

import psycopg2
import yaml

from scripts.config import PG_USER, PG_PASSWORD, PG_HOST, PG_PORT
from scripts.chart import render_chart_from_results
from scripts.fakeseed import seed_fake_data
from scripts.mermaid import render_schema_mermaid
from scripts.sql import exec_sql_block
from scripts.table import render_html_table, escape_html
from scripts.plan import render_explain_plan

ROOT = Path(__file__).resolve().parents[1]
DEMOS_DIR = ROOT / "demos"
BUILD_DIR = ROOT / "build"
STAGING_DIR = BUILD_DIR / "staging"
SITE_DIR = BUILD_DIR / "site"

# Match any code fence; capture language if present
CODE_FENCE_START_RE = re.compile(r"^```\s*([a-zA-Z0-9_-]+)?\s*$", re.IGNORECASE)
CODE_FENCE_END_RE = re.compile(r"^```\s*$")
CHART_DIRECTIVE_RE = re.compile(r"<!--\s*chart:(bar|line|pie)\s+x=(\w+)\s+y=(\w+)(?:\s+title=\"([^\"]*)\")?\s*-->", re.IGNORECASE)
SCHEMA_DIAGRAM_DIRECTIVE_RE = re.compile(r"<!--\s*schemadiagram\s*-->", re.IGNORECASE)
FAKESEED_DIRECTIVE_RE = re.compile(r"<!--\s*fakeseed\s*-->", re.IGNORECASE)
PLAN_DIRECTIVE_RE = re.compile(r"<!--\s*plan\s*-->", re.IGNORECASE)


def ensure_postgres_is_up(timeout_seconds: int = 90) -> None:
    start = time.time()
    last_err = None
    while time.time() - start < timeout_seconds:
        try:
            conn = psycopg2.connect(user=PG_USER, password=PG_PASSWORD, host=PG_HOST, port=PG_PORT, dbname="postgres")
            conn.close()
            return
        except Exception as e:
            last_err = e
            time.sleep(1.5)
    raise RuntimeError(f"Postgres did not become available within {timeout_seconds}s: {last_err}")


def docker_compose_up() -> None:
    # Try docker compose v2, then fall back to v1 (docker-compose)
    for cmd in (["docker", "compose", "up", "-d", "postgres"], ["docker-compose", "up", "-d", "postgres"]):
        try:
            subprocess.run(cmd, check=False, cwd=str(ROOT))
            return
        except Exception:
            continue


def sanitize_db_name(name: str) -> str:
    # Lowercase, alnum and underscores only, must start with a letter per Postgres rules
    slug = re.sub(r"[^a-z0-9_]+", "_", name.lower())
    if not re.match(r"^[a-z]", slug):
        slug = f"d_{slug}"
    return slug[:63]  # postgres name limit


def list_demo_dirs() -> List[Path]:
    if not DEMOS_DIR.exists():
        return []
    return sorted([p for p in DEMOS_DIR.iterdir() if p.is_dir()])


def ensure_database(dbname: str, offline: bool = False) -> None:
    if offline:
        return
    conn = psycopg2.connect(user=PG_USER, password=PG_PASSWORD, host=PG_HOST, port=PG_PORT, dbname="postgres")
    try:
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,))
        exists = cur.fetchone() is not None
        if not exists:
            cur.execute(f"CREATE DATABASE \"{dbname}\"")
        cur.close()
    finally:
        conn.close()


def _slug_to_title(slug: str) -> str:
    # Drop numeric prefix like 01_ or 01- and prettify
    m = re.match(r"^\s*([0-9]+)[_-]+(.*)$", slug)
    base = m.group(2) if m else slug
    base = base.replace("_", " ").replace("-", " ")
    return base.strip().title() or slug.title()


def _extract_h1_title(md_text: str, fallback_slug: str) -> str:
    for line in md_text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return _slug_to_title(Path(fallback_slug).stem)


def _list_markdown_files(demo_dir: Path) -> List[Path]:
    return sorted([p for p in demo_dir.iterdir() if p.is_file() and p.suffix.lower() in ('.md', '.markdown')])


def process_markdown_file(fp: Path, dbname: str, offline: bool = False) -> str:
    # Process a single markdown file, injecting outputs below code blocks
    with fp.open('r', encoding='utf-8') as f:
        lines = f.read().splitlines()
    out_parts: List[str] = []
    i = 0
    prev_nonempty_line = ""
    while i < len(lines):
        line = lines[i]
        m = CODE_FENCE_START_RE.match(line)
        if m:
            lang = (m.group(1) or '').lower()
            # Check directives on the previous non-empty line
            chart_info = None
            schema_diagram = False
            fakeseed = False
            plan = False
            if prev_nonempty_line:
                pl = prev_nonempty_line.strip()
                mdir = CHART_DIRECTIVE_RE.match(pl)
                if mdir:
                    chart_info = {
                        "type": mdir.group(1).lower(),
                        "x": mdir.group(2),
                        "y": mdir.group(3),
                        "title": mdir.group(4) or ""
                    }
                if SCHEMA_DIAGRAM_DIRECTIVE_RE.match(pl):
                    schema_diagram = True
                if FAKESEED_DIRECTIVE_RE.match(pl):
                    fakeseed = True
                if PLAN_DIRECTIVE_RE.match(pl):
                    plan = True
            # collect code block
            i += 1
            code_lines = []
            while i < len(lines) and not CODE_FENCE_END_RE.match(lines[i]):
                code_lines.append(lines[i])
                i += 1
            # consume closing fence if present
            if i < len(lines) and CODE_FENCE_END_RE.match(lines[i]):
                i += 1
            block_text = "\n".join(code_lines)
            # Re-emit the block with its original language
            out_parts.append(f"```{lang}\n" + block_text + "\n```")
            # Execute based on type/directive
            try:
                if lang in ("sql", "postgresql"):
                    snippets: List[str] = []
                    if plan:
                        if offline:
                            snippets.append("> (Offline build: plan not generated)\n")
                        else:
                            plan_html = render_explain_plan(dbname, block_text)
                            if plan_html:
                                snippets.append(plan_html)
                    else:
                        print(f"Executing SQL block in {fp} against {dbname}: {block_text.splitlines()[0]}")
                        results = exec_sql_block(dbname, block_text, offline=offline)
                        # tables
                        for (cols, rows) in results:
                            snippets.append(render_html_table(cols, rows))
                        # chart if present and we have at least one result set
                        if chart_info and results:
                            chart_html = render_chart_from_results(chart_info, results[0])
                            if chart_html:
                                snippets.append(chart_html)
                        # schema diagram if requested
                        if schema_diagram:
                            if offline:
                                snippets.append("> (Offline build: schema diagram not generated)\n")
                            else:
                                diag_html = render_schema_mermaid(dbname)
                                if diag_html:
                                    snippets.append(diag_html)
                    # wrap snippets if any
                    if snippets:
                        out_parts.append("\n<details open><summary>Output</summary>\n")
                        out_parts.extend(snippets)
                        out_parts.append("\n</details>\n")
                    elif not plan and not schema_diagram and offline:
                        # If we didn't execute anything in offline mode
                        out_parts.append("\n> (Offline build: SQL not executed)\n")
                elif lang in ("yaml", "yml") and fakeseed:
                    # run fake seed
                    msg = seed_fake_data(dbname, block_text, offline=offline)
                    if msg:
                        out_parts.append("\n<details open><summary>Output</summary>\n")
                        out_parts.append(msg)
                        out_parts.append("\n</details>\n")
            except Exception as e:
                out_parts.append(f"\n> Error executing block: `{escape_html(str(e))}`\n")
            prev_nonempty_line = ""  # reset after a block
        else:
            out_parts.append(line)
            if line.strip():
                prev_nonempty_line = line
            i += 1
    return "\n".join(out_parts).rstrip() + "\n"


def build_site(offline: bool = False) -> None:
    # Clean staging and site
    if STAGING_DIR.exists():
        shutil.rmtree(STAGING_DIR)
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    SITE_DIR.mkdir(parents=True, exist_ok=True)

    # Discover demos and pages, ensure DBs, and generate processed pages
    demo_dirs = list_demo_dirs()

    # Collect nav structure: List[Dict[str, Any]] for mkdocs
    nav: List[Dict[str, Any]] = [{"Home": "index.md"}]

    # Also build a friendly index with links
    index_lines: List[str] = ["# PG Demo Showcase\n\n", "Welcome! Choose a demo:\n\n"]

    for demo_dir in demo_dirs:
        dbname = sanitize_db_name(demo_dir.name)
        ensure_database(dbname, offline=offline)
        # Per-file processing
        md_files = _list_markdown_files(demo_dir)
        if not md_files:
            continue
        demo_title = _slug_to_title(demo_dir.name)
        demo_nav_entries: List[Dict[str, str]] = []
        index_lines.append(f"\n## {demo_title}\n\n")
        for fp in md_files:
            content = process_markdown_file(fp, dbname, offline=offline)
            out_rel = Path("demos") / demo_dir.name / fp.name
            out_path = STAGING_DIR / out_rel
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(content, encoding='utf-8')
            # Title for nav from H1 if present
            page_title = _extract_h1_title(content, fp.name)
            rel_posix = out_rel.as_posix()
            demo_nav_entries.append({page_title: rel_posix})
            index_lines.append(f"- [{page_title}]({rel_posix})\n")
        # Add this demo section to nav
        nav.append({demo_title: demo_nav_entries})

    # Write index
    (STAGING_DIR / "index.md").write_text("".join(index_lines), encoding='utf-8')

    # Generate a mkdocs config that includes our per-file nav
    base_cfg_path = ROOT / "mkdocs.yml"
    if base_cfg_path.exists():
        with base_cfg_path.open('r', encoding='utf-8') as f:
            base_cfg = yaml.safe_load(f) or {}
    else:
        base_cfg = {}
    # Override docs_dir/site_dir to ensure correct paths relative to BUILD_DIR
    base_cfg["docs_dir"] = "staging"
    base_cfg["site_dir"] = "site"
    if "site_name" not in base_cfg:
        base_cfg["site_name"] = "PG Demo Showcase"
    # Replace nav
    base_cfg["nav"] = nav
    # Ensure theme and markdown extensions defaults if missing
    base_cfg.setdefault("theme", {"name": "readthedocs"})
    base_cfg.setdefault("markdown_extensions", ["tables", "admonition"])

    # Write config into BUILD_DIR as mkdocs.yml
    gen_cfg_path = BUILD_DIR / "mkdocs.yml"
    gen_cfg_path.parent.mkdir(parents=True, exist_ok=True)
    with gen_cfg_path.open('w', encoding='utf-8') as f:
        yaml.safe_dump(base_cfg, f, sort_keys=False, allow_unicode=True)

    # Run mkdocs build using the generated config (Windows-friendly)
    subprocess.run([sys.executable, "-m", "mkdocs", "build", "--clean"], check=True, cwd=str(BUILD_DIR))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build PG Demo Showcase site")
    parser.add_argument("--offline", action="store_true", help="Build without requiring Docker/Postgres; SQL blocks won't be executed")
    args = parser.parse_args()

    if args.offline:
        print("Offline build: skipping Docker/Postgres startup.")
        build_site(offline=True)
        print(f"Done. Site at {SITE_DIR}")
    else:
        print("Starting Docker (if available) and waiting for Postgres...")
        docker_compose_up()
        ensure_postgres_is_up()
        print("Building site...")
        build_site(offline=False)
        print(f"Done. Site at {SITE_DIR}")

