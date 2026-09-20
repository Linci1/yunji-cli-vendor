param(
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA "yunji-cli-vendor"),
    [string]$BinDir = (Join-Path $env:LOCALAPPDATA "Programs\yunji-cli-vendor\bin")
)

$ErrorActionPreference = "Stop"

function Find-PythonCommand {
    $candidates = @(
        @("py", "-3"),
        @("python")
    )
    foreach ($candidate in $candidates) {
        $command = $candidate[0]
        if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {
            continue
        }
        $arguments = @()
        if ($candidate.Length -gt 1) {
            $arguments = $candidate[1..($candidate.Length - 1)]
        }
        $arguments += @("--version")
        $null = & $command @arguments 2>$null
        if ($LASTEXITCODE -eq 0) {
            return $candidate
        }
    }
    throw "Python 3.10 or later is required. Install Python from python.org, then retry."
}

$sourceRoot = Split-Path -Parent $PSScriptRoot
$pythonCommand = Find-PythonCommand
$pythonArguments = @()
if ($pythonCommand.Length -gt 1) {
    $pythonArguments = $pythonCommand[1..($pythonCommand.Length - 1)]
}

foreach ($directory in @($InstallRoot, $BinDir, (Join-Path $InstallRoot "scripts"), (Join-Path $InstallRoot "docs"))) {
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
}

$files = @(
    @("README.md", "README.md"),
    @("docs\vendor-api-2.6-guide.md", "docs\vendor-api-2.6-guide.md"),
    @("docs\vendor-cli-2.6-guide.md", "docs\vendor-cli-2.6-guide.md"),
    @("scripts\yunji.cmd", "scripts\yunji.cmd"),
    @("scripts\yunji_vendor.py", "scripts\yunji_vendor.py")
)

foreach ($file in $files) {
    $source = Join-Path $sourceRoot $file[0]
    $target = Join-Path $InstallRoot $file[1]
    Copy-Item -Path $source -Destination $target -Force
}

$launcher = Join-Path $BinDir "yunji.cmd"
$launcherContent = @("@echo off", "setlocal EnableExtensions", "`"$InstallRoot\scripts\yunji.cmd`" %*", "endlocal", "exit /b %ERRORLEVEL%") -join [Environment]::NewLine
Set-Content -Path $launcher -Value $launcherContent -Encoding Ascii

$helpArguments = $pythonArguments + @((Join-Path $InstallRoot "scripts\yunji_vendor.py"), "--help")
$null = & $pythonCommand[0] @helpArguments
if ($LASTEXITCODE -ne 0) {
    throw "Installed CLI failed its startup check."
}

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
$pathParts = @()
if ($userPath) {
    $pathParts = $userPath -split ";" | Where-Object { $_ }
}
if (-not ($pathParts -contains $BinDir)) {
    $pathParts += $BinDir
    [Environment]::SetEnvironmentVariable("Path", ($pathParts -join ";"), "User")
}

Write-Host "yunji vendor CLI installed."
Write-Host "  command: $launcher"
Write-Host "  install root: $InstallRoot"
Write-Host "Open a new Command Prompt or PowerShell window, then run: yunji --help"
