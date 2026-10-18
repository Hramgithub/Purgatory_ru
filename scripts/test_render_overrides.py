"""Source-pinned tag exceptions must not permit arbitrary markup edits."""
from copy import deepcopy
import hashlib
import unittest

from render_overrides import apply_override, validate_tags, approved_name_audit, restore_paths


class RenderOverrideTests(unittest.TestCase):
    def test_exact_literal_margin_repair_does_not_execute_or_change_bytecode(self):
        item = {'id': 4, 'source': '^^”helper()” ', 'body': '^”helper()” '}
        repair = {4: {'source_sha256': hashlib.sha256(item['source'].encode()).hexdigest(),
                      'before_tags': [], 'after_tags': [],
                      'operations': [{'kind': 'replace_literal', 'before': item['body'],
                                      'after': '^"Слава" '}]}}
        self.assertEqual(apply_override(item, item['body'], repair), '^"Слава" ')
        with self.assertRaisesRegex(ValueError, 'entire exact old text'):
            apply_override(item, 'changed', repair)
    def test_path_restoration_does_not_change_visible_duplicate(self):
        source = {'logic': ['^balanced'], 'ui': ['^balanced']}
        translated = {'logic': ['^средний уровень'], 'ui': ['^средний уровень']}
        repairs = [{'id': 263, 'path': ['logic', 0], 'expected': '^balanced',
                    'source_sha256': hashlib.sha256(b'^balanced').hexdigest(), 'reason': 'Comparison.'}]
        restore_paths(source, translated, repairs)
        self.assertEqual(translated['logic'], ['^balanced'])
        self.assertEqual(translated['ui'], ['^средний уровень'])
        with self.assertRaisesRegex(ValueError, 'source drift'):
            restore_paths({'logic': ['^other']}, translated, repairs)
    def test_name_exception_exact_source_and_token_and_all_occurrences(self):
        item = {'id': 3, 'source': '^Wrong spoke.', 'body': 'Wrong spoke.',
                'mask': {'⟦T000⟧': 'Wrong'}}
        repair = {3: {'source_sha256': hashlib.sha256(item['source'].encode()).hexdigest(),
                      'before_tags': [], 'after_tags': [], 'reason': 'Approved author typo.',
                      'operations': [{'kind': 'proper_name', 'token': '⟦T000⟧',
                                      'before': 'Wrong', 'after': 'Right'}]}}
        self.assertEqual(apply_override(item, 'Wrong сказал.', repair), 'Right сказал.')
        deltas, audit = approved_name_audit(['^Wrong spoke.', ['^Wrong spoke.']], [item], repair)
        self.assertEqual(deltas, {'Wrong': -2, 'Right': 2})
        self.assertEqual(audit[0]['occurrences'], 2)
        plaintext = [{'id': 3, 'kind': 'plaintext-name', 'source_sha256': repair[3]['source_sha256'],
                      'before': 'Wrong', 'after': 'Right', 'reason': 'Approved spelling.'}]
        plain_deltas, _ = approved_name_audit(['^Wrong spoke.'], [item], {}, plaintext)
        self.assertEqual(plain_deltas, {'Wrong': -1, 'Right': 1})
        plaintext[0]['source_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'source drift'):
            approved_name_audit(['^Wrong spoke.'], [item], {}, plaintext)
        bad = deepcopy(item)
        bad['mask']['⟦T000⟧'] = 'Other'
        with self.assertRaisesRegex(ValueError, 'mapping changed'):
            apply_override(bad, 'Wrong сказал.', repair)
    def fixture(self):
        item = {'id': 1, 'source': '^<link=a>one</link><link=a>two</link>',
                'body': '<link=a>one</link><link=a>two</link>'}
        repair = {1: {'source_sha256': hashlib.sha256(item['source'].encode()).hexdigest(),
                      'before_tags': ['<link=a>', '</link>', '<link=a>', '</link>'],
                      'after_tags': ['<link=a>', '</link>', '<link=b>', '</link>'],
                      'operations': [{'kind': 'replace_tag', 'index': 2,
                                      'before': '<link=a>', 'after': '<link=b>'}]}}
        return item, repair

    def test_only_reviewed_tag_delta_allowed(self):
        item, repair = self.fixture()
        ru = '<link=a>один</link><link=a>два</link>'
        expected = '<link=a>один</link><link=b>два</link>'
        self.assertEqual(apply_override(item, ru, repair), expected)
        with self.assertRaisesRegex(ValueError, 'input tags drift'):
            apply_override(item, ru + '<b>extra</b>', repair)
        changed_source = deepcopy(item)
        changed_source['source'] += ' '
        with self.assertRaisesRegex(ValueError, 'source drift'):
            apply_override(changed_source, ru, repair)
        with self.assertRaisesRegex(ValueError, 'unapproved markup'):
            validate_tags(item, item['body'], expected, repair)

    def test_malformed_closer_not_valid_closers(self):
        item = {'id': 2, 'source': '^<b>a</b><b>b</b.', 'body': '<b>a</b><b>b</b.'}
        repair = {2: {'source_sha256': hashlib.sha256(item['source'].encode()).hexdigest(),
                      'before_tags': ['<b>', '</b>', '<b>'],
                      'after_tags': ['<b>', '</b>', '<b>', '</b>'],
                      'operations': [{'kind': 'repair_malformed_b'}]}}
        self.assertEqual(apply_override(item, '<b>а</b><b>б</b их.', repair),
                         '<b>а</b><b>б</b> их.')
        with self.assertRaisesRegex(ValueError, 'one malformed'):
            apply_override(item, '<b>а</b><b>б', repair)


if __name__ == '__main__':
    unittest.main()
