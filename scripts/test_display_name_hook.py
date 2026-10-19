"""Static guardrails for display-only hooks, not a Unity execution test."""
import json
from pathlib import Path
import re
import unittest

from translate_ink_gpt import SKILLS_AND_GIFTS

ROOT = Path(__file__).resolve().parents[1]


class DisplayNameHookContracts(unittest.TestCase):
    def test_hook_targets_only_exact_tmp_display_value(self):
        code = (ROOT / 'src/PurgatoryRu/DisplayNames.cs').read_text(encoding='utf-8-sig')
        self.assertEqual(re.findall(r'\[HarmonyPatch\(([^\n]+)\)\]', code),
                         ['typeof(TMP_Text), "set_text"'])
        self.assertIn('new(StringComparer.Ordinal)', code)
        self.assertIn('displayNames.TryGetValue(__0, out string translated)', code)
        self.assertIn('__0 = translated;', code)
        for unsafe in ('TMP_InputField', '.Replace(', 'GameState.', 'ChoosePathString(',
                       'EvaluateFunction(', 'variablesState[', '.name =', 'SetVariable('):
            self.assertNotIn(unsafe, code)

    def test_loader_runs_before_hook_registration(self):
        code = (ROOT / 'src/PurgatoryRu/Plugin.cs').read_text(encoding='utf-8-sig')
        self.assertLess(code.index('LoadDisplayNames();'),
                        code.index('harmony.PatchAll(typeof(DisplayNameTextPatch));'))

    def test_retained_visible_names_are_excluded_from_runtime_dictionary(self):
        code = (ROOT / 'src/PurgatoryRu/DisplayNames.cs').read_text(encoding='utf-8-sig')
        self.assertIn('new HashSet<string>(StringComparer.Ordinal)', code)
        self.assertIn('policy["retained_visible"] is JArray originals', code)
        self.assertIn('retained.Add((string)original!)', code)
        self.assertRegex(code, r'if \(entry.Value.Type == JTokenType.String && !retained.Contains\(entry.Name\)\)\s*displayNames\[entry.Name\]')
        policy = json.loads((ROOT / 'localization/name-localization.json').read_text(encoding='utf-8-sig'))
        names = {**policy.get('people', {}), **policy.get('packs', {}), **policy.get('extras', {})}
        retained = set(policy.get('retained_visible', []))
        self.assertTrue({'Narew', 'Budy', 'Teremiski', 'Mahi'} <= retained)
        lookup = {key: value for key, value in names.items() if key not in retained}
        for name in retained:
            self.assertNotIn(name, lookup)
        self.assertEqual(lookup['Samira'], 'Самира')

    def test_portable_payload_and_recursive_installer_include_name_policy(self):
        builder = (ROOT / 'scripts/build_package.ps1').read_text(encoding='utf-8-sig')
        installer = (ROOT / 'installer/Install-PurgatoryRu.ps1').read_text(encoding='utf-8-sig')
        self.assertIn("$NamePolicy = Join-Path $Root 'localization\\name-localization.json'", builder)
        self.assertIn("Copy-Item -LiteralPath $NamePolicy -Destination (Join-Path $PluginDir 'name-localization.json')", builder)
        self.assertIn("$PluginDir = Join-Path $Payload 'BepInEx\\plugins\\PurgatoryRu'", builder)
        self.assertIn('Get-ChildItem -LiteralPath $PayloadRoot -Recurse -File', installer)
        self.assertIn('Copy-Item -LiteralPath $_.FullName -Destination $destination -Force', installer)

    def test_runtime_json_dependency_comes_from_game_and_is_not_redistributed(self):
        project = (ROOT / 'src/PurgatoryRu/PurgatoryRu.csproj').read_text(encoding='utf-8-sig')
        reference = re.search(r'<Reference Include="Newtonsoft.Json">(.*?)</Reference>', project, re.S)
        self.assertIsNotNone(reference)
        self.assertIn(r'$(GameManagedDir)\Newtonsoft.Json.dll', reference[1])
        self.assertIn('<Private>false</Private>', reference[1])

    def test_name_dictionary_does_not_translate_a_protected_skill_title(self):
        policy = json.loads((ROOT / 'localization/name-localization.json').read_text(encoding='utf-8-sig'))
        names = {**policy.get('people', {}), **policy.get('packs', {}), **policy.get('extras', {})}
        self.assertFalse(set(names) & set(SKILLS_AND_GIFTS))
        for english, russian in names.items():
            self.assertIsInstance(russian, str, english)
            self.assertRegex(russian, '[А-Яа-яЁё]', english)
            self.assertFalse(re.search(r'[<>|\r\n"{}]', russian), english)


if __name__ == '__main__':
    unittest.main()
