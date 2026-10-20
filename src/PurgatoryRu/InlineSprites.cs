using System;
using System.Collections;
using System.Collections.Generic;
using TMPro;
using UnityEngine;

namespace PurgatoryRu;

public sealed partial class Plugin
{
    // Every named inline sprite found in the canonical story, including stat
    // icons and the filled/empty pips. No sprite names or UVs are translated.
    private static readonly string[] InlineSpriteNames =
        { "health", "willpower", "blank", "rage", "harano", "circle", "circle-filled" };

    private IEnumerator ValidateInlineSpritesWhenAvailable()
    {
        // The main menu need not load the game's story sprite sheet. Wait for
        // its native asset without loading a scene or changing game state.
        for (int frame = 0; frame < 1800; frame++)
        {
            if (!fontsReady) yield break;
            if (frame % 30 == 0)
                foreach (TMP_SpriteAsset asset in Resources.FindObjectsOfTypeAll<TMP_SpriteAsset>())
                {
                    bool complete = asset.spriteSheet != null && asset.material != null;
                    foreach (string sprite in InlineSpriteNames)
                        complete &= asset.GetSpriteIndexFromName(sprite) >= 0;
                    if (!complete) continue;
                    ValidateInlineSpriteMaterials(asset);
                    yield break;
                }
            yield return null;
        }
        Logger.LogInfo("Inline sprite QA deferred: native story sprite sheet was not loaded; no runtime pass claimed.");
    }

    private void ValidateInlineSpriteMaterials(TMP_SpriteAsset asset)
    {
        var root = new GameObject("PurgatoryRu Sprite QA", typeof(RectTransform), typeof(Canvas));
        root.hideFlags = HideFlags.HideAndDontSave;
        root.GetComponent<Canvas>().enabled = false;
        var clones = new List<Material>();
        try
        {
            var child = new GameObject("PurgatoryRu Sprite Probe", typeof(RectTransform));
            child.hideFlags = HideFlags.HideAndDontSave;
            child.transform.SetParent(root.transform, false);
            var probe = child.AddComponent<TextMeshProUGUI>();
            probe.rectTransform.sizeDelta = new Vector2(1000, 120);
            probe.font = russianRegular;
            probe.spriteAsset = asset;
            probe.fontSize = 24;
            probe.enableAutoSizing = false;
            string sample = "";
            foreach (string sprite in InlineSpriteNames) sample += "<sprite tint=1 name=" + sprite + "> ";
            probe.text = sample + "<b>Ярость</b>, <i>Сила воли</i>, Харано.";
            ApplyConsistentFont(probe);
            probe.ForceMeshUpdate(true, true);
            var native = new Dictionary<TMP_SubMeshUI, Material>();
            bool exercisesOldFailure = false;
            foreach (TMP_SubMeshUI mesh in probe.GetComponentsInChildren<TMP_SubMeshUI>(true))
                if (mesh.spriteAsset != null)
                {
                    // Compatible material instances must also survive, as for
                    // native stencil/masking. Never mutate the asset material.
                    var clone = new Material(mesh.sharedMaterial);
                    clones.Add(clone);
                    mesh.sharedMaterial = clone;
                    native.Add(mesh, clone);
                    exercisesOldFailure |= IsRussianFont(mesh.fontAsset) &&
                        !MaterialMatchesFont(clone, mesh.fontAsset, true);
                }
            RepairFormSubMeshes(probe, true);
            bool passed = exercisesOldFailure && native.Count > 0 && AtlasMismatches(probe.textInfo) == 0;
            foreach (var pair in native)
                passed &= pair.Key.sharedMaterial == pair.Value &&
                    pair.Value.HasProperty("_MainTex") &&
                    pair.Value.GetTexture("_MainTex") == pair.Key.spriteAsset.spriteSheet;
            int sprites = 0;
            for (int index = 0; index < probe.textInfo.characterCount; index++)
            {
                TMP_CharacterInfo character = probe.textInfo.characterInfo[index];
                if (character.elementType != TMP_TextElementType.Sprite) continue;
                sprites++;
                int materialIndex = character.materialReferenceIndex;
                passed &= character.spriteAsset == asset && materialIndex >= 0 &&
                    materialIndex < probe.textInfo.meshInfo.Length;
                if (materialIndex >= 0 && materialIndex < probe.textInfo.meshInfo.Length)
                {
                    Material material = probe.textInfo.meshInfo[materialIndex].material;
                    passed &= material != null && material.HasProperty("_MainTex") &&
                        material.GetTexture("_MainTex") == asset.spriteSheet;
                }
            }
            passed &= sprites == InlineSpriteNames.Length;
            if (passed) Logger.LogInfo($"Inline sprite QA OK: {sprites} native sprites; sprite sheet and compatible materials retained; Cyrillic/bold/italic glyph atlases coherent.");
            else Logger.LogError($"Inline sprite QA FAILED: sprites={sprites}; native sprite material overwritten or invalid atlas.");
        }
        catch (Exception exception)
        { Logger.LogError($"Inline sprite QA could not complete: {exception.GetType().Name}: {exception.Message}"); }
        finally
        {
            Destroy(root);
            foreach (Material material in clones) Destroy(material);
        }
    }
}
