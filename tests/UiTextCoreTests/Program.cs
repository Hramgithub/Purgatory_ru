using System.Text.Json;
using PurgatoryRu;

try
{
    if (args.Length != 1) throw new ArgumentException("Usage: UiTextCoreTests <ui-strings.json>");
    var strings = JsonSerializer.Deserialize<Dictionary<string,JsonElement>>(File.ReadAllText(args[0]))!["strings"];
    var map = new Dictionary<string,string>(StringComparer.OrdinalIgnoreCase);
    foreach (var property in strings.EnumerateObject()) map.Add(property.Name, property.Value.GetString()!);
    var names = new Dictionary<string,string> { ["Victoria"]="Виктория", ["Pat"]="Пэт", ["Aleksander"]="Александер" };
    var localizer = new UiTextLocalizer(map,names);
    int passed = 0;
    void Check(string input,string expected)
    {
        bool changed=localizer.TryTranslate(input,out var actual);
        if (actual!=expected || changed!=(input!=expected)) throw new Exception($"{input}: expected {expected}, got {actual}");
        passed++;
    }
    foreach(var pair in map) Check(pair.Key,pair.Value);
    Check("options","Настройки");
    Check("OPTIONS","Настройки");
    Check("  Resume\n","  Продолжить\n");
    Check("Pat","Пэт");
    Check("<u>Victoria</u>","<u>Виктория</u>");
    Check("<color=#ffee00><b>Aleksander</b></color>","<color=#ffee00><b>Александер</b></color>");
    Check("<u>Pat</b>","<u>Pat</b>");
    Check("<link=Pat>Pat</link>","<link=Pat>Pat</link>");
    Check("Pat said something","Pat said something");
    Check("@pat Talk","@pat Talk");
    Check("CharacterCreation_Tribe_SilverFangs","CharacterCreation_Tribe_SilverFangs");
    Check("Feb 7, Afternoon","7 февр., День");
    Check("Feb 9, Late night","9 февр., Поздняя ночь");
    Check("<i>Feb 7, Afternoon</i>","<i>7 февр., День</i>");
    Check("chapter 6","Глава 6");
    Check("+4 hrs 10 min","+4 ч 10 мин");
    Check("+10 min","+10 мин");
    Check("+2 days","+2 дн.");
    Check("Athletics","Athletics");
    Check("Silver Compact","Silver Compact");
    Check("Puszcza Białowieska","Puszcza Białowieska");
    Check("mahi","mahi");
    Check("<b>Use local save</b>\nMay 20, 2020, 1:15 PM\nProgress: 32%",
          "<b>Использовать локальное сохранение</b>\n20 мая 2020, 13:15\nПрогресс: 32%");
    Check("<b>Use local save</b>\nInvalid Date\nProgress: 32%",
          "<b>Use local save</b>\nInvalid Date\nProgress: 32%");
    Check(""," ".Trim());
    Console.WriteLine($"UI_CORE_OK cases={passed}");
}
catch (Exception error)
{
    // Assertions are ordinary console failures, never unhandled native dialogs.
    Console.Error.WriteLine("UI_CORE_FAILED: " + error.Message);
    Environment.ExitCode = 1;
}
