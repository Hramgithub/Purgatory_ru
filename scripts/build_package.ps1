[CmdletBinding()]
param(
    [string]$Version = '0.1.0'
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$SourceZip = Join-Path $Root 'third_party\downloads\BepInEx_win_x64_5.4.23.5.zip'
$PluginDll = Join-Path $Root 'src\PurgatoryRu\bin\Release\netstandard2.1\PurgatoryRu.dll'
$Story = Join-Path $Root 'dist\content\wod02.json'
$OutRoot = Join-Path $Root 'dist'
$Stage = Join-Path $OutRoot "Purgatory-RU-$Version"
$Payload = Join-Path $Stage 'payload'
$Archive = Join-Path $OutRoot "Purgatory-RU-$Version.zip"

foreach ($required in @($SourceZip, $PluginDll, $Story)) {
    if (!(Test-Path -LiteralPath $required)) { throw "Required file missing: $required" }
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
