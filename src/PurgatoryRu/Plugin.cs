using System;
using System.Collections;
using System.IO;
using System.Reflection;
using BepInEx;
using BepInEx.Logging;
using HarmonyLib;
using TMPro;
using UnityEngine;
using UnityEngine.TextCore.LowLevel;

namespace PurgatoryRu;

[BepInPlugin(PluginGuid, PluginName, PluginVersion)]
public sealed class Plugin : BaseUnityPlugin
{
    public const string PluginGuid = "ru.hramgithub.purgatory.localization";
    public const string PluginName = "Purgatory Russian Localization";
    public const string PluginVersion = "0.1.1";

    private const string StoryMarker = "\"^wod02Completed\"";
    private static string? replacementStory;
    private static ManualLogSource? log;
    private Harmony? harmony;
    private TMP_FontAsset? cyrillicFallback;
    private static Font? fallbackSourceFont;
    private static string? fallbackFontPath;

    private void Awake()
    {
        log = Logger;
        string storyPath = Path.Combine(Paths.PluginPath, "PurgatoryRu", "wod02.json");
        if (!File.Exists(storyPath))
        {
            Logger.LogError($"Localization file not found: {storyPath}");
            return;
        }

        string candidate = File.ReadAllText(storyPath);
        if (!candidate.Contains(StoryMarker, StringComparison.Ordinal))
        {
            Logger.LogError("Localization file does not contain the expected Purgatory story marker.");
            return;
        }

        replacementStory = candidate;
        harmony = new Harmony(PluginGuid);
        harmony.PatchAll(typeof(StoryConstructorPatch));
        harmony.PatchAll(typeof(FallbackFontFacePatch));
        StartCoroutine(InstallCyrillicFallback());
        Logger.LogInfo($"Loaded Russian Ink story ({candidate.Length:N0} characters)." );
    }

    private IEnumerator InstallCyrillicFallback()
    {
        // Do not access TMP settings during BepInEx's pre-scene bootstrap.
        yield return null;
        for (int attempt = 0; attempt < 1800; attempt++)
        {
            if (Resources.FindObjectsOfTypeAll<TMP_Text>().Length == 0)
            {
                yield return null;
                continue;
            }
            var fallbacks = TMP_Settings.fallbackFontAssets;
            if (fallbacks != null)
            {
                string fonts = Environment.GetFolderPath(Environment.SpecialFolder.Fonts);
                foreach (string filename in new[] { "segoeui.ttf", "arial.ttf", "tahoma.ttf" })
                {
                    string path = Path.Combine(fonts, filename);
                    if (File.Exists(path))
                    {
                        fallbackFontPath = path;
                        break;
                    }
                }
                if (fallbackFontPath == null)
                {
                    Logger.LogError("No supported system TrueType font was found.");
                    yield break;
                }
                fallbackSourceFont = Font.CreateDynamicFontFromOSFont("Segoe UI", 32);
                cyrillicFallback = TMP_FontAsset.CreateFontAsset(fallbackSourceFont);
                if (cyrillicFallback == null)
                {
                    Logger.LogError("Could not create the Cyrillic TextMeshPro font asset.");
                    yield break;
                }
                cyrillicFallback.name = "PurgatoryRu Cyrillic Fallback";
                DontDestroyOnLoad(cyrillicFallback);
                DontDestroyOnLoad(fallbackSourceFont);
                if (!cyrillicFallback.TryAddCharacters("АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯабвгдеёжзийклмнопрстуфхцчшщъыьэюя«»—–…№"))
                {
                    Logger.LogError("The fallback font is missing required Russian characters.");
                    yield break;
                }
                if (!fallbacks.Contains(cyrillicFallback))
                {
                    fallbacks.Add(cyrillicFallback);
                }
                Logger.LogInfo("Installed dynamic Cyrillic TextMeshPro fallback font.");
                yield break;
            }
            yield return null;
        }
        Logger.LogWarning("TextMeshPro settings did not become available; Cyrillic fallback was not installed.");
    }

    // Unity OS fonts do not expose embedded font bytes to TextCore in a player.
    // Redirect only our dedicated source font to its installed TrueType file.
    [HarmonyPatch(typeof(FontEngine), nameof(FontEngine.LoadFontFace),
        new[] { typeof(Font), typeof(int) })]
    private static class FallbackFontFacePatch
    {
        private static bool Prefix(Font font, int pointSize, ref FontEngineError __result)
        {
            if (fallbackSourceFont == null || font != fallbackSourceFont || fallbackFontPath == null)
            {
                return true;
            }
            __result = FontEngine.LoadFontFace(fallbackFontPath, pointSize);
            return false;
        }
    }

    private void OnDestroy()
    {
        harmony?.UnpatchSelf();
        if (cyrillicFallback != null)
        {
            Destroy(cyrillicFallback);
        }
    }

    private static bool TryReplace(string original, out string translated)
    {
        if (replacementStory != null && original.Contains(StoryMarker, StringComparison.Ordinal))
        {
            translated = replacementStory;
            log?.LogInfo("Replaced the main Purgatory Ink story with the Russian localization.");
            return true;
        }
        translated = original;
        return false;
    }

    [HarmonyPatch]
    private static class StoryConstructorPatch
    {
        private static MethodBase TargetMethod()
        {
            Type storyType = AccessTools.TypeByName("Ink.Runtime.Story")
                ?? throw new TypeLoadException("Ink.Runtime.Story was not found.");
            return AccessTools.Constructor(storyType, new[] { typeof(string) })
                ?? throw new MissingMethodException("Ink.Runtime.Story(string) was not found.");
        }

        private static void Prefix(ref string __0)
        {
            if (TryReplace(__0, out string translated))
            {
                __0 = translated;
            }
        }
    }
}
