"""Contracts for missing map labels and final-view UI translation.

Does not replace live Unity layout/atlas QA. Original game is optional.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import unittest
from unittest.mock import patch

from translate_ink_gpt import SKILLS_AND_GIFTS, split_visible, walk
from translation_catalog import load_catalog

ROOT = Path(__file__).resolve().parents[1]


class UiCoverageContracts(unittest.TestCase):
    def test_map_labels_keep_the_complete_internal_prefix(self):
        for marker, label in [('aleksander', 'Talk about: A Sept Divided'),
                              ('room2', 'Search'), ('afghanwoman2', 'Talk')]:
            self.assertEqual(split_visible('^@'+marker+' '+label, False, set()),
                             ('^@'+marker+' ', label))

    def test_map_filter_does_not_capture_commands_or_costs(self):
        for source in ('^@computer @10', '^@computer  @10', '^@@computer Search',
                       '^>>> ui-character-creation "Search"', '^$TAB$ Map'):
            self.assertIsNone(split_visible(source, False, set()))
        prefix, text = split_visible('^@story:pat Some text', False, set())
        self.assertEqual((prefix, text), ('^@story:pat ', 'Some text'))

    def test_appended_map_ids_are_contiguous_and_metadata_free(self):
        index = json.loads((ROOT/'localization/index.json').read_text(encoding='utf-8-sig'))['items']
        additions = index[14067:]
        chunk = json.loads((ROOT/'localization/ru/chunk-0064.json').read_text(encoding='utf-8-sig'))['items']
        self.assertEqual([x['id'] for x in additions], list(range(14067, 14082)))
        self.assertEqual([x['id'] for x in chunk], [x['id'] for x in additions])
        for record in additions:
            self.assertRegex(record['prefix'], r'^\^@[A-Za-z][A-Za-z0-9_-]* $')
            self.assertEqual(record['mask'], {})
        self.assertEqual(Counter(x['translation'] for x in chunk), Counter({
            'Обсудить: Раскол в септе': 1, 'Обсудить: Мрачные вести': 1,
            'Обсудить: Городская тревога': 1, 'Поговорить': 3, 'Осмотреть': 9}))

    def test_ui_dictionary_preserves_markup_and_protected_game_terms(self):
        data = json.loads((ROOT/'localization/ui-strings.json').read_text(encoding='utf-8-sig'))
        self.assertEqual(data['format'], 1)
        strings = data['strings']
        self.assertEqual(len(strings), len({x.casefold() for x in strings}))
        for source, target in strings.items():
            self.assertTrue(target.strip())
            self.assertRegex(target, '[А-Яа-яЁё]')
            self.assertEqual(Counter(re.findall(r'<[^>]+>', source)),
                             Counter(re.findall(r'<[^>]+>', target)), source)
            self.assertEqual(source.count('\n'), target.count('\n'), source)
            self.assertEqual(source.count('\r'), target.count('\r'), source)
            self.assertEqual(source.count('|'), target.count('|'), source)
        for protected in SKILLS_AND_GIFTS + ['mahi', 'Puszcza Białowieska']:
            self.assertNotIn(protected.casefold(), {x.casefold() for x in strings})

    def test_runtime_changes_the_final_tmp_display_not_game_state(self):
        code = (ROOT/'src/PurgatoryRu/UiText.cs').read_text(encoding='utf-8-sig')
        fonts = (ROOT/'src/PurgatoryRu/Fonts.cs').read_text(encoding='utf-8-sig')
        plugin = (ROOT/'src/PurgatoryRu/Plugin.cs').read_text(encoding='utf-8-sig')
        self.assertIn('text.text = translated', code)
        self.assertIn('LocalizeVisibleUiText(text)', fonts)
        self.assertIn('"ParseInputText"', fonts)
        self.assertIn('LoadUiStrings();', plugin)
        for forbidden in ('ChoosePathString(', 'variablesState', 'PlayerPrefs',
                          '.name =', 'SetValue(', 'onClick', 'File.Write'):
            self.assertNotIn(forbidden, code)

    def test_localized_ui_uses_the_existing_guarded_atlas_repair(self):
        code = (ROOT/'src/PurgatoryRu/Forms.cs').read_text(encoding='utf-8-sig')
        self.assertIn('!IsFormDescription(text) && !IsLocalizedUi(text)', code)
        self.assertIn('!ContainsCyrillic(text.text)', code)
        self.assertIn('MaterialMatchesFont(rendered, text.font, allowSoftMaskShader: uiMask)', code)

    def test_final_ui_soft_mask_keeps_its_native_shader_and_sdf_checks(self):
        code = (ROOT/'src/PurgatoryRu/Forms.cs').read_text(encoding='utf-8-sig')
        for contract in ('bool allowSoftMaskShader = false',
                         'material.shader.name == "Soft Mask/" + font.material.shader.name',
                         'bool uiMask = !IsFormDescription(text) && IsLocalizedUi(text)',
                         'renderer.SetMaterial(rendered, 0)',
                         'Math.Abs(material.GetFloat(property) - font.material.GetFloat(property))'):
            self.assertIn(contract, code)

    def test_package_requires_and_copies_the_ui_dictionary(self):
        code = (ROOT/'scripts/build_package.ps1').read_text(encoding='utf-8-sig')
        self.assertIn('localization\\ui-strings.json', code)
        self.assertGreaterEqual(code.count('$UiStrings'), 3)
        self.assertIn('$uiCoverageQa.live_review.passed -ne $true', code)
        self.assertIn('$uiCoverageQa.ui_dictionary_sha256 -ne', code)
        self.assertIn('$uiCoverageQa.plugin_sha256 -ne', code)
        self.assertIn('UI-COVERAGE-QA.json', code)

    def test_console_assertion_failures_are_caught(self):
        code = (ROOT/'tests/UiTextCoreTests/Program.cs').read_text(encoding='utf-8-sig')
        project = (ROOT/'tests/UiTextCoreTests/UiTextCoreTests.csproj').read_text(encoding='utf-8-sig')
        self.assertIn('catch (Exception error)', code)
        self.assertIn('Environment.ExitCode = 1', code)
        self.assertIn('<UseAppHost>false</UseAppHost>', project)

    def test_ui_dictionary_bytes_match_the_live_receipt_on_windows_too(self):
        attributes = (ROOT/'.gitattributes').read_text(encoding='utf-8-sig')
        self.assertIn('localization/ui-*.json -text', attributes)
        receipt = json.loads((ROOT/'localization/ui-coverage-review.json').read_text(encoding='utf-8-sig'))
        actual = hashlib.sha256((ROOT/'localization/ui-strings.json').read_bytes()).hexdigest()
        self.assertEqual(receipt['ui_dictionary_sha256'], actual)
        self.assertEqual(receipt['live_review']['ui_dictionary_sha256'], actual)

    def test_single_word_ui_fit_is_narrow_reentrant_and_restorable(self):
        code = (ROOT/'src/PurgatoryRu/UiText.cs').read_text(encoding='utf-8-sig')
        for contract in ('value.Length <= 40', 'uiLocalizer.IsLocalizedValue(value)',
                         'value.IndexOfAny', 'MeasuringUiLabels.Add(id)',
                         'finally { MeasuringUiLabels.Remove(id); }',
                         'text.enableWordWrapping = false', 'state.Size * factor',
                         'previous.Restore(text); UiLabelLayouts.Remove(text)'):
            self.assertIn(contract, code)

    def test_hud_uses_native_heading_budget_without_moving_bars(self):
        code = (ROOT/'src/PurgatoryRu/UiText.cs').read_text(encoding='utf-8-sig')
        self.assertIn('{ "Rage", "Willpower", "Harano", "Health" }', code)
        self.assertIn('Math.Min(width, native.Width)', code)
        self.assertIn('text.GetPreferredValues(text.text,', code)
        for forbidden in ('anchoredPosition =', 'offsetMin =', 'offsetMax =', '.sizeDelta ='):
            self.assertNotIn(forbidden, code)

    def test_public_index_reconstructs_all_original_map_labels(self):
        path = ROOT/'work/english_ink/wod02__resources__67.json'
        if not path.exists():
            self.skipTest('Requires local extracted Steam game')
        story = json.loads(path.read_text(encoding='utf-8-sig'))
        # Exercise the public-index fallback without touching the ignored
        # local catalog or creating private temporary game-source files.
        with patch.object(Path, 'exists', return_value=False):
            catalog = load_catalog(ROOT/'localization', story)
        indexed = {x['source'] for x in catalog}
        for _, value in walk(story):
            if isinstance(value, str) and re.match(r'^\^@[A-Za-z][A-Za-z0-9_-]*\s+[^@\n]', value):
                self.assertIn(value, indexed)
        for record in catalog[14067:]:
            self.assertEqual(record['source'], record['prefix']+record['body'])
            self.assertEqual(hashlib.sha256(record['source'].encode()).hexdigest(), record['source_sha256'])


if __name__ == '__main__':
    unittest.main()
