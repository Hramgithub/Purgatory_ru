"""Hash-pinned name slots and all-occurrence canonical QA regressions."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from name_localization import (apply_name_forms, canonical_name_story, digest,
                               load_name_forms, visible_name_occurrences, apply_name_fragments)
from renderer_commands import contract_errors
import qa_translation


class NameLocalizationTests(unittest.TestCase):
    def setUp(self):
        self.policy = {'people': {'Pat': 'Пэт', 'Samira': 'Самира'}, 'packs': {}, 'extras': {}}
        self.text = 'Pat встретила Samira.'
        self.record = {'id': 1, 'before_sha256': digest(self.text),
                       'english': ['Pat', 'Samira'], 'forms': ['Пэт', 'Самиру']}

    def test_reviewed_grammatical_forms(self):
        self.assertEqual(apply_name_forms(1, self.text, self.policy, {1: self.record}),
                         'Пэт встретила Самиру.')

    def test_hash_drift(self):
        with self.assertRaisesRegex(ValueError, 'input drift'):
            apply_name_forms(1, self.text + ' ', self.policy, {1: self.record})

    def test_missing_forms_and_stale_ids(self):
        with self.assertRaisesRegex(ValueError, 'missing reviewed'):
            apply_name_forms(1, self.text, self.policy, {})
        with self.assertRaisesRegex(ValueError, 'stale ID'):
            apply_name_forms(1, 'Нет имён.', self.policy, {1: self.record})

    def test_slot_count_identity_and_order(self):
        record = deepcopy(self.record)
        record['forms'].pop()
        with self.assertRaisesRegex(ValueError, 'count drift'):
            apply_name_forms(1, self.text, self.policy, {1: record})
        for identities in (['Samira', 'Pat'], ['Pat', 'Pat']):
            record = deepcopy(self.record)
            record['english'] = identities
            with self.assertRaisesRegex(ValueError, 'identity/order drift'):
                apply_name_forms(1, self.text, self.policy, {1: record})

    def test_html_attributes_and_metadata_excluded_but_visible_labels_included(self):
        text = '"@story:Pat <link=Samira>Pat</link> {Pat} Samira'
        occurrences = visible_name_occurrences(text, self.policy)
        self.assertEqual([o['english'] for o in occurrences], ['Pat', 'Samira'])
        record = {'id': 7, 'before_sha256': digest(text), 'english': ['Pat', 'Samira'],
                  'forms': ['Пэт', 'Самира']}
        after = apply_name_forms(7, text, self.policy, {7: record})
        self.assertEqual(after, '"@story:Pat <link=Samira>Пэт</link> {Pat} Самира')

    def test_skills_not_localized_even_with_overlapping_name_policy(self):
        policy = {'people': {'Living': 'Живой', 'Ward': 'Страж', 'Pat': 'Пэт'}}
        text = 'Living Ward защищает Pat.'
        self.assertEqual([o['english'] for o in visible_name_occurrences(text, policy)], ['Pat'])
        record = {'id': 8, 'before_sha256': digest(text), 'english': ['Pat'], 'forms': ['Пэт']}
        self.assertEqual(apply_name_forms(8, text, policy, {8: record}), 'Living Ward защищает Пэт.')

    def test_authorial_foreign_terms_retained_without_hiding_personal_names(self):
        policy = {'people': {'Pat': 'Пэт'}, 'extras': {'Puszcza': 'Пуща', 'Mahi': 'Махи',
                  'Porucznik': 'поручик'}, 'retained_visible': ['Puszcza Białowieska',
                  'Mahi', '<b>Porucznik</b>']}
        text = 'Pat: Puszcza Białowieska; Puszcza; <b>Mahi</b>; <b>Porucznik</b>; Porucznik.'
        self.assertEqual([o['english'] for o in visible_name_occurrences(text, policy)],
                         ['Pat', 'Puszcza', 'Porucznik'])

    def test_no_residual_english_or_renderer_delimiters_in_forms(self):
        for form in ('Пэт Pat', 'Пэт|Пэт', '<b>Пэт</b>', 'Пэт\nПэт', '{Пэт}', '"Пэт"'):
            record = deepcopy(self.record)
            record['forms'][0] = form
            with self.subTest(form=form), self.assertRaises(ValueError):
                apply_name_forms(1, self.text, self.policy, {1: record})

    def fixture(self):
        source = {'root': ['^Pat met Samira.', ['^Pat met Samira.'],
                           ['str', '^Pat', '/str', '=='],
                           ['str', '^Pat', '/str', {'x()': 'internal', 'exArgs': 1}],
                           ['str', '^Pat', '/str', {'VAR?': 'name'}, '=='], '^Pat']}
        catalog = [
            {'id': 1, 'source': '^Pat met Samira.', 'body': 'Pat met Samira.', 'prefix': '^',
             'mask': {'⟦T000⟧': 'Pat', '⟦T001⟧': 'Samira'}},
            {'id': 2, 'source': '^Pat', 'body': 'Pat', 'prefix': '^', 'mask': {}},
        ]
        translations = {1: '⟦T000⟧ встретила ⟦T001⟧.', 2: 'Pat'}
        records = {1: deepcopy(self.record),
                   2: {'id': 2, 'before_sha256': digest('Pat'), 'english': ['Pat'], 'forms': ['Пэт']}}
        return source, catalog, translations, records

    def test_all_occurrences_and_comparisons_internal_args_restore(self):
        source, catalog, translations, records = self.fixture()
        expected, audit = canonical_name_story(source, catalog, translations, self.policy, records)
        self.assertEqual(audit['errors'], [])
        self.assertEqual(audit['consumed_registry_ids'], 2)
        self.assertEqual(audit['visible_occurrence_slots'], 5)
        self.assertEqual(audit['restored_technical_literal_count'], 3)
        self.assertEqual(expected['root'][0], '^Пэт встретила Самиру.')
        self.assertEqual(expected['root'][1][0], expected['root'][0])
        self.assertEqual(expected['root'][5], '^Пэт')
        for index in (2, 3, 4):
            self.assertEqual(expected['root'][index][1], '^Pat')
        self.assertEqual(contract_errors(source, expected), [])

    def test_unconsumed_registry_ids_cannot_pass(self):
        source, catalog, translations, records = self.fixture()
        records[99] = deepcopy(self.record)
        _, audit = canonical_name_story(source, catalog, translations, self.policy, records)
        self.assertIn({'id': 99, 'error': 'unconsumed reviewed name ID'}, audit['errors'])

    def test_forms_are_pinned_after_approved_override(self):
        source, catalog, translations, records = self.fixture()
        catalog[0]['mask']['⟦T000⟧'] = 'Wrong'
        overrides = {1: {'source_sha256': digest(catalog[0]['source']),
                         'before_tags': [], 'after_tags': [],
                         'operations': [{'kind': 'proper_name', 'token': '⟦T000⟧',
                                         'before': 'Wrong', 'after': 'Pat'}]}}
        _, audit = canonical_name_story(source, catalog, translations, self.policy, records, overrides)
        self.assertEqual(audit['errors'], [])

    def test_registry_loader_rejects_duplicate_and_incomplete_metadata(self):
        for payload in (
            {'format': 1, 'reviewed_count': 2, 'items': [self.record, self.record]},
            {'format': 1, 'reviewed_count': 5, 'items': [self.record]},
        ):
            with patch.object(Path, 'exists', return_value=True), \
                    patch.object(Path, 'read_text', return_value=json.dumps(payload)):
                with self.assertRaises(ValueError):
                    load_name_forms(Path('fixture'))

    def run_qa(self, source, translated, catalog, translations, records, policy):
        source_path, story_path = Path('source-fixture.json'), Path('story-fixture.json')
        source['root'].append('^wod02Completed')
        translated['root'].append('^wod02Completed')
        catalog[0]['first_path'] = ['root', 0]
        catalog[1]['first_path'] = ['root', 2, 1]
        chunks = {'items': [{'id': item_id, 'translation': text} for item_id, text in translations.items()]}

        def load(path):
            return source if path == source_path else translated if path == story_path else chunks

        with patch.object(qa_translation, 'load_json', side_effect=load), \
                patch.object(qa_translation, 'load_catalog', return_value=catalog), \
                patch.object(qa_translation, 'load_overrides', return_value={}), \
                patch.object(qa_translation, 'load_corrections_audit', return_value=[]), \
                patch.object(qa_translation, 'load_path_restorations', return_value=[]), \
                patch.object(qa_translation, 'load_name_policy', return_value=policy), \
                patch.object(qa_translation, 'load_name_forms', return_value=records), \
                patch.object(qa_translation, 'write_json') as output, \
                patch.object(Path, 'glob', return_value=[Path('chunk-fixture.json')]), \
                patch.object(Path, 'read_bytes', return_value=b'fixture'), \
                patch('sys.argv', ['qa_translation.py', str(source_path), str(story_path),
                                   'localization-fixture', '--report', 'report-fixture.json']), \
                patch('builtins.print'):
            result = qa_translation.main()
            return result, output.call_args.args[1]

    def test_qa_accepts_canonical_names_and_publishes_only_counts_hashes(self):
        source, catalog, translations, records = self.fixture()
        expected, _ = canonical_name_story(source, catalog, translations, self.policy, records)
        result, report = self.run_qa(source, expected, catalog, translations, records, self.policy)
        self.assertEqual(result, 0)
        self.assertTrue(report['passed'])
        self.assertEqual(report['protected_term_mismatches'], [])
        self.assertNotIn('Pat met Samira.', json.dumps(report))
        self.assertEqual(report['name_localization']['error_count'], 0)

    def test_qa_rejects_drift_in_an_alternative_occurrence(self):
        source, catalog, translations, records = self.fixture()
        expected, _ = canonical_name_story(source, catalog, translations, self.policy, records)
        expected['root'][1][0] = '^Пэт увидела Самиру.'
        result, report = self.run_qa(source, expected, catalog, translations, records, self.policy)
        self.assertEqual(result, 2)
        self.assertTrue(any(row['error'] == 'canonical assembled text mismatch'
                            for row in report['name_localization']['errors']))

    def test_qa_without_name_policy_retains_baseline_name_count_gate(self):
        source, catalog, translations, records = self.fixture()
        expected = deepcopy(source)
        expected['root'][0] = '^Pat встретила Samira.'
        expected['root'][1][0] = '^Pat встретила Samira.'
        result, report = self.run_qa(source, expected, catalog, translations, {}, {})
        self.assertEqual(result, 0)
        self.assertFalse(report['name_localization']['enabled'])
        expected['root'][0] = '^Пэт встретила Samira.'
        # A second run must not append a second completion marker to source.
        source['root'].pop()
        expected['root'].pop()
        result, report = self.run_qa(source, expected, catalog, translations, {}, {})
        self.assertEqual(result, 2)
        self.assertTrue(any(row['term'] == 'Pat' for row in report['protected_term_mismatches']))

    def fragment(self, source, path, translation):
        value = source
        for key in path:
            value = value[key]
        return {'path': path, 'source_sha256': digest(value), 'translation': translation,
                'reason': 'Reviewed visible display fragment.'}

    def apply_fragments(self, source, assembled, fragments):
        with patch('name_localization.load_name_fragments', return_value=fragments), \
                patch('name_localization.load_name_policy', return_value=self.policy):
            return apply_name_fragments(source, assembled, Path('fixture'))

    def test_fragment_pins_localize_labels_and_end_story_but_preserve_tags_and_commands(self):
        source = {'root': ['^<link=Pat>Pat</link>', '^>>> END-STORY "Pat <b>spoke</b>.']}
        translated = deepcopy(source)
        fragments = [self.fragment(source, ['root', 0], '^<link=Pat>Пэт</link>'),
                     self.fragment(source, ['root', 1], '^>>> END-STORY "Пэт <b>сказала</b>.')]
        audit = self.apply_fragments(source, translated, fragments)
        self.assertEqual(len(audit), 2)
        self.assertEqual(translated['root'][0], '^<link=Pat>Пэт</link>')
        self.assertEqual(contract_errors(source, translated), [])
        self.assertNotIn('translation', audit[0])
        self.assertNotIn('Pat <b>spoke', json.dumps(audit))

    def test_fragment_validation_is_atomic_and_source_pinned(self):
        source = {'root': ['^Pat.', '^Samira.']}
        translated = deepcopy(source)
        fragments = [self.fragment(source, ['root', 0], '^Пэт.'),
                     self.fragment(source, ['root', 1], '^Самира.')]
        fragments[1]['source_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'source/path drift'):
            self.apply_fragments(source, translated, fragments)
        self.assertEqual(translated, source)

    def test_fragments_cannot_mutate_comparisons_external_args_or_character_metadata(self):
        for source, path in (
            ({'root': ['str', '^Pat', '/str', '==']}, ['root', 1]),
            ({'root': ['str', '^Pat', '/str', {'x()': 'key', 'exArgs': 1}]}, ['root', 1]),
            ({'root': ['^>>> ui "character-name=Pat"']}, ['root', 0]),
        ):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'technical literal|command metadata'):
                self.apply_fragments(source, deepcopy(source), [self.fragment(source, path, '^Пэт')])

    def test_fragments_reject_markup_delimiter_skill_and_residual_name_changes(self):
        for before, after in (
            ('^<b>Pat</b>', '^Пэт'),
            ('^"Pat', '^Пэт'),
            ('^Pat | Samira', '^Пэт и Самира'),
            ('^Pat: Living Ward', '^Пэт: Живой страж'),
            ('^Pat.', '^Pat.'),
        ):
            source = {'root': [before]}
            with self.subTest(before=before), self.assertRaises(ValueError):
                self.apply_fragments(source, deepcopy(source), [self.fragment(source, ['root', 0], after)])

    def test_canonical_qa_applies_the_same_path_pins_after_technical_restoration(self):
        source, catalog, translations, records = self.fixture()
        fragment = self.fragment(source, ['root', 5], '^Пэт!')
        with patch('name_localization.load_name_fragments', return_value=[fragment]), \
                patch('name_localization.load_name_policy', return_value=self.policy):
            expected, audit = canonical_name_story(source, catalog, translations, self.policy, records,
                                                  fragment_directory=Path('fixture'))
        self.assertEqual(expected['root'][5], '^Пэт!')
        self.assertEqual(audit['applied_name_fragment_count'], 1)
        self.assertEqual(expected['root'][2][1], '^Pat')


if __name__ == '__main__':
    unittest.main()
