#!/usr/bin/env python3
"""Static QA for the assembled Russian Purgatory Ink localization."""

from __future__ import annotations

import argparse
import json
import hashlib
import re
from pathlib import Path
from typing import Any, Iterable

from translate_ink_gpt import KNOWN_CHARACTER_NAMES, SKILLS_AND_GIFTS, load_json, walk
from renderer_commands import command_arguments, contract_errors, technical_literal_paths
from translation_catalog import load_catalog
from render_overrides import load_overrides, apply_override, approved_name_audit
from render_overrides import load_corrections_audit
from render_overrides import load_path_restorations
from translate_ink_gpt import TAG_RE
from collections import Counter
from name_localization import load_name_policy, load_name_forms, canonical_name_story, visible_name_occurrences


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
    pattern = re.compile(r"(?<!\w)" + re.escape(term) + r"(?!\w)")
    return sum(len(pattern.findall(value)) for _, value in walk(story) if isinstance(value, str))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("translated", type=Path)
    parser.add_argument("localization_dir", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    source = load_json(args.source)
    arguments = command_arguments(source)
    translated = load_json(args.translated)
    catalog = load_catalog(args.localization_dir, source)
    overrides = load_overrides(args.localization_dir)
    structural_errors = list(same_shape(source, translated))
    source_by_path = dict(walk(source))
    translated_by_path = dict(walk(translated))
    name_policy = load_name_policy(args.localization_dir)
    name_checks = {'enabled': False, 'errors': []}
    expected_name_story = None
    if name_policy:
        chunk_translations, chunk_errors = {}, []
        for chunk in sorted((args.localization_dir / 'ru').glob('chunk-*.json')):
            try:
                for entry in load_json(chunk)['items']:
                    item_id = int(entry['id'])
                    if item_id in chunk_translations:
                        chunk_errors.append({'id': item_id, 'error': 'duplicate RU chunk ID'})
                    else:
                        chunk_translations[item_id] = entry['translation']
            except (ValueError, KeyError, TypeError, OSError):
                chunk_errors.append({'error': 'unreadable RU chunk', 'chunk': chunk.name})
        expected_name_story, name_checks = canonical_name_story(
            source, catalog, chunk_translations, name_policy, load_name_forms(args.localization_dir),
            overrides, load_path_restorations(args.localization_dir), args.localization_dir)
        name_checks['errors'].extend(chunk_errors)
        technical_paths = {row['path'] for row in technical_literal_paths(source)}
        item_ids = {item['source']: int(item['id']) for item in catalog}
        compared = 0
        for path, expected_text in walk(expected_name_story):
            if not isinstance(expected_text, str):
                continue
            compared += 1
            actual = translated_by_path.get(path)
            item_id = item_ids.get(source_by_path.get(path))
            if actual != expected_text:
                name_checks['errors'].append({
                    'id': item_id, 'path': list(path), 'error': 'canonical assembled text mismatch',
                    'expected_sha256': hashlib.sha256(expected_text.encode()).hexdigest(),
                    'actual_sha256': hashlib.sha256(actual.encode()).hexdigest() if isinstance(actual, str) else None,
                })
            if (item_id is not None and path not in technical_paths and isinstance(actual, str)
                    and visible_name_occurrences(actual.removeprefix('^'), name_policy)):
                name_checks['errors'].append({'id': item_id, 'path': list(path),
                                              'error': 'residual visible English policy name'})
        name_checks['compared_string_occurrences'] = compared
        name_checks['error_count'] = len(name_checks['errors'])
        name_checks['errors'] = name_checks['errors'][:200]

    unchanged: list[dict[str, Any]] = []
    cyrillic_count = 0
    renderer_command_errors = contract_errors(source, translated)
    markup_errors = []
    markup_checked = 0
    by_source = {item['source']: item for item in catalog}
    for path, before in source_by_path.items():
        if not isinstance(before, str) or before not in by_source:
            continue
        item = by_source[before]
        after = translated_by_path.get(path)
        if not isinstance(after, str):
            continue
        # RU may reorder protected tags to fit syntax, but may not invent or
        # remove markup. Reviewed exceptional changes are applied to EN only
        # for calculating the expected tag multiset, never to the game source.
        try:
            expected = apply_override(item, item['body'], overrides)
            if Counter(TAG_RE.findall(after)) != Counter(TAG_RE.findall(expected)):
                raise ValueError('markup differs from source plus approved repair')
        except ValueError as exc:
            markup_errors.append({'id': item['id'], 'path': list(path), 'error': str(exc)})
        markup_checked += 1
    for item in catalog:
        path = tuple(item["first_path"])
        before = source_by_path[path]
        after = translated_by_path[path]
        command = re.match(r"\^?(?:HEADER|INFO|SMALL|MARGIN|INV|STYLE [A-Z]+):", before)
        if command and not after.startswith(command[0]):
            renderer_command_errors.append({"id": item["id"], "command": command[0]})
        if before in arguments and before.count('"') != after.count('"'):
            renderer_command_errors.append({"id": item["id"], "command": "quote delimiters"})
        if before == after:
            unchanged.append({"id": item["id"], "sha256": hashlib.sha256(before.encode()).hexdigest(),
                              "characters": len(before), "path": item["first_path"]})
        if re.search(r"[А-Яа-яЁё]", after):
            cyrillic_count += 1

    protected_mismatches: list[dict[str, Any]] = []
    name_deltas, name_correction_audit = approved_name_audit(source, catalog, overrides,
                                                          load_corrections_audit(args.localization_dir))
    protected_name_counts = []
    for term in SKILLS_AND_GIFTS + KNOWN_CHARACTER_NAMES:
        before_count = count_occurrences(source, term)
        after_count = count_occurrences(translated, term)
        if term in KNOWN_CHARACTER_NAMES and expected_name_story is not None:
            expected_count = count_occurrences(expected_name_story, term)
        else:
            expected_count = before_count + name_deltas.get(term, 0)
        if term in KNOWN_CHARACTER_NAMES and expected_name_story is not None:
            protected_name_counts.append({'term': term, 'source_count': before_count,
                                          'expected_count': expected_count, 'translated_count': after_count,
                                          'allowed_localization_delta': expected_count - before_count})
        if expected_count != after_count:
            protected_mismatches.append(
                {"term": term, "source_count": before_count, "expected_count": expected_count,
                 "translated_count": after_count,
                 "expected_basis": 'reviewed-name-canonical' if term in KNOWN_CHARACTER_NAMES and expected_name_story is not None
                 else 'source-plus-approved-corrections'}
            )
    if name_policy:
        name_checks['protected_name_count_basis'] = 'all-path canonical reconstruction from hash-pinned reviewed forms'
        name_checks['protected_name_counts'] = protected_name_counts

    unresolved_placeholders = [
        {"path": list(path), "sha256": hashlib.sha256(value.encode()).hexdigest(),
         "placeholder_count": len(re.findall(r"⟦T\d{3}⟧", value))}
        for path, value in walk(translated)
        if isinstance(value, str) and re.search(r"⟦T\d{3}⟧", value)
    ]
    marker_present = any(
        value == "^wod02Completed" for _, value in walk(translated) if isinstance(value, str)
    )
    # Contract diagnostics identify source locations without redistributing
    # an exact technical literal which might itself contain game prose.
    for error in renderer_command_errors:
        if 'syntax' in error:
            syntax = error.pop('syntax')
            error['syntax_sha256'] = hashlib.sha256(syntax.encode()).hexdigest()
            error['syntax_characters'] = len(syntax)
    report = {
        "sourceSha256": hashlib.sha256(args.source.read_bytes()).hexdigest(),
        "storySha256": hashlib.sha256(args.translated.read_bytes()).hexdigest(),
        "catalog_items": len(catalog),
        "catalog_items_with_cyrillic": cyrillic_count,
        "unchanged_catalog_items": len(unchanged),
        "unchanged_samples": unchanged[:200],
        "protected_term_mismatches": protected_mismatches,
        "unresolved_placeholders": unresolved_placeholders[:200],
        "structural_errors": structural_errors[:200],
        "renderer_command_errors": renderer_command_errors,
        "technical_literal_checks": dict(Counter(r['usage'] for r in technical_literal_paths(source))),
        "markup_checked_occurrences": markup_checked,
        "markup_errors": markup_errors,
        "render_override_ids": sorted(overrides),
        "approved_name_corrections": name_correction_audit,
        "approved_name_count_deltas": name_deltas,
        "source_corrections_audit": load_corrections_audit(args.localization_dir),
        "name_localization": name_checks,
        "story_marker_present": marker_present,
        "passed": not structural_errors
        and not protected_mismatches
        and not unresolved_placeholders
        and not renderer_command_errors
        and not markup_errors
        and not name_checks.get('error_count', 0)
        and marker_present,
    }
    write_json(args.report, report)
    print(json.dumps({k: v for k, v in report.items() if k not in {"unchanged_samples"}}, ensure_ascii=True, indent=2))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
