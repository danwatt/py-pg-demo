import argparse
from pathlib import Path

from scripts.fakeseed import seed_fake_data


def main():
    parser = argparse.ArgumentParser(description="Run a fakeseed YAML against a PostgreSQL database")
    parser.add_argument("--db", required=True, help="Target database name")
    parser.add_argument("--file", required=True, help="Path to YAML fakeseed file")
    args = parser.parse_args()

    yaml_path = Path(args.file)
    if not yaml_path.exists():
        raise SystemExit(f"YAML file not found: {yaml_path}")

    yaml_text = yaml_path.read_text(encoding="utf-8")
    msg = seed_fake_data(args.db, yaml_text, offline=False)
    print(msg, end="")


if __name__ == "__main__":
    main()
