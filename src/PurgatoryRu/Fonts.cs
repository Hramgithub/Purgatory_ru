using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Runtime.CompilerServices;
using HarmonyLib;
using TMPro;
using UnityEngine;
using UnityEngine.TextCore.LowLevel;

namespace PurgatoryRu;

public sealed partial class Plugin
{
    private const string RussianLetters = "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯабвгдеёжзийклмнопрстуфхцчшщъыьэюя";
    private const string FontCoverage = RussianLetters +
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789" +
        "ąćęłńóśźżĄĆĘŁŃÓŚŹŻ .,:;!?-—–…«»\"'()[]+/%№";
    private static readonly Dictionary<Font, string> FontFiles = new Dictionary<Font, string>();
    private static readonly ConditionalWeakTable<TMP_Text, FontBinding> FontBindings = new ConditionalWeakTable<TMP_Text, FontBinding>();
    private static readonly HashSet<int> ReportedOriginalFonts = new HashSet<int>();
    private static readonly HashSet<string> AuditedSamples = new HashSet<string>();
    private readonly List<TMP_FontAsset> ownedFonts = new List<TMP_FontAsset>();
    private readonly List<Font> ownedSources = new List<Font>();
    private static TMP_FontAsset? russianRegular;
    private static bool fontsReady;

    private sealed class FontBinding
    {
        public TMP_FontAsset OriginalFont;
        public Material OriginalMaterial;

        public FontBinding(TMP_Text text)
        {
            OriginalFont = text.font;
            OriginalMaterial = text.fontSharedMaterial;
            text.OnPreRenderText += AuditFontRun;
        }
    }

    private IEnumerator InstallCyrillicFallback()
    {
        yield return null;
        for (int attempt = 0; attempt < 1800; attempt++)
        {
            if (Resources.FindObjectsOfTypeAll<TMP_Text>().Length == 0)
            {
                yield return null;
                continue;
            }
            var fallbacks = TMP_Settings.fallbackFontAssets;
            if (fallbacks == null)
            {
                yield return null;
                continue;
            }

            string directory = Environment.GetFolderPath(Environment.SpecialFolder.Fonts);
            // Require a complete family so bold/italic never fall back glyph by glyph.
            string[][] families = {
                new[] { "segoeui.ttf", "segoeuii.ttf", "segoeuib.ttf", "segoeuiz.ttf" },
                new[] { "arial.ttf", "ariali.ttf", "arialbd.ttf", "arialbi.ttf" }
            };
            string[]? files = null;
            foreach (string[] family in families)
            {
                bool complete = true;
                foreach (string file in family) complete &= File.Exists(Path.Combine(directory, file));
                if (complete) { files = family; break; }
            }
            if (files == null)
            {
                Logger.LogError("No complete Segoe UI or Arial TrueType family was found.");
                yield break;
            }

            string[] styles = { "Regular", "Italic", "Bold", "Bold Italic" };
            foreach (int index in new[] { 0, 1, 2, 3 })
            {
                Font source = Font.CreateDynamicFontFromOSFont("Segoe UI", 32);
                ownedSources.Add(source);
                FontFiles.Add(source, Path.Combine(directory, files[index]));
                TMP_FontAsset asset = TMP_FontAsset.CreateFontAsset(source, 64, 7,
                    GlyphRenderMode.SDFAA, 1024, 1024, AtlasPopulationMode.Dynamic, true);
                if (asset == null)
                {
                    Logger.LogError($"Could not create Cyrillic font face: {styles[index]}.");
                    yield break;
                }
                ownedFonts.Add(asset);
                asset.name = "PurgatoryRu " + styles[index];
                DontDestroyOnLoad(source);
                DontDestroyOnLoad(asset);
                if (!asset.TryAddCharacters(FontCoverage) || !asset.HasCharacters(FontCoverage))
                {
                    Logger.LogError($"Incomplete Russian/Latin glyph coverage: {styles[index]}.");
                    yield break;
                }
            }

            var weights = new TMP_FontWeightPair[10];
            weights[4].italicTypeface = ownedFonts[1];
            weights[7].regularTypeface = ownedFonts[2];
            weights[7].italicTypeface = ownedFonts[3];
            foreach (TMP_FontAsset asset in ownedFonts) Array.Copy(weights, asset.fontWeightTable, weights.Length);
            russianRegular = ownedFonts[0];
            if (!fallbacks.Contains(russianRegular)) fallbacks.Add(russianRegular);
            fontsReady = true;
            if (!ValidateFontFamily())
            {
                fontsReady = false;
                fallbacks.Remove(russianRegular);
                Logger.LogError("Cyrillic font family failed its render test; whole-text replacement disabled.");
                yield break;
            }
            foreach (TMP_Text text in Resources.FindObjectsOfTypeAll<TMP_Text>()) ApplyConsistentFont(text);
            RefreshTribeLabels();
            Logger.LogInfo("Installed coherent Cyrillic font family: Regular, Italic, Bold, Bold Italic; full Russian/Latin coverage.");
            yield break;
        }
        Logger.LogWarning("TextMeshPro settings did not become available; Cyrillic fonts were not installed.");
    }

