using System;
using System.Collections.Generic;
using System.Text.RegularExpressions;

namespace PurgatoryRu;

// Reviewed short captions only. Never infer "label" from paragraph length.
internal static class CompactLabelPolicy
{
    private static readonly Regex RuntimeCaption = new(
        @"^(?:Глава \d+|[+-]?\d+(?:[,.]\d+)? (?:мин|ч|дн\.)(?: \d+ мин)?|\d{1,2} (?:янв\.|февр\.|мар\.|апр\.|мая|июн\.|июл\.|авг\.|сент\.|окт\.|нояб\.|дек\.), (?:Утро|Полдень|День|Вечер|Поздняя ночь))$",
        RegexOptions.CultureInvariant);
    private static readonly HashSet<string> SingleLine = new(StringComparer.Ordinal)
    {
        "Новая игра", "Главное меню", "Другие игры", "Купить полную игру",
        "Выйти и купить полную игру", "Просто выйти", "Начать главу",
        "Глава завершена", "Игра завершена", "Доступны новые истории",
        "Сменить пользователя", "Лист персонажа", "Выберите облик!",
        "Физические навыки", "Социальные навыки", "Ментальные навыки",
        "Выберите физический навык", "Выберите уровень Ярости",
        "Выберите уровень Харано", "Выбор Судьбы", "Выберите покровителя",
        "Оконный режим", "Качество графики", "Высокая контрастность",
        "Задержка текста", "Задержка абзацев", "Показывать затраты",
        "Громкость музыки", "Громкость окружения", "Отключить звук",
        "Музыка в титрах", "Сбросить настройки", "Отправлять аналитику",
        "Управление данными Unity Analytics", "Удобный шрифт",
        "Без засечек (сюжет)", "Без засечек (везде)",
        "OpenDyslexic (сюжет)", "OpenDyslexic (везде)",
        "Нажмите A, чтобы начать", "Я согласен", "Я не согласен",
        "Женщина из Конго", "Сотрудница приюта", "Письменный стол",
        "Книжные полки", "Шкафы с документами", "Выдвижные ящики",
        "Комната 2", "Комната 3", "Комната Анджея",
        "Зарядное устройство и внешний аккумулятор",
        "Обсудить: Раскол в септе", "Обсудить: Мрачные вести",
        "Обсудить: Городская тревога", "Поговорить", "Осмотреть"
    };

    internal static bool IsCaption(string value) => SingleLine.Contains(value) || RuntimeCaption.IsMatch(value);

    internal static bool ShouldFit(string value, bool knownLocalized, bool hud = false, bool displayName = false)
    {
        if (value.Length == 0 || value.Length > 80 ||
            value.IndexOfAny(new[] { '\t', '\r', '\n', '\\' }) >= 0) return false;
        // Rich text is admitted only after the display-name parser has checked
        // exact name identity and balanced wrappers. Never an arbitrary paragraph.
        if (!displayName && value.IndexOfAny(new[] { '<', '>' }) >= 0) return false;
        return displayName || hud || IsCaption(value) || (knownLocalized && value.IndexOf(' ') < 0);
    }
}
