"""Source-pinned visible-name localization with reviewed per-occurrence forms."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re


def load_name_policy(directory: Path) -> dict:
    path = directory / 'name-localization.json'
    return json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {}


def visible_name_occurrences(text: str, policy: dict) -> list[dict]:
    from translate_ink_gpt import SKILLS_AND_GIFTS
    names = {**policy.get('people', {}), **policy.get('packs', {}), **policy.get('extras', {})}
    if not names:
        return []
    pattern = re.compile(r'(?<!\w)(?:' + '|'.join(re.escape(n) for n in sorted(names, key=len, reverse=True)) + r')(?!\w)')
    excluded = [(m.start(), m.end()) for m in re.finditer(r'<[^<>]*>|\{[^{}]*\}', text)]
    for retained in policy.get('retained_visible', []):
        excluded.extend(m.span() for m in re.finditer(r'(?<!\w)' + re.escape(retained) + r'(?!\w)', text))
    skills = re.compile(r'(?<!\w)(?:' + '|'.join(re.escape(s) for s in
                        sorted(SKILLS_AND_GIFTS, key=len, reverse=True)) + r')(?!\w)')
    excluded.extend(m.span() for m in skills.finditer(text))
    metadata = re.match(r'\s*"?\s*@[A-Za-z][^\s]*', text)
    if metadata:
        excluded.append(metadata.span())
    result = []
    for match in pattern.finditer(text):
        if any(start <= match.start() < end for start, end in excluded):
            continue
        result.append({'start': match.start(), 'end': match.end(), 'english': match[0],
                       'base': names[match[0]],
                       'kind': 'pack' if match[0] in policy.get('packs', {}) else 'person'})
    return result


def digest(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def load_name_forms(directory: Path) -> dict[int, dict]:
    path = directory / 'name-forms.json'
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding='utf-8-sig'))
    if payload.get('format') != 1 or payload.get('reviewed_count') != len(payload['items']):
        raise ValueError('incomplete name-form review metadata')
    records = {int(item['id']): item for item in payload['items']}
    if len(records) != len(payload['items']):
        raise ValueError('duplicate name-form IDs')
    return records


def apply_name_forms(item_id: int, text: str, policy: dict, records: dict[int, dict]) -> str:
    occurrences = visible_name_occurrences(text, policy)
    record = records.get(item_id)
    if not occurrences:
        if record:
            raise ValueError(f'name review has stale ID {item_id}')
        return text
    if record is None:
        raise ValueError(f'missing reviewed name forms at ID {item_id}')
    if record['before_sha256'] != digest(text):
        raise ValueError(f'name review input drift at ID {item_id}')
    forms = record['forms']
    if len(forms) != len(occurrences):
        raise ValueError(f'name review occurrence count drift at ID {item_id}')
    if record.get('english') != [o['english'] for o in occurrences]:
        raise ValueError(f'name review identity/order drift at ID {item_id}')
    for form in forms:
        if (not isinstance(form, str) or not re.search(r'[А-Яа-яЁё]', form)
                or re.search(r'[<>|\n\r"{}]', form)):
            raise ValueError(f'invalid name surface form at ID {item_id}')
    for occurrence, form in reversed(list(zip(occurrences, forms))):
        text = text[:occurrence['start']] + form + text[occurrence['end']:]
    if visible_name_occurrences(text, policy):
        raise ValueError(f'residual visible name at ID {item_id}')
    return text


def canonical_name_story(source, catalog, translations, policy, records, overrides=None,
                         path_restorations=(), fragment_directory=None):
    """Independently reconstruct the expected story for strict all-path QA.

    ``translations`` contains masked RU chunks, NOT strings copied from the
    assembled output under test. Audit records intentionally contain no prose.
    Invalid/missing records fail the audit, even if output happens to match.
    """
    from translate_ink_gpt import unmask_text, replace_strings, walk
    from render_overrides import apply_override, restore_paths
    from renderer_commands import technical_literal_paths

    source_map, used, errors = {}, set(), []
    by_id = {int(item['id']): item for item in catalog}
    for item_id in sorted(set(translations) - set(by_id)):
        errors.append({'id': item_id, 'error': 'translation ID absent from source index'})
    for item_id, item in by_id.items():
        if item_id not in translations:
            errors.append({'id': item_id, 'error': 'missing RU chunk translation'})
            continue
        try:
            before = unmask_text(translations[item_id], item['mask'])
            before = apply_override(item, before, overrides or {})
            after = apply_name_forms(item_id, before, policy, records)
            source_map[item['source']] = item['prefix'] + after
            if item_id in records:
                used.add(item_id)
        except (ValueError, KeyError, TypeError, IndexError) as exc:
            # All validation exceptions from these helpers describe IDs/tokens,
            # never include the source or the translated narrative.
            errors.append({'id': item_id, 'error': str(exc)})
    for item_id in sorted(set(records) - used):
        errors.append({'id': item_id, 'error': 'unconsumed reviewed name ID'})
    expected = replace_strings(source, source_map)
    restored = restore_paths(source, expected, path_restorations)
    technical = restore_technical_literals(source, expected)
    fragments = apply_name_fragments(source, expected, fragment_directory) if fragment_directory else []
    source_ids = {item['source']: int(item['id']) for item in catalog}
    technical_paths = {r['path'] for r in technical_literal_paths(source)}
    slots = sum(len(records[item_id]['forms']) for item_id in used)
    visible_slots = 0
    checked_occurrences = 0
    for path, original in walk(source):
        if isinstance(original, str) and original in source_ids:
            checked_occurrences += 1
            item_id = source_ids[original]
            if path not in technical_paths and item_id in used:
                visible_slots += len(records[item_id]['forms'])
    return expected, {
        'enabled': True, 'registry_ids': len(records), 'consumed_registry_ids': len(used),
        'reviewed_unique_slots': slots, 'visible_occurrence_slots': visible_slots,
        'catalog_occurrences': checked_occurrences,
        'restored_path_count': len(restored), 'restored_technical_literal_count': len(technical),
        'applied_name_fragment_count': len(fragments),
        'errors': errors,
    }


def restore_technical_literals(source, translated):
    from renderer_commands import technical_literal_paths
    changed = []
    for record in technical_literal_paths(source):
        parent = translated
        for key in record['path'][:-1]:
            parent = parent[key]
        if parent[record['path'][-1]] != record['literal']:
            parent[record['path'][-1]] = record['literal']
            changed.append({'path': list(record['path']), 'usage': record['usage']})
    return changed


def load_name_fragments(directory: Path) -> list[dict]:
    path = directory / 'name-fragments.json'
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding='utf-8-sig'))
    if payload.get('format') != 1 or not isinstance(payload.get('items'), list):
        raise ValueError('invalid name-fragment format')
    return payload['items']


def apply_name_fragments(source, assembled, directory: Path) -> list[dict]:
    """Apply reviewed display-only exceptions, never comparison/argument keys.

    Translation is the FULL Ink string including its leading ^. An END-STORY
    literal may contain visible prose, but its command prefix/quotes/markup
    remain immutable. Every other >>> command is excluded from this mechanism.
    """
    from collections import Counter
    from renderer_commands import technical_literal_paths, renderer_contracts
    from translate_ink_gpt import TAG_RE, SKILLS_AND_GIFTS

    technical = {row['path'] for row in technical_literal_paths(source)}
    contracts = renderer_contracts(source)
    policy = load_name_policy(directory)
    seen, pending = set(), []
    for item in load_name_fragments(directory):
        path = tuple(item['path'])
        if not path or path in seen:
            raise ValueError('empty/duplicate name-fragment path')
        seen.add(path)
        original, parent = source, assembled
        try:
            for key in path:
                original = original[key]
            for key in path[:-1]:
                parent = parent[key]
            current = parent[path[-1]]
        except (KeyError, IndexError, TypeError):
            raise ValueError('name-fragment path absent') from None
        if (not isinstance(original, str) or not original.startswith('^')
                or digest(original) != item['source_sha256']):
            raise ValueError('name-fragment source/path drift')
        after = item['translation']
        if (not isinstance(current, str) or not isinstance(after, str) or not after.startswith('^')
                or not isinstance(item.get('reason'), str) or not item['reason'].strip()):
            raise ValueError('invalid name-fragment translation/reason')
        if path in technical:
            raise ValueError('name-fragment cannot change a technical literal')
        if original.startswith('^>>>') and not original.startswith('^>>> END-STORY '):
            raise ValueError('name-fragment cannot change command metadata')
        contract = contracts.get(path)
        if contract:
            kind, expected = contract
            if not (after == expected if kind == 'exact' else after.startswith(expected)):
                raise ValueError('name-fragment renderer contract changed')
        if Counter(TAG_RE.findall(original)) != Counter(TAG_RE.findall(after)):
            raise ValueError('name-fragment markup changed')
        if any(original.count(separator) != after.count(separator) for separator in ('"', '|', '\n')):
            raise ValueError('name-fragment delimiter count changed')
        for skill in SKILLS_AND_GIFTS:
            pattern = r'(?<!\w)' + re.escape(skill) + r'(?!\w)'
            if len(re.findall(pattern, original)) != len(re.findall(pattern, after)):
                raise ValueError('name-fragment skill/Gift title changed')
        if visible_name_occurrences(after.removeprefix('^'), policy):
            raise ValueError('name-fragment retains visible English policy names')
        pending.append((parent, path, original, after))
    # Validation is atomic: no partial tree mutation if any later pin fails.
    audit = []
    for parent, path, original, after in pending:
        parent[path[-1]] = after
        audit.append({'path': list(path), 'source_sha256': digest(original),
                      'translation_sha256': digest(after)})
    return audit
