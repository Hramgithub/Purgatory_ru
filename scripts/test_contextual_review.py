"""Regression tests for exhaustive extraction and safe sparse edit application."""
import json
from pathlib import Path
import tempfile
import unittest
import uuid

from apply_contextual_review import apply_review, check_change, replace_translation_spans
from prepare_contextual_review import prepare, write_json


class ContextualReviewTests(unittest.TestCase):
    def test_sparse_bytes_preserve_bom_layout_and_line_ends(self):
        data = b'\xef\xbb\xbf{\r\n "items": [{"id": 1, "translation": "old"}, {"id": 2, "translation": "stay"}]\r\n}\r\n'
        result = replace_translation_spans(data, {1: ('old', 'new "quoted"')})
        self.assertEqual(result, data.replace(b'"old"', b'"new \\"quoted\\""'))
        with self.assertRaisesRegex(ValueError, 'before mismatch'):
            replace_translation_spans(data, {1: ('wrong', 'new')})

    def test_immutable_tokens_markup_commands(self):
        item = {'source': '^HEADER: x', 'body': 'HEADER: x',
                'mask': {'⟦T000⟧': '<i>', '⟦T001⟧': '</i>'}}
        check_change(item, 'HEADER: ⟦T000⟧старое⟦T001⟧', 'HEADER: ⟦T000⟧новое⟦T001⟧', set())
        for bad in ('HEADER: ⟦T001⟧новое⟦T000⟧', 'ЗАГОЛОВОК: ⟦T000⟧новое⟦T001⟧',
                    'HEADER: ⟦T000⟧<b>новое</b>⟦T001⟧'):
            with self.assertRaises(ValueError):
                check_change(item, 'HEADER: ⟦T000⟧старое⟦T001⟧', bad, set())

    def fixture(self, root):
        source = root / 'story.json'
        loc = root / 'localization'
        output = root / 'review'
        # Duplicate story ID in a different alternative named container must not
        # disappear through first_path de-duplication.
        story = {'root': [[], 'done', {'early': ['^I ran.', {'*': '.^.branch', 'flg': 4},
                       {'branch': ['^A face.', '^I ran.', None]}],
                       'late': ['^I ran.', None]}]}
        catalog = [{'id': 0, 'source': '^I ran.', 'prefix': '^', 'body': 'I ran.',
                    'masked': 'I ran.', 'first_path': ['root', 2, 'early', 0], 'mask': {}},
                   {'id': 1, 'source': '^A face.', 'prefix': '^', 'body': 'A face.',
                    'masked': 'A face.', 'first_path': ['root', 2, 'early', 2, 'branch', 0], 'mask': {}}]
        write_json(source, story)
        write_json(loc / 'catalog.json', catalog)
        write_json(loc / 'ru' / 'chunk-0001.json', {'items': [
            {'id': 0, 'translation': 'Я побежала.'}, {'id': 1, 'translation': 'Лицо.'}]})
        return source, loc, output

    def test_all_occurrences_owned_once_and_context_required(self):
        temporary_root = Path(__file__).resolve().parents[1] / 'work'
        temporary_root.mkdir(exist_ok=True)
        # Windows sandbox denies mkdtemp's restricted 0700 ACL; use normal
        # workspace directory permissions. Fixtures remain ignored for diagnosis.
        temporary = temporary_root / ('editorial-test-' + uuid.uuid4().hex)
        temporary.mkdir()
        if temporary:
            root = Path(temporary)
            source, loc, output = self.fixture(root)
            manifest = prepare(source, loc, output)
            self.assertEqual(manifest['occurrence_count'], 4)
            self.assertEqual(sum(len(unit['owner_ids']) for unit in manifest['units']), 2)
            receipts = [{'unit': unit['unit'], 'reviewed_ids': unit['owner_ids'],
                         'context_checked': unit['scene'] == 'early', 'changes': [], 'notes': []}
                        for unit in manifest['units']]
            write_json(output / 'reviews' / 'reviews.json', receipts)
            with self.assertRaisesRegex(ValueError, 'unread context units'):
                apply_review(source, loc, output, root / 'report.json')
            partial = apply_review(source, loc, output, root / 'report.json', allow_partial=True)
            self.assertFalse(partial['complete'])
            self.assertEqual(partial['context_checked_occurrences'], 3)
            receipts[-1]['context_checked'] = True
            receipts[0]['changes'] = [{'id': 0, 'before': 'Я побежала.',
                                       'after': 'Я бросилась бежать.', 'reason': 'Связность повествования.'}]
            write_json(output / 'reviews' / 'reviews.json', receipts)
            result = apply_review(source, loc, output, root / 'report.json', apply=True)
            self.assertTrue(result['complete'])
            self.assertEqual(result['context_checked_occurrences'], 4)
            self.assertIn('Я бросилась бежать.', (loc / 'ru' / 'chunk-0001.json').read_text(encoding='utf-8'))
            with self.assertRaisesRegex(ValueError, 'drift'):
                apply_review(source, loc, output, root / 'report.json')


if __name__ == '__main__':
    unittest.main()
