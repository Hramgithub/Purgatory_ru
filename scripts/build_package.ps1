[CmdletBinding()]
param(
    [string]$Version = '0.1.4'
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$SourceZip = Join-Path $Root 'third_party\downloads\BepInEx_win_x64_5.4.23.5.zip'
$PluginDll = Join-Path $Root 'src\PurgatoryRu\bin\Release\netstandard2.1\PurgatoryRu.dll'
$Story = Join-Path $Root 'dist\content\wod02.json'
$UiReport = Join-Path $Root 'dist\ui-command-report.json'
$SummaryReport = Join-Path $Root 'dist\chapter-summary-report.json'
$RenownReport = Join-Path $Root 'dist\renown-report.json'
$EditorialReport = Join-Path $Root 'localization\editorial-review.json'
$OutRoot = Join-Path $Root 'dist'
$Stage = Join-Path $OutRoot "Purgatory-RU-$Version"
$Payload = Join-Path $Stage 'payload'
$Archive = Join-Path $OutRoot "Purgatory-RU-$Version.zip"

foreach ($required in @($SourceZip, $PluginDll, $Story, $UiReport, $SummaryReport, $RenownReport, $EditorialReport)) {
    if (!(Test-Path -LiteralPath $required)) { throw "Required file missing: $required" }
}
$storyHash = (Get-FileHash -LiteralPath $Story -Algorithm SHA256).Hash
foreach ($reportPath in @($SummaryReport, $RenownReport)) {
    $runtimeQa = Get-Content -Raw -LiteralPath $reportPath | ConvertFrom-Json
    if (!$runtimeQa.passed -or $runtimeQa.storySha256 -ne $storyHash) {
        throw "Run the runtime QA against the current story before packaging: $reportPath"
    }
}
$summaryQa = Get-Content -Raw -LiteralPath $SummaryReport | ConvertFrom-Json
if ($summaryQa.command_count -ne 6) { throw 'Expected all six chapter-summary commands.' }
$renownQa = Get-Content -Raw -LiteralPath $RenownReport | ConvertFrom-Json
if (@($renownQa.results).Count -ne 2 -or
    @($renownQa.results | Where-Object { !$_.passed -or $_.cases -ne 5 -or $_.evaluations -ne 20 }).Count -ne 0) {
    throw 'Expected all five maxRenown cases on both original and translated stories.'
}
$editorialQa = Get-Content -Raw -LiteralPath $EditorialReport | ConvertFrom-Json
if (!$editorialQa.complete -or !$editorialQa.applied -or
    $editorialQa.reviewed_count -ne $editorialQa.catalog_items -or
    $editorialQa.context_checked_occurrences -ne $editorialQa.source_occurrences -or
    $editorialQa.story_sha256 -ne $storyHash) {
    throw 'A complete contextual editorial review tied to the current story is required.'
}
$uiQa = Get-Content -Raw -LiteralPath $UiReport | ConvertFrom-Json
if (!$uiQa.passed -or $uiQa.command_count -ne 8 -or
    $uiQa.storySha256 -ne (Get-FileHash -LiteralPath $Story -Algorithm SHA256).Hash) {
    throw 'Run Test-InkUiCommands.ps1 against the current story before packaging.'
}
foreach ($targetPath in @($Stage, $Archive)) {
    $resolvedTarget = [IO.Path]::GetFullPath($targetPath)
    $resolvedDist = [IO.Path]::GetFullPath($OutRoot).TrimEnd('\') + '\'
    if (!$resolvedTarget.StartsWith($resolvedDist, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing package cleanup outside dist: $resolvedTarget"
    }
}
if (Test-Path -LiteralPath $Stage) { Remove-Item -LiteralPath $Stage -Recurse -Force }
New-Item -ItemType Directory -Force -Path $Payload | Out-Null
Expand-Archive -LiteralPath $SourceZip -DestinationPath $Payload -Force

$PluginDir = Join-Path $Payload 'BepInEx\plugins\PurgatoryRu'
New-Item -ItemType Directory -Force -Path $PluginDir | Out-Null
Copy-Item -LiteralPath $PluginDll -Destination (Join-Path $PluginDir 'PurgatoryRu.dll')
Copy-Item -LiteralPath $Story -Destination (Join-Path $PluginDir 'wod02.json')
Copy-Item -Path (Join-Path $Root 'installer\*') -Destination $Stage -Force
Copy-Item -LiteralPath (Join-Path $Root 'COMPATIBILITY.md') -Destination $Stage -Force
Copy-Item -LiteralPath (Join-Path $Root 'GLOSSARY.md') -Destination $Stage -Force
Copy-Item -LiteralPath (Join-Path $Root 'QA_REPORT.md') -Destination $Stage -Force
Copy-Item -LiteralPath $UiReport -Destination (Join-Path $Stage 'UI-COMMAND-QA.json') -Force
Copy-Item -LiteralPath $SummaryReport -Destination (Join-Path $Stage 'CHAPTER-SUMMARY-QA.json') -Force
Copy-Item -LiteralPath $RenownReport -Destination (Join-Path $Stage 'RENOWN-QA.json') -Force
Copy-Item -LiteralPath $EditorialReport -Destination (Join-Path $Stage 'EDITORIAL-REVIEW.json') -Force
Copy-Item -LiteralPath (Join-Path $Root 'localization\render_overrides.json') -Destination (Join-Path $Stage 'RENDER-CORRECTIONS.json') -Force

# Windows PowerShell 5.1 (used by install.bat) requires a BOM for Cyrillic.
Get-ChildItem -LiteralPath $Stage -Filter '*.ps1' -File | ForEach-Object {
    $scriptText = [System.IO.File]::ReadAllText($_.FullName)
    [System.IO.File]::WriteAllText($_.FullName, $scriptText, [System.Text.UTF8Encoding]::new($true))
}

$files = Get-ChildItem -LiteralPath $Stage -Recurse -File | ForEach-Object {
    [ordered]@{
        path = $_.FullName.Substring($Stage.Length).TrimStart('\', '/') -replace '\\', '/'
        size = $_.Length
        sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    }
}
$manifest = [ordered]@{
    package = 'Purgatory Russian Localization'
    version = $Version
    createdAt = (Get-Date).ToUniversalTime().ToString('o')
    files = @($files)
}
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $Stage 'manifest.json') -Encoding UTF8

if (Test-Path -LiteralPath $Archive) { Remove-Item -LiteralPath $Archive -Force }
Compress-Archive -LiteralPath $Stage -DestinationPath $Archive -CompressionLevel Optimal
Get-FileHash -LiteralPath $Archive -Algorithm SHA256
