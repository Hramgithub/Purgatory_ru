#!/usr/bin/env python3
"""Validate translated Codex chunks and assemble a complete Ink story JSON."""

from __future__ import annotations

import argparse
import json
import hashlib
import re
import sys
from pathlib import Path
from typing import Any
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parent))

from translate_ink_gpt import load_json, replace_strings, unmask_text  # noqa: E402
from renderer_commands import command_arguments, contract_errors
from translation_catalog import load_catalog
from render_overrides import load_overrides, apply_override, approved_name_audit
from render_overrides import load_path_restorations, restore_paths
from render_overrides import load_corrections_audit
from translate_ink_gpt import TAG_RE


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def id_ranges(values: list[int]) -> list[str]:
    if not values:
        return []
    ranges: list[str] = []
    start = previous = values[0]
    for value in values[1:]:
        if value == previous + 1:
            previous = value
            continue
        ranges.append(str(start) if start == previous else f"{start}-{previous}")
        start = previous = value
    ranges.append(str(start) if start == previous else f"{start}-{previous}")
    return ranges


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("localization_dir", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--allow-incomplete", action="store_true")
    args = parser.parse_args()

    story = load_json(args.source)
    arguments = command_arguments(story)
    catalog = load_catalog(args.localization_dir, story)
    by_id = {int(item["id"]): item for item in catalog}
    overrides = load_overrides(args.localization_dir)
    if set(overrides) - set(by_id):
        raise ValueError('render override IDs absent from source index')
    name_deltas, name_audit = approved_name_audit(story, catalog, overrides,
                                                load_corrections_audit(args.localization_dir))
    translated: dict[int, str] = {}
    errors: list[str] = []

    for path in sorted((args.localization_dir / "ru").glob("chunk-*.json")):
        try:
            payload = load_json(path)
            entries = payload.get("items", [])
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{path.name}: unreadable: {exc}")
            continue
        for entry in entries:
            try:
                item_id = int(entry["id"])
                text = str(entry["translation"])
                if item_id in translated:
                    raise ValueError("duplicate id")
                source_item = by_id[item_id]
                unmasked = unmask_text(text, source_item["mask"])
                if Counter(TAG_RE.findall(unmasked)) != Counter(TAG_RE.findall(source_item['body'])):
                    raise ValueError('unapproved markup mutation before renderer repairs')
                marker = re.match(r"^(?:HEADER|INFO|SMALL|MARGIN|INV|STYLE [A-Z]+):", source_item["body"])
                if marker and not unmasked.startswith(marker[0]):
                    raise ValueError("game renderer command prefix changed")
                if source_item["source"] in arguments and unmasked.count('"') != source_item["body"].count('"'):
                    raise ValueError("game command quote delimiters changed")
                if unmasked.count("|") != source_item["body"].count("|"):
                    raise ValueError("pipe separator count changed")
                if unmasked.count("\n") != source_item["body"].count("\n"):
                    raise ValueError("newline count changed")
                unmasked = apply_override(source_item, unmasked, overrides)
                translated[item_id] = source_item["prefix"] + unmasked
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{path.name}: id={entry.get('id')}: {exc}")

    missing = sorted(set(by_id) - set(translated))
    source_map = {by_id[item_id]["source"]: text for item_id, text in translated.items()}
    assembled = replace_strings(story, source_map)
    restored = restore_paths(story, assembled, load_path_restorations(args.localization_dir))
    syntax_errors = contract_errors(story, assembled)
    errors.extend(f'renderer contract: {error}' for error in syntax_errors)
    write_json(args.output, assembled)
    report = {
        "sourceSha256": hashlib.sha256(args.source.read_bytes()).hexdigest(),
        "storySha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
        "catalog_items": len(catalog),
        "translated_items": len(translated),
        "missing_items": len(missing),
        "missing_id_ranges": id_ranges(missing),
        "errors": errors,
        "complete": not missing and not errors,
        "render_override_ids": sorted(overrides),
        "approved_name_corrections": name_audit,
        "approved_name_count_deltas": name_deltas,
        "path_restorations": restored,
        "source_corrections_audit": load_corrections_audit(args.localization_dir),
    }
    write_json(args.report, report)
    print(json.dumps(report, ensure_ascii=True, indent=2))
    if errors or (missing and not args.allow_incomplete):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
