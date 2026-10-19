[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$SourcePath,
    [Parameter(Mandatory = $true)][string]$StoryPath,
    [Parameter(Mandatory = $true)][string]$ReportPath,
    [string]$GamePath = 'D:\SteamLibrary\steamapps\common\Purgatory'
)
# Developer QA requires PowerShell 7. No Unity UI or running save is accessed.
$ErrorActionPreference = 'Stop'
$managed = Join-Path $GamePath 'Purgatory_Data\Managed'
[Reflection.Assembly]::LoadFrom((Join-Path $managed 'Newtonsoft.Json.dll')) | Out-Null
$assembly = [Reflection.Assembly]::LoadFrom((Join-Path $managed 'Assembly-CSharp-firstpass.dll'))
$storyType = $assembly.GetType('Ink.Runtime.Story', $true)
$constructor = $storyType.GetConstructor([Type[]]@([string]))
$callbackType = $storyType.GetNestedType('ExternalFunction')
$callback = [scriptblock]{ param([object[]]$values) return [int]0 } -as $callbackType
$formNames = [ordered]@{ homid = 'Хомид'; glabro = 'Глабро'; hispo = 'Хиспо'; lupus = 'Люпус'; crinos = 'Кринос' }
$results = @()
foreach ($path in @($SourcePath, $StoryPath)) {
    $isSource = $path -eq $SourcePath
    $json = [IO.File]::ReadAllText((Resolve-Path -LiteralPath $path))
    $story = $constructor.Invoke([object[]]@($json))
    $externalNames = [regex]::Matches($json, '"x\(\)"\s*:\s*"([^"]+)"') |
        ForEach-Object { $_.Groups[1].Value } | Select-Object -Unique
    foreach ($name in $externalNames) { $story.BindExternalFunctionGeneral($name, $callback) }
    foreach ($form in @($formNames.Keys) + @('default', '__unknown_form_qa__')) {
        [string]$description = ''
        $null = $story.EvaluateFunction('changeform_description', [ref]$description, [object[]]@($form))
        $description = $description.Trim()
        $emptyExpected = !$formNames.Contains($form)
        if ($emptyExpected) {
            if ($description.Length -ne 0) { throw "Nonempty form description for $form source=$isSource" }
        }
        else {
            if ($description.Length -lt 30) { throw "Missing form description for $form source=$isSource" }
            $label = if ($isSource) { (Get-Culture).TextInfo.ToTitleCase($form) } else { $formNames[$form] }
            if (!$description.StartsWith("<b>$label</b>")) { throw "Wrong bold form label for $form source=$isSource" }
            if (!$isSource -and $description -notmatch '[А-Яа-яЁё]') { throw "Non-Russian form description for $form" }
            $tags = @([regex]::Matches($description, '<[^>]*>') | ForEach-Object Value)
            if (($tags -join '') -cne '<b></b>') { throw "Unexpected rich-text structure for $form source=$isSource" }
            if ($description -match '[⟦⟧]|>>>|ui-choice|renownMargin|\[\.\]') { throw "Unresolved renderer content for $form source=$isSource" }
        }
        $results += [ordered]@{ source = $isSource; form = $form; characters = $description.Length; emptyExpected = $emptyExpected; passed = $true }
    }
}
[ordered]@{
    passed = $true
    sourceSha256 = (Get-FileHash -LiteralPath $SourcePath -Algorithm SHA256).Hash
    storySha256 = (Get-FileHash -LiteralPath $StoryPath -Algorithm SHA256).Hash
    evaluations = $results.Count
    results = $results
    limitation = 'Evaluates the real game Ink function in isolation; atlas/material and visual layout require the plugin Unity UGUI self-test and in-game verification.'
} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $ReportPath -Encoding utf8
Write-Host "INK_FORMS_OK forms=5 empty-branches=2 evaluations=$($results.Count)"
