[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$SourcePath,
    [Parameter(Mandatory = $true)][string]$StoryPath,
    [Parameter(Mandatory = $true)][string]$ReportPath,
    [string]$GamePath = 'D:\SteamLibrary\steamapps\common\Purgatory'
)
# Developer QA: PowerShell 7; isolated Ink state, never a running save/UI.
$ErrorActionPreference = 'Stop'
$managed = Join-Path $GamePath 'Purgatory_Data\Managed'
[Reflection.Assembly]::LoadFrom((Join-Path $managed 'Newtonsoft.Json.dll')) | Out-Null
$assembly = [Reflection.Assembly]::LoadFrom((Join-Path $managed 'Assembly-CSharp-firstpass.dll'))
$storyType = $assembly.GetType('Ink.Runtime.Story', $true)
$constructor = $storyType.GetConstructor([Type[]]@([string]))
$callbackType = $storyType.GetNestedType('ExternalFunction')
$zeroCallback = [scriptblock]{ param([object[]]$values) return [int]0 } -as $callbackType
$listCallback = [scriptblock]{
    param([object[]]$values)
    $key = [string]$values[0]
    $definition, $value = switch ($key) {
        'name' { 'namevalue'; $script:qaChosenName }
        'tribe' { 'tribevalue'; 'BLACKFURIES' }
        'auspice' { 'auspicevalue'; 'AHROUN' }
        'packpatron' { 'packvalue'; 'LYNX' }
        { $_ -in @('renown1', 'renown2', 'renown3') } { 'pathlevel'; 'ONE' }
        default { 'pathlevel'; 'ZERO' }
    }
    $list = [Ink.Runtime.InkList]::new($definition, $script:qaNameStory)
    $list.AddItem($value)
    return ,$list
} -as $callbackType
$cases = [ordered]@{ ZOHAL = @('Zohal', 'Зохаль'); QUOY = @('Quoy', 'Куой'); MINU = @('Minu', 'Мину');
                       PARISA = @('Parisa', 'Париса'); AZADEH = @('Azadeh', 'Азаде'); SAMIRASHORT = @('Samira', 'Самира') }
$results = @()
foreach ($path in @($SourcePath, $StoryPath)) {
    $isSource = $path -eq $SourcePath
    $json = [IO.File]::ReadAllText((Resolve-Path -LiteralPath $path))
    foreach ($case in $cases.Keys) {
        $script:qaNameStory = $constructor.Invoke([object[]]@($json))
        $script:qaChosenName = $case
        $externalNames = [regex]::Matches($json, '"x\(\)"\s*:\s*"([^"]+)"') |
            ForEach-Object { $_.Groups[1].Value } | Select-Object -Unique
        foreach ($name in $externalNames) {
            $callback = if ($name -eq 'getListBackpackItem') { $listCallback } else { $zeroCallback }
            $script:qaNameStory.BindExternalFunctionGeneral($name, $callback)
        }
        [string]$nameText = ''
        $null = $script:qaNameStory.EvaluateFunction('getNameString', [ref]$nameText, [object[]]@())
        $expected = $cases[$case][[int](!$isSource)]
        if ($nameText.Trim() -cne $expected) { throw "getNameString output mismatch case=$case source=$isSource" }
        # Start at the END-STORY command, before the runtime name insertion.
        $script:qaNameStory.ChoosePathString('epilogues.finish.0.24.18', $true, [object[]]@())
        $ending = $script:qaNameStory.ContinueMaximally().Trim()
        if (!$ending.StartsWith('>>> END-STORY "') -or !$ending.EndsWith('"') -or
                ([regex]::Matches($ending, '"')).Count -ne 2) {
            throw "END-STORY command continuation/delimiters failed case=$case source=$isSource"
        }
        if (!$ending.Contains($expected)) { throw "END-STORY lost generated name case=$case source=$isSource" }
        if ($ending -match '⟦T\d{3}⟧|\^>>>') { throw "END-STORY unresolved renderer content case=$case source=$isSource" }
        $results += [ordered]@{ source = $isSource; case = $case; commandCharacters = $ending.Length;
                              generatedNameCharacters = $nameText.Trim().Length; passed = $true }
    }
    foreach ($entry in @('SAMIRASHORT', 'SAMIRAFULL')) {
        $list = [Ink.Runtime.InkList]::new('namevalue', $script:qaNameStory)
        $list.AddItem($entry)
        $identity = $list.ToString()
        [string]$display = ''
        $null = $script:qaNameStory.EvaluateFunction('list_display', [ref]$display, [object[]]@($list))
        if ([string]::IsNullOrWhiteSpace($display) -or $list.ToString() -cne $identity) {
            throw "list_display changed list identity or lost output case=$entry source=$isSource"
        }
        $results += [ordered]@{ source = $isSource; case = "list_display:$entry";
                              displayCharacters = $display.Trim().Length; identityPreserved = $true; passed = $true }
    }
}
[ordered]@{
    passed = $true
    sourceSha256 = (Get-FileHash -LiteralPath $SourcePath -Algorithm SHA256).Hash
    storySha256 = (Get-FileHash -LiteralPath $StoryPath -Algorithm SHA256).Hash
    cases = $results.Count
    results = $results
    limitation = 'Controlled list callbacks and default ending facts; verifies command gluing and dispatch, not all ending branches or live TMP display replacement.'
} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $ReportPath -Encoding utf8
Write-Host "INK_NAMES_OK ending-name-cases=12 list-display-cases=4 identities=preserved"
