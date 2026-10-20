"""Publishing an offline beta must be explicit and must not rewrite live proof."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]


class ReleaseV017Contracts(unittest.TestCase):
    def test_offline_packaging_is_opt_in_and_limited_to_this_beta(self):
        code=(ROOT/'scripts/build_package.ps1').read_text(encoding='utf-8-sig')
        for token in ('[switch]$OfflineBeta',"$Version -cne '0.1.7'",'scripts\\verify_release_v017.py',
                      'if (!$OfflineBeta -and ($uiCoverageQa.live_review.passed',
                      'if (!$OfflineBeta -and ($renderQa.passed',
                      'UI-COVERAGE-BASELINE-v016.json','FORM-RENDER-BASELINE-v016.json',
                      "'offline_beta_live_unverified'",'RELEASE-QA.json'):
            self.assertIn(token,code)

    def test_offline_receipt_must_stay_false_for_current_live_qa(self):
        code=(ROOT/'scripts/verify_release_v017.py').read_text(encoding='utf-8-sig')
        for token in ("receipt['current_dll_live_qa_passed'] is False",
                      "receipt['current_sprite_unity_probe_executed'] is False",
                      "receipt['plugin_sha256']==digest", "receipt['artifacts'].items()",
                      "path.is_relative_to(ROOT)","receipt['story_and_display_dictionaries_unchanged_from_v016'] is True"):
            self.assertIn(token,code)

    def test_receipt_producer_executes_offline_tests_without_launching_game(self):
        code=(ROOT/'scripts/prepare_release_v017_review.py').read_text(encoding='utf-8-sig')
        for token in ("run('build'", "run('python-tests'", "run('csharp-tests'", "run('ink-tooltips'",
                      'v0.1.6:localization/', "z.read(key)==(ROOT/relative).read_bytes()"):
            self.assertIn(token,code)
        for forbidden in ('Start-Process','steam://','Stop-Process','AppData/LocalLow'):
            self.assertNotIn(forbidden,code)


if __name__=='__main__':
    unittest.main()
