import unittest

from renderer_commands import command_arguments, contract_errors, technical_literal_paths
from copy import deepcopy


class CommandArgumentsTests(unittest.TestCase):
    def test_comparison_and_real_external_args_not_visible_labels(self):
        source = ['ev', {'VAR?': 'mode'}, 'str', '^balanced', '/str', '==',
                  'str', '^Visible label', '/str', {'x()': 'getForm'},
                  'str', '^glabro', '/str', '==',
                  'str', '^internal-key', '/str', {'x()': 'getKeyForAction', 'exArgs': 1}]
        records = technical_literal_paths(source)
        self.assertEqual({r['literal'] for r in records}, {'^balanced', '^glabro', '^internal-key'})
        translated = deepcopy(source)
        translated[7] = '^Видимая строка'
        self.assertEqual(contract_errors(source, translated), [])
        translated[3] = '^средний уровень'
        self.assertEqual(len(contract_errors(source, translated)), 1)
    def test_margin_ascii_quote_and_social_summary_keys_all_occurrences(self):
        source = ['^^"', 'ev', {'f()': 'haranoMargin'}, 'out', '/ev',
                  '^" "Visible choice"', '\n', '^>>> ui-social-choices', '\n', '<>',
                  '^ 1-monster 1-monster 3', '\n', '<>', '^ eye "English"',
                  {'other': ['^^"', 'ev', {'f()': 'rageMargin'}, 'out', '/ev',
                             '^" @story:rage=+1 text', None]}]
        translated = deepcopy(source)
        translated[5] = '^" «Видимый выбор»'
        translated[13] = '^ eye "Перевод"'
        self.assertEqual(contract_errors(source, translated), [])
        translated[5] = '^« «Видимый выбор»'
        translated[10] = '^ 1-монстр 1-монстр 3'
        translated[13] = '^ глаз "Перевод"'
        translated[14]['other'][5] = '^« @story:rage=+1 текст'
        self.assertEqual(len(contract_errors(source, translated)), 4)
    def test_glued_arguments_survive_inline_output(self):
        story = [
            '^>>> ui-character-creation', '\n', '<>', '^ "Description ',
            'ev', 'str', '^<sprite name=harano>', '/str', 'out', '/ev',
            '^continued text', '\n', '<>', '^ end."', '\n', '<>',
            '^ "Low|Medium|High"', '\n', '<>', '^ "Fight! +',
            'ev', 'str', '^<sprite name=rage>', '/str', 'out', '/ev',
            '^|Despair! +', '^"', '\n', '^Narrative, not a parameter.',
        ]
        result = command_arguments(story)
        self.assertIn('^ "Low|Medium|High"', result)
        self.assertIn('^ "Fight! +', result)
        self.assertIn('^continued text', result)
        self.assertIn('^"', result)
        self.assertNotIn('^Narrative, not a parameter.', result)

    def test_inline_branch_inherits_command_but_next_line_does_not(self):
        story = [
            '^>>> ui', '\n', '<>', '^ "',
            ['ev', True, '/ev', {'b': ['^branch text', None]}],
            '^"', '\n', '^normal line', '\n', '<>', '^more narrative',
        ]
        result = command_arguments(story)
        self.assertIn('^branch text', result)
        self.assertNotIn('^normal line', result)
        self.assertNotIn('^more narrative', result)


if __name__ == '__main__':
    unittest.main()
