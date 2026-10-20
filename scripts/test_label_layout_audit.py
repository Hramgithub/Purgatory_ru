"""Offline coverage receipts must not masquerade as expanded live Unity QA."""
import hashlib
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class LabelLayoutAuditContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads((ROOT/'localization/label-layout-review.json').read_text(encoding='utf-8-sig'))

    def test_serialized_objects_are_all_classified_with_explicit_failures(self):
        report = self.report
        self.assertEqual(report['scanned_asset_files'],17)
        self.assertEqual(report['serialized_tmp_objects'],193)
        self.assertEqual(sum(report['object_categories'].values()),193)
        self.assertEqual(report['unresolved_object_headers'],2)
        self.assertEqual(report['explicit_compact_captions'],57)

    def test_all_command_groups_and_labels_are_covered_without_translation(self):
        groups = self.report['creation_groups']
        self.assertEqual(len(groups),8)
        self.assertEqual(sum(x['options'] for x in groups),27)
        skills = [x for x in groups if x['group'].endswith('Skills')]
        self.assertEqual([x['labels'] for x in skills], [
            ['Athletics','Stealth','Survival'],
            ['Animal Ken','Intimidation','Persuasion'],
            ['The Occult','Medicine','Technology']])
        self.assertTrue(all(x['word_only_breaks'] for x in groups))

    def test_offline_candidate_is_not_claimed_installed_or_live_checked(self):
        report = self.report
        self.assertEqual(report['status'],'offline_candidate_not_installed_or_live_verified')
        self.assertIs(report['client_restarted_for_this_expanded_pass'],False)
        self.assertTrue(report['previous_patron_only_live_check']['not_proof_for_expanded_candidate'])
        self.assertNotEqual(report['candidate_plugin_sha256'],report['previous_patron_only_live_check']['plugin_sha256'])
        self.assertNotRegex(json.dumps(report),r'(?i)[a-z]:[\\/]+Users[\\/]')

    def test_policy_pins_are_checkout_newline_independent(self):
        for filename,key in [('CreationLabelPolicy.cs','creation_policy_sha256_lf'),
                             ('CompactLabelPolicy.cs','compact_policy_sha256_lf')]:
            code=(ROOT/'src/PurgatoryRu'/filename).read_text(encoding='utf-8-sig')
            self.assertEqual(self.report[key],hashlib.sha256(code.encode()).hexdigest())
        pure=(ROOT/'src/PurgatoryRu/CompactLabelPolicy.cs').read_text(encoding='utf-8-sig')
        self.assertIn('^',pure)
        self.assertIn('RegexOptions.CultureInvariant',pure)
        runtime=(ROOT/'src/PurgatoryRu/UiText.cs').read_text(encoding='utf-8-sig')
        self.assertIn('text.GetComponentInParent(CreationWidgetType) == null',runtime)


if __name__=='__main__':
    unittest.main()
