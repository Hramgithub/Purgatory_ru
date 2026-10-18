"""Rebuild catalog metadata from a user's own game, without publishing EN prose."""
import hashlib
import json
from pathlib import Path


def load_catalog(directory: Path, story):
    catalog = directory / "catalog.json"
    if catalog.exists():
        return json.loads(catalog.read_text(encoding="utf-8-sig"))
    index = json.loads((directory / "index.json").read_text(encoding="utf-8-sig"))
    result = []
    for record in index["items"]:
        source = story
        for key in record["first_path"]:
            source = source[key]
        if hashlib.sha256(source.encode("utf-8")).hexdigest() != record["source_sha256"]:
            raise ValueError(f"Game text differs from the indexed build at id {record['id']}")
        item = dict(record)
        item["source"] = source
        item["body"] = source[len(item["prefix"]):]
        result.append(item)
    return result


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    catalog = json.loads((root / "localization/catalog.json").read_text(encoding="utf-8-sig"))
    items = []
    for item in catalog:
        record = {key: item[key] for key in ("id", "prefix", "first_path", "mask")}
        record["source_sha256"] = hashlib.sha256(item["source"].encode("utf-8")).hexdigest()
        items.append(record)
    (root / "localization/index.json").write_text(
        json.dumps({"format": 1, "items": items}, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(f"Exported index for {len(items)} strings (no English prose)")
