using System;
using System.Collections.Generic;
using System.Reflection;
using HarmonyLib;
using TMPro;
using UnityEngine;

namespace PurgatoryRu;

public sealed partial class Plugin
{
    private static readonly Type? FormWindowType = AccessTools.TypeByName("ChangeForm");
    private static readonly FieldInfo? FormInfoField = FormWindowType == null ? null : AccessTools.Field(FormWindowType, "infoDump");
    private static readonly HashSet<int> AuditedFormDescriptions = new HashSet<int>();
    private static readonly HashSet<int> AuditedFormCanvasBindings = new HashSet<int>();
    private static readonly Dictionary<string, string> FormLabels = new Dictionary<string, string>(StringComparer.Ordinal)
    {
        ["Choose Your Form!"] = "Выберите облик!",
        ["Homid"] = "Хомид",
        ["Glabro"] = "Глабро",
        ["Crinos"] = "Кринос",
        ["Hispo"] = "Хиспо",
        ["Lupus"] = "Люпус"
    };

    private static Component? FormWindow(TMP_Text text) =>
        FormWindowType == null ? null : text.GetComponentInParent(FormWindowType);

    private static bool IsFormDescription(TMP_Text text)
    {
        Component? window = FormWindow(text);
        return window != null && ReferenceEquals(FormInfoField?.GetValue(window), text);
    }

    private static void LocalizeFormLabel(TMP_Text text)
    {
        // Only visible TMP labels inside this exact game window. Never touch
        // GameObject/button names: ChangeForm.Show uses them as internal keys.
        if (FormLabels.TryGetValue(text.text, out string translated) && FormWindow(text) != null)
            text.text = translated;
    }

    private static bool MaterialMatchesFont(Material? material, TMP_FontAsset font, bool allowAdditionalAtlases = false,
        bool allowSoftMaskShader = false)
    {
        if (material == null || font == null || font.material == null ||
            !material.HasProperty("_MainTex")) return false;
        // The game's Soft Mask wrapper is a legitimate final UI material.
        // Admit only its exact wrapper for this font shader; atlas and every
        // SDF metric below must still match. Never replace it with the unmasked
        // base material, and retain strict shader identity everywhere else.
        bool shaderMatches = material.shader == font.material.shader ||
            (allowSoftMaskShader && material.shader != null && font.material.shader != null &&
             material.shader.name == "Soft Mask/" + font.material.shader.name);
        if (!shaderMatches) return false;
        Texture atlas = material.GetTexture("_MainTex");
        bool atlasMatches = atlas == font.atlasTexture;
        if (!atlasMatches && allowAdditionalAtlases)
            foreach (Texture texture in font.atlasTextures) atlasMatches |= atlas == texture;
        if (!atlasMatches) return false;
        // Match SDF metrics, not material identity. A valid masking/stencil
        // instance can differ from font.material and must remain in place.
        foreach (string property in new[] { "_GradientScale", "_TextureWidth", "_TextureHeight" })
        {
            if (!material.HasProperty(property) || !font.material.HasProperty(property) ||
                Math.Abs(material.GetFloat(property) - font.material.GetFloat(property)) > 0.001f) return false;
        }
        return true;
    }

    private static void RepairFormSubMeshes(TMP_Text text)
    {
        if (!IsFormDescription(text) && !IsLocalizedUi(text)) return;
        foreach (TMP_SubMeshUI mesh in text.GetComponentsInChildren<TMP_SubMeshUI>(true))
        {
            TMP_FontAsset font = mesh.fontAsset;
            if (IsRussianFont(font) && !MaterialMatchesFont(mesh.sharedMaterial, font, true))
                mesh.sharedMaterial = font.material;
        }
    }

    private static void BindFormCanvasAtlas(TextMeshProUGUI text, bool diagnosticProbe = false)
    {
        if (!fontsReady || text == null || !IsRussianFont(text.font) ||
            (!diagnosticProbe && (!text.isActiveAndEnabled || text.canvas == null)) ||
            !ContainsCyrillic(text.text) || (!diagnosticProbe && !IsFormDescription(text) && !IsLocalizedUi(text))) return;
        Material shared = text.fontSharedMaterial;
        // In this game's TMP build, changing the font while ParseInputText is
        // already rebuilding graphics can lose SetMaterialDirty. Mesh metadata
        // then looks correct while the CanvasRenderer still draws the old atlas.
        // Use the normal stencil/masking material, not the unmasked font material.
        Material rendered = text.materialForRendering;
        bool uiMask = !IsFormDescription(text) && IsLocalizedUi(text);
        if (!MaterialMatchesFont(shared, text.font) || !MaterialMatchesFont(rendered, text.font, allowSoftMaskShader: uiMask))
        {
            log?.LogError("Form canvas binding skipped: final font/material atlas is inconsistent.");
            return;
        }
        CanvasRenderer renderer = text.canvasRenderer;
        Material previous = renderer.materialCount > 0 ? renderer.GetMaterial(0) : null!;
        bool previousMismatch = !MaterialMatchesFont(previous, text.font, allowSoftMaskShader: uiMask);
        renderer.materialCount = 1;
        renderer.SetMaterial(rendered, 0);
        // Legacy EnableMasking / outline APIs can also pin a texture separately
        // from Material._MainTex. A material-only replacement does not clear it.
        renderer.SetTexture(shared.GetTexture("_MainTex"));
        if (!diagnosticProbe && AuditedFormCanvasBindings.Add(text.text.GetHashCode()))
            log?.LogInfo($"Form final canvas binding: previousMaterialMismatch={previousMismatch}; boundMaterialMatches={MaterialMatchesFont(renderer.GetMaterial(0), text.font, allowSoftMaskShader: uiMask)}; explicitAtlasTexture=true; characters={text.textInfo.characterCount}.");
    }

