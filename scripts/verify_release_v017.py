"""Strict, explicitly offline-only v0.1.7 beta packaging gate."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def digest(path,mode='bytes'):
    data=path.read_bytes() if mode=='bytes' else path.read_text(encoding='utf-8-sig').encode()
    return hashlib.sha256(data).hexdigest()


def verify():
    receipt=json.loads((ROOT/'localization/release-v017-review.json').read_text(encoding='utf-8-sig'))
    assert receipt['version']=='0.1.7'
    assert receipt['validation']=='offline_beta_live_unverified'
    assert receipt['current_dll_live_qa_passed'] is False
    assert receipt['current_sprite_unity_probe_executed'] is False
    assert receipt['client_restarted'] is False
    assert receipt['installed_dll_changed'] is False
    assert receipt['story_and_display_dictionaries_unchanged_from_v016'] is True
    assert receipt['tests']['python_cases']>=89 and receipt['tests']['csharp_cases']==267
    assert receipt['tests']['ink_phase_cases']==8 and receipt['tests']['ink_stat_tooltip_cases']==4
    assert receipt['tests']['build_exit_code']==0 and receipt['tests']['dll_privacy_passed'] is True
    assert receipt['plugin_sha256']==digest(ROOT/'src/PurgatoryRu/bin/Release/netstandard2.1/PurgatoryRu.dll')
    assert receipt['story_sha256']==digest(ROOT/'dist/content/wod02.json')
    assert receipt['baseline_dll_sha256']=='029a20df2a8d8364e05ee1ce24442cc5ae14dd503ae06e46ed2ea51af81e6bec'
    assert 'PluginVersion = "0.1.7"' in (ROOT/'src/PurgatoryRu/Plugin.cs').read_text(encoding='utf-8-sig')
    for relative,pin in receipt['artifacts'].items():
        path=(ROOT/relative).resolve()
        assert path.is_relative_to(ROOT) and path.is_file(),relative
        assert digest(path,pin['mode'])==pin['sha256'],relative
    for name in ('form-render-v016-review.json','ui-coverage-review.json'):
        assert 'localization/'+name in receipt['artifacts']
    return receipt


if __name__=='__main__':
    receipt=verify()
    print('OFFLINE_BETA_V017_VERIFIED: live_qa=false; tests and exact artifacts pinned; historical receipts are baselines only.')
