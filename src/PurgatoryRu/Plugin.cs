using System;
using System.Collections;
using System.IO;
using System.Reflection;
using BepInEx;
using BepInEx.Logging;
using HarmonyLib;
using TMPro;
using UnityEngine;

namespace PurgatoryRu;

[BepInPlugin(PluginGuid, PluginName, PluginVersion)]
public sealed class Plugin : BaseUnityPlugin
{
    public const string PluginGuid = "ru.hramgithub.purgatory.localization";
    public const string PluginName = "Purgatory Russian Localization";
    public const string PluginVersion = "0.1.0";

    private const string StoryMarker = "\"^wod02Completed\"";
    private static string? replacementStory;
    private static ManualLogSource? log;
    private Harmony? harmony;
    private TMP_FontAsset? cyrillicFallback;

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
        StartCoroutine(InstallCyrillicFallback());
        Logger.LogInfo($"Loaded Russian Ink story ({candidate.Length:N0} characters)." );
    }

    private IEnumerator InstallCyrillicFallback()
    {
        for (int attempt = 0; attempt < 120; attempt++)
        {
            var fallbacks = TMP_Settings.fallbackFontAssets;
            if (fallbacks != null)
            {
                Font osFont = Font.CreateDynamicFontFromOSFont(
                    new[] { "Segoe UI", "Arial", "Tahoma" }, 32);
                cyrillicFallback = TMP_FontAsset.CreateFontAsset(osFont);
                cyrillicFallback.name = "PurgatoryRu Cyrillic Fallback";
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
