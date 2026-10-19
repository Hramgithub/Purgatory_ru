using System;
using System.Collections;
using System.Collections.Generic;
using System.Reflection;
using System.Runtime.CompilerServices;
using HarmonyLib;
using TMPro;
using UnityEngine;

namespace PurgatoryRu;

public sealed partial class Plugin
{
    private static readonly Type? CreationWidgetType = AccessTools.TypeByName("CharacterCreationWidget");
    private static readonly FieldInfo? CreationButtonsField = CreationWidgetType == null ? null : AccessTools.Field(CreationWidgetType, "buttons");
    private static readonly FieldInfo? CreationIconsField = CreationWidgetType == null ? null : AccessTools.Field(CreationWidgetType, "buttonsIcons");
    private static readonly FieldInfo? CreationInfoField = CreationWidgetType == null ? null : AccessTools.Field(CreationWidgetType, "infoDumpText");
    private static readonly string[] TribeIcons = {
        "CharacterCreation_Tribe_BlackFuries", "CharacterCreation_Tribe_BoneGnawers",
        "CharacterCreation_Tribe_GlassWalkers", "CharacterCreation_Tribe_ShadowLords",
        "CharacterCreation_Tribe_SilverFangs"
    };
    private static readonly Dictionary<string, string> TribeLabelLines = new(StringComparer.Ordinal)
    {
        ["Чёрные Фурии"] = "Чёрные\nФурии",
        ["Костегрызы"] = "Костегрызы",
        ["Стеклоходы"] = "Стеклоходы",
        ["Повелители Теней"] = "Повелители\nТеней",
        ["Серебряные Клыки"] = "Серебряные\nКлыки"
    };
    private static readonly ConditionalWeakTable<TMP_Text, CreationLabelState> CreationLabelStates = new();

    private sealed class CreationLabelState
    {
        internal readonly float Size, Minimum, Maximum;
        internal readonly bool AutoSize, Wrap;
        internal readonly VerticalAlignmentOptions Vertical;
        internal readonly Vector2 OffsetMin, OffsetMax;
        internal readonly string Text;
        internal CreationLabelState(TMP_Text text)
        {
            Size = text.fontSize; Minimum = text.fontSizeMin; Maximum = text.fontSizeMax;
            AutoSize = text.enableAutoSizing; Wrap = text.enableWordWrapping;
            Vertical = text.verticalAlignment;
            OffsetMin = text.rectTransform.offsetMin; OffsetMax = text.rectTransform.offsetMax;
            Text = text.text;
        }
        internal void Restore(TMP_Text text)
        {
            text.fontSizeMin = Minimum; text.fontSizeMax = Maximum;
            text.fontSize = Size; text.enableAutoSizing = AutoSize;
            text.enableWordWrapping = Wrap; text.verticalAlignment = Vertical;
            text.rectTransform.offsetMin = OffsetMin; text.rectTransform.offsetMax = OffsetMax;
            text.text = Text;
        }
    }

    private static List<TMP_Text> CreationButtonLabels(Component widget)
    {
        var labels = new List<TMP_Text>();
        if (CreationButtonsField?.GetValue(widget) is not Array buttons) return labels;
        foreach (object button in buttons)
        {
            if (button is not Component component) continue;
            TMP_Text label = component.GetComponentInChildren<TextMeshProUGUI>(true);
            if (label != null) labels.Add(label);
        }
        return labels;
    }

    private static void RestoreCreationLabels(Component widget)
    {
        // CharacterCreationWidget reuses the same buttons for skills, auspices,
        // rage, etc. Restore their native layout before the next initialization.
        foreach (TMP_Text text in CreationButtonLabels(widget))
            if (CreationLabelStates.TryGetValue(text, out CreationLabelState state))
            {
                state.Restore(text);
                CreationLabelStates.Remove(text);
            }
    }

