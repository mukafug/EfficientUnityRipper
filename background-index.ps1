# SPDX-License-Identifier: GPL-3.0-only
[CmdletBinding()]
param([Parameter(Mandatory)][string]$InputPath, [Parameter(Mandatory)][string]$OutputDirectory)
$ErrorActionPreference = 'Stop'
$inputFull = (Resolve-Path -LiteralPath $InputPath).Path
$outputFull = [IO.Path]::GetFullPath($OutputDirectory)
$python = Join-Path $PSScriptRoot '.local/venv/Scripts/python.exe'
if (!(Test-Path -LiteralPath $python)) { throw 'Run setup.ps1 first.' }
$inputRoot = if ((Get-Item -LiteralPath $inputFull).PSIsContainer) { $inputFull } else { Split-Path -LiteralPath $inputFull }
$inputBoundary = $inputRoot.TrimEnd('\') + '\'
if ($outputFull -eq $inputRoot -or $outputFull.StartsWith($inputBoundary, [StringComparison]::OrdinalIgnoreCase)) { throw 'Output must be outside the input installation.' }
if ((Test-Path -LiteralPath $outputFull) -and (Get-ChildItem -LiteralPath $outputFull -Force | Select-Object -First 1) -and !(Test-Path -LiteralPath (Join-Path $outputFull '.eur-index.json'))) { throw 'Existing nonempty output must already be an owned EfficientUnityRipper index.' }
New-Item -ItemType Directory -Path $outputFull -Force | Out-Null
if (!(Test-Path -LiteralPath (Join-Path $outputFull '.eur-index.json'))) { '{"application":"EfficientUnityRipper","kind":"index"}' | Set-Content -LiteralPath (Join-Path $outputFull '.eur-index.json') -Encoding utf8 }
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss_fff'
$stdout = Join-Path $outputFull "background_$stamp.stdout.ndjson"
$stderr = Join-Path $outputFull "background_$stamp.stderr.log"
# Windows Start-Process arguments need explicit quotes around paths containing spaces.
if ($inputFull.Contains('"') -or $outputFull.Contains('"')) { throw 'Invalid path quoting' }
$arguments = @('-m', 'eur.cli', 'scan', ('"' + $inputFull + '"'), '--output', ('"' + $outputFull + '"'))
$process = Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
Write-Host "Index running in background. PID: $($process.Id)"
Write-Host "When scan completes, reference: $(Join-Path $outputFull 'agent-context.md')"
Write-Host "Progress: $stdout"
