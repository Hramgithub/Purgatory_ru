"""Run current offline tests and pin v0.1.7 without inventing current live QA."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import zipfile

from verify_release_privacy import verify as privacy
from verify_release_v017 import digest, verify

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'work/release-v017'


def run(name,args,env):
    result=subprocess.run(args,cwd=ROOT,env=env,capture_output=True,encoding='utf-8',errors='replace')
    output=result.stdout+'\n'+result.stderr
    (WORK/(name+'.txt')).write_text(output,encoding='utf-8')
    if result.returncode:
        raise RuntimeError(name+' failed; see private work/release-v017 transcript')
    return output


def main():
    WORK.mkdir(parents=True,exist_ok=True)
    env=dict(os.environ,DOTNET_CLI_HOME=str(ROOT/'.dotnet-home'),
             NUGET_PACKAGES=str(ROOT/'.nuget-packages'),APPDATA=str(ROOT/'.appdata'),
             DOTNET_CLI_UI_LANGUAGE='en-US')
    build=run('build',['dotnet','build','src/PurgatoryRu/PurgatoryRu.csproj','-c','Release','--no-restore'],env)
    assert '0 Warning(s)' in build and '0 Error(s)' in build
    tests=run('python-tests',[sys.executable,'-X','utf8','-m','unittest','discover','-s','scripts','-p','test_*.py'],env)
    python_cases=int(re.search(r'Ran (\d+) tests',tests).group(1))
    csharp=run('csharp-tests',['dotnet','run','--no-restore','--project','tests/UiTextCoreTests/UiTextCoreTests.csproj',
                            '--','localization/ui-strings.json'],env)
    csharp_cases=sum(int(x) for x in re.findall(r'^[A-Z_]+_OK cases=(\d+)',csharp,re.M))
    run('ink-tooltips',['pwsh.exe','-NoProfile','-File','scripts/Test-InkMoonPhases.ps1',
                       '-StoryPath','dist/content/wod02.json','-ReportPath','dist/moon-tooltips-report.json'],env)
    ink=json.loads((ROOT/'dist/moon-tooltips-report.json').read_text(encoding='utf-8-sig'))
    assert ink['passed'] and ink['phases']==8 and ink['stat_tooltips']==4
    dll=ROOT/'src/PurgatoryRu/bin/Release/netstandard2.1/PurgatoryRu.dll'
    assert privacy(dll)['passed']
    with zipfile.ZipFile(ROOT/'dist/Purgatory-RU-0.1.6.zip') as z:
        for relative,name in [('dist/content/wod02.json','wod02.json'),
                              ('localization/name-localization.json','name-localization.json'),
                              ('localization/ui-strings.json','ui-strings.json')]:
            key=next(n for n in z.namelist() if n.endswith('/PurgatoryRu/'+name))
            assert z.read(key)==(ROOT/relative).read_bytes(),relative
    for name in ('form-render-v016-review.json','ui-coverage-review.json'):
        expected=subprocess.check_output(['git','show','v0.1.6:localization/'+name],cwd=ROOT)
        assert expected==(ROOT/'localization'/name).read_bytes(),name
    paths=list((ROOT/'src/PurgatoryRu').glob('*.cs'))+[ROOT/'src/PurgatoryRu/PurgatoryRu.csproj']
    paths += [ROOT/x for x in ('localization/name-localization.json','localization/ui-strings.json',
        'localization/form-render-v016-review.json','localization/ui-coverage-review.json',
        'localization/label-layout-review.json','localization/sprites-moon-review.json',
        'dist/moon-tooltips-report.json','scripts/prepare_release_v017_review.py',
        'scripts/verify_release_v017.py','scripts/Test-InkMoonPhases.ps1')]
    artifacts={}
    for path in paths:
        mode='bytes' if path.suffix=='.json' else 'utf8-lf'
        artifacts[path.relative_to(ROOT).as_posix()]={'sha256':digest(path,mode),'mode':mode}
    receipt={
        'format':1,'version':'0.1.7','date':'2026-10-21',
        'validation':'offline_beta_live_unverified',
        'current_dll_live_qa_passed':False,'current_sprite_unity_probe_executed':False,
        'client_restarted':False,'installed_dll_changed':False,
        'plugin_sha256':digest(dll),'story_sha256':digest(ROOT/'dist/content/wod02.json'),
        'baseline_dll_sha256':'029a20df2a8d8364e05ee1ce24442cc5ae14dd503ae06e46ed2ea51af81e6bec',
        'story_and_display_dictionaries_unchanged_from_v016':True,
        'tests':{'python_cases':python_cases,'csharp_cases':csharp_cases,
                 'ink_phase_cases':8,'ink_stat_tooltip_cases':4,'build_exit_code':0,'dll_privacy_passed':True},
        'artifacts':artifacts,
        'limitations':[
            'Current DLL is offline-tested only; hidden Unity sprite probe and visible UI inspection have not run.',
            'v0.1.6 live receipts are unchanged historical baselines, not current v0.1.7 live evidence.',
            'Skills and Gifts remain in English; story and name-slot review is inherited unchanged from v0.1.6.',
            'Not a claim about every story branch, resolution or accessible-font mode.'
        ]}
    (ROOT/'localization/release-v017-review.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    verify()
    print(f'RELEASE_V017_OFFLINE_OK python={python_cases} csharp={csharp_cases} ink=12 live_qa=false')


if __name__=='__main__':
    main()
