#!/usr/bin/env python3
"""Translate Purgatory's compiled Ink JSON with a local Ollama GPT model.

The script is resumable. It only changes human-facing strings prefixed with
``^`` and preserves Ink commands, TMP markup, character names, and gameplay
skill/Gift titles.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Iterable


SKILLS_AND_GIFTS = [
    "Athletics",
    "Stealth",
    "Survival",
    "Animal Ken",
    "Intimidation",
    "Persuasion",
    "Occult",
    "Medicine",
    "Technology",
    "Streets Tell Stories",
    "Doppelganger",
    "Hare's Leap",
    "Curse of Aeolus",
    "Scent of the Past",
    "Blissful Ignorance",
    "Song of Serenity",
    "Geas",
    "Living Ward",
    "Silver Compact",
]

KNOWN_CHARACTER_NAMES = [
    "Samira Rahmani",
    "Andrzej Skarżyński",
    "Helena Zielińska",
    "Miłosz Juskowiak",
    "Samira",
    "Khadija",
    "Ilona",
    "Andrzej",
    "Aleksander",
    "Victoria",
    "Zuzanna",
    "Tariq",
    "Emeryk",
    "Helena",
    "Miłosz",
    "Juskowiak",
    "Olga",
    "Tomasz",
    "Pat",
    "Kim",
    "Lisa",
    "Daniel",
    "Kornel",
    "Bartek",
    "Maia",
    "Agnieszka",
    "Mashal",
    "Nsimire",
    "Jan",
]

SYSTEM_PROMPT = """You are the Russian localization editor for the narrative game
Werewolf: The Apocalypse — Purgatory. Translate each English item into natural,
concise literary Russian. Samira narrates in first person and is a woman, so use
feminine grammatical forms when the speaker is Samira. Preserve tone, profanity,
ambiguity, sentence fragments, punctuation intent, and the exact number of '|'
separators. Never translate, transliterate, alter, remove, duplicate, or reorder
tokens shaped like ⟦T000⟧. Latin-script personal names are already masked.

Use consistent World of Darkness / W5 terminology:
Garou=Гару; Gaia=Гайя; Wyrm=Вирм; Wyld=Вайлд; Weaver=Ткач;
Umbra=Умбра; Bane=Бэйн; fomor=формор; sept=септ; caern=каэрн;
Harano=Харано; Hauglosk=Хауглоск; Rage=Ярость; Willpower=Сила воли;
Breed=Происхождение; Auspice=Судьба; Tribe=Племя; Pack=Стая;
Renown=Принципы; Gift=Дар; Rite=Обряд; Veil=Завеса;
Homid=Хомид; Glabro=Глабро; Crinos=Кринос; Hispo=Хиспо; Lupus=Люпус;
Ragabash=Рагабаш; Theurge=Теург; Philodox=Филодокс;
Galliard=Галлиард; Ahroun=Ахрун;
Black Furies=Чёрные Фурии; Shadow Lords=Повелители Теней;
Glass Walkers=Стеклоходы; Bone Gnawers=Костеглодатели;
Silver Fangs=Серебряные Клыки.

