[CmdletBinding()]
param(
    [string]$GamePath,
    [switch]$NoPause
)

$ErrorActionPreference = 'Stop'
$PackageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PayloadRoot = Join-Path $PackageRoot 'payload'

function Find-PurgatoryPath {
    param([string]$ExplicitPath)
    $candidates = [System.Collections.Generic.List[string]]::new()
    if ($ExplicitPath) { $candidates.Add($ExplicitPath) }
    $candidates.Add((Get-Location).Path)
    $candidates.Add($PackageRoot)

    try {
        $steamPath = (Get-ItemProperty -LiteralPath 'HKCU:\Software\Valve\Steam' -ErrorAction Stop).SteamPath
        if ($steamPath) {
            $candidates.Add((Join-Path $steamPath 'steamapps\common\Purgatory'))
            $vdf = Join-Path $steamPath 'steamapps\libraryfolders.vdf'
            if (Test-Path -LiteralPath $vdf) {
                foreach ($match in [regex]::Matches((Get-Content -Raw -LiteralPath $vdf), '"path"\s+"([^"]+)"')) {
                    $library = $match.Groups[1].Value -replace '\\\\', '\'
                    $candidates.Add((Join-Path $library 'steamapps\common\Purgatory'))
                }
            }
        }
    } catch {
        Write-Verbose "Steam registry discovery unavailable: $($_.Exception.Message)"
    }

    foreach ($candidate in $candidates | Select-Object -Unique) {
        if (!$candidate) { continue }
        $resolved = [System.IO.Path]::GetFullPath($candidate)
        if ((Test-Path -LiteralPath (Join-Path $resolved 'Purgatory.exe')) -and
            (Test-Path -LiteralPath (Join-Path $resolved 'Purgatory_Data\Managed\Assembly-CSharp.dll'))) {
            return $resolved
        }
    }
    return $null
}

if (!(Test-Path -LiteralPath (Join-Path $PayloadRoot 'BepInEx\plugins\PurgatoryRu\PurgatoryRu.dll'))) {
    throw 'Пакет повреждён: отсутствует payload\BepInEx\plugins\PurgatoryRu\PurgatoryRu.dll.'
}

$Target = Find-PurgatoryPath -ExplicitPath $GamePath
if (!$Target) {
    $entered = Read-Host 'Укажите полный путь к папке игры Purgatory'
    $Target = Find-PurgatoryPath -ExplicitPath $entered
}
if (!$Target) {
    throw 'Не удалось найти Purgatory.exe. Запустите install.bat из распакованного пакета или передайте -GamePath.'
}

$ptBrConflict = Join-Path $Target 'BepInEx\plugins\PurgatoryPtBr\PurgatoryPtBrPlugin.dll'
if (Test-Path -LiteralPath $ptBrConflict) {
    throw 'Обнаружена португальская локализация PurgatoryPtBr. Удалите или переместите её папку перед установкой русской локализации.'
}

$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backupRoot = Join-Path $Target ".purgatory-ru-backup\$timestamp"
$installed = [System.Collections.Generic.List[string]]::new()
$backedUp = [System.Collections.Generic.List[string]]::new()

Get-ChildItem -LiteralPath $PayloadRoot -Recurse -File | ForEach-Object {
    $relative = $_.FullName.Substring($PayloadRoot.Length).TrimStart('\', '/')
    $destination = Join-Path $Target $relative
    if (Test-Path -LiteralPath $destination) {
        $sourceHash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
        $targetHash = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash
        if ($sourceHash -ne $targetHash) {
            $backup = Join-Path $backupRoot $relative
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $backup) | Out-Null
            Copy-Item -LiteralPath $destination -Destination $backup -Force
            $backedUp.Add($relative)
        }
    }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
    Copy-Item -LiteralPath $_.FullName -Destination $destination -Force
    $installed.Add($relative)
}

$state = [ordered]@{
    packageVersion = '0.1.0'
    installedAt = (Get-Date).ToString('o')
    gamePath = $Target
    backupRoot = if ($backedUp.Count) { $backupRoot } else { $null }
    installedFiles = @($installed)
    backedUpFiles = @($backedUp)
}
$statePath = Join-Path $Target 'BepInEx\plugins\PurgatoryRu\install-state.json'
$state | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $statePath -Encoding UTF8

Write-Host ''
Write-Host "Русская локализация установлена: $Target" -ForegroundColor Green
Write-Host 'Запустите игру из Steam. После первого запуска журнал находится в BepInEx\LogOutput.log.'
if ($backedUp.Count) { Write-Host "Резервная копия изменённых файлов: $backupRoot" }
if (!$NoPause) { Read-Host 'Нажмите Enter для выхода' | Out-Null }
