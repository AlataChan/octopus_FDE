#!/usr/bin/env python3
"""Smoke test Hiagent TOP auth with CheckAppByName.

Reads `.env` from the repository root. Never prints AK/SK or signatures.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from loom.runtimes.hiagent.api_client import HiagentAPIClient, HiagentAPIError


def _load_env(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key, value.strip().strip('"').strip("'"))


def main() -> int:
    _load_env(Path(".env"))
    try:
        client = HiagentAPIClient.from_env()
        duplicated = client.check_app_by_name("loom-smoke-test")
    except HiagentAPIError as e:
        print(f"FAIL CheckAppByName: {e}", file=sys.stderr)
        debug = getattr(e, "debug", None)
        if debug is not None:
            print(debug, file=sys.stderr)
        return 1
    print(
        "OK CheckAppByName "
        f"base_url={client.base_url} service={client.service} "
        f"region={client.region} Reduplicated={duplicated}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
