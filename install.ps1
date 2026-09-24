# Windows PowerShell 5.1 / PowerShell 7. No admin rights or policy changes.
[CmdletBinding()]
param(
    [string]$ProjectPath = "",
    [switch]$Replace,
    [switch]$WithRuntime,
    [switch]$WithUpstream
)
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$env:PYTHONUTF8 = "1"
$python = $null
$prefix = @()
$probe = 'import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)'
if (Get-Command py -ErrorAction SilentlyContinue) {
    foreach ($version in @('-3.12', '-3.11', '-3')) {
        try {
            & py $version -c $probe 2>$null
            if ($LASTEXITCODE -eq 0) { $python = 'py'; $prefix = @($version); break }
        } catch { continue }
    }
}
if (-not $python -and (Get-Command python -ErrorAction SilentlyContinue)) {
    & python -c $probe 2>$null
    if ($LASTEXITCODE -eq 0) { $python = 'python' }
}
if (-not $python) { throw 'Python 3.11+ is required. Install Python 3.12, then run again.' }
$arguments = @((Join-Path $PSScriptRoot 'install.py'))
if ($ProjectPath) { $arguments += @('--project', $ProjectPath) }
if ($Replace) { $arguments += '--replace' }
$raw = & $python @prefix @arguments
if ($LASTEXITCODE -ne 0) { throw 'Skill installation failed. Existing skill was not overwritten without backup.' }
$info = ($raw -join "`n") | ConvertFrom-Json
Write-Host ('Skill installed: ' + $info.installed)
if ($info.backup) { Write-Host ('Previous version backup: ' + $info.backup) }
foreach ($legacy in @($info.legacy_backups)) { if ($legacy) { Write-Host ('Earlier ReleasePick install moved to: ' + $legacy) } }
$bootstrap = Join-Path $info.installed 'scripts\bootstrap.py'
if ($WithRuntime -or $WithUpstream) {
    & $python @prefix $bootstrap core --allow-network
    if ($LASTEXITCODE -ne 0) { throw 'Skill installed, but Python runtime setup failed. See the output above.' }
}
if ($WithUpstream) {
    & $python @prefix $bootstrap upstream --allow-network --install-deps
    if ($LASTEXITCODE -ne 0) { throw 'Skill installed, but optional upstream setup failed. Existing source was not replaced.' }
}
Write-Host 'Open a new Codex session and invoke $Jeju_Cardmaker. No API call or SNS post was made.'
