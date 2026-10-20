[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$StoryPath,
    [Parameter(Mandatory=$true)][string]$ReportPath,
    [string]$GamePath='D:\SteamLibrary\steamapps\common\Purgatory'
)
# Isolated Ink runtime only. Does not connect to the running game or its saves.
$ErrorActionPreference='Stop'
$managed=Join-Path $GamePath 'Purgatory_Data/Managed'
[Reflection.Assembly]::LoadFrom((Join-Path $managed 'Newtonsoft.Json.dll')) | Out-Null
$assembly=[Reflection.Assembly]::LoadFrom((Join-Path $managed 'Assembly-CSharp-firstpass.dll'))
$storyType=$assembly.GetType('Ink.Runtime.Story',$true)
$constructor=$storyType.GetConstructor([Type[]]@([string]))
$callbackType=$storyType.GetNestedType('ExternalFunction')
$zero=[scriptblock]{param([object[]]$values) return [int]0} -as $callbackType
$json=[IO.File]::ReadAllText((Resolve-Path -LiteralPath $StoryPath))
$externalNames=[regex]::Matches($json,'"x\(\)"\s*:\s*"([^"]+)"') | ForEach-Object {$_.Groups[1].Value} | Select-Object -Unique
$phases=@('new moon','waxing crescent','first quarter','waxing gibbous','full moon','waning gibbous','last quarter','waning crescent')
$results=@()
foreach($phaseName in $phases){
    $story=$constructor.Invoke([object[]]@($json))
    $moonCallback=([scriptblock]{param([object[]]$values) return [string]$phaseName}.GetNewClosure()) -as $callbackType
    foreach($name in $externalNames){
        $callback=if($name -ceq 'getMoonphase'){$moonCallback}else{$zero}
        $story.BindExternalFunctionGeneral($name,$callback)
    }
    [string]$text=''
    $null=$story.EvaluateFunction('werewolf_tooltips',[ref]$text,[object[]]@('moonphase'))
    if($text.Trim() -cne "<b>Фаза Луны:</b> $phaseName."){throw "Unexpected phase tooltip: $phaseName"}
    $results += [ordered]@{phase=$phaseName;text=$text.Trim();passed=$true}
}
$story=$constructor.Invoke([object[]]@($json))
foreach($name in $externalNames){$story.BindExternalFunctionGeneral($name,$zero)}
foreach($statName in @('rage','willpower','harano','health')){
    [string]$text=''
    $null=$story.EvaluateFunction('werewolf_tooltips',[ref]$text,[object[]]@($statName))
    if($text -cnotmatch "<sprite tint=1 name=$statName>" -or $text -notmatch '[А-Яа-яЁё]'){throw "Missing native sprite in $statName tooltip"}
    $results += [ordered]@{stat=$statName;native_sprite_tag_present=$true;passed=$true}
}
[ordered]@{
    passed=$true
    story_sha256=(Get-FileHash -LiteralPath $StoryPath -Algorithm SHA256).Hash.ToLowerInvariant()
    evaluations=$results.Count
    phases=8
    stat_tooltips=4
    results=$results
    limitation='Isolated Ink output. Display-only phase translation is covered separately by C# tests; sprite material preservation and visible rendering require Unity QA after an authorized future launch.'
} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $ReportPath -Encoding utf8
'INK_MOON_AND_STAT_TOOLTIPS_OK phases=8 stat_tooltips=4'
