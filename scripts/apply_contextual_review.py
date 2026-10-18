#!/usr/bin/env python3
"""Validate actual contextual editor receipts; optionally apply sparse RU edits.

Default is validation only and requires full coverage. --allow-partial permits
honest progress reports, never marks a partial review complete. English prose,
before/after text, and runtime source paths are omitted from the public report.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import re

from prepare_contextual_review import digest, translations, write_json
from renderer_commands import command_arguments
from translation_catalog import load_catalog
from translate_ink_gpt import TAG_RE, load_json, unmask_text


TOKEN_RE = re.compile(r'⟦T\d{3}⟧')
ENTRY_RE = re.compile(r'("id"\s*:\s*(\d+)\s*,\s*"translation"\s*:\s*)("(?:[^"\\]|\\.)*")')
MARKER_RE = re.compile(r'^(?:HEADER|INFO|SMALL|MARGIN|INV|STYLE [A-Z]+):')


def check_change(item: dict, before: str, after: str, arguments: set[str]) -> None:
    if not isinstance(after, str) or not after.strip():
        raise ValueError('empty/non-string replacement')
    if TOKEN_RE.findall(before) != TOKEN_RE.findall(after):
        raise ValueError('protected placeholder sequence changed')
    plain = unmask_text(after, item['mask'])
    original = unmask_text(before, item['mask'])
    if TAG_RE.findall(original) != TAG_RE.findall(plain):
        raise ValueError('markup sequence changed')
    for separator in ('|', '\n'):
        if before.count(separator) != after.count(separator):
            raise ValueError(f'separator {separator!r} count changed')
    marker = MARKER_RE.match(item['body'])
    if marker and not plain.startswith(marker[0]):
        raise ValueError('renderer marker changed')
    if item['source'] in arguments and plain.count('"') != item['body'].count('"'):
        raise ValueError('renderer ASCII quote delimiters changed')


def replace_translation_spans(data: bytes, changes: dict[int, tuple[str, str]]) -> bytes:
    """Change JSON string spans only, preserving whitespace, BOM and line ends."""
    bom = data.startswith(b'\xef\xbb\xbf')
    text = data.decode('utf-8-sig')
    spans, found = [], set()
    for match in ENTRY_RE.finditer(text):
        item_id = int(match[2])
        if item_id not in changes:
            continue
        if item_id in found:
            raise ValueError(f'duplicate serialized ID {item_id}')
        before, after = changes[item_id]
        if json.loads(match[3]) != before:
            raise ValueError(f'serialized before mismatch for ID {item_id}')
        found.add(item_id)
        spans.append((match.start(3), match.end(3), json.dumps(after, ensure_ascii=False)))
    if found != set(changes):
        raise ValueError(f'cannot locate serialized IDs {sorted(set(changes) - found)}')
    for start, end, replacement in reversed(spans):
        text = text[:start] + replacement + text[end:]
    return (b'\xef\xbb\xbf' if bom else b'') + text.encode('utf-8')


def apply_review(source: Path, localization: Path, review_root: Path, report_path: Path,
                 apply: bool = False, allow_partial: bool = False) -> dict:
    manifest = load_json(review_root / 'manifest.json')
    source_hash = __import__('hashlib').sha256(source.read_bytes()).hexdigest()
    if source_hash != manifest['source_sha256']:
        raise ValueError('source changed after contextual review preparation')
    story = load_json(source)
    by_id = {int(item['id']): item for item in load_catalog(localization, story)}
    current, files = translations(localization)
    baseline = {int(key): value for key, value in manifest['baseline'].items()}
    if set(current) != set(baseline):
        raise ValueError('current IDs differ from frozen review')
    for item_id, record in baseline.items():
        if digest(current[item_id]) != record['sha256'] or files[item_id] != record['file']:
            raise ValueError(f'localization drift after preparation at ID {item_id}')
    arguments = command_arguments(story)
    units = {unit['unit']: unit for unit in manifest['units']}
    seen_units, context_units, checked, changes, errors, notes = set(), set(), set(), {}, [], []
    for path in sorted((review_root / 'reviews').glob('*.json')):
        payload = load_json(path)
        receipts = payload if isinstance(payload, list) else [payload]
        for receipt in receipts:
            unit_id = receipt.get('unit')
            try:
                if unit_id not in units:
                    raise ValueError('unknown unit')
                if unit_id in seen_units:
                    raise ValueError('duplicate unit receipt')
                seen_units.add(unit_id)
                if receipt.get('context_checked') is True:
                    context_units.add(unit_id)
                owner_ids = set(units[unit_id]['owner_ids'])
                reviewed_list = receipt['reviewed_ids']
                reviewed = set(reviewed_list)
                if len(reviewed_list) != len(reviewed) or not reviewed <= owner_ids:
                    raise ValueError('reviewed IDs duplicate or owned by another unit')
                if checked & reviewed:
                    raise ValueError('duplicate reviewed IDs')
                checked.update(reviewed)
                for change in receipt.get('changes', []):
                    item_id = change['id']
                    if item_id not in reviewed:
                        raise ValueError(f'changed ID {item_id} not reviewed/owned')
                    if item_id in changes:
                        raise ValueError(f'conflicting edits at ID {item_id}')
                    if change['before'] != current[item_id]:
                        raise ValueError(f'expected-before mismatch at ID {item_id}')
                    if not isinstance(change.get('reason'), str) or not change['reason'].strip():
                        raise ValueError(f'no editorial reason at ID {item_id}')
                    if change['before'] == change['after']:
                        raise ValueError(f'no-op change at ID {item_id}')
                    try:
                        check_change(by_id[item_id], change['before'], change['after'], arguments)
                    except ValueError as exc:
                        raise ValueError(f'ID {item_id}: {exc}') from exc
                    changes[item_id] = change
                notes.extend({'unit': unit_id, 'note': note} for note in receipt.get('notes', []))
            except (KeyError, TypeError, ValueError) as exc:
                errors.append(f'{path.name}/{unit_id}: {exc}')
    missing = sorted(set(baseline) - checked)
    required_context = {unit['unit'] for unit in units.values() if unit['occurrences']}
    missing_context = sorted(required_context - context_units)
    checked_occurrences = sum(unit['occurrences'] for unit in units.values()
                              if unit['unit'] in context_units)
    report = {
        'format': 1, 'source_sha256': source_hash,
        'catalog_items': len(baseline), 'source_occurrences': manifest['occurrence_count'],
        'context_units': len(units), 'submitted_units': len(seen_units),
        'reviewed_ids': sorted(checked), 'reviewed_count': len(checked),
        'context_checked_units': sorted(context_units),
        'context_checked_occurrences': checked_occurrences,
        'missing_context_units': missing_context,
        'missing_ids': missing, 'missing_count': len(missing),
        'changes': [{'id': item_id, 'before_sha256': digest(change['before']),
                     'after_sha256': digest(change['after']), 'reason': change['reason']}
                    for item_id, change in sorted(changes.items())],
        'changed_count': len(changes), 'errors': errors,
        'complete': not errors and not missing and not missing_context, 'applied': False,
        # Notes stay local; report only their count to avoid source prose leaks.
        'local_note_count': len(notes),
    }
    write_json(report_path, report)
    if errors or ((missing or missing_context) and not allow_partial):
        raise ValueError(f'review not accepted: {len(errors)} errors, {len(missing)} unchecked IDs, {len(missing_context)} unread context units; see {report_path}')
    if apply:
        grouped = defaultdict(dict)
        for item_id, change in changes.items():
            grouped[files[item_id]][item_id] = (change['before'], change['after'])
        prepared = {}
        for filename, replacements in grouped.items():
            path = localization / 'ru' / filename
            prepared[path] = replace_translation_spans(path.read_bytes(), replacements)
        for path, data in prepared.items():
            backup = review_root / 'backups' / path.name
            if backup.exists():
                raise ValueError(f'backup already exists: {backup}; do not reapply a frozen review')
        for path, data in prepared.items():
            backup = review_root / 'backups' / path.name
            backup.parent.mkdir(parents=True, exist_ok=True)
            backup.write_bytes(path.read_bytes())
            temporary = path.with_suffix(path.suffix + '.editorial.tmp')
            temporary.write_bytes(data)
            temporary.replace(path)
        report['applied'] = True
        write_json(report_path, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('localization', type=Path)
    parser.add_argument('review_root', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--allow-partial', action='store_true')
    args = parser.parse_args()
    report = apply_review(args.source, args.localization, args.review_root, args.report,
                          args.apply, args.allow_partial)
    print(json.dumps({key: value for key, value in report.items()
                      if key not in ('reviewed_ids', 'missing_ids', 'changes')}, indent=2))


if __name__ == '__main__':
    main()
