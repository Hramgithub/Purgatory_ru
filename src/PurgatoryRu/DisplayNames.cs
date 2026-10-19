using System;
using System.Collections.Generic;
using System.IO;
using BepInEx;
using HarmonyLib;
using Newtonsoft.Json.Linq;
using TMPro;

namespace PurgatoryRu;

public sealed partial class Plugin
{
    private static readonly Dictionary<string, string> displayNames = new(StringComparer.Ordinal);

    private static void LoadDisplayNames()
    {
        string path = Path.Combine(Paths.PluginPath, "PurgatoryRu", "name-localization.json");
        if (!File.Exists(path))
        {
            log?.LogWarning("Visible-name dictionary is absent; internal character identifiers remain unchanged.");
            return;
        }
        try
        {
            JObject policy = JObject.Parse(File.ReadAllText(path));
            var retained = new HashSet<string>(StringComparer.Ordinal);
            if (policy["retained_visible"] is JArray originals)
                foreach (JToken original in originals)
                    if (original.Type == JTokenType.String) retained.Add((string)original!);
            foreach (string section in new[] { "people", "packs", "extras" })
            {
                if (policy[section] is not JObject names) continue;
                foreach (JProperty entry in names.Properties())
                    if (entry.Value.Type == JTokenType.String && !retained.Contains(entry.Name))
                        displayNames[entry.Name] = (string)entry.Value!;
            }
            log?.LogInfo($"Loaded {displayNames.Count} standalone display names (internal IDs are untouched).");
        }
        catch (Exception exception)
        {
            log?.LogError($"Cannot read visible-name dictionary: {exception.GetType().Name}");
        }
    }

    // Character metadata is also used as a gameplay identity. Translate only
    // its final, entire TMP display value, never the underlying Ink/GameState ID.
    [HarmonyPatch(typeof(TMP_Text), "set_text")]
    private static class DisplayNameTextPatch
    {
        private static void Prefix(ref string __0)
        {
            if (__0 != null && displayNames.TryGetValue(__0, out string translated))
                __0 = translated;
        }
    }
}
