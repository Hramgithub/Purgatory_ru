#!/usr/bin/env python3
"""Freeze a local, exhaustive contextual editorial review of compiled Ink.

English prose is written ONLY to the explicitly supplied local output directory.
Every visible occurrence, including duplicate IDs and alternative containers, is
retained. Ordered records and Ink control edges are context, not claimed runtime
playthroughs. Each ID has one edit owner; other occurrences remain review context.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from translation_catalog import load_catalog
from translate_ink_gpt import load_json


def digest(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def translations(directory: Path) -> tuple[dict[int, str], dict[int, str]]:
    values, files = {}, {}
    for path in sorted((directory / 'ru').glob('chunk-*.json')):
        for item in load_json(path)['items']:
            item_id = int(item['id'])
            if item_id in values:
                raise ValueError(f'duplicate translation ID {item_id}')
            values[item_id] = item['translation']
            files[item_id] = path.name
    return values, files


def scene_name(path: tuple[Any, ...]) -> str:
    if len(path) >= 3 and path[:2] == ('root', 2):
        return str(path[2])
    return 'global'


def extract_records(story: Any, by_source: dict[str, dict], ru: dict[int, str]) -> list[dict]:
    records = []

    def visit(node: Any, path: tuple[Any, ...]) -> None:
        if isinstance(node, list):
            for index, child in enumerate(node):
                visit(child, path + (index,))
        elif isinstance(node, dict):
            # Preserve condition/evaluation and branches, not only choice text.
            if any(key in node for key in ('*', '->', 'f()', 'x()', 'VAR?', 'CNT?', '^->')):
                records.append({'path': list(path), 'control': node, 'scene': scene_name(path)})
            for key, child in node.items():
                if isinstance(child, (list, dict)):
                    visit(child, path + (key,))
        elif isinstance(node, str) and node.startswith('^'):
            record = {'path': list(path), 'scene': scene_name(path)}
            item = by_source.get(node)
            if item is not None:
                item_id = int(item['id'])
                record.update(id=item_id, en=item.get('masked', item['body']), ru=ru[item_id])
                if item['mask']:
                    record['tokens'] = item['mask']
            else:
                record['context_only_en'] = node
            records.append(record)

    visit(story, ())
    return records


def prepare(source: Path, localization: Path, output: Path, max_chars: int = 60000,
            overlap: int = 8) -> dict:
    if (output / 'manifest.json').exists():
        raise ValueError('review directory already frozen; choose a new output directory')
    story = load_json(source)
    catalog = load_catalog(localization, story)
    ru, files = translations(localization)
    by_id = {int(item['id']): item for item in catalog}
    if set(ru) != set(by_id):
        raise ValueError('translation/catalog IDs differ')
    records = extract_records(story, {item['source']: item for item in catalog}, ru)
    groups: dict[str, list[dict]] = {}
    for record in records:
        groups.setdefault(record['scene'], []).append(record)
    owner, units, occurrences = {}, [], []
    # Stable split by the existing compiled container order. A small overlap makes
    # adjacent text explicit while every primary record occurs exactly once.
    for scene, entries in groups.items():
        start, part = 0, 0
        while start < len(entries):
            end, size = start, 0
            while end < len(entries):
                length = len(json.dumps(entries[end], ensure_ascii=False))
                if end > start and size + length > max_chars:
                    break
                size += length
                end += 1
            part += 1
            safe_scene = re.sub(r'[^A-Za-z0-9_.-]', '_', scene)
            unit_id = f'{safe_scene}-{part:03d}'
            own_ids = []
            for record in entries[start:end]:
                if 'id' in record:
                    item_id = record['id']
                    occurrences.append({'id': item_id, 'path': record['path'], 'unit': unit_id})
                    if item_id not in owner:
                        owner[item_id] = unit_id
                        own_ids.append(item_id)
            view = {
                'format': 1, 'unit': unit_id, 'scene': scene, 'owner_ids': own_ids,
                'policy': {
                    'narration': 'Samira: first-person feminine, past-tense narrative; preserve justified dialogue/UI tense.',
                    'immutable': 'Do not change/reorder tokens, names, skills/Gifts, tags, separators, renderer commands.',
                    'context': 'Ordered compiled containers, not one linear playthrough. Paths/control records distinguish alternative branches. Inspect all duplicate contexts; flag incompatible reuse in notes.',
                    'output': '{unit, reviewed_ids: owner_ids actually checked, context_checked:true only when every record/branch was read, changes:[{id,before,after,reason}], notes:[]}. before/after are exact masked RU. Never claim unread IDs reviewed.',
                },
                'context_before': entries[max(0, start - overlap):start],
                'records': entries[start:end],
                'context_after': entries[end:end + overlap],
            }
            write_json(output / 'units' / f'{unit_id}.json', view)
            units.append({'unit': unit_id, 'scene': scene, 'file': f'units/{unit_id}.json',
                          'owner_ids': own_ids, 'records': end - start,
                          'occurrences': sum('id' in item for item in entries[start:end])})
            start = end
    if set(owner) != set(by_id):
        raise ValueError(f'catalog IDs absent from source traversal: {sorted(set(by_id) - set(owner))}')
    manifest = {
        'format': 1, 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'catalog_items': len(by_id), 'occurrence_count': len(occurrences),
        'record_count': len(records), 'units': units, 'occurrences': occurrences,
        'baseline': {str(item_id): {'sha256': digest(ru[item_id]), 'file': files[item_id],
                                  'owner': owner[item_id]} for item_id in by_id},
    }
    write_json(output / 'manifest.json', manifest)
    print(json.dumps({'units': len(units), 'scenes': len(groups),
                      'ids': len(by_id), 'occurrences': len(occurrences),
                      'scene_units': dict(Counter(unit['scene'] for unit in units))}, indent=2))
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('localization', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--max-chars', type=int, default=60000)
    parser.add_argument('--overlap', type=int, default=8)
    args = parser.parse_args()
    prepare(args.source, args.localization, args.output, args.max_chars, args.overlap)


if __name__ == '__main__':
    main()
