"""Read-only, whitelisted TMP layout inventory. Not live Unity fit proof.

Outputs only display objects (never settings/product fields), original UI
geometry and component ancestry. Keep detailed output in ignored work/.
"""
import argparse
import hashlib
import json
from pathlib import Path

import UnityPy
from UnityPy.helpers.TypeTreeGenerator import TypeTreeGenerator


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
    rows, failures, manifests = [], [], []
    for path in inputs:
        env = UnityPy.load(str(path))
        env.typetree_generator = generator
        for obj in env.objects:
            if obj.type.name != 'MonoBehaviour':
                continue
            try:
                head = obj.parse_monobehaviour_head()
                script = head.m_Script.deref_parse_as_object()
                if script.m_ClassName != 'TextMeshProUGUI':
                    continue
                tree = obj.read_typetree()
                game_object = head.m_GameObject.deref_parse_as_object()
                transform = next(p.component.deref() for p in game_object.m_Component
                                 if p.component.deref().type.name == 'RectTransform')
                rect = transform.read_typetree()
                ancestors = []
                current = transform
                for _ in range(30):
                    parsed = current.read()
                    go = parsed.m_GameObject.deref_parse_as_object()
                    classes = []
                    for p in go.m_Component:
                        component = p.component.deref()
                        if component.type.name == 'MonoBehaviour':
                            h = component.parse_monobehaviour_head()
                            s = h.m_Script.deref_parse_as_object()
                            classes.append(s.m_ClassName)
                        else:
                            classes.append(component.type.name)
                    ancestors.append({'name': go.m_Name, 'classes': classes})
                    if not parsed.m_Father.path_id:
                        break
                    current = parsed.m_Father.deref()
                selected = {k:tree[k] for k in ('m_text', 'm_fontSize', 'm_fontSizeMin',
                    'm_fontSizeMax', 'm_enableAutoSizing', 'm_enableWordWrapping',
                    'm_overflowMode', 'm_margin') if k in tree}
                rows.append({'asset':path.name, 'object':obj.path_id,
                    'ancestry':ancestors, 'text':selected,
                    'rect':{k:rect[k] for k in ('m_AnchorMin','m_AnchorMax','m_AnchoredPosition',
                        'm_SizeDelta','m_Pivot') if k in rect}})
            except Exception as exc:
                failures.append({'asset':path.name,'object':obj.path_id,'error':type(exc).__name__})
        manifests.append({'file':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    result = {'format':1,'unity_version':version,'inputs':manifests,
        'records':rows,'failure_count':len(failures),'failures':failures,
        'scope':'Serialized geometry only; dynamic text, resolved widths and font fit require runtime validation.'}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'tmp_objects':len(rows),'failures':len(failures),'files':len(inputs)}))


if __name__ == '__main__':
    main()
