[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$PackagePath,
    [string]$GamePath='D:\SteamLibrary\steamapps\common\Purgatory'
)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$package=(Resolve-Path -LiteralPath $PackagePath).Path
$fixture=Join-Path $root ('work/installer-check-'+[Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path (Join-Path $fixture 'Purgatory_Data/Managed') -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $fixture 'BepInEx/plugins/OtherMod') -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $GamePath 'Purgatory.exe') -Destination $fixture
Copy-Item -LiteralPath (Join-Path $GamePath 'Purgatory_Data/Managed/Assembly-CSharp.dll') -Destination (Join-Path $fixture 'Purgatory_Data/Managed')
$sentinel=Join-Path $fixture 'BepInEx/plugins/OtherMod/sentinel.txt'
Copy-Item -LiteralPath (Join-Path $root 'installer/BepInEx-LICENSE.txt') -Destination $sentinel
$sentinelHash=(Get-FileHash $sentinel).Hash
foreach($name in @('Install-PurgatoryRu.ps1','Uninstall-PurgatoryRu.ps1')) {
    $bytes=[IO.File]::ReadAllBytes((Join-Path $package $name))
    if($bytes.Length -lt 3 -or $bytes[0] -ne 239 -or $bytes[1] -ne 187 -or $bytes[2] -ne 191) { throw 'PS5 installer requires UTF8 BOM' }
}
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $package 'Install-PurgatoryRu.ps1') -GamePath $fixture -NoPause
if($LASTEXITCODE -ne 0){throw 'Windows PowerShell 5 installation failed'}
foreach($name in @('PurgatoryRu.dll','wod02.json','name-localization.json','ui-strings.json')) {
    $actual=Join-Path $fixture "BepInEx/plugins/PurgatoryRu/$name"
    $expected=Join-Path $package "payload/BepInEx/plugins/PurgatoryRu/$name"
    if((Get-FileHash $actual).Hash -ne (Get-FileHash $expected).Hash){throw "Payload mismatch: $name"}
}
if((Get-FileHash $sentinel).Hash -ne $sentinelHash){throw 'Unrelated mod changed'}
$plugin=[IO.Path]::GetFullPath((Join-Path $fixture 'BepInEx/plugins/PurgatoryRu'))
$allowed=[IO.Path]::GetFullPath($fixture).TrimEnd('\','/')+[IO.Path]::DirectorySeparatorChar
if(!$plugin.StartsWith($allowed,[StringComparison]::OrdinalIgnoreCase)){throw 'Refuse uninstall outside test fixture'}
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $package 'Uninstall-PurgatoryRu.ps1') -GamePath $fixture -NoPause
if($LASTEXITCODE -ne 0 -or (Test-Path $plugin)){throw 'Test uninstall failed'}
if((Get-FileHash $sentinel).Hash -ne $sentinelHash){throw 'Unrelated mod removed'}
if(!(Test-Path (Join-Path $fixture 'BepInEx/core/BepInEx.dll'))){throw 'BepInEx removed'}
Write-Output 'PORTABLE_INSTALL_UNINSTALL_OK: four payload files; PS5/BOM; unrelated mod and BepInEx preserved.'
