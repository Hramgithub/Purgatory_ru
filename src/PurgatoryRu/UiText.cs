using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.CompilerServices;
using BepInEx;
using Newtonsoft.Json.Linq;
using TMPro;
using UnityEngine;

namespace PurgatoryRu;

public sealed partial class Plugin
{
    private static UiTextLocalizer? uiLocalizer;
    private static readonly ConditionalWeakTable<TMP_Text, object> LocalizedUiTexts = new();
    private static readonly ConditionalWeakTable<TMP_Text, UiLabelLayout> UiLabelLayouts = new();
    private static readonly HashSet<int> MeasuringUiLabels = new();
    private static readonly ConditionalWeakTable<TMP_Text, UiNativeWidth> UiNativeWidths = new();
    private static readonly HashSet<string> HudSourceLabels = new(StringComparer.OrdinalIgnoreCase)
        { "Rage", "Willpower", "Harano", "Health" };
    private static readonly HashSet<string> HudTranslatedLabels = new(StringComparer.Ordinal)
        { "Ярость", "Сила воли", "Харано", "Здоровье" };
    private static readonly HashSet<string> ReportedUiFits = new();
    private static readonly HashSet<string> SingleLineUiValues = new(StringComparer.Ordinal)
        { "Без засечек (сюжет)", "Без засечек (везде)",
          "OpenDyslexic (сюжет)", "OpenDyslexic (везде)" };

    private sealed class UiNativeWidth
    {
        internal readonly float Width;
        internal UiNativeWidth(float width) { Width = width; }
    }

    private sealed class UiLabelLayout
    {
        internal readonly float Size;
        internal readonly bool Auto, Wrap;
        internal UiLabelLayout(TMP_Text text)
        { Size = text.fontSize; Auto = text.enableAutoSizing; Wrap = text.enableWordWrapping; }
        internal void Restore(TMP_Text text)
        { text.fontSize = Size; text.enableAutoSizing = Auto; text.enableWordWrapping = Wrap; }
    }

    private static void LoadUiStrings()
    {
        string path = Path.Combine(Paths.PluginPath, "PurgatoryRu", "ui-strings.json");
        if (!File.Exists(path)) { log?.LogWarning("UI dictionary is absent; story localization remains available."); return; }
        try
        {
            JObject data = JObject.Parse(File.ReadAllText(path));
            if ((int?)data["format"] != 1 || data["strings"] is not JObject entries)
                throw new FormatException("Unsupported UI dictionary");
            var strings = new Dictionary<string,string>(StringComparer.OrdinalIgnoreCase);
            foreach (JProperty entry in entries.Properties())
            {
                if (entry.Value.Type != JTokenType.String) throw new FormatException("Invalid UI string");
                strings.Add(entry.Name, (string)entry.Value!);
            }
            uiLocalizer = new UiTextLocalizer(strings, displayNames);
            log?.LogInfo($"Loaded {strings.Count} exact UI strings; game identifiers are unchanged.");
        }
        catch (Exception exception) { log?.LogError($"UI dictionary not loaded: {exception.GetType().Name}"); }
    }

    private static void LocalizeVisibleUiText(TMP_Text text)
    {
        int id = text.GetInstanceID();
        if (MeasuringUiLabels.Contains(id)) return;
        if (uiLocalizer != null && uiLocalizer.TryTranslate(text.text, out string translated))
        {
            if (HudSourceLabels.Contains(text.text) && !UiNativeWidths.TryGetValue(text, out _))
            {
                // HUD bars are positioned independently inside a larger rect.
                // The native English heading's measured width is its actual
                // budget, not that rect's full width. Never move the bars.
                MeasuringUiLabels.Add(id);
                try
                {
                    float width = text.GetPreferredValues(text.text, float.PositiveInfinity, float.PositiveInfinity).x;
                    if (width > 1) UiNativeWidths.Add(text, new UiNativeWidth(width));
                }
                finally { MeasuringUiLabels.Remove(id); }
            }
            // Only the final view. SetText, serialized m_text and rich-text name
            // labels can bypass the ordinary set_text name hook.
            text.text = translated;
            LocalizedUiTexts.GetValue(text, _ => new object());
        }
        else if (uiLocalizer != null && uiLocalizer.IsLocalizedValue(text.text))
            LocalizedUiTexts.GetValue(text, _ => new object());
    }

    private static bool IsLocalizedUi(TMP_Text text) => LocalizedUiTexts.TryGetValue(text, out _);

    private static void FitSingleWordUiLabel(TMP_Text text)
    {
        // Narrow label-only rule: do not resize narrative paragraphs, rich-text
        // descriptions or arbitrary multi-word prompts. Explicit font-selector
        // values and the four HUD headings also occupy fixed one-line slots.
        // A different Russian font can make
        // CONTINUE -> Продолжить wider than the native condensed label's rect.
        string value = text.text;
        bool hud = HudTranslatedLabels.Contains(value) && UiNativeWidths.TryGetValue(text, out _);
        bool eligible = uiLocalizer != null && uiLocalizer.IsLocalizedValue(value) &&
            ContainsCyrillic(value) && value.Length <= 40 &&
            (hud || SingleLineUiValues.Contains(value) || value.IndexOfAny(new[] { ' ', '\t', '\r', '\n', '<' }) < 0);
        if (!eligible)
        {
            if (UiLabelLayouts.TryGetValue(text, out UiLabelLayout previous))
            { previous.Restore(text); UiLabelLayouts.Remove(text); }
            return;
        }
        int id = text.GetInstanceID();
        if (!MeasuringUiLabels.Add(id)) return; // GetPreferredValues may parse again.
        try
        {
            float width = text.rectTransform.rect.width - text.margin.x - text.margin.z;
            if (hud && UiNativeWidths.TryGetValue(text, out UiNativeWidth native)) width = Math.Min(width, native.Width);
            if (width <= 1) return; // Layout may not have resolved its rect yet.
            UiLabelLayout state = UiLabelLayouts.GetValue(text, item => new UiLabelLayout(item));
            text.enableAutoSizing = false;
            text.enableWordWrapping = false;
            text.fontSize = state.Size;
            Vector2 preferred = text.GetPreferredValues(value, float.PositiveInfinity, float.PositiveInfinity);
            float factor = Math.Min(1f, width / Math.Max(1f, preferred.x));
            float size = factor < 1 ? (float)Math.Floor(state.Size * factor * 0.98f * 10) / 10 : state.Size;
            text.fontSize = size;
            if ((hud || value == "Продолжить") && ReportedUiFits.Add(value))
                log?.LogInfo($"UI label fit: label={value}; baseSize={state.Size:F1}; size={size:F1}; budget={width:F1}; preferred={preferred.x:F1}; wrapping=false.");
        }
        finally { MeasuringUiLabels.Remove(id); }
    }
}
