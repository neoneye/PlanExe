#!/usr/bin/env python3
"""
Emit shell exports for host-specific environment needed by the PlanExe containers.
Run once per terminal session, e.g.:
    eval "$(python setup_env.py)"
This avoids manually exporting PLANEXE_OPEN_DIR_SERVER_URL every time.
"""
from __future__ import annotations

import os
import platform
from pathlib import Path


def detect_host_os() -> str:
    system = platform.system().lower()
    if system.startswith("darwin"):
        return "darwin"
    if system.startswith("windows"):
        return "windows"
    return "linux"


def default_open_dir_server_url(host_os: str) -> str:
    if host_os in {"darwin", "windows"}:
        return "http://host.docker.internal:5100"
    return "http://172.17.0.1:5100"


def main() -> None:
    repo_root = Path(__file__).resolve().parent
    run_dir = (repo_root / "run").resolve()

    host_os = detect_host_os()
    open_dir_server_url = os.environ.get("PLANEXE_OPEN_DIR_SERVER_URL", "").strip() or default_open_dir_server_url(host_os)
    host_run_dir = os.environ.get("PLANEXE_HOST_RUN_DIR", "").strip() or str(run_dir)

    exports = {
        "PLANEXE_OPEN_DIR_SERVER_URL": open_dir_server_url,
        "PLANEXE_HOST_RUN_DIR": host_run_dir,
    }

    for key, value in exports.items():
        print(f'export {key}="{value}"')


if __name__ == "__main__":
    main()
