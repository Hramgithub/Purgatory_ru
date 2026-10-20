"""Static regressions; neither these nor console tests execute Unity graphics."""
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class InlineSpritesAndMoonContracts(unittest.TestCase):
    def test_sprite_guard_precedes_font_submesh_material_repair(self):
        code=(ROOT/'src/PurgatoryRu/Forms.cs').read_text(encoding='utf-8-sig')
        body=code.split('private static void RepairFormSubMeshes(',1)[1].split('private static void BindFormCanvasAtlas(',1)[0]
        self.assertLess(body.index('if (mesh.spriteAsset != null) continue;'),body.index('TMP_FontAsset font = mesh.fontAsset;'))
        self.assertLess(body.index('if (mesh.spriteAsset != null) continue;'),body.index('mesh.sharedMaterial = font.material;'))
        self.assertIn('if (!diagnosticProbe && !IsFormDescription(text) && !IsLocalizedUi(text)) return;',body)

    def test_delayed_hidden_probe_covers_all_story_sprite_names(self):
        code=(ROOT/'src/PurgatoryRu/InlineSprites.cs').read_text(encoding='utf-8-sig')
        expected={'health','willpower','blank','rage','harano','circle','circle-filled'}
        names=set(re.findall(r'"([a-z-]+)"',code.split('InlineSpriteNames =',1)[1].split(';',1)[0]))
        self.assertEqual(names,expected)
        story=ROOT/'dist/content/wod02.json'
        if story.exists():
            from translate_ink_gpt import walk
            actual={name for _,value in walk(json.loads(story.read_text(encoding='utf-8-sig')))
                    if isinstance(value,str) for name in re.findall(r'<sprite[^>]*name=[\x22\x27]?([\w-]+)',value)}
            self.assertEqual(actual,expected)
        for contract in ('GetComponent<Canvas>().enabled = false', 'HideFlags.HideAndDontSave',
            'probe.ForceMeshUpdate(true, true)', 'RepairFormSubMeshes(probe, true)',
            'IsRussianFont(mesh.fontAsset)', 'pair.Key.sharedMaterial == pair.Value',
            'character.elementType != TMP_TextElementType.Sprite', 'asset.spriteSheet',
            'AtlasMismatches(probe.textInfo) == 0', 'sprites == InlineSpriteNames.Length',
            'Destroy(root)', 'Destroy(material)', 'Inline sprite QA deferred'):
            self.assertIn(contract,code)
        fonts=(ROOT/'src/PurgatoryRu/Fonts.cs').read_text(encoding='utf-8-sig')
        self.assertIn('StartCoroutine(ValidateInlineSpritesWhenAvailable());',fonts)

    def test_all_eight_game_phase_literals_have_display_translations(self):
        code=(ROOT/'src/PurgatoryRu/MoonPhaseLocalizer.cs').read_text(encoding='utf-8-sig')
        phases=set(re.findall(r'\["([^"]+)"\]',code))
        self.assertEqual(phases,{'new moon','waxing crescent','first quarter','waxing gibbous',
            'full moon','waning gibbous','last quarter','waning crescent'})
        inventory=ROOT/'work/ui-coverage/managed-strings.json'
        if inventory.exists():
            rows=json.loads(inventory.read_text(encoding='utf-8-sig'))['records']
            actual={row['text'] for row in rows if row['type']=='PlayerState' and row['method']=='InitStats'
                    and re.search(r'\b(moon|crescent|quarter|gibbous)\b',row['text'])}
            self.assertEqual(actual,phases)
        localizer=(ROOT/'src/PurgatoryRu/UiTextLocalizer.cs').read_text(encoding='utf-8-sig')
        self.assertIn('MoonPhaseLocalizer.TryTranslate(core, out string moonPhase)',localizer)
        for forbidden in ('variablesState','setMoonphase','SetValue(', 'File.', 'PlayerState', 'ChoosePathString('):
            self.assertNotIn(forbidden,code.split('internal static class',1)[1])


if __name__=='__main__':
    unittest.main()
