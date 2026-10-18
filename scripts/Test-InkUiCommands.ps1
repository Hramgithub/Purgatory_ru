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
$sourceJson = [IO.File]::ReadAllText((Resolve-Path $SourcePath))
$translatedJson = [IO.File]::ReadAllText((Resolve-Path $StoryPath))
$externalNames = [regex]::Matches($sourceJson, '"x\(\)"\s*:\s*"([^"]+)"') |
    ForEach-Object { $_.Groups[1].Value } | Select-Object -Unique
$locations = Get-Content -Raw $LocationsPath | ConvertFrom-Json
$results = @()
foreach ($location in $locations) {
    $commands = @()
    foreach ($json in @($sourceJson, $translatedJson)) {
        $story = $constructor.Invoke([object[]]@($json))
        foreach ($name in $externalNames) { $story.BindExternalFunctionGeneral($name, $callback) }
        $story.ChoosePathString([string]$location, $true, [object[]]@())
        $line = $story.Continue().Trim()
        if (!$line.StartsWith('>>> ui-character-creation')) { throw "Wrong command at $location" }
        $commands += $line
    }
    # This command uses seven quoted fields; fields 3-6 contain equally sized pipe lists.
    $originalFields = @([regex]::Matches($commands[0], '"([^"]*)"') | ForEach-Object { $_.Groups[1].Value })
    $translatedFields = @([regex]::Matches($commands[1], '"([^"]*)"') | ForEach-Object { $_.Groups[1].Value })
    if ($originalFields.Count -ne 7 -or $translatedFields.Count -ne 7) {
        throw "Expected 7 quoted fields at $location; EN=$($originalFields.Count), RU=$($translatedFields.Count)"
    }
    if ($commands[1] -match '[«»“”]') { throw "Typographic quote in command at $location" }
    $counts = @()
    foreach ($index in 2..5) {
        $before = $originalFields[$index].Split('|').Count
        $after = $translatedFields[$index].Split('|').Count
        if ($before -ne $after) { throw "Pipe field $index differs at $location" }
        $counts += $after
    }
    if (($counts | Select-Object -Unique).Count -ne 1) { throw "Option lists have different sizes at $location" }
    foreach ($index in @(2,5,6)) {
        if ($originalFields[$index] -cne $translatedFields[$index]) { throw "Internal UI field $index changed at $location" }
    }
    $results += [ordered]@{ path = $location; options = $counts[0]; fields = $translatedFields; passed = $true }
}
$report = [ordered]@{
    command_count = $results.Count
    passed = $true
    sourceSha256 = (Get-FileHash -LiteralPath $SourcePath -Algorithm SHA256).Hash
    storySha256 = (Get-FileHash -LiteralPath $StoryPath -Algorithm SHA256).Hash
    commands = $results
}
$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ReportPath -Encoding utf8
Write-Host "INK_UI_OK commands=$($results.Count) quoted_fields=7 option_lists=matched"