    private static bool ContainsCyrillic(string text)
    {
        foreach (char ch in text) if (ch >= '\u0400' && ch <= '\u052f') return true;
        return false;
    }

    private static bool IsRussianFont(TMP_FontAsset asset) => asset != null && asset.name.StartsWith("PurgatoryRu ", StringComparison.Ordinal);

    private bool ValidateFontFamily()
    {
        // Exercise the installed TMP renderer without displaying UI or advancing Ink.
        var probeObject = new GameObject("PurgatoryRu Font QA");
        probeObject.hideFlags = HideFlags.HideAndDontSave;
        try
        {
            var probe = probeObject.AddComponent<TextMeshPro>();
            probeObject.GetComponent<MeshRenderer>().enabled = false;
            probe.font = russianRegular;
            probe.fontSize = 24;
            probe.enableAutoSizing = false;
            FontStyles[] styles = { FontStyles.Normal, FontStyles.Italic, FontStyles.Bold, FontStyles.Bold | FontStyles.Italic };
            foreach (string sample in new[] { "Скорее.", "Ты должна бежать." })
            {
                for (int style = 0; style < styles.Length; style++)
                {
                    probe.fontStyle = styles[style];
                    probe.text = sample;
                    probe.ForceMeshUpdate(true, true);
                    int letters = 0;
                    float scale = -1;
                    for (int index = 0; index < probe.textInfo.characterCount; index++)
                    {
                        TMP_CharacterInfo ch = probe.textInfo.characterInfo[index];
                        if (!char.IsLetter(ch.character)) continue;
                        letters++;
                        if (ch.fontAsset != ownedFonts[style] ||
                            (scale >= 0 && Math.Abs(ch.scale - scale) > 0.0001f))
                        {
                            Logger.LogError($"Font family QA FAILED: '{sample}', {styles[style]}, character '{ch.character}', face '{ch.fontAsset?.name}'.");
                            return false;
                        }
                        scale = ch.scale;
                    }
                    int required = 0;
                    foreach (char ch in sample) if (char.IsLetter(ch)) required++;
                    if (letters != required)
                    {
                        Logger.LogError($"Font family QA FAILED: '{sample}', {styles[style]}, rendered {letters}/{required} letters.");
                        return false;
                    }
                }
            }
            Logger.LogInfo("Font family QA OK: both reported Russian samples rendered with one face and uniform letter scale in all four styles (8 cases).");
            return ValidateFormFontMaterial();
        }
        catch (Exception exception)
        {
            Logger.LogError($"Font family render test could not complete: {exception}");
            return false;
        }
        finally { Destroy(probeObject); }
    }

