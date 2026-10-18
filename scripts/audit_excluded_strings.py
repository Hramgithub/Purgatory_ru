#!/usr/bin/env python3
"""List caret strings excluded by the translation-catalog heuristic."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from translate_ink_gpt import load_json, walk


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("catalog", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    story = load_json(args.source)
    catalog = load_json(args.catalog)
    included = {item["source"] for item in catalog}
    seen: set[str] = set()
    excluded: list[dict[str, object]] = []
    for path, value in walk(story):
        if not isinstance(value, str) or not value.startswith("^") or value in included or value in seen:
            continue
        seen.add(value)
        body = value[1:]
        if re.search(r"[A-Za-z]", body):
            excluded.append({"text": body, "path": list(path), "length": len(body)})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(excluded, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    likely_visible = [
        item
        for item in excluded
        if not re.fullmatch(r"[A-Za-z0-9_.\-/]+", str(item["text"]))
        and not str(item["text"]).lstrip().startswith(("@", '"', ">>>", "$TAB$"))
    ]
    print(
        json.dumps(
            {
                "excluded_with_latin": len(excluded),
                "likely_visible": len(likely_visible),
                "likely_visible_samples": likely_visible[:200],
            },
            ensure_ascii=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
