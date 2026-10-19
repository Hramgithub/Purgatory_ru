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

    def test_exact_five_tribe_icon_gate(self):
        icons = re.findall(r'"(CharacterCreation_Tribe_\w+)"', self.code)
        self.assertEqual(icons, ['CharacterCreation_Tribe_'+x for x in
            ('BlackFuries', 'BoneGnawers', 'GlassWalkers', 'ShadowLords', 'SilverFangs')])
        self.assertIn('icons.Length != TribeIcons.Length', self.code)
        self.assertIn('icons[index] != TribeIcons[index]', self.code)
        self.assertLess(self.code.index('TribeLabelLines.TryGetValue'),
                        self.code.index('CreationLabelStates.GetValue'))

    def test_only_whole_word_breaks_and_no_abbreviations(self):
        labels = dict(re.findall(r'\["([^"]+)"\] = "([^"]+)"', self.code))
        self.assertEqual(labels, {'Чёрные Фурии': r'Чёрные\nФурии',
            'Костегрызы': 'Костегрызы', 'Стеклоходы': 'Стеклоходы',
            'Повелители Теней': r'Повелители\nТеней',
            'Серебряные Клыки': r'Серебряные\nКлыки'})
        for label, lines in labels.items():
            self.assertEqual(lines.replace(r'\n', ' '), label)

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
        self.assertIn('RefreshTribeLabels();',
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


if __name__ == '__main__':
    unittest.main()
