using System;

namespace PurgatoryRu;

// All eight inspected ui-character-creation groups; exact icon AND label order.
internal static class CreationLabelPolicy
{
    private sealed class Group
    {
        internal readonly string Name;
        internal readonly string[] Icons, Labels;
        internal Group(string name, string icons, string labels)
        { Name = name; Icons = icons.Split('|'); Labels = labels.Split('|'); }
    }

    private static readonly Group[] Groups = {
        new Group("PhysicalSkills",
            "CharacterCreation_SkillPhysical_Athletics|CharacterCreation_SkillPhysical_Stealth|CharacterCreation_SkillPhysical_Survival",
            "Athletics|Stealth|Survival"),
        new Group("SocialSkills",
            "CharacterCreation_SkillSocial_AnimalKen|CharacterCreation_SkillSocial_Intimidation|CharacterCreation_SkillSocial_Persuasion",
            "Animal Ken|Intimidation|Persuasion"),
        new Group("MentalSkills",
            "CharacterCreation_SkillMental_Occult|CharacterCreation_SkillMental_Medicine|CharacterCreation_SkillMental_Technology",
            "The Occult|Medicine|Technology"),
        new Group("Rage",
            "CharacterCreation_Rage_Low|CharacterCreation_Rage_Medium|CharacterCreation_Rage_High",
            "Низкий|Средний|Высокий"),
        new Group("Harano",
            "CharacterCreation_Harano_Low|CharacterCreation_Harano_High",
            "Низкий|Высокий"),
        new Group("Auspice",
            "CharacterCreation_Auspice_Ragabash|CharacterCreation_Auspice_Theurge|CharacterCreation_Auspice_Philodox|CharacterCreation_Auspice_Galliard|CharacterCreation_Auspice_Ahroun",
            "Рагабаш|Теург|Филодокс|Галлиард|Ахрун"),
        new Group("Tribe",
            "CharacterCreation_Tribe_BlackFuries|CharacterCreation_Tribe_BoneGnawers|CharacterCreation_Tribe_GlassWalkers|CharacterCreation_Tribe_ShadowLords|CharacterCreation_Tribe_SilverFangs",
            "Чёрные Фурии|Костегрызы|Стеклоходы|Повелители Теней|Серебряные Клыки"),
        new Group("Patron",
            "CharacterCreation_Totem_BalefulOtter|CharacterCreation_Totem_ArcaneLynx|CharacterCreation_Totem_ImmortalPeacock",
            "Зловещая выдра|Мистическая рысь|Бессмертный павлин")
    };

    private static bool SameIcons(string[] actual, string[] expected)
    {
        if (actual.Length != expected.Length) return false;
        for (int index = 0; index < actual.Length; index++)
            if (actual[index] != expected[index]) return false;
        return true;
    }

    internal static bool TryGetLines(string[] icons, string[] labels, out string[] lines, out string group)
    {
        lines = Array.Empty<string>();
        group = "";
        Group? matched = null;
        foreach (Group candidate in Groups)
            if (SameIcons(icons, candidate.Icons)) { matched = candidate; break; }
        if (matched == null || labels.Length != matched.Labels.Length) return false;
        var proposed = new string[labels.Length];
        for (int index = 0; index < labels.Length; index++)
        {
            string plain = labels[index].Replace('\n', ' ');
            string open = "", close = "";
            if (plain.Length >= 2 && ((plain[0] == '«' && plain[plain.Length - 1] == '»') ||
                (plain[0] == '“' && plain[plain.Length - 1] == '”') ||
                (plain[0] == '"' && plain[plain.Length - 1] == '"')))
            {
                open = plain.Substring(0, 1); close = plain.Substring(plain.Length - 1);
                plain = plain.Substring(1, plain.Length - 2);
            }
            if (plain != matched.Labels[index]) return false;
            proposed[index] = open + plain.Replace(' ', '\n') + close;
        }
        lines = proposed;
        group = matched.Name;
        return true;
    }
}
