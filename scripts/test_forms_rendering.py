"""Source-contract regressions. These do not claim to execute Unity graphics.

Actual UGUI/atlas assertions live in ValidateFormFontMaterial inside the plugin;
Test-InkForms.ps1 separately executes the installed game's Ink runtime.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class FormsRenderingContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fonts = (ROOT / "src/PurgatoryRu/Fonts.cs").read_text(encoding="utf-8-sig")
        cls.forms = (ROOT / "src/PurgatoryRu/Forms.cs").read_text(encoding="utf-8-sig")

    def test_material_guard_is_independent_of_font_change(self):
        # Regression: matching font must not bypass a stale material repair.
        changed_font = re.search(
            r"if \(text.font != russianRegular\)\s*\{\s*text.font = russianRegular;\s*\}",
            self.fonts,
        )
        self.assertIsNotNone(changed_font)
        following = self.fonts[changed_font.end():]
        self.assertRegex(following, r"if \(!MaterialMatchesFont\(text.fontSharedMaterial, russianRegular\)\)")
        self.assertIn("text.fontSharedMaterial = russianRegular.material;", following)

    def test_material_policy_checks_atlas_shader_and_sdf_metrics(self):
        for required in (
            'material.shader != font.material.shader',
            'material.GetTexture("_MainTex")',
            'font.atlasTexture',
            '"_GradientScale"', '"_TextureWidth"', '"_TextureHeight"',
            'allowAdditionalAtlases', 'font.atlasTextures',
        ):
            self.assertIn(required, self.forms)
        # Equivalent stencil instances must not be rejected for their identity.
        self.assertNotIn("material != font.material", self.forms)
        self.assertNotIn("material == font.material", self.forms)

    def test_only_static_visible_form_labels_are_localized(self):
        labels = self.forms.split("FormLabels =", 1)[1].split("};", 1)[0]
        self.assertEqual(
            set(re.findall(r'\["([^"]+)"\]', labels)),
            {"Choose Your Form!", "Homid", "Glabro", "Crinos", "Hispo", "Lupus"},
        )
        self.assertIn("FormWindow(text) != null", self.forms)
        self.assertIn('AccessTools.TypeByName("ChangeForm")', self.forms)
        self.assertIn('AccessTools.Field(FormWindowType, "infoDump")', self.forms)
        self.assertNotRegex(self.forms, r"\bname\s*=")
        for prohibited in ("ChoosePathString(", "EvaluateFunction(", "Select(", "Application.Quit("):
            self.assertNotIn(prohibited, self.forms)

    def test_hidden_ugui_probe_covers_original_failure_and_masking(self):
        for required in (
            "typeof(Canvas)", "GetComponent<Canvas>().enabled = false",
            "HideFlags.HideAndDontSave", "AddComponent<TextMeshProUGUI>()",
            "probe.fontSharedMaterial = ownedFonts[2].material",
            "probe.ForceMeshUpdate(true, true)",
            "AtlasMismatches(probe.textInfo) == 0",
            "probe.fontSharedMaterial == maskingMaterial",
            "Destroy(probeObject)", "Destroy(maskingMaterial)",
        ):
            self.assertIn(required, self.forms)
        self.assertIn("<b><i>", self.forms)

    def test_final_canvas_binding_is_scoped_to_russian_form_description(self):
        binding = self.forms.split('private static void BindFormCanvasAtlas(', 1)[1].split('\n    [HarmonyPatch', 1)[0]
        for required in ('!fontsReady', 'text == null', '!IsRussianFont(text.font)',
                         '!ContainsCyrillic(text.text)', '!IsFormDescription(text)',
                         '!MaterialMatchesFont(shared, text.font)',
                         '!MaterialMatchesFont(rendered, text.font)'):
            self.assertIn(required, binding)
        # Bind only native draw state: never advance story, regenerate meshes,
        # change the font or recursively ask TMP to update the material.
        for prohibited in ('ForceMeshUpdate(', 'UpdateMaterial(', 'text.font =',
                           'ChoosePathString(', 'EvaluateFunction('):
            self.assertNotIn(prohibited, binding)

    def test_final_binding_keeps_stencil_material_and_rebinds_native_texture(self):
        binding = self.forms.split('private static void BindFormCanvasAtlas(', 1)[1].split('\n    [HarmonyPatch', 1)[0]
        self.assertIn('Material rendered = text.materialForRendering;', binding)
        self.assertIn('renderer.GetMaterial(0)', binding)
        count = binding.index('renderer.materialCount = 1;')
        material = binding.index('renderer.SetMaterial(rendered, 0);')
        texture = binding.index('renderer.SetTexture(shared.GetTexture("_MainTex"));')
        self.assertLess(count, material)
        self.assertLess(material, texture)
        self.assertNotIn('renderer.SetMaterial(text.font.material', binding)
        self.assertNotIn('renderer.SetMaterial(shared,', binding)

    def test_both_final_render_hooks_are_postfixes_and_registered(self):
        plugin = (ROOT / 'src/PurgatoryRu/Plugin.cs').read_text(encoding='utf-8-sig')
        for method, patch in (('OnPreRenderCanvas', 'FormCanvasPreRenderPatch'),
                              ('UpdateMaterial', 'FormCanvasMaterialPatch')):
            self.assertIn(f'[HarmonyPatch(typeof(TextMeshProUGUI), "{method}")]', self.forms)
            block = self.forms.split(f'private static class {patch}', 1)[1].split('\n    }', 1)[0]
            self.assertIn('private static void Postfix(TextMeshProUGUI __instance)', block)
            self.assertIn('BindFormCanvasAtlas(__instance)', block)
            self.assertIn(f'harmony.PatchAll(typeof({patch}));', plugin)
        # OnPreRenderCanvas is required independently: TMP can suppress dirty
        # material flags during its own graphics rebuild, skipping UpdateMaterial.

    def test_hidden_probe_injects_wrong_native_material_and_texture_then_checks_binding(self):
        for required in ('probe.canvasRenderer.SetMaterial(ownedFonts[2].material, 0);',
                         'probe.canvasRenderer.SetTexture(ownedFonts[2].atlasTexture);',
                         'BindFormCanvasAtlas(probe, true);',
                         'MaterialMatchesFont(probe.canvasRenderer.GetMaterial(0), russianRegular!)',
                         'probe.canvasRenderer.GetMaterial(0) == maskingMaterial'):
            self.assertIn(required, self.forms)

    def test_release_privacy_still_enabled(self):
        project = (ROOT / "src/PurgatoryRu/PurgatoryRu.csproj").read_text(encoding="utf-8-sig")
        for required in ("<DebugType>none</DebugType>", "<DebugSymbols>false</DebugSymbols>",
                         "<Deterministic>true</Deterministic>", "<PathMap>",
                         '<Reference Include="UnityEngine.UIModule">'):
            self.assertIn(required, project)


if __name__ == "__main__":
    unittest.main()
