# PurgatoryRu plugin

The plugin patches only `Ink.Runtime.Story(string)` and replaces the main
`wod02` story when its stable marker is present. It does not intercept arbitrary
TextMeshPro or Unity UI setters, so unrelated interface strings and protected
skill/Gift titles are not rewritten by a broad runtime dictionary.

Build locally:

```powershell
dotnet build .\src\PurgatoryRu\PurgatoryRu.csproj -c Release
```

Override `GameManagedDir` and `BepInExDir` MSBuild properties when the game or
BepInEx reference assemblies are in different locations.
