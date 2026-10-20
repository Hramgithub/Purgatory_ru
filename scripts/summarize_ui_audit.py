"""Write a public, value-redacted receipt from private game-string inventories.

Never copy raw inventories into a release: technical serialized settings can
contain vendor identifiers or credentials. This receipt whitelists metadata.
"""
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
    parser.add_argument('work', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--plugin', type=Path)
    parser.add_argument('--live-review', type=Path)
    args = parser.parse_args()
    def read(name):
        return json.loads((args.work/name).read_text(encoding='utf-8-sig'))
    assets = read('asset-strings.json')
    managed = read('managed-strings.json')
    failures = read('failed-objects-review.json')
    qa = read('story-qa.json')
    runtime = read('map-labels-runtime.json')
    dictionary_path = ROOT/'localization/ui-strings.json'
    dictionary = json.loads(dictionary_path.read_text(encoding='utf-8-sig'))
    names_policy = json.loads((ROOT/'localization/name-localization.json').read_text(encoding='utf-8-sig'))
    names = {key for category in ('people', 'packs', 'extras') for key in names_policy[category]}
    strings = {key.casefold() for key in dictionary['strings']}
    retained = set(dictionary['retained']) | set(names_policy['retained_visible'])
    candidates = {row['text'] for row in assets['records'] if
        (row['class']=='TMPro.TextMeshProUGUI' and row['field']==['m_text']) or
        (row['class']=='MapLabel' and row['field'][-1]=='text') or
        ('TooltipTrigger' in row['class'] and row['field']==['text'])}
    classifications = []
    for value in sorted(candidates):
        if value.casefold() in strings:
            category = 'exact_dictionary'
        elif value in names:
            category = 'display_name_policy'
        elif value in retained:
            category = 'retained_by_policy'
        elif re.fullmatch(r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) \d{1,2}, (?:Morning|Midday|Afternoon|Evening|Late night)', value) or re.fullmatch(r'chapter \d+', value) or re.fullmatch(r'[+-]?\d+ (?:min|hrs|days)', value) or value.startswith('<b>Use '):
            category = 'anchored_runtime_template'
        else:
            category = 'unmodified_template_or_technical_value_needs_live_observation'
        classifications.append({'sha256':hashlib.sha256(value.encode()).hexdigest(),
                                'characters':len(value), 'category':category})
    report = {
        'format':1, 'status':'source_candidate_not_installed_or_visually_verified',
        'unity_version':assets['unity_version'],
        'source_sha256':qa['sourceSha256'], 'story_sha256':qa['storySha256'],
        'plugin_sha256':digest(args.plugin or args.work/'plugin/PurgatoryRu.dll'),
        'ui_dictionary_sha256':digest(dictionary_path),
        'ui_dictionary_entries':len(dictionary['strings']),
        'asset_input_files':[{key:row[key] for key in ('file','bytes','sha256','objects')}
                             for row in assets['input_files']],
        'scanned_objects':assets['objects'], 'extracted_string_records':assets['record_count'],
        'typetree_failures':assets['failure_count'],
        'failure_classes':dict(Counter(row['class'] for row in failures)),
        'managed_string_constants':managed['record_count'],
        'managed_source_sha256':managed['source_sha256'],
        'serialized_display_candidates':len(candidates),
        'candidate_categories':dict(Counter(row['category'] for row in classifications)),
        'candidates':classifications,
        'new_map_catalog_ids':list(range(14067,14082)),
        'isolated_ink_map_literal_evaluations':runtime['evaluations'],
        'bar_choice_generation':runtime['bar_choice_generation'],
        'story_static_qa_passed':qa['passed'],
        'markup_checked_occurrences':qa['markup_checked_occurrences'],
        'limitations':[
            'String inventory is not proof that every serialized template is visible.',
            'Typetree failures include product-definition settings; embedded consent/privacy paragraphs are not claimed translated.',
            'Technical constants, original credits, skills and Gifts are not translation targets.',
            'Map literal tests do not test conditional branch availability or Unity layout.',
            'New menu/map glyphs, line wrapping and pooled-view reuse still require live Unity QA.',
            'Raw asset and managed inventories remain private ignored work files; no raw settings are published.'
        ]
    }
    if args.live_review:
        live = json.loads(args.live_review.read_text(encoding='utf-8-sig'))
        for key in ('plugin_sha256', 'story_sha256', 'ui_dictionary_sha256'):
            if live[key] != report[key]:
                raise ValueError('Live review is stale: '+key)
        if live['passed'] is not True:
            raise ValueError('Do not mark a failed live review as tested')
        report['status'] = 'installed_limited_live_qa_passed_not_a_new_release'
        report['live_review'] = live
        report['limitations'] = [line for line in report['limitations'] if not line.startswith('New menu/map glyphs')]
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'candidates':len(candidates),'categories':report['candidate_categories'],
                      'dictionary':len(dictionary['strings']),'story_passed':qa['passed']}))


if __name__ == '__main__':
    main()
