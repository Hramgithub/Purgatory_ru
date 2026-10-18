#!/usr/bin/env python3
"""Static QA for the assembled Russian Purgatory Ink localization."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable

from translate_ink_gpt import KNOWN_CHARACTER_NAMES, SKILLS_AND_GIFTS, load_json, walk


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def same_shape(left: Any, right: Any, path: tuple[Any, ...] = ()) -> Iterable[str]:
    if type(left) is not type(right):  # noqa: E721 - exact JSON node type matters
        yield f"{path}: type {type(left).__name__} != {type(right).__name__}"
        return
    if isinstance(left, dict):
        if list(left) != list(right):
            yield f"{path}: dictionary keys/order changed"
            return
        for key in left:
            yield from same_shape(left[key], right[key], path + (key,))
    elif isinstance(left, list):
        if len(left) != len(right):
            yield f"{path}: list length {len(left)} != {len(right)}"
            return
        for index, (left_child, right_child) in enumerate(zip(left, right)):
            yield from same_shape(left_child, right_child, path + (index,))
    elif not isinstance(left, str) and left != right:
        yield f"{path}: non-string value changed"


def count_occurrences(story: Any, term: str) -> int:
    return sum(value.count(term) for _, value in walk(story) if isinstance(value, str))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("translated", type=Path)
    parser.add_argument("localization_dir", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    source = load_json(args.source)
    translated = load_json(args.translated)
    catalog = load_json(args.localization_dir / "catalog.json")
    structural_errors = list(same_shape(source, translated))
    source_by_path = dict(walk(source))
    translated_by_path = dict(walk(translated))

    unchanged: list[dict[str, Any]] = []
    cyrillic_count = 0
    for item in catalog:
        path = tuple(item["first_path"])
        before = source_by_path[path]
        after = translated_by_path[path]
        if before == after:
            unchanged.append({"id": item["id"], "text": item["body"], "path": item["first_path"]})
        if re.search(r"[А-Яа-яЁё]", after):
            cyrillic_count += 1

    protected_mismatches: list[dict[str, Any]] = []
    for term in SKILLS_AND_GIFTS + KNOWN_CHARACTER_NAMES:
        before_count = count_occurrences(source, term)
        after_count = count_occurrences(translated, term)
        if before_count != after_count:
            protected_mismatches.append(
                {"term": term, "source_count": before_count, "translated_count": after_count}
            )

    unresolved_placeholders = [
        {"path": list(path), "text": value}
        for path, value in walk(translated)
        if isinstance(value, str) and re.search(r"⟦T\d{3}⟧", value)
    ]
    marker_present = any(
        value == "^wod02Completed" for _, value in walk(translated) if isinstance(value, str)
    )
    report = {
        "catalog_items": len(catalog),
        "catalog_items_with_cyrillic": cyrillic_count,
        "unchanged_catalog_items": len(unchanged),
        "unchanged_samples": unchanged[:200],
        "protected_term_mismatches": protected_mismatches,
        "unresolved_placeholders": unresolved_placeholders[:200],
        "structural_errors": structural_errors[:200],
        "story_marker_present": marker_present,
        "passed": not structural_errors
        and not protected_mismatches
        and not unresolved_placeholders
        and marker_present,
    }
    write_json(args.report, report)
    print(json.dumps({k: v for k, v in report.items() if k not in {"unchanged_samples"}}, ensure_ascii=True, indent=2))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
