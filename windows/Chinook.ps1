# Chinook Windows provisioning.
# Run from an elevated PowerShell, or use install.ps1 (it elevates itself).
[CmdletBinding()]
param(
    [string]$ConfigPath = '',
    [string]$FleetMsi = '',
    [switch]$NonInteractive,
    [switch]$Check,
    [switch]$SelfTest,
    [switch]$PauseOnError
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

# Keep the elevated window open long enough to read a failure.
trap {
    Write-Host ''
    Write-Host "Chinook failed: $_" -ForegroundColor Red
    if ($PauseOnError) {
        Read-Host 'Press Enter to close'
    }
    exit 1
}

if ($Check) {
    Write-Host 'Chinook Windows script parsed successfully.'
    return
}

if (-not $ConfigPath) {
    $base = if ($env:LOCALAPPDATA) { $env:LOCALAPPDATA } elseif ($env:TEMP) { $env:TEMP } else { [System.IO.Path]::GetTempPath() }
    $ConfigPath = Join-Path (Join-Path $base 'Chinook') 'config.json'
}

$Catalog = @(
    [pscustomobject]@{ Key = 'base';       Label = 'Git, GitHub CLI, jq, and Node.js LTS';           Type = 'winget'; Ids = @('Git.Git', 'GitHub.cli', 'jqlang.jq', 'OpenJS.NodeJS.LTS'); Default = $true }
    [pscustomobject]@{ Key = 'chrome';     Label = 'Google Chrome';                                  Type = 'winget'; Ids = @('Google.Chrome'); Default = $true }
    [pscustomobject]@{ Key = 'discord';    Label = 'Discord';                                        Type = 'winget'; Ids = @('Discord.Discord'); Default = $false }
    [pscustomobject]@{ Key = 'spotify';    Label = 'Spotify';                                        Type = 'winget'; Ids = @('Spotify.Spotify'); Default = $false }
    [pscustomobject]@{ Key = 'localsend';  Label = 'LocalSend';                                      Type = 'winget'; Ids = @('LocalSend.LocalSend'); Default = $false }
    [pscustomobject]@{ Key = 'onlyoffice'; Label = 'ONLYOFFICE Desktop Editors';                     Type = 'winget'; Ids = @('ONLYOFFICE.DesktopEditors'); Default = $false }
    [pscustomobject]@{ Key = 'obs';        Label = 'OBS Studio';                                     Type = 'winget'; Ids = @('OBSProject.OBSStudio'); Default = $false }
    [pscustomobject]@{ Key = 'gimp';       Label = 'GIMP';                                           Type = 'winget'; Ids = @('GIMP.GIMP'); Default = $false }
    [pscustomobject]@{ Key = 'cursor';     Label = 'Cursor editor';                                  Type = 'winget'; Ids = @('Anysphere.Cursor'); Default = $false }
    [pscustomobject]@{ Key = 'tailscale';  Label = 'Tailscale (install only; join manually)';        Type = 'winget'; Ids = @('Tailscale.Tailscale'); Default = $false }
    [pscustomobject]@{ Key = 'opencode';   Label = 'OpenCode CLI (npm)';                              Type = 'npm';    Package = 'opencode-ai'; Default = $true }
    [pscustomobject]@{ Key = 'claude';     Label = 'Claude Code';                                    Type = 'winget'; Ids = @('Anthropic.ClaudeCode'); Default = $true }
    [pscustomobject]@{ Key = 'codex';      Label = 'Codex CLI (official installer)';                  Type = 'script'; Default = $false }
    [pscustomobject]@{ Key = 'fleet';      Label = 'Fleet (fleetd MSI from the Fleet admin)';         Type = 'fleet';  Default = $false }
)

function Write-Step([string]$Message) {
    Write-Host ''
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Refresh-Path {
    $machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $user = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = ($machine, $user | Where-Object { $_ }) -join ';'
}

function Add-UserPath([string]$Path) {
    if (-not (Test-Path $Path)) { return }
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    if (-not $userPath) { $userPath = '' }
    $parts = @($userPath -split ';' | Where-Object { $_ })
    if ($parts -notcontains $Path) {
        [Environment]::SetEnvironmentVariable('Path', (($parts + $Path) -join ';'), 'User')
    }
    $session = @($env:Path -split ';' | Where-Object { $_ })
    if ($session -notcontains $Path) {
        $env:Path = "$Path;$env:Path"
    }
}

function Ensure-Winget {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw 'winget is required. Install or update "App Installer" from the Microsoft Store, then re-run Chinook.'
    }
}

function Test-WingetInstalled([string]$Id) {
    $output = & winget list --id $Id -e --accept-source-agreements 2>$null | Out-String
    return $output -match [Regex]::Escape($Id)
}

function Install-WingetPackage([string]$Id) {
    if (Test-WingetInstalled $Id) {
        Write-Host "  $Id is already installed."
        return
    }
    & winget install --id $Id -e --silent --accept-package-agreements --accept-source-agreements
    # 0x8A150061 means "already installed"; winget sometimes reports it after list.
    if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne -1978335135) {
        throw "winget failed for $Id (exit $LASTEXITCODE)."
    }
}

