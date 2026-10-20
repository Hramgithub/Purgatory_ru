[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$SourcePath,
    [Parameter(Mandatory = $true)][string]$StoryPath,
    [Parameter(Mandatory = $true)][string]$ReportPath,
    [string]$GamePath = 'D:\SteamLibrary\steamapps\common\Purgatory'
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$managed = Join-Path $GamePath 'Purgatory_Data\Managed'
[Reflection.Assembly]::LoadFrom((Join-Path $managed 'Newtonsoft.Json.dll')) | Out-Null
$assembly = [Reflection.Assembly]::LoadFrom((Join-Path $managed 'Assembly-CSharp-firstpass.dll'))
$storyType = $assembly.GetType('Ink.Runtime.Story', $true)
$constructor = $storyType.GetConstructor([Type[]]@([string]))
$sourceJson = [IO.File]::ReadAllText((Resolve-Path $SourcePath))
$translatedJson = [IO.File]::ReadAllText((Resolve-Path $StoryPath))
$documents = @($sourceJson, $translatedJson) | ForEach-Object { ConvertFrom-Json -InputObject $_ -AsHashtable -Depth 100 }
$index = Get-Content -Raw -Encoding UTF8 (Join-Path $root 'localization/index.json') | ConvertFrom-Json
$chunk = Get-Content -Raw -Encoding UTF8 (Join-Path $root 'localization/ru/chunk-0064.json') | ConvertFrom-Json
$results = @()
foreach ($record in @($index.items | Where-Object { $_.id -ge 14067 })) {
    $path = @($record.first_path)
    $expected = @($chunk.items | Where-Object { $_.id -eq $record.id })
    if ($expected.Count -ne 1) { throw "Missing translation at id $($record.id)" }
    $lines = @()
    foreach ($document in $documents) {
        $literal = $document
        foreach ($part in $path) { $literal = $literal[$part] }
        # Isolate the original compiled choice's literal inside Ink's own
        # string-evaluation commands. Conditional availability is NOT tested;
        # no player's save, choices or game state are loaded or changed.
        $probe = [ordered]@{ inkVersion=$document.inkVersion;
            root=@('ev', 'str', $literal, '/str', 'out', '/ev', "`n", 'done', $null);
            listDefs=@{} } | ConvertTo-Json -Depth 20 -Compress
        $story = $constructor.Invoke([object[]]@([string]$probe))
        $lines += $story.Continue().Trim()
    }
    $prefix = $record.prefix.Substring(1)
    if (!$lines[0].StartsWith($prefix) -or $lines[1] -cne ($prefix + $expected[0].translation)) {
        throw "Map label differs at id $($record.id)"
    }
    $results += [ordered]@{ id=$record.id; json_path=$path; marker=$prefix.Trim(); passed=$true }
}
if ($results.Count -ne 15) { throw 'Expected 15 unique map labels' }
$barCases = @()
$callback = [scriptblock]{ param([object[]]$values) return [int]0 } -as $storyType.GetNestedType('ExternalFunction')
$externalNames = [regex]::Matches($sourceJson, '"x\(\)"\s*:\s*"([^"]+)"') |
    ForEach-Object { $_.Groups[1].Value } | Select-Object -Unique
foreach ($json in @($sourceJson, $translatedJson)) {
    $bar = $constructor.Invoke([object[]]@($json))
    foreach ($name in $externalNames) { $bar.BindExternalFunctionGeneral($name, $callback) }
    # Starts at the bar's choice-generating code. Fresh globals; all external
    # functions are stubbed to 0. No save is loaded and no choice is selected.
    $bar.ChoosePathString('garoubar.barmap.0.10', $true, [object[]]@())
    $continues = 0
    while ($bar.canContinue) {
        $null = $bar.Continue()
        if (++$continues -gt 100) { throw 'Unexpected loop while generating bar choices' }
    }
    $choices = @($bar.currentChoices)
    if ($choices.Count -ne 3) { throw 'Expected three generated bar choices' }
    for ($i = 0; $i -lt 3; $i++) {
        $entry = $index.items[14067+$i]
        $literal = $json | ConvertFrom-Json -AsHashtable -Depth 100
        foreach ($part in $entry.first_path) { $literal = $literal[$part] }
        if ($choices[$i].text -cne $literal.Substring(1)) { throw 'Generated bar choice differs from its indexed literal' }
    }
    $barCases += [ordered]@{ source=($json -ceq $sourceJson); choices=$choices.Count; passed=$true }
}
[ordered]@{
    passed=$true; evaluations=$results.Count; scope='Isolated compiled string evaluation, not branch availability or Unity layout';
    sourceSha256=(Get-FileHash $SourcePath).Hash;
    storySha256=(Get-FileHash $StoryPath).Hash; results=$results;
    bar_choice_generation=[ordered]@{ path='garoubar.barmap.0.10';
        fresh_globals=$true; external_functions_stubbed_to=0; cases=$barCases }
} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ReportPath -Encoding utf8
Write-Host "INK_MAP_OK evaluations=$($results.Count) markers=unchanged"
