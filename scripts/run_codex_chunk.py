#!/usr/bin/env python3
"""Translate one prepared chunk through authenticated Codex CLI structured output."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


GLOSSARY = """Garou=Гару; Gaia=Гайя; Wyrm=Вирм; Wyld=Вайлд; Weaver=Ткач;
Umbra=Умбра; Bane=Бэйн; fomor=формор; sept=септ; caern=каэрн;
Harano=Харано; Hauglosk=Хауглоск; Rage=Ярость; Willpower=Сила воли;
Breed=Происхождение; Auspice=Судьба; Tribe=Племя; Pack=Стая;
Renown=Принципы; Gift=Дар; Rite=Обряд; Veil=Завеса;
Homid=Хомид; Glabro=Глабро; Crinos=Кринос; Hispo=Хиспо; Lupus=Люпус;
Ragabash=Рагабаш; Theurge=Теург; Philodox=Филодокс;
Galliard=Галлиард; Ahroun=Ахрун; Black Furies=Чёрные Фурии;
Shadow Lords=Повелители Теней; Glass Walkers=Стеклоходы;
Bone Gnawers=Костегрызы; Silver Fangs=Серебряные Клыки."""

PROTECTED_NAMES = """Samira Rahmani, Khadija, Ilona, Andrzej Skarżyński,
Aleksander, Victoria, Zuzanna, Tariq, Emeryk, Helena Zielińska,
Miłosz Juskowiak, Olga, Tomasz, Pat, Kim, Lisa, Daniel, Kornel, Bartek,
Maia, Agnieszka, Mashal, Nsimire, Jan, Mourning Wolf, Winter Weasel,
Arcane Lynx, Immortal Peacock, Baleful Otter, Wolf-father, Scavenger,
Granica, VX."""

PROTECTED_SKILLS = """Athletics, Stealth, Survival, Animal Ken,
Intimidation, Persuasion, Occult, Medicine, Technology, Streets Tell Stories,
Doppelganger, Hare's Leap, Curse of Aeolus, Scent of the Past,
Blissful Ignorance, Song of Serenity, Geas, Living Ward, Silver Compact."""


def prompt_for(source: Path, chunk: int, item_count: int) -> str:
    return f"""Translate the game-localization chunk in {source.as_posix()} from English to Russian.
This is narrative and UI text for Werewolf: The Apocalypse — Purgatory.
Return JSON matching the supplied schema: chunk={chunk}, exactly {item_count} items,
the same ids in the same order, and only id plus translation for each item.

Rules:
- Natural literary Russian, concise enough for game UI. Preserve tone, ambiguity,
  profanity, fragments, punctuation intent, and first-person feminine grammar for Samira.
- Never alter, translate, remove, duplicate, or reorder placeholders like ⟦T000⟧.
- Preserve the exact count and positions of | separators and newlines.
- Keep renderer prefixes HEADER:, INFO:, STYLE TUTORIAL:, STYLE TUTORIALHEADER:,
  SMALL:, MARGIN: and INV: exactly as written; translate only their content.
- Preserve ASCII double-quote delimiters in command arguments; never convert them to guillemets.
- Personal, pack, spirit, and company names stay exactly as written in Latin/Polish.
- Render geographical names in their conventional Russian forms: Poland=Польша,
  Warsaw=Варшава, Białowieża Forest=Беловежская пуща, Białystok=Белосток,
  Narew=Нарев, Vistula=Висла. Preserve Polish spellings inside pronunciation entries.
- Do not translate protected skill or Gift titles when they occur in text.
- Translate story, dialogue, descriptions, clue titles, ordinary item titles, and UI labels.
- Do not add notes or explanations.

Locked terminology:
{GLOSSARY}

Protected names:
{PROTECTED_NAMES}

Protected skill and Gift titles:
{PROTECTED_SKILLS}

Read only the specified source chunk. Do not edit workspace files."""


def validate_output(output: Path, chunk: int, expected_ids: list[int]) -> bool:
    try:
        translated = json.loads(output.read_text(encoding="utf-8"))
        actual_ids = [int(item["id"]) for item in translated.get("items", [])]
        return translated.get("chunk") == chunk and actual_ids == expected_ids
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("chunk", type=int)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--model", default="gpt-5.6-sol")
    parser.add_argument("--effort", default="medium")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    root = args.root.resolve()
    source = root / "localization" / "source" / f"chunk-{args.chunk:04d}.json"
    output = root / "localization" / "ru" / f"chunk-{args.chunk:04d}.json"
    schema = root / "localization" / "translation-output.schema.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    expected_ids = [int(item["id"]) for item in payload["items"]]
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and not args.force:
        if validate_output(output, args.chunk, expected_ids):
            print(f"Chunk {args.chunk:04d} already exists and is valid; skipping.")
            return 0
        print(f"Chunk {args.chunk:04d} exists but is invalid; use --force.", file=sys.stderr)
        return 2

    command = [
        "codex",
        "exec",
        "--ephemeral",
        "--sandbox",
        "read-only",
        "--model",
        args.model,
        "--config",
        f'model_reasoning_effort="{args.effort}"',
        "--output-schema",
        str(schema),
        "--output-last-message",
        str(output),
        "--cd",
        str(root),
        prompt_for(source.relative_to(root), args.chunk, int(payload["item_count"])),
    ]
    completed = subprocess.run(
        command,
        cwd=root,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    log_dir = root / "work" / "codex_runs"
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / f"chunk-{args.chunk:04d}.stdout.log").write_text(
        completed.stdout, encoding="utf-8"
    )
    (log_dir / f"chunk-{args.chunk:04d}.stderr.log").write_text(
        completed.stderr, encoding="utf-8"
    )
    if completed.returncode != 0:
        print(completed.stderr[-4000:], file=sys.stderr)
        return completed.returncode
    translated = json.loads(output.read_text(encoding="utf-8"))
    actual_ids = [int(item["id"]) for item in translated.get("items", [])]
    if translated.get("chunk") != args.chunk or actual_ids != expected_ids:
        print("Structured output has the wrong chunk number or id sequence.", file=sys.stderr)
        return 2
    print(f"Translated chunk {args.chunk:04d}: {len(actual_ids)} items -> {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