function Get-Npm {
    $npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if ($npm) { return $npm.Source }
    $candidate = Join-Path $env:ProgramFiles 'nodejs\npm.cmd'
    if (Test-Path $candidate) { return $candidate }
    return $null
}

function Ensure-Node {
    if (Get-Npm) { return }
    Install-WingetPackage 'OpenJS.NodeJS.LTS'
    Refresh-Path
    if (-not (Get-Npm)) {
        throw 'Node.js installed but npm was not found. Open a new terminal and re-run Chinook.'
    }
}

function Install-NpmGlobal([string]$Package) {
    Ensure-Node
    $npm = Get-Npm
    & $npm install -g $Package
    if ($LASTEXITCODE -ne 0) {
        throw "npm failed for $Package (exit $LASTEXITCODE)."
    }
    Add-UserPath (Join-Path $env:APPDATA 'npm')
}

function Install-Fleet([string]$Msi) {
    if ([string]::IsNullOrWhiteSpace($Msi)) {
        Write-Warning 'Fleet is selected, but no fleetd MSI was provided. Ask your Fleet admin for the Windows MSI and re-run with -FleetMsi <path-or-url>.'
        return
    }
    $local = $Msi
    if ($Msi -match '^https?://') {
        $local = Join-Path $env:TEMP 'fleet-osquery.msi'
        Write-Host "  Downloading $Msi"
        Invoke-WebRequest -Uri $Msi -OutFile $local -UseBasicParsing
    }
    if (-not (Test-Path $local)) {
        throw "Fleet MSI not found: $local"
    }
    Write-Host "  Installing $local"
    $process = Start-Process -FilePath 'msiexec.exe' -ArgumentList "/i `"$local`" /qn /norestart" -Wait -PassThru
    if ($process.ExitCode -ne 0 -and $process.ExitCode -ne 3010) {
        throw "fleetd MSI failed (exit $($process.ExitCode))."
    }
    if ($process.ExitCode -eq 3010) {
        Write-Warning 'fleetd installed; Windows asks for a reboot to finish.'
    }
    Start-Sleep -Seconds 2
    $service = Get-Service | Where-Object { $_.Name -match 'orbit|fleet|osquery' } | Select-Object -First 1
    if ($service) {
        Write-Host "  fleetd service: $($service.Name) ($($service.Status))"
    } else {
        Write-Warning 'fleetd installed, but no Fleet service was found. Check the MSI and the Fleet admin console.'
    }
}

function Read-Config {
    if (-not (Test-Path $ConfigPath)) { return $null }
    try {
        return Get-Content -Raw -Path $ConfigPath | ConvertFrom-Json
    } catch {
        Write-Warning "Ignoring unreadable config at $ConfigPath."
        return $null
    }
}

function Save-Config($Selection, [string]$Msi) {
    $directory = Split-Path -Parent $ConfigPath
    if ($directory -and -not (Test-Path $directory)) {
        New-Item -ItemType Directory -Path $directory -Force | Out-Null
    }
    [pscustomobject]@{
        Selection = @($Selection)
        FleetMsi = $Msi
    } | ConvertTo-Json | Set-Content -Path $ConfigPath -Encoding UTF8
}

function Select-Apps($Initial) {
    $selected = New-Object 'System.Collections.Generic.HashSet[string]'
    foreach ($key in @($Initial)) {
        if ($key) { [void]$selected.Add([string]$key) }
    }
    while ($true) {
        Write-Host ''
        Write-Host 'Select apps and modules'
        for ($i = 0; $i -lt $Catalog.Count; $i++) {
            $mark = if ($selected.Contains($Catalog[$i].Key)) { 'x' } else { ' ' }
            Write-Host ("  {0,2}. [{1}] {2}" -f ($i + 1), $mark, $Catalog[$i].Label)
        }
        Write-Host "Enter numbers to toggle, 'a' for all, 'n' for none, or press Enter to continue."
        $value = Read-Host '>'
        if ([string]::IsNullOrWhiteSpace($value)) { break }
        if ($value -eq 'a') {
            foreach ($app in $Catalog) { [void]$selected.Add($app.Key) }
            continue
        }
        if ($value -eq 'n') {
            $selected.Clear()
            continue
        }
        foreach ($part in ($value -replace ',', ' ').Split(' ', [StringSplitOptions]::RemoveEmptyEntries)) {
            $number = 0
            if ([int]::TryParse($part, [ref]$number) -and $number -ge 1 -and $number -le $Catalog.Count) {
                $key = $Catalog[$number - 1].Key
                if ($selected.Contains($key)) {
                    [void]$selected.Remove($key)
                } else {
                    [void]$selected.Add($key)
                }
            }
        }
    }
    return @($selected)
}

if ($SelfTest) {
    $keys = @($Catalog | ForEach-Object { $_.Key })
    if (($keys | Select-Object -Unique).Count -ne $keys.Count) {
        throw 'Self-test failed: duplicate catalog keys.'
    }
    if (@($Catalog | Where-Object { $_.Default }).Count -eq 0) {
        throw 'Self-test failed: no default apps.'
    }

    $originalConfig = $ConfigPath
    $ConfigPath = Join-Path ([System.IO.Path]::GetTempPath()) ("chinook-selftest-" + [guid]::NewGuid().ToString() + ".json")
    try {
        Save-Config @('base', 'fleet') '/tmp/fleetd.msi'
        $saved = Read-Config
        if (@($saved.Selection).Count -ne 2 -or $saved.FleetMsi -ne '/tmp/fleetd.msi') {
            throw 'Self-test failed: config round-trip.'
        }
    } finally {
        if (Test-Path $ConfigPath) { Remove-Item $ConfigPath -Force }
        $ConfigPath = $originalConfig
    }

    $answers = New-Object System.Collections.Queue
    $answers.Enqueue('1')
    $answers.Enqueue('')
    function Read-Host { param([string]$Prompt) return $answers.Dequeue() }
    $picked = Select-Apps @() 6>$null
    if (@($picked) -notcontains 'base') {
        throw 'Self-test failed: selector did not toggle the first entry.'
    }
    Remove-Item Function:\Read-Host

    Write-Host "Self-test OK: $($Catalog.Count) entries; defaults: $((@($Catalog | Where-Object { $_.Default } | ForEach-Object { $_.Key })) -join ', ')"
    return
}

# winget installs system packages, and the Fleet MSI needs administrator rights.
if (-not $env:LOCALAPPDATA) {
    throw 'LOCALAPPDATA is not set. Run this from a normal Windows user session.'
}
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this from an elevated PowerShell (Run as Administrator), or use the one-line installer.'
}

Write-Host @'
   _____ _     _
  / ____| |__ (_)_ __   ___   ___ | | __
 | |    | '_ \| | '_ \ / _ \ / _ \| |/ /
 | |___ | | | | | | | | (_) | (_) |   <
  \____|_| |_|_|_| |_|\___/ \___/|_|\_\

  Windows -> daily driver
'@

$config = Read-Config
$defaults = @($Catalog | Where-Object { $_.Default } | ForEach-Object { $_.Key })
if ($config -and $config.Selection) {
    $defaults = @($config.Selection)
}
if ($FleetMsi) {
    $savedMsi = $FleetMsi
} elseif ($config -and $config.FleetMsi) {
    $savedMsi = [string]$config.FleetMsi
} else {
    $savedMsi = ''
}

if ($NonInteractive) {
    $selected = $defaults
} else {
    $selected = Select-Apps $defaults
    if (($selected -contains 'fleet') -and -not $savedMsi) {
        $savedMsi = Read-Host 'Fleet fleetd MSI path or URL (leave empty to skip Fleet)'
    }
}

Save-Config $selected $savedMsi
Write-Host ''
Write-Host "Config saved to $ConfigPath"

Ensure-Winget
Refresh-Path

foreach ($key in $selected) {
    $app = $Catalog | Where-Object { $_.Key -eq $key } | Select-Object -First 1
    if (-not $app) { continue }
    if ($app.Type -eq 'winget') {
        Write-Step "Installing $($app.Label)"
        foreach ($id in $app.Ids) { Install-WingetPackage $id }
        Refresh-Path
    } elseif ($app.Type -eq 'npm') {
        Write-Step "Installing $($app.Label)"
        Install-NpmGlobal $app.Package
    } elseif ($app.Type -eq 'script') {
        Write-Step "Installing $($app.Label)"
        $installer = Invoke-RestMethod -Uri 'https://chatgpt.com/codex/install.ps1'
        & ([scriptblock]::Create([string]$installer))
        Add-UserPath (Join-Path $env:USERPROFILE '.local\bin')
    } elseif ($app.Type -eq 'fleet') {
        Write-Step 'Installing Fleet'
        Install-Fleet $savedMsi
    }
}

Add-UserPath (Join-Path $env:USERPROFILE '.local\bin')
Add-UserPath (Join-Path $env:APPDATA 'npm')
Refresh-Path

Write-Host ''
Write-Host 'Chinook is ready.' -ForegroundColor Green
Write-Host 'Next steps:'
Write-Host '  1. Open a new PowerShell window so PATH changes take effect.'
Write-Host '  2. Sign in to the agent CLIs you installed (opencode, claude, codex).'
Write-Host '  3. If you installed Fleet, confirm the device appears in the Fleet console.'
