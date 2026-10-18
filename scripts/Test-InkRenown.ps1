[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$SourcePath,
    [Parameter(Mandatory = $true)][string]$StoryPath,
    [Parameter(Mandatory = $true)][string]$ReportPath,
    [string]$GamePath = 'D:\SteamLibrary\steamapps\common\Purgatory'
)
# Developer QA: run with PowerShell 7 (pwsh), not the player's PS5 installer.
$ErrorActionPreference = 'Stop'
$managed = Join-Path $GamePath 'Purgatory_Data\Managed'
[Reflection.Assembly]::LoadFrom((Join-Path $managed 'Newtonsoft.Json.dll')) | Out-Null
$assembly = [Reflection.Assembly]::LoadFrom((Join-Path $managed 'Assembly-CSharp-firstpass.dll'))
$storyType = $assembly.GetType('Ink.Runtime.Story', $true)
$constructor = $storyType.GetConstructor([Type[]]@([string]))
$callbackType = $storyType.GetNestedType('ExternalFunction')
$zeroCallback = [scriptblock]{ param([object[]]$values) return [int]0 } -as $callbackType
$callback = [scriptblock]{
    param([object[]]$values)
    $list = [Ink.Runtime.InkList]::new('pathlevel', $script:qaRenownStory)
    $list.AddItem([string]$script:qaRenownLevels[[string]$values[0]])
    return ,$list
} -as $callbackType
$cases = @(
    @{ levels = @('ONE', 'ONE', 'ONE'); expected = @(1, 1, 1, 1) },
    @{ levels = @('ONE', 'ONE', 'TWO'); expected = @(0, 1, 0, 0) },
    @{ levels = @('TWO', 'ONE', 'ONE'); expected = @(0, 0, 0, 1) },
    @{ levels = @('ONE', 'TWO', 'ONE'); expected = @(0, 0, 1, 0) },
    @{ levels = @('TWO', 'TWO', 'ONE'); expected = @(0, 0, 1, 1) }
)
$names = @('balanced', 'glory', 'wisdom', 'honor')
$results = @()
foreach ($path in @($SourcePath, $StoryPath)) {
    $json = [IO.File]::ReadAllText((Resolve-Path -LiteralPath $path))
    $script:qaRenownStory = $constructor.Invoke([object[]]@($json))
    $externalNames = [regex]::Matches($json, '"x\(\)"\s*:\s*"([^"]+)"') |
        ForEach-Object { $_.Groups[1].Value } | Select-Object -Unique
    foreach ($name in $externalNames) {
        if ($name -ne 'getListBackpackItem') { $script:qaRenownStory.BindExternalFunctionGeneral($name, $zeroCallback) }
    }
    $script:qaRenownStory.BindExternalFunctionGeneral('getListBackpackItem', $callback)
    for ($caseIndex = 0; $caseIndex -lt $cases.Count; $caseIndex++) {
        $case = $cases[$caseIndex]
        $script:qaRenownLevels = @{ renown1 = $case.levels[0]; renown2 = $case.levels[1]; renown3 = $case.levels[2] }
        for ($index = 0; $index -lt $names.Count; $index++) {
            $actual = $script:qaRenownStory.EvaluateFunction('maxRenown', [object[]]@($names[$index]))
            if ([int]$actual -ne $case.expected[$index]) {
                throw "maxRenown regression case=$caseIndex kind=$($names[$index]) expected=$($case.expected[$index]) actual=$actual"
            }
        }
    }
    $results += [ordered]@{ source = ($path -eq $SourcePath); cases = $cases.Count; evaluations = ($cases.Count * $names.Count); passed = $true }
}
[ordered]@{
    passed = $true
    sourceSha256 = (Get-FileHash -LiteralPath $SourcePath -Algorithm SHA256).Hash
    storySha256 = (Get-FileHash -LiteralPath $StoryPath -Algorithm SHA256).Hash
    results = $results
    limitation = 'Game Ink function evaluated with controlled inventory callback; not an in-game save-state playthrough.'
} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $ReportPath -Encoding utf8
Write-Host 'INK_RENOWN_OK cases=5 evaluations=40 balanced-and-ties=verified'
