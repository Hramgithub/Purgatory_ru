import unittest

from renderer_commands import command_arguments


class CommandArgumentsTests(unittest.TestCase):
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
