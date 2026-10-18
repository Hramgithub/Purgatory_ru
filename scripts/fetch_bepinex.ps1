[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$DownloadDir = Join-Path $Root 'third_party\downloads'
$Archive = Join-Path $DownloadDir 'BepInEx_win_x64_5.4.23.5.zip'
$ExpectedSha256 = '82F9878551030F54657792C0740D9D51A09500EEAE1FBA21106B0C441E6732C4'
$Uri = 'https://github.com/BepInEx/BepInEx/releases/download/v5.4.23.5/BepInEx_win_x64_5.4.23.5.zip'

New-Item -ItemType Directory -Force -Path $DownloadDir | Out-Null
if (!(Test-Path -LiteralPath $Archive)) {
    Invoke-WebRequest -Uri $Uri -OutFile $Archive
}
$actual = (Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash
if ($actual -ne $ExpectedSha256) {
    throw "BepInEx archive hash mismatch. Expected $ExpectedSha256, got $actual"
}
Write-Host "BepInEx 5.4.23.5 verified: $actual"
