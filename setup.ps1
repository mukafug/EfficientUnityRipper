# SPDX-License-Identifier: GPL-3.0-only
[CmdletBinding()]
param([string]$Python = 'python', [string]$Git = 'git', [string]$Dotnet = '')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
function Check-Exit([string]$Step) { if ($LASTEXITCODE -ne 0) { throw "$Step failed ($LASTEXITCODE)" } }
New-Item -ItemType Directory -Path .local -Force | Out-Null
if (!(Test-Path -LiteralPath .local/venv/Scripts/python.exe)) {
    & $Python -m venv .local/venv; Check-Exit 'Create Python environment'
}
& ./.local/venv/Scripts/python.exe -m pip install -r requirements.txt; Check-Exit 'Install PySide6'
if (!$Dotnet) {
    $Dotnet = Join-Path $PSScriptRoot '.local/dotnet/dotnet.exe'
    if (!(Test-Path -LiteralPath $Dotnet)) {
        Invoke-WebRequest 'https://dot.net/v1/dotnet-install.ps1' -OutFile .local/dotnet-install.ps1
        & ./.local/dotnet-install.ps1 -Channel 10.0 -InstallDir (Join-Path $PSScriptRoot '.local/dotnet') -NoPath
        if (!(Test-Path -LiteralPath $Dotnet)) { throw 'NET 10 SDK unavailable' }
    }
}
$upstream = Join-Path $PSScriptRoot '.local/AssetRipper'
$commit = 'beeb50ee1c223e856c860caa338e5309404956a3'
if (!(Test-Path -LiteralPath $upstream)) {
    & $Git clone --filter=blob:none https://github.com/AssetRipper/AssetRipper.git $upstream; Check-Exit 'Clone AssetRipper'
    & $Git -C $upstream checkout --detach $commit; Check-Exit 'Pin AssetRipper'
}
$actual = & $Git -C $upstream rev-parse HEAD; Check-Exit 'Read AssetRipper commit'
if ($actual -ne $commit) { throw "AssetRipper checkout mismatch: $actual" }
if (& $Git -C $upstream status --porcelain) { throw 'AssetRipper checkout has modifications; inspect before build' }
& $Dotnet publish backend -c Release "-p:AssetRipperRoot=$upstream" -o .local/backend -v minimal; Check-Exit 'Publish backend'
Write-Host 'Ready. Run launch.cmd. CLI: .local/venv/Scripts/python.exe -m eur.cli --help'
