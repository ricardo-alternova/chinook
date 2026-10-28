# Chinook one-line installer for Windows.
# irm https://github.com/ricardo-alternova/chinook/releases/latest/download/install.ps1 | iex
#Requires -Version 5.1
[CmdletBinding()]
param(
    [switch]$Check
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$ref = if ($env:CHINOOK_REF) { $env:CHINOOK_REF } else { 'main' }
$base = if ($env:CHINOOK_DIR) { $env:CHINOOK_DIR } elseif ($env:LOCALAPPDATA) { $env:LOCALAPPDATA } else { [System.IO.Path]::GetTempPath() }
$root = if ($env:CHINOOK_DIR) { $env:CHINOOK_DIR } else { Join-Path $base 'Chinook' }
$source = Join-Path $root 'src'

# Use the checkout this script came from when it was run as a file.
$provision = $null
if ($PSScriptRoot) {
    $candidate = Join-Path (Join-Path $PSScriptRoot 'windows') 'Chinook.ps1'
    if (Test-Path $candidate) { $provision = $candidate }
}

if ($Check) {
    if (-not $provision) { throw 'Could not find windows/Chinook.ps1 next to install.ps1.' }
    Write-Host 'install.ps1 check OK.'
    return
}

if (-not $provision) {
    $zip = Join-Path $env:TEMP "chinook-$ref.zip"
    $url = "https://github.com/ricardo-alternova/chinook/archive/$ref.zip"
    Write-Host "Downloading Chinook ($ref)..."
    Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
    if (Test-Path $source) { Remove-Item $source -Recurse -Force }
    New-Item -ItemType Directory -Path $source -Force | Out-Null
    Expand-Archive -Path $zip -DestinationPath $source -Force
    $checkout = Get-ChildItem -Path $source -Directory | Select-Object -First 1
    if (-not $checkout) { throw 'The Chinook archive did not contain a checkout.' }
    $provision = Join-Path (Join-Path $checkout.FullName 'windows') 'Chinook.ps1'
}

if (-not (Test-Path $provision)) {
    throw "Could not find windows\Chinook.ps1 in the Chinook checkout."
}

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
$isAdmin = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host 'Chinook needs administrator rights; opening an elevated PowerShell...'
    $powershell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$provision`" -PauseOnError"
    $process = Start-Process -FilePath $powershell -ArgumentList $arguments -Verb RunAs -WorkingDirectory (Get-Location) -Wait -PassThru
    exit $process.ExitCode
}

& $provision
