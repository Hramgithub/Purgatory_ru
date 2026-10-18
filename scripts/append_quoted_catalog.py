#!/usr/bin/env python3
"""Append visible quoted Ink text that the conservative base filter skipped."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from translate_ink_gpt import (
    SKILLS_AND_GIFTS,
    collect_character_names,
    load_json,
    mask_text,
    walk,
)


EXTRA_NAMES = ["Kazim", "Sarah Johnson", "Maryam Ebrahimi", "Anna Nowak"]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def internal_quoted(body: str, path: tuple[Any, ...]) -> bool:
    path_names = {part for part in path if isinstance(part, str)}
    if path_names & {"CS_SIMPLE", "CS_INCREASE_LIST"}:
        return True
    content = body.strip().lstrip('"“').rstrip('"”').strip()
    if not content:
        return True
    if "CharacterCreation_" in content or content.startswith("Fill_"):
        return True
    if re.fullmatch(r"(?:true|false|\d+)(?:\|(?:true|false|\d+))*", content, re.I):
        return True
    skill_parts = [part.strip() for part in content.split("|")]
    normalized_parts = [part.removeprefix("The ") for part in skill_parts]
    if len(skill_parts) > 1 and all(part in SKILLS_AND_GIFTS for part in normalized_parts):
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("localization_dir", type=Path)
    args = parser.parse_args()

    story = load_json(args.source)
    catalog_path = args.localization_dir / "catalog.json"
    catalog = load_json(catalog_path)
    included = {item["source"] for item in catalog}
    protected = sorted(
        set(SKILLS_AND_GIFTS + collect_character_names(story) + EXTRA_NAMES),
        key=len,
        reverse=True,
    )
    additions: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path, value in walk(story):
        if not isinstance(value, str) or not value.startswith("^") or value in included or value in seen:
            continue
        seen.add(value)
        body = value[1:]
        if not body.lstrip().startswith(('"', "“")) or not re.search(r"[A-Za-z]", body):
            continue
        if internal_quoted(body, path):
            continue
        masked, mask = mask_text(body, protected)
        additions.append(
            {
                "id": len(catalog) + len(additions),
                "source": value,
                "prefix": "^",
                "body": body,
                "first_path": list(path),
                "pt_changed": False,
                "masked": masked,
                "mask": mask,
            }
        )

    catalog.extend(additions)
    write_json(catalog_path, catalog)
    existing_chunks = sorted((args.localization_dir / "source").glob("chunk-*.json"))
    next_chunk = max(int(path.stem.split("-")[-1]) for path in existing_chunks) + 1
    chunks: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_chars = 0
    for item in additions:
        size = len(item["masked"])
        if current and (len(current) >= 200 or current_chars + size > 24_000):
            chunks.append(current)
            current = []
            current_chars = 0
        current.append(item)
        current_chars += size
    if current:
        chunks.append(current)

    manifest_path = args.localization_dir / "manifest.json"
    manifest = load_json(manifest_path)
    for offset, chunk in enumerate(chunks, next_chunk):
        chunk_path = args.localization_dir / "source" / f"chunk-{offset:04d}.json"
        chars = sum(len(item["masked"]) for item in chunk)
        write_json(
            chunk_path,
            {
                "chunk": offset,
                "item_count": len(chunk),
                "source_chars": chars,
                "items": [
                    {"id": item["id"], "text": item["masked"], "path": item["first_path"]}
                    for item in chunk
                ],
            },
        )
        manifest["chunks"].append(
            {
                "chunk": offset,
                "file": chunk_path.name,
                "first_id": chunk[0]["id"],
                "last_id": chunk[-1]["id"],
                "item_count": len(chunk),
                "source_chars": chars,
            }
        )
    manifest["catalog_items"] = len(catalog)
    manifest["source_chars"] = sum(len(item["masked"]) for item in catalog)
    manifest["chunk_count"] = len(manifest["chunks"])
    write_json(manifest_path, manifest)
    print(
        json.dumps(
            {
                "added": len(additions),
                "first_chunk": next_chunk,
                "last_chunk": next_chunk + len(chunks) - 1,
                "catalog_items": len(catalog),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
