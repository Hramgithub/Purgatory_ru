"""Summarize offline label coverage without claiming live fit or exposing raw assets."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inventory',type=Path)
    parser.add_argument('commands',type=Path)
    parser.add_argument('dll',type=Path)
    parser.add_argument('output',type=Path)
    args = parser.parse_args()
    read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
    inventory, commands = read(args.inventory), read(args.commands)
    policy_path = ROOT/'src/PurgatoryRu/CreationLabelPolicy.cs'
    compact_path = ROOT/'src/PurgatoryRu/CompactLabelPolicy.cs'
    policies = re.findall(r'new Group\("([^"]+)",\s*"([^"]+)",\s*"([^"]+)"\)',policy_path.read_text(encoding='utf-8-sig'))
    signatures = {icons:(name,names.split('|')) for name,icons,names in policies}
    groups = []
    for command in commands['commands']:
        fields = command['fields']
        group, expected = signatures[fields[2]]
        labels = fields[3].split('|')
        assert expected == [x[1:-1] if x.startswith('«') and x.endswith('»') else x for x in labels]
        groups.append({'group':group,'path':command['path'],'options':len(labels),
                       'labels':labels,'word_only_breaks':True})
    assert len(groups)==8 and sum(x['options'] for x in groups)==27
    compact = compact_path.read_text(encoding='utf-8-sig')
    block = re.search(r'SingleLine = new\(StringComparer.Ordinal\)\s*\{(.*?)\};',compact,re.S).group(1)
    captions = set(re.findall(r'"([^"\n]+)"',block))
    dictionary = {k.casefold():v for k,v in read(ROOT/'localization/ui-strings.json')['strings'].items()}
    policy = read(ROOT/'localization/name-localization.json')
    names = {k.casefold():v for category in ('people','packs','extras') for k,v in policy[category].items()}
    categories = Counter()
    native_multiline = set()
    for row in inventory['records']:
        source = row['text'].get('m_text','')
        target = dictionary.get(source.casefold())
        if any('CharacterCreationWidget' in x['classes'] for x in row['ancestry']):
            category = 'creation_widget_dynamic_group_title_or_body'
        elif source.casefold() in names:
            category = 'exact_display_name_policy'
        elif target is not None:
            if target in captions or (not re.search(r'[\s<>\\]',target) and len(target)<=80):
                category = 'exact_compact_ui_policy'
            else:
                category = 'native_multiline_prompt_or_explicit_break'
                native_multiline.add(source)
        elif re.fullmatch(r'chapter \d+|[+-]?\d+ (?:hrs|min|days)|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) \d{1,2}, (?:Morning|Midday|Afternoon|Evening|Late night)',source):
            category = 'anchored_runtime_caption_policy'
        elif not source or re.fullmatch(r'[+\d%\s.x]+',source):
            category = 'empty_dynamic_or_numeric_template'
        else:
            category = 'original_credit_retained_term_or_runtime_body_template'
        categories[category]+=1
    assert sum(categories.values())==len(inventory['records'])
    report = {
        'format':1,'date':'2026-10-21',
        'status':'offline_candidate_not_installed_or_live_verified',
        'client_restarted_for_this_expanded_pass':False,
        'source_sha256':commands['sourceSha256'].lower(),
        'story_sha256':commands['storySha256'].lower(),
        'candidate_plugin_sha256':digest(args.dll),
        'creation_policy_sha256_lf':hashlib.sha256(policy_path.read_text(encoding='utf-8-sig').encode()).hexdigest(),
        'compact_policy_sha256_lf':hashlib.sha256(compact_path.read_text(encoding='utf-8-sig').encode()).hexdigest(),
        'scanned_asset_files':len(inventory['inputs']),
        'serialized_tmp_objects':len(inventory['records']),
        'unresolved_object_headers':inventory['failure_count'],
        'object_categories':dict(categories),
        'creation_groups':groups,'creation_options':27,
        'explicit_compact_captions':len(captions),
        'native_multiline_prompts_and_explicit_breaks':sorted(native_multiline),
        'previous_patron_only_live_check':{
            'passed':True,'plugin_sha256':'f668bd4747b7ef429272616f58f6376f5e070d113180663f553a4b449964d489',
            'labels':3,'uniform_font_size':20.2,'word_only_breaks':True,
            'not_proof_for_expanded_candidate':True},
        'limitations':[
            'Serialized templates are not all runtime strings; classification does not prove visual fit.',
            'Two object headers could not be resolved; they are not claimed reviewed TMP elements.',
            'Narrative, long tooltips, consent prompts, save metadata and explicit multiline text retain native wrapping.',
            'Expanded candidate is build/test verified only; no live QA, installation, publication or save replacement is claimed.',
            'Skills and Gifts retain their source wording; only label layout changes.',
            'The published v0.1.6 package and its historical receipts remain unchanged.'
        ]
    }
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'groups':len(groups),'options':27,'compact_captions':len(captions),
                      'tmp_objects':len(inventory['records']),'categories':dict(categories)}))


if __name__=='__main__':
    main()
