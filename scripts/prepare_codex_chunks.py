#!/usr/bin/env python3
"""Prepare stable, reviewable chunks for a human/Codex Russian translation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from translate_ink_gpt import (  # noqa: E402
    SKILLS_AND_GIFTS,
    build_catalog,
    collect_character_names,
    load_json,
    mask_text,
)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--max-chars", type=int, default=24_000)
    parser.add_argument("--max-items", type=int, default=240)
    args = parser.parse_args()

    story = load_json(args.source)
    reference = load_json(args.reference) if args.reference else None
    catalog = build_catalog(story, reference)
    protected = sorted(
        set(SKILLS_AND_GIFTS + collect_character_names(story)), key=len, reverse=True
    )

    for item in catalog:
        item["masked"], item["mask"] = mask_text(item["body"], protected)

    chunks: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_chars = 0
    for item in catalog:
        size = len(item["masked"])
        if current and (current_chars + size > args.max_chars or len(current) >= args.max_items):
            chunks.append(current)
            current = []
            current_chars = 0
        current.append(item)
        current_chars += size
    if current:
        chunks.append(current)

    source_dir = args.output_dir / "source"
    for old_file in source_dir.glob("chunk-*.json") if source_dir.exists() else []:
        old_file.unlink()
    chunk_manifest: list[dict[str, Any]] = []
    for index, chunk in enumerate(chunks, 1):
        filename = f"chunk-{index:04d}.json"
        payload = {
            "chunk": index,
            "item_count": len(chunk),
            "source_chars": sum(len(item["masked"]) for item in chunk),
            "items": [
                {
                    "id": item["id"],
                    "text": item["masked"],
                    "path": item["first_path"],
                }
                for item in chunk
            ],
        }
        write_json(source_dir / filename, payload)
        chunk_manifest.append(
            {
                "chunk": index,
                "file": filename,
                "first_id": chunk[0]["id"],
                "last_id": chunk[-1]["id"],
                "item_count": len(chunk),
                "source_chars": payload["source_chars"],
            }
        )

    write_json(args.output_dir / "catalog.json", catalog)
    manifest = {
        "source": str(args.source),
        "reference": str(args.reference) if args.reference else None,
        "catalog_items": len(catalog),
        "source_chars": sum(len(item["masked"]) for item in catalog),
        "chunk_count": len(chunks),
        "max_chars": args.max_chars,
        "max_items": args.max_items,
        "protected_skills_and_gifts": SKILLS_AND_GIFTS,
        "protected_character_names": collect_character_names(story),
        "chunks": chunk_manifest,
    }
    write_json(args.output_dir / "manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
