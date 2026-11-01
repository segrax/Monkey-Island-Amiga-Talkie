# SPDX-License-Identifier: GPL-3.0-or-later
param(
    [Parameter(Mandatory=$true)][string]$Amiga,
    [Parameter(Mandatory=$true)][string]$Sou,
    [Parameter(Mandatory=$true)][string]$Engine,
    [Parameter(Mandatory=$true)][string]$Work
)
$ErrorActionPreference = 'Stop'
$sourceRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$root = [IO.Path]::GetFullPath((Join-Path $sourceRoot '..'))
$workRoot = [IO.Path]::GetFullPath($Work)
if (Test-Path -LiteralPath $workRoot) { throw 'Choose a new test working directory.' }
[IO.Directory]::CreateDirectory($workRoot) | Out-Null
$exe = Join-Path $workRoot 'Standalone Builder.exe'
Copy-Item -LiteralPath (Join-Path $root 'Build Amiga Talkie.exe') -Destination $exe
& $exe --verify-payload
if ($LASTEXITCODE -ne 0) { throw 'Standalone payload verification failed.' }
$output = Join-Path $workRoot 'Game output with spaces'
& $exe --amiga $Amiga --sou $Sou --engine $Engine --output $output
if ($LASTEXITCODE -ne 0) { throw 'Build failed.' }
$pins = Get-Content -LiteralPath (Join-Path $sourceRoot 'assets\supported-inputs.json') -Raw | ConvertFrom-Json
$sourceHash = (Get-FileHash -LiteralPath $Sou -Algorithm SHA256).Hash.ToLowerInvariant()
$profile = @($pins.profiles.PSObject.Properties | ForEach-Object { $_.Value } | Where-Object { $_.source_sha256 -eq $sourceHash })[0]
if (-not $profile) { throw 'Input is not a supported profile.' }
function Assert-Hash([string]$file, [string]$expected) {
    if ((Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) { throw "Hash mismatch: $file" }
}
Assert-Hash (Join-Path $output 'Monkey_Talkie') $pins.hybrid_engine
Assert-Hash (Join-Path $output 'amiga-talkie.dat') $profile.map_sha256
Assert-Hash (Join-Path $output 'native-voice.pcm') $profile.pcm_sha256
Assert-Hash (Join-Path $output 'VoiceServer') ((Get-FileHash -LiteralPath (Join-Path $sourceRoot ('assets\' + $profile.worker)) -Algorithm SHA256).Hash.ToLowerInvariant())
foreach ($room in $pins.rooms.PSObject.Properties) { Assert-Hash (Join-Path $output ('Rooms\' + $room.Name)) $room.Value }
$manifest = Get-Content -LiteralPath (Join-Path $output 'build-manifest.json') -Raw | ConvertFrom-Json
if (-not $manifest.complete) { throw 'Incomplete build manifest.' }
foreach ($file in $manifest.files.PSObject.Properties) { Assert-Hash (Join-Path $output $file.Name) $file.Value }
function Rejected([string[]]$Arguments) {
    $saved = $ErrorActionPreference
    try { $ErrorActionPreference = 'Continue'; & $exe @Arguments 2>&1 | Out-Null; return $LASTEXITCODE }
    finally { $ErrorActionPreference = $saved }
}
$before = (Get-FileHash -LiteralPath (Join-Path $output 'native-voice.pcm') -Algorithm SHA256).Hash
if ((Rejected @('--amiga',$Amiga,'--sou',$Sou,'--engine',$Engine,'--output',$output)) -eq 0) { throw 'Existing output was unexpectedly accepted.' }
if ($before -ne (Get-FileHash -LiteralPath (Join-Path $output 'native-voice.pcm') -Algorithm SHA256).Hash) { throw 'Existing output changed.' }
$bad = Join-Path $workRoot 'invalid.sou'
[IO.File]::WriteAllText($bad, 'not speech')
$rejected = Join-Path $workRoot 'rejected'
if ((Rejected @('--amiga',$Amiga,'--sou',$bad,'--engine',$Engine,'--output',$rejected)) -eq 0 -or (Test-Path -LiteralPath $rejected)) { throw 'Invalid SOU was not cleanly rejected.' }
if ((Rejected @('--amiga',$Amiga,'--sou',$Sou,'--engine',$bad,'--output',$rejected)) -eq 0 -or (Test-Path -LiteralPath $rejected)) { throw 'Invalid executable was not cleanly rejected.' }
Write-Output "PASS: standalone EXE; exact engine, map, prepared speech, worker and room hashes; existing output preserved; bad inputs rejected ($($profile.label))."
