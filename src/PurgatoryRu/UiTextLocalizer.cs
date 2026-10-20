using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text.RegularExpressions;

namespace PurgatoryRu;

// Pure text transformation: no Unity, game-state, filesystem or network APIs.
internal sealed class UiTextLocalizer
{
    private readonly IDictionary<string, string> strings;
    private readonly IDictionary<string, string> names;
    private readonly HashSet<string> localizedValues;
    private static readonly Regex Wrapper = new(@"^(?<open>(?:<(?:u|b|i|s|color=[^<>]+|size=[^<>]+)>)+)(?<text>[^<>]+)(?<close>(?:</(?:u|b|i|s|color|size)>)+)$", RegexOptions.CultureInvariant);
    private static readonly Regex Date = new(@"^(?<month>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) (?<day>\d{1,2}), (?<time>Morning|Midday|Afternoon|Evening|Late night)$", RegexOptions.CultureInvariant);
    private static readonly Dictionary<string, string> Months = new(StringComparer.Ordinal)
    {
        ["Jan"]="янв.", ["Feb"]="февр.", ["Mar"]="мар.", ["Apr"]="апр.",
        ["May"]="мая", ["Jun"]="июн.", ["Jul"]="июл.", ["Aug"]="авг.",
        ["Sep"]="сент.", ["Oct"]="окт.", ["Nov"]="нояб.", ["Dec"]="дек."
    };
    private static readonly Regex Chapter = new(@"^chapter (?<number>\d+)$", RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);
    private static readonly Regex Cost = new(@"^(?<number>[+-]?[0-9][0-9\s,.]*) (?<unit>min|hrs|days)(?<rest> [0-9][0-9\s,.]* min)?$", RegexOptions.CultureInvariant);
    private static readonly Regex SaveChoice = new(@"^<b>Use (?<kind>cloud save \(newer\)|local save)</b>\r?\n(?<date>[^\r\n]+)\r?\nProgress: (?<progress>\d+%)$", RegexOptions.CultureInvariant);

    internal UiTextLocalizer(IDictionary<string, string> strings, IDictionary<string, string> names)
    {
        this.strings = strings; this.names = names;
        localizedValues = new HashSet<string>(strings.Values, StringComparer.Ordinal);
        localizedValues.UnionWith(names.Values);
    }

    internal bool IsLocalizedValue(string input)
    {
        if (string.IsNullOrEmpty(input)) return false;
        string core = input.Trim();
        if (localizedValues.Contains(core)) return true;
        Match wrapper = Wrapper.Match(core);
        return wrapper.Success && BalancedWrapper(wrapper.Groups["open"].Value, wrapper.Groups["close"].Value) &&
            localizedValues.Contains(wrapper.Groups["text"].Value);
    }

    internal bool TryTranslate(string input, out string result)
    {
        result = input;
        if (string.IsNullOrEmpty(input)) return false;
        // Some serialized paragraphs contain intentional trailing CR/LF bytes.
        // Match the exact dictionary entry before looking at trimmed labels.
        if (strings.TryGetValue(input, out string? exact) || names.TryGetValue(input, out exact))
        { result = exact!; return result != input; }
        string core = input.Trim();
        string? translated = null;
        if (strings.TryGetValue(core, out string? literal) || names.TryGetValue(core, out literal))
            translated = literal;
        else
        {
            Match wrapper = Wrapper.Match(core);
            if (wrapper.Success && BalancedWrapper(wrapper.Groups["open"].Value, wrapper.Groups["close"].Value) &&
                TryTranslate(wrapper.Groups["text"].Value, out string inner))
                translated = wrapper.Groups["open"].Value + inner + wrapper.Groups["close"].Value;
            Match date = Date.Match(core);
            if (translated == null && date.Success && strings.TryGetValue(date.Groups["time"].Value, out string? time))
                translated = date.Groups["day"].Value + " " + Months[date.Groups["month"].Value] + ", " + time;
            Match chapter = Chapter.Match(core);
            if (translated == null && chapter.Success) translated = "Глава " + chapter.Groups["number"].Value;
            Match cost = Cost.Match(core);
            if (translated == null && cost.Success)
            {
                string unit = cost.Groups["unit"].Value;
                translated = cost.Groups["number"].Value + " " + (unit == "min" ? "мин" : unit == "hrs" ? "ч" : "дн.");
                if (cost.Groups["rest"].Success)
                    translated += cost.Groups["rest"].Value.Substring(0, cost.Groups["rest"].Value.Length-3) + "мин";
            }
            Match save = SaveChoice.Match(core);
            if (translated == null && save.Success && DateTime.TryParse(save.Groups["date"].Value,
                CultureInfo.InvariantCulture, DateTimeStyles.AllowWhiteSpaces, out DateTime stamp))
                translated = "<b>" + (save.Groups["kind"].Value == "local save" ? "Использовать локальное сохранение" : "Использовать облачное сохранение (новее)") +
                    "</b>\n" + stamp.ToString("d MMMM yyyy, HH:mm", CultureInfo.GetCultureInfo("ru-RU")) +
                    "\nПрогресс: " + save.Groups["progress"].Value;
        }
        if (translated == null || translated == core) return false;
        int start = input.IndexOf(core, StringComparison.Ordinal);
        result = input.Substring(0, start) + translated + input.Substring(start+core.Length);
        return true;
    }

    private static bool BalancedWrapper(string open, string close)
    {
        MatchCollection starts = Regex.Matches(open, @"<(?<tag>u|b|i|s|color|size)(?:=[^<>]+)?>");
        MatchCollection ends = Regex.Matches(close, @"</(?<tag>u|b|i|s|color|size)>");
        if (starts.Count != ends.Count) return false;
        for (int index=0; index<starts.Count; index++)
            if (starts[index].Groups["tag"].Value != ends[ends.Count-1-index].Groups["tag"].Value) return false;
        return true;
    }
}
