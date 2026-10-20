using System;
using System.Collections.Generic;

namespace PurgatoryRu;

// PlayerState.InitStats defines exactly these eight values. This runs only
// on final displayed TMP text, never on stats, Ink commands or saved values.
internal static class MoonPhaseLocalizer
{
    private static readonly Dictionary<string, string> Phases = new(StringComparer.OrdinalIgnoreCase)
    {
        ["new moon"] = "Новолуние",
        ["waxing crescent"] = "Растущий серп",
        ["first quarter"] = "Первая четверть",
        ["waxing gibbous"] = "Растущая выпуклая Луна",
        ["full moon"] = "Полнолуние",
        ["waning gibbous"] = "Убывающая выпуклая Луна",
        ["last quarter"] = "Последняя четверть",
        ["waning crescent"] = "Убывающий серп"
    };

    internal static bool TryTranslate(string input, out string result)
    {
        result = input;
        string value = input;
        string prefix = "";
        foreach (string heading in new[] { "<b>Фаза Луны:</b> ", "<b>Moon Phase:</b> ", "Фаза Луны: ", "Moon Phase: " })
            if (input.StartsWith(heading, StringComparison.Ordinal))
            {
                prefix = heading.StartsWith("<b>", StringComparison.Ordinal) ? "<b>Фаза Луны:</b> " : "Фаза Луны: ";
                value = input.Substring(heading.Length);
                break;
            }
        string punctuation = "";
        if (value.EndsWith(".", StringComparison.Ordinal))
        { punctuation = "."; value = value.Substring(0, value.Length - 1); }
        if (!Phases.TryGetValue(value, out string? translated)) return false;
        result = prefix + translated + punctuation;
        return true;
    }
}
