[CmdletBinding()]
param(
    [string]$GamePath = 'D:\SteamLibrary\steamapps\common\Purgatory',
    [Parameter(Mandatory = $true)][string]$ReportPath
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
[Reflection.Assembly]::LoadFrom((Join-Path $root 'reference/ptbr-v1.0.0/BepInEx/core/Mono.Cecil.dll')) | Out-Null
$source = Join-Path $GamePath 'Purgatory_Data/Managed/Assembly-CSharp.dll'
$assembly = [Mono.Cecil.AssemblyDefinition]::ReadAssembly($source)
function Read-TypeStrings($type) {
    foreach ($method in $type.Methods) {
        if (!$method.HasBody) { continue }
        foreach ($instruction in $method.Body.Instructions) {
            if ($instruction.OpCode.Name -eq 'ldstr' -and $instruction.Operand -match '[A-Za-z]') {
                [ordered]@{ type = $type.FullName; method = $method.Name;
                    offset = $instruction.Offset; text = [string]$instruction.Operand }
            }
        }
    }
    foreach ($nested in $type.NestedTypes) { Read-TypeStrings $nested }
}
$rows = @(foreach ($type in $assembly.MainModule.Types) { Read-TypeStrings $type })
$report = [ordered]@{ source_sha256 = (Get-FileHash $source -Algorithm SHA256).Hash;
    records = $rows; record_count = $rows.Count }
$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ReportPath -Encoding utf8
Write-Host "MANAGED_STRINGS records=$($rows.Count)"
$assembly.Dispose()
