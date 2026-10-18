"""Narrow, source-hash-pinned renderer repairs, independent of English catalog.

Only the reviewed tag profile/delta is allowed. All prose and immutable names
remain in the RU chunks; this file and the allowlist contain no game narrative.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from translate_ink_gpt import TAG_RE
from translate_ink_gpt import walk
from collections import Counter


def load_overrides(directory: Path) -> dict[int, dict]:
    path = directory / 'render_overrides.json'
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    if data['format'] != 1:
        raise ValueError('unsupported render override format')
    result = {}
    for item in data['items']:
        item_id = item['id']
        if item_id in result:
            raise ValueError(f'duplicate render override {item_id}')
        if not item.get('reason') or not re.fullmatch(r'[0-9a-f]{64}', item['source_sha256']):
            raise ValueError(f'invalid render override metadata {item_id}')
        result[item_id] = item
    return result


def load_path_restorations(directory: Path) -> list[dict]:
    path = directory / 'render_overrides.json'
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding='utf-8-sig')).get('path_restorations', [])


def load_corrections_audit(directory: Path) -> list[dict]:
    path = directory / 'render_overrides.json'
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding='utf-8-sig')).get('source_corrections_audit', [])


def restore_paths(source, translated, restorations):
    audit, seen = [], set()
    for repair in restorations:
        path = tuple(repair['path'])
        if path in seen:
            raise ValueError('duplicate path restoration')
        seen.add(path)
        before, parent = source, translated
        for key in path:
            before = before[key]
        if (before != repair['expected'] or
                hashlib.sha256(before.encode('utf-8')).hexdigest() != repair['source_sha256']):
            raise ValueError(f'path restoration source drift at ID {repair["id"]}')
        for key in path[:-1]:
            parent = parent[key]
        parent[path[-1]] = before
        audit.append({'id': repair['id'], 'path': list(path), 'reason': repair['reason']})
    return audit


def apply_override(item: dict, text: str, overrides: dict[int, dict]) -> str:
    repair = overrides.get(int(item['id']))
    if repair is None:
        return text
    digest = hashlib.sha256(item['source'].encode('utf-8')).hexdigest()
    if digest != repair['source_sha256']:
        raise ValueError(f'render override source drift at ID {item["id"]}')
    if TAG_RE.findall(text) != repair['before_tags']:
        raise ValueError(f'render override input tags drift at ID {item["id"]}')
    for operation in repair['operations']:
        kind = operation['kind']
        if kind == 'replace_tag':
            tags = list(TAG_RE.finditer(text))
            tag = tags[operation['index']]
            if tag[0] != operation['before']:
                raise ValueError('override expected tag mismatch')
            text = text[:tag.start()] + operation['after'] + text[tag.end():]
        elif kind == 'repair_malformed_b':
            # Do not match the existing, valid </b> elsewhere in this line.
            text, count = re.subn(r'</b(?!>)', '</b>', text)
            if count != 1:
                raise ValueError('expected one malformed bold closer')
        elif kind == 'append_closer':
            if operation['tag'] not in ('</b>', '</link>'):
                raise ValueError('unapproved appended tag')
            text = text.rstrip() + operation['tag'] + text[len(text.rstrip()):]
        elif kind == 'proper_name':
            if item['mask'].get(operation['token']) != operation['before']:
                raise ValueError('override protected token mapping changed')
            pattern = r'(?<!\w)' + re.escape(operation['before']) + r'(?!\w)'
            text, count = re.subn(pattern, operation['after'], text)
            if count != 1:
                raise ValueError('expected exactly one approved name token')
        elif kind == 'replace_literal':
            if text != operation['before']:
                raise ValueError('literal repair expected entire exact old text')
            text = operation['after']
        else:
            raise ValueError(f'unknown render override operation {kind}')
    if TAG_RE.findall(text) != repair['after_tags']:
        raise ValueError(f'render override output tags mismatch at ID {item["id"]}')
    return text


def approved_name_audit(story, catalog, overrides, plaintext_corrections=()):
    by_id = {int(item['id']): item for item in catalog}
    occurrences = Counter(value for _, value in walk(story) if isinstance(value, str))
    deltas, audit = Counter(), []
    for item_id, repair in overrides.items():
        for operation in repair['operations']:
            if operation['kind'] != 'proper_name':
                continue
            item = by_id[item_id]
            apply_override(item, item['body'], overrides)  # verify hash/token/profile
            count = occurrences[item['source']]
            deltas[operation['before']] -= count
            deltas[operation['after']] += count
            audit.append({'id': item_id, 'before': operation['before'],
                          'after': operation['after'], 'occurrences': count,
                          'reason': repair['reason']})
    for repair in plaintext_corrections:
        if repair['kind'] != 'plaintext-name':
            continue
        item = by_id[repair['id']]
        if hashlib.sha256(item['source'].encode('utf-8')).hexdigest() != repair['source_sha256']:
            raise ValueError('plaintext name correction source drift')
        pattern = r'(?<!\w)' + re.escape(repair['before']) + r'(?!\w)'
        if len(re.findall(pattern, item['body'])) != 1:
            raise ValueError('plaintext name correction expected one literal')
        count = occurrences[item['source']]
        deltas[repair['before']] -= count
        deltas[repair['after']] += count
        audit.append({'id': repair['id'], 'before': repair['before'], 'after': repair['after'],
                      'occurrences': count, 'reason': repair['reason'], 'application': 'editorial-receipt'})
    return dict(deltas), audit


def validate_tags(item: dict, original: str, translated: str, overrides: dict[int, dict]) -> None:
    # Original author's malformed tag sequences are the baseline; only the
    # hash-pinned deltas above may differ. Translation must not add other tags.
    if TAG_RE.findall(original) != TAG_RE.findall(translated):
        raise ValueError('unapproved markup sequence change')
    apply_override(item, translated, overrides)