Return one JSON object only, with this exact shape:
{"items":[{"id":0,"translation":"..."}]}
Return exactly one result for every input id, in the same order. Do not add notes."""

TAG_RE = re.compile(r"<[^<>]+>|\{[^{}]+\}|\$[A-Z][A-Z0-9_]*\$")
LINK_NAME_RE = re.compile(r"<link=[^>]+>([^<]+)</link>")
CHARACTER_NAME_RE = re.compile(r"character-name=([^\"]+)")
IDENTIFIER_RE = re.compile(r"[a-z0-9_.\-/]+")
STORY_PREFIX_RE = re.compile(r'^(?P<prefix>\"?\s*@story:[^ ]+\s+)(?P<body>.+)$')


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def walk(value: Any, path: tuple[Any, ...] = ()) -> Iterable[tuple[tuple[Any, ...], Any]]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk(child, path + (key,))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk(child, path + (index,))
    else:
        yield path, value


def collect_character_names(story: Any) -> list[str]:
    names = set(KNOWN_CHARACTER_NAMES)
    for _, value in walk(story):
        if not isinstance(value, str):
            continue
        names.update(match.group(1).strip() for match in CHARACTER_NAME_RE.finditer(value))
    return sorted((name for name in names if name), key=len, reverse=True)


def split_visible(source: str, pt_changed: bool, protected_exact: set[str]) -> tuple[str, str] | None:
    if not source.startswith("^"):
        return None
    body = source[1:]
    if not body.strip() or body in protected_exact:
        return None
    stripped = body.lstrip()
    if stripped.startswith((">>>", "$TAB$", "ERROR:", "DEBUG:")):
        return None
    if "CharacterCreation_" in body:
        return None
    story_match = STORY_PREFIX_RE.match(body)
    if story_match:
        return "^" + story_match.group("prefix"), story_match.group("body")
    if stripped.startswith(("@", '"', "CS_")):
        return None
    if not re.search(r"[A-Za-z]", body):
        return None
    if IDENTIFIER_RE.fullmatch(body) and not pt_changed:
        return None
    if pt_changed:
        return "^", body
    if len(body) >= 12 and (" " in body or re.search(r"[.!?,;:]", body)):
        return "^", body
    return None


def build_catalog(story: Any, reference: Any | None) -> list[dict[str, Any]]:
    reference_by_path = dict(walk(reference)) if reference is not None else {}
    protected_exact = set(SKILLS_AND_GIFTS)
    seen: set[str] = set()
    catalog: list[dict[str, Any]] = []
    for path, value in walk(story):
        if not isinstance(value, str) or value in seen:
            continue
        pt_changed = reference is not None and reference_by_path.get(path) != value
        visible = split_visible(value, pt_changed, protected_exact)
        if visible is None:
            continue
        prefix, body = visible
        seen.add(value)
        catalog.append(
            {
                "id": len(catalog),
                "source": value,
                "prefix": prefix,
                "body": body,
                "first_path": list(path),
                "pt_changed": pt_changed,
            }
        )
    return catalog


def mask_text(text: str, protected: list[str]) -> tuple[str, dict[str, str]]:
    tokens: list[tuple[int, int, str]] = []
    for match in TAG_RE.finditer(text):
        tokens.append((match.start(), match.end(), match.group(0)))
    for phrase in protected:
        start = 0
        while True:
            index = text.find(phrase, start)
            if index < 0:
                break
            tokens.append((index, index + len(phrase), phrase))
            start = index + len(phrase)
    selected: list[tuple[int, int, str]] = []
    for token in sorted(tokens, key=lambda item: (item[0], -(item[1] - item[0]))):
        if selected and token[0] < selected[-1][1]:
            continue
        selected.append(token)
    mapping: dict[str, str] = {}
    chunks: list[str] = []
    cursor = 0
    for index, (start, end, original) in enumerate(selected):
        placeholder = f"⟦T{index:03d}⟧"
        chunks.append(text[cursor:start])
        chunks.append(placeholder)
        mapping[placeholder] = original
        cursor = end
    chunks.append(text[cursor:])
    return "".join(chunks), mapping


def unmask_text(text: str, mapping: dict[str, str]) -> str:
    result = text
    for placeholder, original in mapping.items():
        if result.count(placeholder) != 1:
            raise ValueError(f"placeholder mismatch: {placeholder}")
        result = result.replace(placeholder, original)
    if re.search(r"⟦T\d{3}⟧", result):
        raise ValueError("unexpected placeholder in translation")
    return result


def call_ollama(model: str, items: list[dict[str, Any]], timeout: int) -> dict[int, str]:
    payload = {
        "model": model,
        "stream": False,
        "format": "json",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    {"items": [{"id": item["id"], "text": item["masked"]} for item in items]},
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            },
        ],
        "options": {
            "temperature": 0.1,
            "num_ctx": 16384,
            "num_predict": 8192,
            "top_p": 0.9,
        },
    }
    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/chat",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        result = json.load(response)
    content = result.get("message", {}).get("content", "")
    if not content:
        raise ValueError(f"model returned no content; done_reason={result.get('done_reason')}")
    parsed = json.loads(content)
    output: dict[int, str] = {}
    for entry in parsed.get("items", []):
        output[int(entry["id"])] = str(entry["translation"])
    expected = {int(item["id"]) for item in items}
    if set(output) != expected:
        raise ValueError(f"id mismatch: expected {len(expected)}, got {len(output)}")
    return output


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)


def make_batches(items: list[dict[str, Any]], max_chars: int, max_items: int) -> list[list[dict[str, Any]]]:
    batches: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_chars = 0
    for item in items:
        item_chars = len(item["masked"])
        if current and (current_chars + item_chars > max_chars or len(current) >= max_items):
            batches.append(current)
            current = []
            current_chars = 0
        current.append(item)
        current_chars += item_chars
    if current:
        batches.append(current)
    return batches


def translate_batch_resilient(
    model: str, batch: list[dict[str, Any]], timeout: int, failures: list[dict[str, Any]]
) -> dict[int, str]:
    try:
        return call_ollama(model, batch, timeout)
    except Exception as exc:  # noqa: BLE001 - retry and record model/protocol failures
        if len(batch) == 1:
            failures.append({"id": batch[0]["id"], "error": repr(exc)})
            return {}
        middle = len(batch) // 2
        left = translate_batch_resilient(model, batch[:middle], timeout, failures)
        right = translate_batch_resilient(model, batch[middle:], timeout, failures)
        return {**left, **right}


def replace_strings(value: Any, translations: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {key: replace_strings(child, translations) for key, child in value.items()}
    if isinstance(value, list):
        return [replace_strings(child, translations) for child in value]
    if isinstance(value, str):
        return translations.get(value, value)
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--model", default="gpt-oss:20b")
    parser.add_argument("--max-chars", type=int, default=10_000)
    parser.add_argument("--max-items", type=int, default=80)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--limit-batches", type=int)
    args = parser.parse_args()

    story = load_json(args.source)
    reference = load_json(args.reference) if args.reference else None
    catalog = build_catalog(story, reference)
    atomic_write_json(args.catalog, catalog)

    protected = sorted(
        set(SKILLS_AND_GIFTS + collect_character_names(story)), key=len, reverse=True
    )
    for item in catalog:
        item["masked"], item["mask"] = mask_text(item["body"], protected)

    state: dict[str, str] = {}
    if args.state.exists():
        state = load_json(args.state)
    pending = [item for item in catalog if item["source"] not in state]
    batches = make_batches(pending, args.max_chars, args.max_items)
    if args.limit_batches is not None:
        batches = batches[: args.limit_batches]

    failures: list[dict[str, Any]] = []
    started = time.monotonic()
    for batch_index, batch in enumerate(batches, 1):
        batch_started = time.monotonic()
        outputs = translate_batch_resilient(args.model, batch, args.timeout, failures)
        accepted = 0
        for item in batch:
            translated = outputs.get(item["id"])
            if translated is None:
                continue
            try:
                translated = unmask_text(translated, item["mask"])
                if translated.count("|") != item["body"].count("|"):
                    raise ValueError("pipe separator count changed")
                if translated.count("\n") != item["body"].count("\n"):
                    raise ValueError("newline count changed")
                final = item["prefix"] + translated
                state[item["source"]] = final
                accepted += 1
            except Exception as exc:  # noqa: BLE001
                failures.append({"id": item["id"], "error": repr(exc)})
        atomic_write_json(args.state, state)
        elapsed = time.monotonic() - batch_started
        print(
            f"batch {batch_index}/{len(batches)}: accepted {accepted}/{len(batch)}; "
            f"state={len(state)}/{len(catalog)}; {elapsed:.1f}s",
            flush=True,
        )

    translated_story = replace_strings(story, state)
    atomic_write_json(args.output, translated_story)
    report = {
        "model": args.model,
        "source": str(args.source),
        "source_unique_caret_strings": len(
            {value for _, value in walk(story) if isinstance(value, str) and value.startswith("^")}
        ),
        "catalog_strings": len(catalog),
        "translated_strings": len(state),
        "remaining_strings": len(catalog) - len(state),
        "skill_and_gift_titles_preserved": SKILLS_AND_GIFTS,
        "protected_character_names": collect_character_names(story),
        "failures": failures,
        "elapsed_seconds": round(time.monotonic() - started, 2),
    }
    atomic_write_json(args.report, report)
    print(json.dumps(report, ensure_ascii=True, indent=2), flush=True)
    return 0 if not failures and len(state) == len(catalog) else 2


if __name__ == "__main__":
    raise SystemExit(main())
