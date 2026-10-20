"""Verify exact ZIP manifest/payload and write a portable SHA-256 sidecar."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive',type=Path)
    parser.add_argument('--version',required=True)
    args=parser.parse_args()
    prefix='Purgatory-RU-'+args.version+'/'
    with zipfile.ZipFile(args.archive) as z:
        entries=[i for i in z.infolist() if not i.is_dir()]
        assert len(entries)==len({i.filename for i in entries}),'Duplicate ZIP entry'
        assert all(i.filename.startswith(prefix) and '..' not in PurePosixPath(i.filename).parts
                   and ':' not in i.filename and '\\' not in i.filename for i in entries)
        files={i.filename[len(prefix):]:z.read(i) for i in entries}
        manifest=json.loads(files['manifest.json'].decode('utf-8-sig'))
        assert manifest['version']==args.version
        expected={r['path']:r for r in manifest['files']}
        assert len(expected)==len(manifest['files'])
        assert set(expected)==set(files)-{'manifest.json'}
        for name,row in expected.items():
            assert row['size']==len(files[name]),name
            assert row['sha256']==hashlib.sha256(files[name]).hexdigest(),name
            assert not name.lower().endswith(('.pdb','.key','.pem','.pfx','.p12')),name
            assert not any(p.lower() in {'saves','work','.git'} for p in PurePosixPath(name).parts),name
        for name,relative in [('PurgatoryRu.dll','src/PurgatoryRu/bin/Release/netstandard2.1/PurgatoryRu.dll'),
                              ('wod02.json','dist/content/wod02.json'),
                              ('name-localization.json','localization/name-localization.json'),
                              ('ui-strings.json','localization/ui-strings.json')]:
            assert files['payload/BepInEx/plugins/PurgatoryRu/'+name]==(ROOT/relative).read_bytes(),name
        if args.version=='0.1.7':
            assert manifest['validation']=='offline_beta_live_unverified'
            receipt=json.loads(files['RELEASE-QA.json'].decode('utf-8-sig'))
            assert receipt['current_dll_live_qa_passed'] is False
            assert receipt['current_sprite_unity_probe_executed'] is False
            assert receipt['plugin_sha256']==hashlib.sha256(files['payload/BepInEx/plugins/PurgatoryRu/PurgatoryRu.dll']).hexdigest()
            assert 'FORM-RENDER-QA.json' not in files and 'UI-COVERAGE-QA.json' not in files
            assert 'FORM-RENDER-BASELINE-v016.json' in files and 'UI-COVERAGE-BASELINE-v016.json' in files
    checksum=hashlib.sha256(args.archive.read_bytes()).hexdigest()
    args.archive.with_suffix('.sha256').write_text(checksum+'  '+args.archive.name+'\n',encoding='ascii',newline='\n')
    print(json.dumps({'passed':True,'version':args.version,'files':len(files),'sha256':checksum}))


if __name__=='__main__':
    main()
