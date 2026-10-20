using System;
using System.IO;
using System.Reflection;
using BepInEx;
using BepInEx.Logging;
using HarmonyLib;
using UnityEngine;

namespace PurgatoryRu;

[BepInPlugin(PluginGuid, PluginName, PluginVersion)]
public sealed partial class Plugin : BaseUnityPlugin
{
    public const string PluginGuid = "ru.hramgithub.purgatory.localization";
    public const string PluginName = "Purgatory Russian Localization";
    public const string PluginVersion = "0.1.6";

    private const string StoryMarker = "\"^wod02Completed\"";
    private static string? replacementStory;
    private static ManualLogSource? log;
    private Harmony? harmony;

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
        LoadDisplayNames();
        LoadUiStrings();
        harmony = new Harmony(PluginGuid);
        harmony.PatchAll(typeof(StoryConstructorPatch));
        harmony.PatchAll(typeof(FallbackFontFacePatch));
        harmony.PatchAll(typeof(CyrillicTextPatch));
        harmony.PatchAll(typeof(DisplayNameTextPatch));
        harmony.PatchAll(typeof(FormCanvasPreRenderPatch));
        harmony.PatchAll(typeof(FormCanvasMaterialPatch));
        harmony.PatchAll(typeof(CreationLabelsPatch));
        StartCoroutine(InstallCyrillicFallback());
        Logger.LogInfo($"Loaded Russian Ink story ({candidate.Length:N0} characters)." );
    }

    private void OnDestroy()
    {
        harmony?.UnpatchSelf();
        DisposeFonts();
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