    private static void ApplyConsistentFont(TMP_Text text)
    {
        if (!fontsReady || russianRegular == null || text == null || text.font == null) return;
        LocalizeVisibleUiText(text);
        LocalizeFormLabel(text);
        if (ContainsCyrillic(text.text))
        {
            FontBinding binding = FontBindings.GetValue(text, value => new FontBinding(value));
            if (!IsRussianFont(text.font))
            {
                binding.OriginalFont = text.font;
                binding.OriginalMaterial = text.fontSharedMaterial;
                if (ReportedOriginalFonts.Add(text.font.GetInstanceID()))
                {
                    int present = 0;
                    foreach (char ch in RussianLetters) if (text.font.HasCharacter(ch)) present++;
                    log?.LogInfo($"Original font '{text.font.name}': native Russian coverage {present}/{RussianLetters.Length}; using complete family for Russian text.");
                }
            }
            if (text.font != russianRegular)
            {
                text.font = russianRegular;
            }
            // A pooled UI view or the game's FontReplacer may reassign a
            // material independently of font. Glyph UVs belong to the font's
            // atlas: equal font does NOT imply a compatible material.
            // Keep valid stencil/masking instances instead of overwriting them.
            if (!MaterialMatchesFont(text.fontSharedMaterial, russianRegular))
            {
                text.fontSharedMaterial = russianRegular.material;
            }
            RepairFormSubMeshes(text);
        }
        else if (FontBindings.TryGetValue(text, out FontBinding binding) && IsRussianFont(text.font))
        {
            // Pooled views reused for English-only names/skills retain the game's font.
            text.font = binding.OriginalFont;
            text.fontSharedMaterial = binding.OriginalMaterial;
        }
        FitSingleWordUiLabel(text);
    }

    private static void AuditFontRun(TMP_TextInfo info)
    {
        if (!fontsReady || info.textComponent == null) return;
        if (info.textComponent.gameObject.name == "PurgatoryRu Font QA") return;
        AuditFormFontRun(info);
        string text = info.textComponent.text;
        string? sample = text.Contains("Ты должна бежать.") ? "Ты должна бежать." :
            text.Contains("Скорее.") ? "Скорее." : null;
        if (sample == null || AuditedSamples.Contains(sample)) return;
        int sampleStart = text.IndexOf(sample, StringComparison.Ordinal);
        int sampleEnd = sampleStart + sample.Length;
        var faces = new HashSet<string>();
        float minimum = float.MaxValue;
        float maximum = 0;
        int letters = 0;
        for (int index = 0; index < info.characterCount; index++)
        {
            TMP_CharacterInfo ch = info.characterInfo[index];
            if (ch.index < sampleStart || ch.index >= sampleEnd) continue;
            if (!char.IsLetter(ch.character)) continue;
            letters++;
            faces.Add(ch.fontAsset != null ? ch.fontAsset.name : "<none>");
            minimum = Math.Min(minimum, ch.scale);
            maximum = Math.Max(maximum, ch.scale);
        }
        int required = 0;
        foreach (char ch in sample) if (char.IsLetter(ch)) required++;
        if (letters < required) return;
        AuditedSamples.Add(sample);
        bool stable = faces.Count == 1 && Math.Abs(maximum - minimum) < 0.0001f;
        string message = $"Font run QA {(stable ? "OK" : "FAILED")}: '{sample}'; faces={string.Join(",", faces)}; letterScale={minimum:F6}..{maximum:F6}.";
        if (stable) log?.LogInfo(message); else log?.LogError(message);
    }

    private void DisposeFonts()
    {
        fontsReady = false;
        foreach (TMP_FontAsset asset in ownedFonts) if (asset != null) Destroy(asset);
        foreach (Font source in ownedSources) if (source != null) Destroy(source);
        FontFiles.Clear();
        russianRegular = null;
    }

    [HarmonyPatch(typeof(FontEngine), nameof(FontEngine.LoadFontFace), new[] { typeof(Font), typeof(int) })]
    private static class FallbackFontFacePatch
    {
        private static bool Prefix(Font font, int pointSize, ref FontEngineError __result)
        {
            if (font == null || !FontFiles.TryGetValue(font, out string path)) return true;
            __result = FontEngine.LoadFontFace(path, pointSize);
            return false;
        }
    }

    [HarmonyPatch(typeof(TMP_Text), "ParseInputText")]
    private static class CyrillicTextPatch
    {
        private static void Prefix(TMP_Text __instance) => ApplyConsistentFont(__instance);
    }
}
