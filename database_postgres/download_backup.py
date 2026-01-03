#!/usr/bin/env python3
"""
Fetch a Postgres dump from the Railway database_postgres service.

Usage (on your machine):
  python database_postgres/download_backup.py

What it does:
- Runs `railway link` (unless --skip-link).
- Streams `pg_dump -F c -Z9` over `railway ssh --service database_postgres -- ...`.
- Saves to ./YYYYMMDD-HHMM.dump by default.

Options:
  --user       Postgres user (default: $PLANEXE_POSTGRES_USER or 'planexe')
  --db         Postgres database (default: $PLANEXE_POSTGRES_DB or 'planexe')
  --skip-link  Skip `railway link` if already linked
  --service    Railway service name (default: database_postgres)
  --output-dir Directory for the dump file (default: current directory)
  --filename   Override dump filename (default: YYYYMMDD-HHMM.dump)
"""

from __future__ import annotations

import argparse
import datetime as _dt
import os
import shutil
import subprocess
from pathlib import Path
import sys


def run(cmd: list[str], **kwargs) -> None:
    """Run a command and raise on failure."""
    result = subprocess.run(cmd, **kwargs)
    if result.returncode != 0:
        raise SystemExit(f"Command failed ({result.returncode}): {' '.join(cmd)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download a Railway Postgres backup.")
    parser.add_argument(
        "--skip-link",
        action="store_true",
        help="Skip running `railway link` (use if already linked).",
    )
    parser.add_argument(
        "--service",
        default="database_postgres",
        help="Railway service name to connect to (default: database_postgres).",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory to write the dump into (default: current directory).",
    )
    parser.add_argument(
        "--filename",
        help="Override dump filename (default: YYYYMMDD-HHMM.dump).",
    )
    parser.add_argument(
        "--user",
        default=os.environ.get("PLANEXE_POSTGRES_USER", "planexe"),
        help="Postgres user (default: $PLANEXE_POSTGRES_USER or 'planexe').",
    )
    parser.add_argument(
        "--db",
        default=os.environ.get("PLANEXE_POSTGRES_DB", "planexe"),
        help="Postgres database (default: $PLANEXE_POSTGRES_DB or 'planexe').",
    )
    args = parser.parse_args()

    if shutil.which("railway") is None:
        raise SystemExit("railway CLI not found in PATH. Install it and try again.")

    if not args.skip_link:
        run(["railway", "link"])

    timestamp = _dt.datetime.now().strftime("%Y%m%d-%H%M")
    filename = args.filename or f"{timestamp}.dump"
    out_path = Path(args.output_dir).expanduser().resolve() / filename
    out_path.parent.mkdir(parents=True, exist_ok=True)

    dump_cmd = [
        "railway",
        "ssh",
        "--service",
        args.service,
        "--",
        "pg_dump",
        "-U",
        args.user,
        "-d",
        args.db,
        "-F",
        "c",
        "-Z9",
    ]

    print(f"Running: {' '.join(dump_cmd)}")
    print(f"Writing to: {out_path}")
    with out_path.open("wb") as out_file:
        run(dump_cmd, stdout=out_file)

    print(f"Backup complete: {out_path}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
