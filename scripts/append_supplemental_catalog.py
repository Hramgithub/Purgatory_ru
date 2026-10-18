#!/usr/bin/env python3
"""Append short visible strings missed by the conservative initial heuristic."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from translate_ink_gpt import (
    KNOWN_CHARACTER_NAMES,
    SKILLS_AND_GIFTS,
    collect_character_names,
    load_json,
    mask_text,
    walk,
)


LINK_TERMS = {
    "<link=journalist>Journalist</link>",
    "<link=ahroun>Ahroun</link>",
    "<link=galliard>Galliard</link>",
    "<link=philodox>Philodox</link>",
    "<link=theurge>Theurge</link>",
    "<link=ragabash>Ragabash</link>",
    "<link=cliath>Cliath</link>",
}

INTERNAL_BRANCHES = {
    "werewolf_tooltips",
    "global_tooltips",
    "debug",
    "CS_SET_LIST",
    "NEXT_STORY",
    "CHANGE_SEQUENCE",
    "__getItemString",
}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("localization_dir", type=Path)
    args = parser.parse_args()

    story = load_json(args.source)
    catalog_path = args.localization_dir / "catalog.json"
    catalog = load_json(catalog_path)
    base_count = 12_889
    if len(catalog) < base_count:
        raise ValueError(f"Expected at least {base_count} base items, found {len(catalog)}")
    catalog = catalog[:base_count]
    for old_chunk in (args.localization_dir / "source").glob("chunk-*.json"):
        if int(old_chunk.stem.split("-")[-1]) >= 58:
            old_chunk.unlink()
    included = {item["source"] for item in catalog}
    protected_exact = set(SKILLS_AND_GIFTS)
    protected_names = set(KNOWN_CHARACTER_NAMES + ["Anna Nowak"])
    protected = sorted(
        set(SKILLS_AND_GIFTS + collect_character_names(story) + ["Anna Nowak"]),
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
        stripped = body.strip().strip('“”"').rstrip(".!?")
        if not re.search(r"[A-Za-z]", body):
            continue
        if body in protected_exact or stripped in protected_names:
            continue
        path_names = {part for part in path if isinstance(part, str)}
        if path_names & INTERNAL_BRANCHES:
            continue

        root_table_title = (
            len(path) >= 2
            and path[0] == "root"
            and path[1] == 0
            and body[:1].isupper()
            and "_" not in body
            and not body.startswith(">>>")
        )
        narrative_fragment = (
            len(path) >= 2
            and path[0] == "root"
            and path[1] == 2
            and (
                bool(re.search(r"[.!?…]", body))
                or body in {"and ", " pack. ", " outside.", " zero"}
            )
            and len(body) <= 80
        )
        explicit_link_term = body in LINK_TERMS
        if not (root_table_title or narrative_fragment or explicit_link_term):
            continue
        if body.startswith(("ERROR:", "INFO:", "MARGIN:", "$")):
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
    chunks = [additions[index : index + 240] for index in range(0, len(additions), 240)]
    chunk_files: list[str] = []
    chunk_records: list[dict[str, Any]] = []
    for offset, chunk in enumerate(chunks, 58):
        chunk_path = args.localization_dir / "source" / f"chunk-{offset:04d}.json"
        write_json(
            chunk_path,
            {
                "chunk": offset,
                "item_count": len(chunk),
                "source_chars": sum(len(item["masked"]) for item in chunk),
                "items": [
                    {"id": item["id"], "text": item["masked"], "path": item["first_path"]}
                    for item in chunk
                ],
            },
        )
        chunk_files.append(str(chunk_path))
        chunk_records.append(
            {
                "chunk": offset,
                "file": chunk_path.name,
                "first_id": chunk[0]["id"],
                "last_id": chunk[-1]["id"],
                "item_count": len(chunk),
                "source_chars": sum(len(item["masked"]) for item in chunk),
            }
        )
    manifest_path = args.localization_dir / "manifest.json"
    manifest = load_json(manifest_path)
    manifest["catalog_items"] = len(catalog)
    manifest["source_chars"] = sum(len(item["masked"]) for item in catalog)
    manifest["chunk_count"] = 57 + len(chunks)
    manifest["chunks"] = [item for item in manifest["chunks"] if int(item["chunk"]) <= 57]
    manifest["chunks"].extend(chunk_records)
    write_json(manifest_path, manifest)
    print(json.dumps({"first_chunk": 58, "added": len(additions), "files": chunk_files}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
