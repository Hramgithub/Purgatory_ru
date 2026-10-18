[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$SourcePath,
    [Parameter(Mandatory = $true)][string]$StoryPath,
    [Parameter(Mandatory = $true)][string]$LocationsPath,
    [Parameter(Mandatory = $true)][string]$ReportPath,
    [string]$GamePath = 'D:\SteamLibrary\steamapps\common\Purgatory'
)
$ErrorActionPreference = 'Stop'
$managed = Join-Path $GamePath 'Purgatory_Data\Managed'
[Reflection.Assembly]::LoadFrom((Join-Path $managed 'Newtonsoft.Json.dll')) | Out-Null
$assembly = [Reflection.Assembly]::LoadFrom((Join-Path $managed 'Assembly-CSharp-firstpass.dll'))
$storyType = $assembly.GetType('Ink.Runtime.Story', $true)
$constructor = $storyType.GetConstructor([Type[]]@([string]))
$callbackType = $storyType.GetNestedType('ExternalFunction')
$callback = [scriptblock]{ param([object[]]$values) return [int]0 } -as $callbackType
$sourceJson = [IO.File]::ReadAllText((Resolve-Path -LiteralPath $SourcePath))
$translatedJson = [IO.File]::ReadAllText((Resolve-Path -LiteralPath $StoryPath))
$externalNames = [regex]::Matches($sourceJson, '"x\(\)"\s*:\s*"([^"]+)"') |
    ForEach-Object { $_.Groups[1].Value } | Select-Object -Unique
$locations = @(Get-Content -Raw -LiteralPath $LocationsPath | ConvertFrom-Json)
if ($locations.Count -eq 0) { throw 'No chapter-summary command locations supplied.' }
$results = @()
foreach ($location in $locations) {
    $commands = @()
    foreach ($json in @($sourceJson, $translatedJson)) {
        $story = $constructor.Invoke([object[]]@($json))
        foreach ($name in $externalNames) { $story.BindExternalFunctionGeneral($name, $callback) }
        $story.ChoosePathString([string]$location, $true, [object[]]@())
        $line = $story.Continue().Trim()
        if (!$line.StartsWith('>>> ui-social-choices')) { throw "Wrong command at $location" }
        $commands += $line
    }
    # The game splits on ASCII quotes. Everything OUTSIDE the translated
    # descriptions is metadata: section IDs, selection keys and option counts.
    $skeletons = @()
    $fieldCounts = @()
    foreach ($command in $commands) {
        $parts = $command.Split([char]'"')
        if (($parts.Count % 2) -ne 1) { throw "Unbalanced ASCII fields at $location" }
        $outside = @()
        for ($index = 0; $index -lt $parts.Count; $index += 2) { $outside += $parts[$index] }
        $skeletons += (($outside -join '""') -replace '\s+', ' ').Trim()
        $fieldCounts += [int](($parts.Count - 1) / 2)
    }
    if ($fieldCounts[0] -ne $fieldCounts[1] -or $fieldCounts[0] -eq 0) {
        throw "Summary quoted field counts differ at $location"
    }
    if ($skeletons[0] -cne $skeletons[1]) { throw "Summary metadata keys/counts changed at $location" }
    $results += [ordered]@{ path = $location; fields = $fieldCounts[1]; metadataMatched = $true; passed = $true }
}
$report = [ordered]@{
    command_count = $results.Count
    passed = $true
    sourceSha256 = (Get-FileHash -LiteralPath $SourcePath -Algorithm SHA256).Hash
    storySha256 = (Get-FileHash -LiteralPath $StoryPath -Algorithm SHA256).Hash
    commands = $results
    limitation = 'Invokes each summary directly with default Ink state; not a playthrough or save-state branch exhaustiveness test.'
}
$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ReportPath -Encoding utf8
Write-Host "INK_SUMMARIES_OK commands=$($results.Count) metadata=matched"
