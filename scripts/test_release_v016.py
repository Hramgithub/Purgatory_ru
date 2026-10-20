"""The new release must extend, not rewrite, the frozen v0.1.5 reviews."""
import hashlib
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]


def read(name):
    return json.loads((ROOT/'localization'/name).read_text(encoding='utf-8-sig'))


class ReleaseV016Contracts(unittest.TestCase):
    def test_old_receipts_stay_anchored_to_the_original_story(self):
        baseline='d9a82ee78f2db6bf87a850a248776f129ca47a0795c6f85d40422b4476799798'
        self.assertEqual(read('form-render-review.json')['story_sha256'],baseline)
        self.assertEqual(read('name-review-audit.json')['story_sha256'],baseline)
        self.assertEqual(read('name-review-audit.json')['version'],'0.1.5')

    def test_name_delta_inherits_identical_identity_slots(self):
        delta=read('release-v016-review.json')
        audit=read('name-review-v016.json')
        self.assertEqual(delta['changed_unique_ids'],37)
        self.assertEqual(delta['changed_occurrences'],44)
        self.assertEqual(set(delta['changed_name_input_guards']),{488,1349,3095})
        self.assertTrue(delta['name_identity_order_and_forms_unchanged'])
        self.assertEqual(audit['reviewed_count'],4106)
        self.assertEqual(audit['reviewed_slots'],5259)
        self.assertEqual(audit['baseline_review_sha256'],hashlib.sha256((ROOT/'localization/name-review-audit.json').read_bytes()).hexdigest())
        self.assertEqual(audit['delta_review_sha256'],hashlib.sha256((ROOT/'localization/release-v016-review.json').read_bytes()).hexdigest())
        for relative,digest in audit['artifacts'].items():
            self.assertEqual(digest,hashlib.sha256((ROOT/relative).read_bytes()).hexdigest())

    def test_version_and_new_fresh_render_gate_are_required(self):
        plugin=(ROOT/'src/PurgatoryRu/Plugin.cs').read_text(encoding='utf-8-sig')
        package=(ROOT/'scripts/build_package.ps1').read_text(encoding='utf-8-sig')
        self.assertIn('PluginVersion = "0.1.6"',plugin)
        self.assertIn("[string]$Version = '0.1.6'",package)
        self.assertIn('localization\\form-render-v016-review.json',package)
        self.assertIn('$renderQa.dll_sha256 -ne',package)
        self.assertIn('$renderQa.story_sha256 -ne',package)
        self.assertIn('NAME-REVIEW-BASELINE-v015.json',package)
        self.assertIn('RELEASE-DELTA-QA.json',package)

    def test_installer_smoke_is_confined_to_a_generated_fixture(self):
        code=(ROOT/'scripts/Test-PortablePackage.ps1').read_text(encoding='utf-8-sig')
        self.assertIn('work/installer-check-',code)
        self.assertIn('Refuse uninstall outside test fixture',code)
        self.assertIn('powershell.exe -NoProfile',code)
        self.assertIn("'ui-strings.json'",code)
        self.assertIn('Unrelated mod removed',code)


if __name__=='__main__':
    unittest.main()