    [HarmonyPatch(typeof(TextMeshProUGUI), "OnPreRenderCanvas")]
    private static class FormCanvasPreRenderPatch
    {
        private static void Postfix(TextMeshProUGUI __instance) => BindFormCanvasAtlas(__instance);
    }

    [HarmonyPatch(typeof(TextMeshProUGUI), "UpdateMaterial")]
    private static class FormCanvasMaterialPatch
    {
        private static void Postfix(TextMeshProUGUI __instance) => BindFormCanvasAtlas(__instance);
    }

    private static int AtlasMismatches(TMP_TextInfo info)
    {
        int failures = 0;
        for (int index = 0; index < info.characterCount; index++)
        {
            TMP_CharacterInfo character = info.characterInfo[index];
            if (!character.isVisible || character.elementType != TMP_TextElementType.Character) continue;
            TMP_FontAsset font = character.fontAsset;
            if (!IsRussianFont(font))
            {
                if (character.character >= '\u0400' && character.character <= '\u052f') failures++;
                continue;
            }
            int materialIndex = character.materialReferenceIndex;
            if (materialIndex < 0 || materialIndex >= info.meshInfo.Length ||
                character.textElement?.glyph == null) { failures++; continue; }
            int atlasIndex = character.textElement.glyph.atlasIndex;
            Material material = info.meshInfo[materialIndex].material;
            if (atlasIndex < 0 || atlasIndex >= font.atlasTextures.Length || material == null ||
                !material.HasProperty("_MainTex") ||
                material.GetTexture("_MainTex") != font.atlasTextures[atlasIndex]) failures++;
        }
        return failures;
    }

    private bool ValidateFormFontMaterial()
    {
        var probeObject = new GameObject("PurgatoryRu Form Font QA", typeof(RectTransform), typeof(Canvas));
        probeObject.hideFlags = HideFlags.HideAndDontSave;
        // TMP UGUI refuses to generate a mesh without a Canvas ancestor.
        // A disabled Canvas makes this runtime self-test entirely invisible.
        probeObject.GetComponent<Canvas>().enabled = false;
        try
        {
            var textObject = new GameObject("PurgatoryRu Form Probe", typeof(RectTransform));
            textObject.hideFlags = HideFlags.HideAndDontSave;
            textObject.transform.SetParent(probeObject.transform, false);
            var probe = textObject.AddComponent<TextMeshProUGUI>();
            probe.rectTransform.sizeDelta = new Vector2(784, 73);
            probe.font = russianRegular;
            probe.fontSize = 24;
            probe.enableAutoSizing = false;
            probe.text = "Проверка <b>жирного</b>, <i>курсивного</i> и <b><i>жирного курсива</i></b>.";
            // Regression: correct primary font but deliberately wrong atlas.
            // The previous font-only guard silently left this material intact.
            probe.fontSharedMaterial = ownedFonts[2].material;
            ApplyConsistentFont(probe);
            probe.ForceMeshUpdate(true, true);
            probe.canvasRenderer.materialCount = 1;
            probe.canvasRenderer.SetMaterial(ownedFonts[2].material, 0);
            probe.canvasRenderer.SetTexture(ownedFonts[2].atlasTexture);
            BindFormCanvasAtlas(probe, true);
            bool passed = MaterialMatchesFont(probe.fontSharedMaterial, russianRegular!) &&
                probe.textInfo.characterCount > 0 && AtlasMismatches(probe.textInfo) == 0 &&
                MaterialMatchesFont(probe.canvasRenderer.GetMaterial(0), russianRegular!);
            // A compatible clone (as used for UI masking) must not be reset.
            var maskingMaterial = new Material(russianRegular!.material);
            try
            {
                probe.fontSharedMaterial = maskingMaterial;
                ApplyConsistentFont(probe);
                passed &= probe.fontSharedMaterial == maskingMaterial;
                probe.ForceMeshUpdate(true, true);
                BindFormCanvasAtlas(probe, true);
                passed &= probe.canvasRenderer.GetMaterial(0) == maskingMaterial;
                passed &= AtlasMismatches(probe.textInfo) == 0;
            }
            finally { Destroy(maskingMaterial); }
            if (passed) Logger.LogInfo("Form UGUI font QA OK: stale font and final CanvasRenderer materials repaired; atlas explicitly rebound; bold/italic runs coherent; compatible material instance retained.");
            else Logger.LogError("Form UGUI font QA FAILED: material/atlas mismatch or compatible material lost.");
            return passed;
        }
        catch (Exception exception)
        {
            Logger.LogError($"Form UGUI font QA could not complete: {exception.GetType().Name}: {exception.Message}");
            return false;
        }
        finally { Destroy(probeObject); }
    }

    private static void AuditFormFontRun(TMP_TextInfo info)
    {
        TMP_Text text = info.textComponent;
        if (!IsFormDescription(text) || string.IsNullOrWhiteSpace(text.text) ||
            !AuditedFormDescriptions.Add(text.text.GetHashCode())) return;
        int failures = AtlasMismatches(info);
        string message = $"Form infoDump render QA: characters={info.characterCount}; materials={info.materialCount}; atlasMismatches={failures}; overflow={text.isTextOverflowing}; size={text.fontSize:F2}; rect={text.rectTransform.rect.width:F1}x{text.rectTransform.rect.height:F1}.";
        if (failures == 0) log?.LogInfo(message); else log?.LogError(message);
    }
}
