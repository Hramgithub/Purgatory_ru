"""Guardrails for the tribe-label patch. Not a substitute for Unity visual QA."""
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CreationLabelsContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.code = (ROOT/'src/PurgatoryRu/CreationLabels.cs').read_text(encoding='utf-8-sig')
        cls.policy = (ROOT/'src/PurgatoryRu/CreationLabelPolicy.cs').read_text(encoding='utf-8-sig')

    def test_exact_five_tribe_icon_gate(self):
        icons = re.findall(r'(CharacterCreation_Tribe_\w+)', self.policy)
        self.assertEqual(icons, ['CharacterCreation_Tribe_'+x for x in
            ('BlackFuries', 'BoneGnawers', 'GlassWalkers', 'ShadowLords', 'SilverFangs')])
        self.assertIn('SameIcons(icons, candidate.Icons)', self.policy)
        self.assertIn('actual[index] != expected[index]', self.policy)
        self.assertLess(self.code.index('CreationLabelPolicy.TryGetLines'),
                        self.code.index('CreationLabelStates.GetValue'))

    def test_only_whole_word_breaks_and_no_abbreviations(self):
        groups = re.findall(r'new Group\("([^"]+)",\s*"([^"]+)",\s*"([^"]+)"\)', self.policy)
        labels = {x: x.replace(' ', r'\n') for name, icons, names in groups
                  if name in ('Tribe', 'Patron') for x in names.split('|')}
        self.assertEqual(labels, {'Чёрные Фурии': r'Чёрные\nФурии',
            'Костегрызы': 'Костегрызы', 'Стеклоходы': 'Стеклоходы',
            'Повелители Теней': r'Повелители\nТеней',
            'Серебряные Клыки': r'Серебряные\nКлыки',
            'Зловещая выдра': r'Зловещая\nвыдра',
            'Мистическая рысь': r'Мистическая\nрысь',
            'Бессмертный павлин': r'Бессмертный\nпавлин'})
        for label, lines in labels.items():
            self.assertEqual(lines.replace(r'\n', ' '), label)

    def test_all_eight_story_groups_have_exact_ordered_policies(self):
        groups = re.findall(r'new Group\("([^"]+)",\s*"([^"]+)",\s*"([^"]+)"\)', self.policy)
        self.assertEqual(len(groups), 8)
        self.assertEqual(sum(len(names.split('|')) for _, _, names in groups), 27)
        self.assertIn('plain != matched.Labels[index]', self.policy)
        report = ROOT/'dist/ui-command-report.json'
        if not report.exists():
            self.skipTest('Requires local canonical Ink UI runtime report')
        signatures = {icons: names.split('|') for _, icons, names in groups}
        for command in json.loads(report.read_text(encoding='utf-8-sig'))['commands']:
            fields = command['fields']
            self.assertEqual(signatures[fields[2]], [x.strip('«»') for x in fields[3].split('|')])

    def test_one_size_fits_both_dimensions_with_native_metrics(self):
        for expected in ('text.enableAutoSizing = false', 'text.enableWordWrapping = false',
            'GetPreferredValues(', 'text.rectTransform.rect.width - margin.x - margin.z',
            'text.rectTransform.rect.height - margin.y - margin.w',
            'commonSize = Math.Min(commonSize, state.Size * factor)',
            'labels[index].fontSize = commonSize', 'VerticalAlignmentOptions.Top'):
            self.assertIn(expected, self.code)

    def test_pooled_buttons_restore_layout_before_every_initialization(self):
        for expected in ('Size = text.fontSize', 'Minimum = text.fontSizeMin',
            'Maximum = text.fontSizeMax', 'AutoSize = text.enableAutoSizing',
            'Wrap = text.enableWordWrapping', 'Vertical = text.verticalAlignment',
            'text.enableAutoSizing = AutoSize', 'text.enableWordWrapping = Wrap',
            'CreationLabelStates.Remove(text)',
            'private static void Prefix(Component __instance) => RestoreCreationLabels(__instance)'):
            self.assertIn(expected, self.code)

    def test_two_lines_use_free_band_above_description_not_shallow_native_rect(self):
        for expected in ('AccessTools.Field(CreationWidgetType, "infoDumpText")',
            'rect.InverseTransformPoint(infoTop)', 'float originalHeight = rect.rect.height',
            'if (freeHeight > originalHeight)', 'state.OffsetMin.y - (freeHeight - originalHeight)',
            'text.rectTransform.offsetMin = OffsetMin', 'text.rectTransform.offsetMax = OffsetMax'):
            self.assertIn(expected, self.code)

    def test_hook_does_not_mutate_gameplay_or_internal_option_strings(self):
        for prohibited in ('.name =', 'SetValue(', 'ChoosePathString(', 'EvaluateFunction(',
            'set_result', 'onClick', 'Select(', 'buttonsTexts', 'buttonsDescs', 'variablesState'):
            self.assertNotIn(prohibited, self.code)
        self.assertIn('"InitButtons"', self.code)
        self.assertIn('harmony.PatchAll(typeof(CreationLabelsPatch))',
                      (ROOT/'src/PurgatoryRu/Plugin.cs').read_text(encoding='utf-8-sig'))

    def test_initial_fonts_and_deferred_panel_layout_are_covered(self):
        self.assertIn('RefreshCreationLabels();',
                      (ROOT/'src/PurgatoryRu/Fonts.cs').read_text(encoding='utf-8-sig'))
        self.assertIn('yield return null;', self.code)
        self.assertIn('widget.gameObject.activeInHierarchy', self.code)

    def test_terminology_is_consistent_in_all_current_chunks(self):
        rows = {}
        for path in (ROOT/'localization/ru').glob('chunk-*.json'):
            rows.update({x['id']:x['translation'] for x in json.loads(path.read_bytes())['items']})
        self.assertFalse(any('костеглод' in t.lower() for t in rows.values()))
        self.assertEqual(rows[178], 'Костегрызы')
        self.assertIn('из Костегрызов', rows[488])
        self.assertIn('Остальным Костегрызам', rows[3437])
        self.assertIn('|Костегрызы|', rows[13557])
        self.assertIn('⟦T002⟧дух бетона⟦T003⟧', rows[1294])
        self.assertEqual(rows[915], 'Но меня мучил голод.')

    def test_tribe_motivation_choice_and_all_five_continuations(self):
        rows = {}
        for path in (ROOT/'localization/ru').glob('chunk-*.json'):
            rows.update({x['id']:x['translation'] for x in json.loads(path.read_bytes())['items']})
        self.assertEqual(rows[1298], 'Одна черта этого племени особенно привлекала меня.')
        for item_id, tribe in ((1299, 'Стеклоходов'), (1305, 'Серебряных Клыков'),
            (1310, 'Костегрызов'), (1317, 'Повелителей Теней'), (1322, 'Чёрных Фурий')):
            self.assertEqual(rows[item_id], f' Я выбрала {tribe} по одной причине.')

    def test_column_prose_and_polish_quote_preserve_markup_and_original(self):
        from collections import Counter
        rows = {x['id']:x['translation'] for x in
            json.loads((ROOT/'localization/ru/chunk-0007.json').read_bytes())['items']}
        self.assertIn('На выступавшей над землёй', rows[1340])
        self.assertEqual(Counter(re.findall(r'⟦T\d+⟧', rows[1340])),
                         Counter(f'⟦T{i:03d}⟧' for i in range(8)))
        self.assertEqual(rows[1341],
            '⟦T000⟧Day, ut ia pobrusa, a ti poziwai⟦T001⟧: «Давай я поработаю, а ты отдохни».')
        self.assertEqual(rows[1345], 'Мы были товарищами.')

    def test_garou_name_description_does_not_rewrite_author_name_meanings(self):
        rows = {x['id']:x['translation'] for x in
            json.loads((ROOT/'localization/ru/chunk-0007.json').read_bytes())['items']}
        self.assertIn('Она звала меня ⟦T001⟧именем Гару⟦T002⟧', rows[1349])
        self.assertEqual(rows[1350], 'Zohal — «луна далёкой планеты».')
        self.assertIn('воображала своё родство с', rows[1355])


if __name__ == '__main__':
    unittest.main()
