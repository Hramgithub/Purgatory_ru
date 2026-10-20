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
    string[] patrons = { "CharacterCreation_Totem_BalefulOtter", "CharacterCreation_Totem_ArcaneLynx", "CharacterCreation_Totem_ImmortalPeacock" };
    string[] tribes = { "CharacterCreation_Tribe_BlackFuries", "CharacterCreation_Tribe_BoneGnawers", "CharacterCreation_Tribe_GlassWalkers", "CharacterCreation_Tribe_ShadowLords", "CharacterCreation_Tribe_SilverFangs" };
    int layoutCases = 0;
    void Layout(string[] icons, string[] labels, string[]? expected, string expectedGroup = "")
    {
        string[] inputIcons = (string[])icons.Clone(), inputLabels = (string[])labels.Clone();
        bool changed = CreationLabelPolicy.TryGetLines(icons, labels, out var lines, out var group);
        if (changed != (expected != null) || (expected != null && (!lines.SequenceEqual(expected) || group != expectedGroup)) ||
            (!changed && lines.Length != 0) || !icons.SequenceEqual(inputIcons) || !labels.SequenceEqual(inputLabels))
            throw new Exception("Creation label policy failed");
        layoutCases++;
    }
    foreach (var quote in new[] { ("", ""), ("«", "»"), ("“", "”"), ("\"", "\"") })
    {
        string[] patronNames = { "Зловещая выдра", "Мистическая рысь", "Бессмертный павлин" };
        var expected = patronNames.Select(n => quote.Item1 + n.Replace(' ', '\n') + quote.Item2).ToArray();
        Layout(patrons, patronNames.Select(n => quote.Item1+n+quote.Item2).ToArray(), expected, "Patron");
        Layout(patrons, expected, expected, "Patron");
    }
    Layout(tribes, new[] { "Чёрные Фурии", "Костегрызы", "Стеклоходы", "Повелители Теней", "Серебряные Клыки" },
        new[] { "Чёрные\nФурии", "Костегрызы", "Стеклоходы", "Повелители\nТеней", "Серебряные\nКлыки" }, "Tribe");
    Layout(patrons.Reverse().ToArray(), new[] { "Зловещая выдра", "Мистическая рысь", "Бессмертный павлин" }, null);
    Layout(patrons, new[] { "«Зловещая выдра", "Мистическая рысь", "Бессмертный павлин" }, null);
    Layout(patrons, new[] { "Зловещая выдра", "Мистическая рысь" }, null);
    Layout(patrons, new[] { "Baleful Otter", "Arcane Lynx", "Immortal Peacock" }, null);
    Layout(new[] { "CharacterCreation_SkillPhysical_Athletics" }, new[] { "Athletics" }, null);
    void GroupLayout(string group, string prefix, string suffixes, string values)
    {
        var icons = suffixes.Split('|').Select(x => prefix+x).ToArray();
        var labels = values.Split('|');
        var expected = labels.Select(x => x.Replace(' ', '\n')).ToArray();
        Layout(icons, labels, expected, group);
        Layout(icons, expected, expected, group);
        Layout(icons, labels.Reverse().ToArray(), null);
        Layout(icons.Reverse().ToArray(), labels, null);
    }
    GroupLayout("PhysicalSkills", "CharacterCreation_SkillPhysical_", "Athletics|Stealth|Survival", "Athletics|Stealth|Survival");
    GroupLayout("SocialSkills", "CharacterCreation_SkillSocial_", "AnimalKen|Intimidation|Persuasion", "Animal Ken|Intimidation|Persuasion");
    GroupLayout("MentalSkills", "CharacterCreation_SkillMental_", "Occult|Medicine|Technology", "The Occult|Medicine|Technology");
    GroupLayout("Rage", "CharacterCreation_Rage_", "Low|Medium|High", "Низкий|Средний|Высокий");
    GroupLayout("Harano", "CharacterCreation_Harano_", "Low|High", "Низкий|Высокий");
    GroupLayout("Auspice", "CharacterCreation_Auspice_", "Ragabash|Theurge|Philodox|Galliard|Ahroun", "Рагабаш|Теург|Филодокс|Галлиард|Ахрун");
    Layout(patrons, new[] { "Мистическая рысь", "Зловещая выдра", "Бессмертный павлин" }, null);
    Console.WriteLine($"CREATION_LABEL_POLICY_OK cases={layoutCases}");
    int captionCases = 0;
    void Caption(string value, bool known, bool expected)
    {
        if (CompactLabelPolicy.ShouldFit(value,known) != expected)
            throw new Exception("Compact caption policy failed: "+value);
        captionCases++;
    }
    foreach (string value in new[] { "Новая игра", "Главное меню", "Лист персонажа", "Оконный режим",
        "Качество графики", "Громкость окружения", "Выбор Судьбы", "Выберите покровителя",
        "Обсудить: Мрачные вести", "Комната Анджея", "Зарядное устройство и внешний аккумулятор" })
        Caption(value, false, true);
    Caption("Продолжить",true,true);
    Caption("НеизвестноеСлово",false,false);
    foreach (string value in new[] { "", "Я подошла к столу.", "Ваш прогресс будет удалён. Вы уверены?",
        "Найдено облачное сохранение новее локального.", "<b>Главное меню</b>", "Главное\nменю",
        "Главное\rменю", "Главное\tменю", "Открыть\\nлист персонажа", new string('Я',81) })
        Caption(value, true, false);
    foreach (var pair in map)
    {
        if (pair.Value.Contains('<') || pair.Value.Contains('\n') || pair.Value.Contains('\r'))
            Caption(pair.Value, true, false);
    }
    Console.WriteLine($"COMPACT_LABEL_POLICY_OK cases={captionCases}");
    int nameCaptionCases = 0;
    foreach (string value in new[] { "Виктория", "<u>Виктория</u>", "<color=#ffee00><b>Пэт</b></color>" })
    {
        if (!localizer.IsDisplayName(value) || !CompactLabelPolicy.ShouldFit(value,false,displayName:localizer.IsDisplayName(value)))
            throw new Exception("Display-name caption rejected");
        nameCaptionCases++;
    }
    foreach (string value in new[] { "<u>Виктория</b>", "Виктория сказала", "<link=Pat>Пэт</link>", "<b>Настройки</b>" })
    {
        if (localizer.IsDisplayName(value)) throw new Exception("Non-name accepted as caption");
        nameCaptionCases++;
    }
    foreach (string value in new[] { "Глава 6", "+4 ч 10 мин", "+2 дн.", "7 февр., Поздняя ночь" })
    {
        if (!CompactLabelPolicy.ShouldFit(value,false)) throw new Exception("Runtime caption rejected");
        nameCaptionCases++;
    }
    foreach (string value in new[] { "Глава 6: Предательство", "За 4 ч я дошла до дома.", "+2 дня спустя", "7 февр., Нечто" })
    {
        if (CompactLabelPolicy.ShouldFit(value,false)) throw new Exception("Prose accepted as runtime caption");
        nameCaptionCases++;
    }
    Console.WriteLine($"NAME_RUNTIME_LABEL_POLICY_OK cases={nameCaptionCases}");
    int moonCases = 0;
    var phases = new Dictionary<string,string> {
        ["new moon"]="Новолуние", ["waxing crescent"]="Растущий серп",
        ["first quarter"]="Первая четверть", ["waxing gibbous"]="Растущая выпуклая Луна",
        ["full moon"]="Полнолуние", ["waning gibbous"]="Убывающая выпуклая Луна",
        ["last quarter"]="Последняя четверть", ["waning crescent"]="Убывающий серп"
    };
    foreach (var phase in phases)
    {
        foreach (var sample in new[] {
            (phase.Key, phase.Value),
            ("<b>Фаза Луны:</b> "+phase.Key+".", "<b>Фаза Луны:</b> "+phase.Value+"."),
            ("<b>Moon Phase:</b> "+phase.Key, "<b>Фаза Луны:</b> "+phase.Value),
            ("<i>"+phase.Key+"</i>", "<i>"+phase.Value+"</i>"),
            ("  "+phase.Key.ToUpperInvariant()+"\n", "  "+phase.Value+"\n"),
            (phase.Value, phase.Value) })
        {
            if (!localizer.TryTranslate(sample.Item1,out var actual) && sample.Item1!=sample.Item2 || actual!=sample.Item2)
                throw new Exception("Moon-phase localization failed");
            moonCases++;
        }
    }
    foreach (string unchanged in new[] { ">>> setMoonphase \"full moon\"", "moonphase",
        "getMoonphase", "<link=full moon>full moon</link>", "The full moon was bright.",
        "<b>Фаза Луны:</b> unknown.", "first quarter extra", "not a phase" })
    {
        if (localizer.TryTranslate(unchanged,out var actual) || actual!=unchanged)
            throw new Exception("Moon translation modified non-display data/prose");
        moonCases++;
    }
    Console.WriteLine($"MOON_PHASE_LOCALIZER_OK cases={moonCases} phases={phases.Count}");
}
catch (Exception error)
{
    // Assertions are ordinary console failures, never unhandled native dialogs.
    Console.Error.WriteLine("UI_CORE_FAILED: " + error.Message);
    Environment.ExitCode = 1;
}
