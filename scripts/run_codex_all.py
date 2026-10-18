#!/usr/bin/env python3
"""Run the authenticated Codex translator over a sequential chunk range."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=int, required=True)
    parser.add_argument("--model", default="gpt-5.6-sol")
    parser.add_argument("--effort", default="medium")
    parser.add_argument("--retries", type=int, default=2)
    args = parser.parse_args()

    root = Path.cwd()
    runner = root / "scripts" / "run_codex_chunk.py"
    failures: list[int] = []
    for chunk in range(args.start, args.end + 1):
        output = root / "localization" / "ru" / f"chunk-{chunk:04d}.json"
        if output.exists():
            print(f"[{chunk:04d}/{args.end:04d}] already present", flush=True)
            continue
        success = False
        for attempt in range(1, args.retries + 2):
            print(f"[{chunk:04d}/{args.end:04d}] attempt {attempt}", flush=True)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(runner),
                    str(chunk),
                    "--model",
                    args.model,
                    "--effort",
                    args.effort,
                ],
                cwd=root,
            )
            if completed.returncode == 0 and output.exists():
                success = True
                break
            if attempt <= args.retries:
                time.sleep(5)
        if not success:
            failures.append(chunk)
            print(f"[{chunk:04d}/{args.end:04d}] FAILED", flush=True)
    print(f"Completed range; failures={failures}", flush=True)
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
