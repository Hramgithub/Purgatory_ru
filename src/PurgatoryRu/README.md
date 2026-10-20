# PurgatoryRu plugin

The plugin replaces `Ink.Runtime.Story(string)` only when the stable `wod02`
marker is present. The assembled story keeps gameplay identifiers and commands.

Visible names use the separate name policy. `UiTextLocalizer` also translates
exact final TMP display values from `ui-strings.json`, plus anchored date,
chapter and time-cost templates. It covers serialized text and `SetText` calls
that bypass `set_text`, without renaming objects or changing Ink variables,
save data or choice handlers. Skills, Gifts and retained foreign phrases are
not dictionary keys. Cyrillic uses the existing full font-family and guarded
canvas-atlas repair; tribe labels have an independently scoped layout patch.

Pure UI text regression tests (developer .NET 10 SDK, not a player dependency):

```powershell
dotnet run --project tests/UiTextCoreTests/UiTextCoreTests.csproj -- localization/ui-strings.json
```

`scripts/audit_game_ui.py` uses optional UnityPy 1.25.4 and
TypeTreeGeneratorAPI 0.0.10 for a read-only inventory of a local game install.
Keep raw inventories in ignored `work/`: serialized technical settings may
contain vendor credentials. `summarize_ui_audit.py` exports only whitelisted
metadata and hashes for a public receipt. Inventory and console tests are not
substitutes for live Unity layout checks. See `QA_REPORT.md` for tested scope.

Build locally:

```powershell
dotnet build .\src\PurgatoryRu\PurgatoryRu.csproj -c Release
```

Override `GameManagedDir` and `BepInExDir` MSBuild properties when the game or
BepInEx reference assemblies are in different locations.
