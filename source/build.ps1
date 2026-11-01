# SPDX-License-Identifier: GPL-3.0-or-later
$ErrorActionPreference = 'Stop'
$cmake = (Get-Command cmake -ErrorAction SilentlyContinue).Source
if (-not $cmake) {
    $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
    if (Test-Path -LiteralPath $vswhere) {
        $installation = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
        if ($installation) { $cmake = Join-Path $installation 'Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe' }
    }
}
if (-not $cmake -or -not (Test-Path -LiteralPath $cmake)) { throw 'Install CMake and the Visual Studio C++ desktop tools.' }
$repoRoot = Split-Path -Parent $PSScriptRoot
$buildRoot = Join-Path $repoRoot 'build\windows'
Push-Location $repoRoot
try {
    & $cmake -S $PSScriptRoot -B $buildRoot -A x64
    if ($LASTEXITCODE -ne 0) { throw 'CMake configuration failed.' }
    & $cmake --build $buildRoot --config Release --parallel
    if ($LASTEXITCODE -ne 0) { throw 'C++ compilation failed.' }
    $ctest = Join-Path ([IO.Path]::GetDirectoryName($cmake)) 'ctest.exe'
    & $ctest --test-dir $buildRoot -C Release --output-on-failure
    if ($LASTEXITCODE -ne 0) { throw 'Self-tests failed.' }
    Copy-Item -LiteralPath (Join-Path $buildRoot 'Release\Build Amiga Talkie.exe') -Destination (Join-Path $repoRoot 'Build Amiga Talkie.exe')
    Write-Host 'Ready: Build Amiga Talkie.exe'
} finally { Pop-Location }
