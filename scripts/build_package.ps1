[CmdletBinding()]
param(
    [string]$Version = '0.1.5'
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
$NamePolicy = Join-Path $Root 'localization\name-localization.json'
$UiStrings = Join-Path $Root 'localization\ui-strings.json'
$UiCoverageReview = Join-Path $Root 'localization\ui-coverage-review.json'
$NameForms = Join-Path $Root 'localization\name-forms.json'
$NameFragments = Join-Path $Root 'localization\name-fragments.json'
$NameAudit = Join-Path $Root 'localization\name-review-audit.json'
$NameReport = Join-Path $Root 'dist\name-qa-report.json'
$FormsReport = Join-Path $Root 'dist\forms-report.json'
$NameContinuationsReport = Join-Path $Root 'dist\name-continuations-report.json'
$RetainedTerms = Join-Path $Root 'localization\retained-terms.json'
$FormRenderReview = Join-Path $Root 'localization\form-render-review.json'
# The v0.1.4 editorial receipt is immutable evidence for the baseline, not v0.1.5.
$EditorialBaselineStoryHash = '2c7afd169a941ddd43bfb661c3b211b12e53066d5a2e7b60f1a0dd8041a1f46b'
$OutRoot = Join-Path $Root 'dist'
$Stage = Join-Path $OutRoot "Purgatory-RU-$Version"
$Payload = Join-Path $Stage 'payload'
$Archive = Join-Path $OutRoot "Purgatory-RU-$Version.zip"

foreach ($required in @($SourceZip, $PluginDll, $Story, $UiReport, $SummaryReport, $RenownReport,
        $EditorialReport, $NamePolicy, $NameForms, $NameFragments, $NameAudit, $NameReport, $FormsReport,
        $NameContinuationsReport, $RetainedTerms, $FormRenderReview, $UiStrings, $UiCoverageReview)) {
    if (!(Test-Path -LiteralPath $required)) { throw "Required file missing: $required" }
}
$Python = Join-Path $Root '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $Python)) { $Python = 'python' }
& $Python (Join-Path $Root 'scripts\verify_release_privacy.py') $PluginDll
if ($LASTEXITCODE -ne 0) { throw 'Release DLL contains private paths or symbols.' }
$storyHash = (Get-FileHash -LiteralPath $Story -Algorithm SHA256).Hash
$uiCoverageQa = Get-Content -Raw -Encoding UTF8 -LiteralPath $UiCoverageReview | ConvertFrom-Json
if ($uiCoverageQa.live_review.passed -ne $true -or
    $uiCoverageQa.story_sha256 -ne $storyHash -or
    $uiCoverageQa.plugin_sha256 -ne (Get-FileHash -LiteralPath $PluginDll -Algorithm SHA256).Hash -or
    $uiCoverageQa.ui_dictionary_sha256 -ne (Get-FileHash -LiteralPath $UiStrings -Algorithm SHA256).Hash) {
    throw 'Repeat limited live UI QA for the current story, DLL and UI dictionary before packaging.'
}
$renderQa = Get-Content -Raw -Encoding UTF8 -LiteralPath $FormRenderReview | ConvertFrom-Json
if ($renderQa.passed -ne $true -or $renderQa.story_sha256 -ne $storyHash -or
    $renderQa.dll_sha256 -ne (Get-FileHash -LiteralPath $PluginDll -Algorithm SHA256).Hash -or
    @($renderQa.cases).Count -ne 4 -or @($renderQa.cases | Where-Object { $_.passed -ne $true }).Count -ne 0) {
    throw 'Live form-render QA must match the current DLL and story before packaging.'
}
foreach ($reportPath in @($SummaryReport, $RenownReport)) {
    $runtimeQa = Get-Content -Raw -Encoding UTF8 -LiteralPath $reportPath | ConvertFrom-Json
    if (!$runtimeQa.passed -or $runtimeQa.storySha256 -ne $storyHash) {
        throw "Run the runtime QA against the current story before packaging: $reportPath"
    }
}
$summaryQa = Get-Content -Raw -Encoding UTF8 -LiteralPath $SummaryReport | ConvertFrom-Json
if ($summaryQa.command_count -ne 6) { throw 'Expected all six chapter-summary commands.' }
$renownQa = Get-Content -Raw -Encoding UTF8 -LiteralPath $RenownReport | ConvertFrom-Json
if (@($renownQa.results).Count -ne 2 -or
    @($renownQa.results | Where-Object { !$_.passed -or $_.cases -ne 5 -or $_.evaluations -ne 20 }).Count -ne 0) {
    throw 'Expected all five maxRenown cases on both original and translated stories.'
}
$editorialQa = Get-Content -Raw -Encoding UTF8 -LiteralPath $EditorialReport | ConvertFrom-Json
if (!$editorialQa.complete -or !$editorialQa.applied -or
    $editorialQa.reviewed_count -ne $editorialQa.catalog_items -or
    $editorialQa.context_checked_occurrences -ne $editorialQa.source_occurrences -or
    $editorialQa.story_sha256 -ne $EditorialBaselineStoryHash) {
    throw 'The complete v0.1.4 contextual editorial baseline receipt is required unchanged.'
}
$nameFormsQa = Get-Content -Raw -Encoding UTF8 -LiteralPath $NameForms | ConvertFrom-Json
$nameAuditQa = Get-Content -Raw -Encoding UTF8 -LiteralPath $NameAudit | ConvertFrom-Json
$nameItems = @($nameFormsQa.items)
$nameSlots = 0
foreach ($item in $nameItems) { $nameSlots += @($item.forms).Count }
if ($nameFormsQa.format -ne 1 -or $nameItems.Count -eq 0 -or
    $nameFormsQa.reviewed_count -ne $nameItems.Count -or
    @($nameItems.id | Select-Object -Unique).Count -ne $nameItems.Count -or
    $nameSlots -le 0 -or $nameAuditQa.complete -ne $true -or
    $nameAuditQa.baseline_story_sha256 -ne $editorialQa.story_sha256 -or
    $nameAuditQa.story_sha256 -ne $storyHash -or
    $nameAuditQa.reviewed_count -ne $nameItems.Count -or
    $nameAuditQa.reviewed_slots -ne $nameSlots) {
    throw 'A complete name review tied to the editorial baseline, current story, IDs and slots is required.'
}
$nameQa = Get-Content -Raw -Encoding UTF8 -LiteralPath $NameReport | ConvertFrom-Json
if ($nameQa.passed -ne $true -or $nameQa.storySha256 -ne $storyHash) {
    throw 'Run name QA against the current story before packaging.'
}
foreach ($relative in @('localization/name-localization.json', 'localization/name-forms.json',
        'localization/name-fragments.json', 'localization/retained-terms.json')) {
    $actualHash = (Get-FileHash -LiteralPath (Join-Path $Root $relative) -Algorithm SHA256).Hash
    if ($nameAuditQa.artifacts.$relative -ne $actualHash) { throw "Name audit artifact drift: $relative" }
}
$continuationQa = Get-Content -Raw -Encoding UTF8 -LiteralPath $NameContinuationsReport | ConvertFrom-Json
if ($continuationQa.passed -ne $true -or $continuationQa.storySha256 -ne $storyHash) {
    throw 'Run the ending-name continuation checks against the current story.'
}
$formsQa = Get-Content -Raw -Encoding UTF8 -LiteralPath $FormsReport | ConvertFrom-Json
$formResults = @($formsQa.results)
$expectedFormCases = @('homid', 'glabro', 'hispo', 'lupus', 'crinos', 'default', '__unknown_form_qa__')
if ($formsQa.passed -ne $true -or $formsQa.storySha256 -ne $storyHash -or
    $formsQa.sourceSha256 -ne $editorialQa.source_sha256 -or
    $formsQa.evaluations -ne 14 -or $formResults.Count -ne 14 -or
    @($formResults | Where-Object { $_.passed -ne $true -or $_.source -isnot [bool] }).Count -ne 0) {
    throw 'Expected 14 successful form-description evaluations on the original and current stories.'
}
foreach ($isSource in @($true, $false)) {
    $cases = @($formResults | Where-Object { $_.source -eq $isSource })
    if ($cases.Count -ne 7) { throw 'Expected seven form cases for each story.' }
    foreach ($form in $expectedFormCases) {
        $case = @($cases | Where-Object { $_.form -ceq $form })
        $emptyExpected = $form -in @('default', '__unknown_form_qa__')
        if ($case.Count -ne 1 -or $case[0].emptyExpected -isnot [bool] -or
            $case[0].emptyExpected -ne $emptyExpected -or
            ($emptyExpected -and $case[0].characters -ne 0) -or
            (!$emptyExpected -and $case[0].characters -lt 30)) {
            throw "Invalid or duplicate form case: $form source=$isSource"
        }
    }
}
$uiQa = Get-Content -Raw -Encoding UTF8 -LiteralPath $UiReport | ConvertFrom-Json
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
Copy-Item -LiteralPath $NamePolicy -Destination (Join-Path $PluginDir 'name-localization.json')
Copy-Item -LiteralPath $UiStrings -Destination (Join-Path $PluginDir 'ui-strings.json')
Copy-Item -Path (Join-Path $Root 'installer\*') -Destination $Stage -Force
Copy-Item -LiteralPath (Join-Path $Root 'COMPATIBILITY.md') -Destination $Stage -Force
Copy-Item -LiteralPath (Join-Path $Root 'GLOSSARY.md') -Destination $Stage -Force
Copy-Item -LiteralPath (Join-Path $Root 'QA_REPORT.md') -Destination $Stage -Force
Copy-Item -LiteralPath $UiReport -Destination (Join-Path $Stage 'UI-COMMAND-QA.json') -Force
Copy-Item -LiteralPath $UiCoverageReview -Destination (Join-Path $Stage 'UI-COVERAGE-QA.json') -Force
Copy-Item -LiteralPath $SummaryReport -Destination (Join-Path $Stage 'CHAPTER-SUMMARY-QA.json') -Force
Copy-Item -LiteralPath $RenownReport -Destination (Join-Path $Stage 'RENOWN-QA.json') -Force
Copy-Item -LiteralPath $EditorialReport -Destination (Join-Path $Stage 'EDITORIAL-REVIEW.json') -Force
Copy-Item -LiteralPath $NameForms -Destination (Join-Path $Stage 'NAME-FORMS.json') -Force
Copy-Item -LiteralPath $NameFragments -Destination (Join-Path $Stage 'NAME-FRAGMENTS.json') -Force
Copy-Item -LiteralPath $NameAudit -Destination (Join-Path $Stage 'NAME-REVIEW-AUDIT.json') -Force
Copy-Item -LiteralPath $FormRenderReview -Destination (Join-Path $Stage 'FORM-RENDER-QA.json') -Force
Copy-Item -LiteralPath $RetainedTerms -Destination (Join-Path $Stage 'RETAINED-TERMS.json') -Force
Copy-Item -LiteralPath $NameContinuationsReport -Destination (Join-Path $Stage 'NAME-CONTINUATIONS-QA.json') -Force
Copy-Item -LiteralPath $NameReport -Destination (Join-Path $Stage 'NAME-QA.json') -Force
Copy-Item -LiteralPath $FormsReport -Destination (Join-Path $Stage 'FORMS-QA.json') -Force
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

& $Python (Join-Path $Root 'scripts\verify_release_privacy.py') $Stage
if ($LASTEXITCODE -ne 0) { throw 'Package privacy verification failed.' }
if (Test-Path -LiteralPath $Archive) { Remove-Item -LiteralPath $Archive -Force }
Compress-Archive -LiteralPath $Stage -DestinationPath $Archive -CompressionLevel Optimal
Get-FileHash -LiteralPath $Archive -Algorithm SHA256
