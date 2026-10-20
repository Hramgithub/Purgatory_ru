#!/usr/bin/env python3
"""Append newly covered map labels without renumbering existing translations."""
import argparse
import json
from pathlib import Path
import re

from translate_ink_gpt import load_json, split_visible, walk

TRANSLATIONS = {
    'Talk about: A Sept Divided': 'Обсудить: Раскол в септе',
    'Talk about: Grim Tidings': 'Обсудить: Мрачные вести',
    'Talk about: Urban Unrest': 'Обсудить: Городская тревога',
    'Talk': 'Поговорить',
    'Search': 'Осмотреть',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('localization', type=Path)
    args = parser.parse_args()
    source = load_json(args.source)
    catalog = load_json(args.localization/'catalog.json')
    included = {x['source'] for x in catalog}
    additions, translations = [], []
    for path, value in walk(source):
        if not isinstance(value, str) or value in included or not re.match(r'^\^@[A-Za-z][A-Za-z0-9_-]*\s+', value):
            continue
        split = split_visible(value, False, set())
        if split is None:
            continue
        prefix, body = split
        if body not in TRANSLATIONS:
            raise ValueError('Unreviewed map label at '+str(path)+': '+body)
        record = {'id':len(catalog)+len(additions),'source':value,'prefix':prefix,'body':body,
            'first_path':list(path),'pt_changed':False,'masked':body,'mask':{}}
        additions.append(record)
        translations.append({'id':record['id'],'translation':TRANSLATIONS[body]})
        included.add(value)
    if not additions:
        print('Map labels already indexed; no files changed.')
        return
    if len(additions) != 15:
        raise ValueError('Expected 15 unique labels in the indexed game build')
    chunk = args.localization/'ru/chunk-0064.json'
    if chunk.exists():
        raise ValueError('Preserve an existing chunk 64; append with a new index instead')
    (args.localization/'catalog.json').write_text(json.dumps(catalog+additions,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    chunk.write_text(json.dumps({'chunk':64,'items':translations},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'Appended {len(additions)} map labels; existing IDs unchanged.')


if __name__ == '__main__':
    main()
