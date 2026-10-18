[CmdletBinding()]
param(
    [string]$GamePath,
    [switch]$NoPause
)

$ErrorActionPreference = 'Stop'
if (!$GamePath) {
    $GamePath = Read-Host 'Укажите полный путь к папке игры Purgatory'
}
$Target = [System.IO.Path]::GetFullPath($GamePath)
if (!(Test-Path -LiteralPath (Join-Path $Target 'Purgatory.exe'))) {
    throw "Purgatory.exe не найден в $Target"
}

$pluginRoot = Join-Path $Target 'BepInEx\plugins\PurgatoryRu'
if (Test-Path -LiteralPath $pluginRoot) {
    Remove-Item -LiteralPath $pluginRoot -Recurse -Force
    Write-Host 'Файлы русской локализации удалены.' -ForegroundColor Green
} else {
    Write-Host 'Русская локализация не найдена.'
}
Write-Host 'BepInEx оставлен на месте: он может использоваться другими модами.'
Write-Host 'Резервные копии в .purgatory-ru-backup сохранены и не удалялись.'
if (!$NoPause) { Read-Host 'Нажмите Enter для выхода' | Out-Null }
