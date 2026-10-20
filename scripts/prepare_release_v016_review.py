"""Verify the exact reviewed v0.1.6 story/name delta without rewriting v0.1.5 receipts."""
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

from translate_ink_gpt import walk
from translation_catalog import load_catalog

ROOT = Path(__file__).resolve().parents[1]
BASE = 'd9a82ee78f2db6bf87a850a248776f129ca47a0795c6f85d40422b4476799798'
TARGET = '28f901eca9dfca5f0c57a45c15aba31bcf3a1d638c62a91ab2d20b642b08a32a'
IDS = {178,233,296,451,488,915,1294,1298,1299,1305,1310,1317,1322,
       1330,1340,1341,1349,1694,1699,3095,3437,13557} | set(range(14067,14082))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def main():
    location = ROOT/'localization'
    before_audit = read(location/'name-review-audit.json')
    story_bytes = (ROOT/'dist/content/wod02.json').read_bytes()
    with zipfile.ZipFile(ROOT/'dist/Purgatory-RU-0.1.5.zip') as archive:
        name = next(n for n in archive.namelist() if n.endswith('/PurgatoryRu/wod02.json'))
        before_bytes = archive.read(name)
    if sha(before_bytes) != BASE or sha(story_bytes) != TARGET or before_audit['story_sha256'] != BASE:
        raise ValueError('Not the reviewed baseline/target stories')
    source = read(ROOT/'work/english_ink/wod02__resources__67.json')
    source_nodes = dict(walk(source))
    by_source = {r['source']:r['id'] for r in load_catalog(location,source)}
    before, after = dict(walk(json.loads(before_bytes))), dict(walk(json.loads(story_bytes)))
    if before.keys() != after.keys():
        raise ValueError('Story structure changed')
    delta = []
    for path, old in before.items():
        new = after[path]
        if old == new:
            continue
        item_id = by_source.get(source_nodes.get(path))
        if not isinstance(old,str) or not isinstance(new,str) or item_id not in IDS:
            raise ValueError('Unreviewed story change')
        delta.append({'id':item_id,'path':list(path),'before_sha256':sha(old.encode()),'after_sha256':sha(new.encode())})
    if {r['id'] for r in delta} != IDS or len(delta) != 44:
        raise ValueError('Reviewed delta coverage differs')
    old_forms = json.loads(subprocess.check_output(['git','show','v0.1.5:localization/name-forms.json'],cwd=ROOT))
    new_forms = read(location/'name-forms.json')
    changed_inputs = []
    if len(old_forms['items']) != len(new_forms['items']):
        raise ValueError('Name identities/count changed')
    for old, new in zip(old_forms['items'],new_forms['items']):
        if {k:v for k,v in old.items() if k!='before_sha256'} != {k:v for k,v in new.items() if k!='before_sha256'}:
            raise ValueError('Name slots changed; a new contextual review is required')
        if old['before_sha256'] != new['before_sha256']:
            changed_inputs.append(new['id'])
    if set(changed_inputs) != {488,1349,3095}:
        raise ValueError('Unexpected name-input delta')
    artifacts = {}
    for relative in before_audit['artifacts']:
        if not relative.startswith('localization/'):
            continue
        path = ROOT/relative
        artifacts[relative] = sha(path.read_bytes())
        if relative != 'localization/name-forms.json':
            baseline = subprocess.check_output(['git','show','v0.1.5:'+relative],cwd=ROOT)
            if baseline != path.read_bytes():
                raise ValueError('Policy/fragments/retained terms changed: '+relative)
    qa = read(ROOT/'dist/name-qa-report.json')
    if qa['passed'] is not True or qa['storySha256'] != TARGET or qa['name_localization']['error_count']:
        raise ValueError('Current canonical name QA failed')
    receipt = {
        'format':1,'version':'0.1.6','complete':True,
        'baseline_story_sha256':BASE,'story_sha256':TARGET,
        'baseline_name_review_sha256':sha((location/'name-review-audit.json').read_bytes()),
        'changed_unique_ids':len(IDS),'changed_occurrences':len(delta),'changes':delta,
        'changed_name_input_guards':changed_inputs,
        'name_identity_order_and_forms_unchanged':True,
        'method':'Exact reviewed delta only: terminology/wording and 15 map labels. Inherits immutable v0.1.5 name-slot context review; not another full editorial pass.',
    }
    (location/'release-v016-review.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    audit = {
        'format':1,'version':'0.1.6','date':'2026-10-20','complete':True,
        'baseline_story_sha256':before_audit['baseline_story_sha256'],
        'source_sha256':before_audit['source_sha256'],'story_sha256':TARGET,
        'reviewed_count':new_forms['reviewed_count'],
        'reviewed_slots':sum(len(row['forms']) for row in new_forms['items']),
        'method':'Inherited v0.1.5 name context audit plus exact v0.1.6 input/slot/policy delta verification and current full canonical-name QA.',
        'baseline_review':'name-review-audit.json','baseline_review_sha256':receipt['baseline_name_review_sha256'],
        'delta_review':'release-v016-review.json',
        'delta_review_sha256':sha((location/'release-v016-review.json').read_bytes()),
        'artifacts':artifacts,
        'limitations':['No new full-script editorial pass or all-branches live playthrough is claimed.']
    }
    (location/'name-review-v016.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('RELEASE_DELTA_OK ids=37 occurrences=44 unchanged_name_slots='+str(audit['reviewed_slots']))


if __name__ == '__main__':
    main()
