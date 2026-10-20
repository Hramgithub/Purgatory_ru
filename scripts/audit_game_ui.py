#!/usr/bin/env python3
"""Read-only inventory of serialized UI strings outside the main Ink story.

Requires UnityPy and its optional TypeTreeGeneratorAPI dependency. Never writes
to the game, collects saves/logs, or executes the game's managed assemblies.
Inventory is evidence for review, not a claim that every string is visible.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

import UnityPy
from UnityPy.helpers.TypeTreeGenerator import TypeTreeGenerator


def strings(value, path=()):
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, child in value.items():
            yield from strings(child, path+(key,))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            yield from strings(child, path+(index,))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('game', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    data = args.game/'Purgatory_Data'
    resources = UnityPy.load(str(data/'resources.assets'))
    version = str(next(iter(resources.files.values())).unity_version)
    generator = TypeTreeGenerator(version)
    generator.load_local_game(str(args.game))
    inputs = sorted(set(data.glob('*.assets')) | set(data.glob('level[0-9]*')) |
                    set((data/'StreamingAssets/Bundles').glob('*.hd')))
    records, failures, manifest = [], [], []
    counts = Counter()
    for path in inputs:
        env = UnityPy.load(str(path))
        env.typetree_generator = generator
        local = Counter()
        for obj in env.objects:
            if obj.type.name not in ('MonoBehaviour', 'TextAsset'):
                continue
            local[obj.type.name] += 1
            try:
                if obj.type.name == 'TextAsset':
                    value = obj.read()
                    if value.m_Name in ('wod02', 'wod02-credits'):
                        continue  # Main story has a separate all-path catalog QA.
                    raw = value.m_Script
                    text = raw.decode('utf-8') if isinstance(raw, bytes) else raw
                    try:
                        tree = json.loads(text)
                    except (ValueError, TypeError):
                        tree = {'asset_text': text}
                    script_name = value.m_Name
                else:
                    head = obj.parse_monobehaviour_head()
                    script = head.m_Script.deref_parse_as_object()
                    script_name = (script.m_Namespace+'.' if script.m_Namespace else '')+script.m_ClassName
                    tree = obj.read_typetree()
                for field, text in strings(tree):
                    if text and re.search('[A-Za-z]', text):
                        records.append({'asset':path.name,'object':obj.path_id,'class':script_name,
                            'field':list(field),'text':text})
            except Exception as exc:
                failures.append({'asset':path.name,'object':obj.path_id,'type':obj.type.name,
                    'error':type(exc).__name__+': '+str(exc)})
        counts.update(local)
        manifest.append({'file':path.name,'bytes':path.stat().st_size,
            'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'objects':dict(local)})
        print(f'{path.name}: {dict(local)}', flush=True)
    report = {'unity_version':version,'input_files':manifest,'objects':dict(counts),
        'records':records,'failures':failures,'record_count':len(records),'failure_count':len(failures)}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'strings':len(records),'failures':len(failures)}))


if __name__ == '__main__':
    main()
