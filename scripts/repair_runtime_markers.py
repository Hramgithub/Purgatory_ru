#!/usr/bin/env python3
"""Migrate initial GPT chunks after the in-game parser/font smoke test."""
import json
import re
from pathlib import Path
from renderer_commands import command_arguments

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "localization/catalog.json"
catalog = json.loads(CATALOG.read_text(encoding="utf-8-sig"))
by_id = {item["id"]: item for item in catalog}
story = json.loads((ROOT / "work/english_ink/wod02__resources__67.json").read_text(encoding="utf-8-sig"))
arguments = command_arguments(story)
# These tokens matched the beginning of ordinary English words, not people.
false_names = {443: "⟦T001⟧", 1296: "⟦T004⟧", 2896: "⟦T000⟧",
               4625: "⟦T001⟧", 4632: "⟦T000⟧", 4644: "⟦T000⟧",
               4652: "⟦T002⟧", 4658: "⟦T004⟧", 4661: "⟦T000⟧",
               4753: "⟦T001⟧", 12645: "⟦T000⟧"}
special = {
    1296: ("⟦T004⟧tern Spider", "паук узора"),
    2896: ("⟦T000⟧варя", "января"),
    12645: ("⟦T000⟧h Чистилища", "Путь через Чистилище"),
}
changed = 0
for path in sorted((ROOT / "localization/ru").glob("chunk-*.json")):
    chunk = json.loads(path.read_text(encoding="utf-8-sig"))
    dirty = False
    for entry in chunk["items"]:
        item_id = entry["id"]
        text = entry["translation"]
        source = by_id[item_id]
        command = re.match(r"^(?:HEADER|INFO|SMALL|MARGIN|INV|STYLE [A-Z]+):", source["body"])
        if command:
            text = re.sub(r"^[^:]+:", command[0], text, count=1)
        if source["source"] in arguments:
            text = text.translate(str.maketrans({'«': '"', '»': '"', '“': '"', '”': '"'}))
            if source["body"].rstrip().endswith('"'):
                text = re.sub(r'"([.,!?…]+)(\s*)$', r'\1"\2', text)
            if text.count('"') != source["body"].count('"'):
                raise ValueError(f"Command quote count mismatch for {item_id}: {text!r}")
        if item_id in false_names:
            token = false_names[item_id]
            if token in source["mask"]:
                original = source["mask"].pop(token)
                source["masked"] = source["masked"].replace(token, original)
                if item_id in special:
                    before, after = special[item_id]
                    if before not in text:
                        raise ValueError(f"Unexpected translation for {item_id}")
                    text = text.replace(before, after)
                else:
                    text = text.replace(token, "")
        if item_id in (13782, 13783):
            text = text.replace("участии⟦T003⟧ ", "участии ⟦T003⟧")
            text = text.replace("также хотел услышать", "также хотела услышать")
            if item_id == 13783:
                text = text.replace("Он сказал, что происходящее", "Она сказала, что происходящее")
        if text != entry["translation"]:
            entry["translation"] = text
            dirty = True
            changed += 1
    if dirty:
        path.write_text(json.dumps(chunk, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
CATALOG.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"Repaired {changed} translations")
