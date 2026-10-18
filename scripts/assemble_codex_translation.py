#!/usr/bin/env python3
"""Validate translated Codex chunks and assemble a complete Ink story JSON."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from translate_ink_gpt import load_json, replace_strings, unmask_text  # noqa: E402
from renderer_commands import command_arguments
from translation_catalog import load_catalog


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
                marker = re.match(r"^(?:HEADER|INFO|SMALL|MARGIN|INV|STYLE [A-Z]+):", source_item["body"])
                if marker and not unmasked.startswith(marker[0]):
                    raise ValueError("game renderer command prefix changed")
                if source_item["source"] in arguments and unmasked.count('"') != source_item["body"].count('"'):
                    raise ValueError("game command quote delimiters changed")
                if unmasked.count("|") != source_item["body"].count("|"):
                    raise ValueError("pipe separator count changed")
                if unmasked.count("\n") != source_item["body"].count("\n"):
                    raise ValueError("newline count changed")
                translated[item_id] = source_item["prefix"] + unmasked
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{path.name}: id={entry.get('id')}: {exc}")

    missing = sorted(set(by_id) - set(translated))
    source_map = {by_id[item_id]["source"]: text for item_id, text in translated.items()}
    assembled = replace_strings(story, source_map)
    write_json(args.output, assembled)
    report = {
        "catalog_items": len(catalog),
        "translated_items": len(translated),
        "missing_items": len(missing),
        "missing_id_ranges": id_ranges(missing),
        "errors": errors,
        "complete": not missing and not errors,
    }
    write_json(args.report, report)
    print(json.dumps(report, ensure_ascii=True, indent=2))
    if errors or (missing and not args.allow_incomplete):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
