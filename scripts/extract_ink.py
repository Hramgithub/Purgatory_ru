#!/usr/bin/env python3
"""Extract compiled Ink JSON TextAssets from Purgatory Unity bundles."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import UnityPy


def as_bytes(script: object) -> bytes:
    if isinstance(script, bytes):
        return script
    if isinstance(script, str):
        return script.encode("utf-8")
    return bytes(script)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", type=Path, nargs="+")
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, object]] = []

    input_paths: list[Path] = []
    for input_path in args.inputs:
        if input_path.is_dir():
            input_paths.extend(sorted(input_path.glob("*.hd")))
        else:
            input_paths.append(input_path)

    for bundle_path in input_paths:
        env = UnityPy.load(str(bundle_path))
        for obj in env.objects:
            if obj.type.name != "TextAsset":
                continue
            data = obj.read()
            name = str(data.m_Name)
            raw = as_bytes(data.m_Script)
            record: dict[str, object] = {
                "bundle": bundle_path.name,
                "path_id": obj.path_id,
                "name": name,
                "size": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
            try:
                parsed = json.loads(raw.decode("utf-8-sig"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                parsed = None
            if isinstance(parsed, dict) and "inkVersion" in parsed and "root" in parsed:
                safe_name = "".join(c if c.isalnum() or c in "-_." else "_" for c in name)
                out_name = f"{safe_name}__{bundle_path.stem}__{obj.path_id}.json"
                out_path = args.output_dir / out_name
                out_path.write_bytes(raw)
                record["output"] = out_name
                record["ink_version"] = parsed.get("inkVersion")
            manifest.append(record)

    manifest_path = args.output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    ink_count = sum("output" in item for item in manifest)
    print(f"Scanned {len(manifest)} TextAssets; extracted {ink_count} Ink JSON files.")
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
