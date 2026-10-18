[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$StoryPath,
    [string]$GamePath = 'D:\SteamLibrary\steamapps\common\Purgatory'
)

$ErrorActionPreference = 'Stop'
$managed = Join-Path $GamePath 'Purgatory_Data\Managed'
$newtonsoft = Join-Path $managed 'Newtonsoft.Json.dll'
$firstPass = Join-Path $managed 'Assembly-CSharp-firstpass.dll'
foreach ($required in @($StoryPath, $newtonsoft, $firstPass)) {
    if (!(Test-Path -LiteralPath $required)) { throw "Required file missing: $required" }
}

[Reflection.Assembly]::LoadFrom($newtonsoft) | Out-Null
$inkAssembly = [Reflection.Assembly]::LoadFrom($firstPass)
$storyType = $inkAssembly.GetType('Ink.Runtime.Story', $true)
$constructor = $storyType.GetConstructor([Type[]]@([string]))
if (!$constructor) { throw 'Ink.Runtime.Story(string) constructor not found.' }
$json = [IO.File]::ReadAllText((Resolve-Path -LiteralPath $StoryPath))
$story = $constructor.Invoke([object[]]@($json))
Write-Host "INK_OK type=$($story.GetType().FullName) chars=$($json.Length)"