    private static bool FitTribeLabels(Component widget)
    {
        if (!fontsReady || CreationIconsField?.GetValue(widget) is not string[] icons || icons.Length != TribeIcons.Length) return false;
        for (int index = 0; index < icons.Length; index++)
            if (icons[index] != TribeIcons[index]) return false;
        List<TMP_Text> labels = CreationButtonLabels(widget);
        if (labels.Count < icons.Length) return false;
        // Validate the entire group before altering anything. Never edit the
        // widget's arrays, GameObject names, listeners or selected result.
        var lines = new string[icons.Length];
        for (int index = 0; index < lines.Length; index++)
        {
            string plain = labels[index].text.Replace('\n', ' ');
            if (!TribeLabelLines.TryGetValue(plain, out lines[index])) return false;
        }
        float commonSize = float.MaxValue;
        for (int index = 0; index < lines.Length; index++)
        {
            TMP_Text text = labels[index];
            CreationLabelState state = CreationLabelStates.GetValue(text, value => new CreationLabelState(value));
            ApplyConsistentFont(text);
            text.enableAutoSizing = false;
            text.enableWordWrapping = false;
            text.verticalAlignment = VerticalAlignmentOptions.Top;
            text.fontSize = state.Size;
            text.text = lines[index];
            Vector2 preferred = text.GetPreferredValues(lines[index], float.PositiveInfinity, float.PositiveInfinity);
            // Native labels have a shallow one-line rect, although the game
            // permits their text to overflow below it. Do not fit two lines to
            // that height: use the actual free band above the description.
            RectTransform rect = text.rectTransform;
            rect.offsetMin = state.OffsetMin; rect.offsetMax = state.OffsetMax;
            if (CreationInfoField?.GetValue(widget) is not TMP_Text info)
            { RestoreCreationLabels(widget); return false; }
            Vector3 infoTop = info.rectTransform.TransformPoint(new Vector3(0, info.rectTransform.rect.yMax, 0));
            float freeHeight = rect.rect.yMax - rect.InverseTransformPoint(infoTop).y - 6f;
            float originalHeight = rect.rect.height;
            if (freeHeight > originalHeight)
                rect.offsetMin = new Vector2(state.OffsetMin.x, state.OffsetMin.y - (freeHeight - originalHeight));
            Vector4 margin = text.margin;
            float width = text.rectTransform.rect.width - margin.x - margin.z;
            float height = text.rectTransform.rect.height - margin.y - margin.w;
            if (width <= 0 || height <= 0) { RestoreCreationLabels(widget); return false; }
            float factor = Math.Min(1f, Math.Min(width / Math.Max(1, preferred.x), height / Math.Max(1, preferred.y)));
            commonSize = Math.Min(commonSize, state.Size * factor);
            log?.LogInfo($"Tribe label metrics: index={index}; baseSize={state.Size:F1}; preferred={preferred.x:F1}x{preferred.y:F1}; originalHeight={originalHeight:F1}; freeHeight={freeHeight:F1}; room={width:F1}x{height:F1}; factor={factor:F3}.");
        }
        // Same base size for every name, with a small rounding safety margin.
        // Wrapping is disabled: only the explicit breaks between words remain.
        commonSize = (float)Math.Floor(commonSize * 0.98f * 10) / 10;
        for (int index = 0; index < lines.Length; index++) labels[index].fontSize = commonSize;
        log?.LogInfo($"Tribe label layout: labels={lines.Length}; uniformSize={commonSize:F1}; explicitWordBreaks=true; characterWrapping=false.");
        return true;
    }

    private static IEnumerator FitTribeLabelsAfterLayout(Component widget)
    {
        yield return null;
        // The panel's layout may not yet have its final width in InitButtons.
        if (widget != null && widget.gameObject.activeInHierarchy) FitTribeLabels(widget);
    }

    private static void RefreshTribeLabels()
    {
        if (CreationWidgetType == null) return;
        foreach (UnityEngine.Object item in Resources.FindObjectsOfTypeAll(CreationWidgetType))
            if (item is Component widget && widget.gameObject.activeInHierarchy) FitTribeLabels(widget);
    }

    [HarmonyPatch]
    private static class CreationLabelsPatch
    {
        private static MethodBase TargetMethod() =>
            AccessTools.Method(CreationWidgetType ?? throw new TypeLoadException("CharacterCreationWidget was not found."), "InitButtons")
            ?? throw new MissingMethodException("CharacterCreationWidget.InitButtons was not found.");
        private static void Prefix(Component __instance) => RestoreCreationLabels(__instance);
        private static void Postfix(Component __instance)
        {
            FitTribeLabels(__instance);
            if (__instance is MonoBehaviour widget) widget.StartCoroutine(FitTribeLabelsAfterLayout(__instance));
        }
    }
}
