# Cadence probe for E5 (publication lag).
#
# Keeps one WhoScored stage page open and appends one JSON line per interval.
# Run on a matchday, from the first kickoff to a few hours after the last one.
#
#   pwsh -File experiments/whoscored/cadence_probe.ps1 `
#     -StageUrl "https://www.whoscored.com/regions/252/tournaments/2/seasons/11141/stages/25544/show/england-premier-league-2026-2027" `
#     -OutFile "data/probes/epl-2026-10-24.jsonl" `
#     -IntervalSeconds 300 -DurationMinutes 360
#
# The page must be a stage page (`/show/...`): the tournament page has no
# standings table. Do not run two probes in the same session at once.

param(
    [Parameter(Mandatory = $false)]
    [string]$StageUrl = "https://www.whoscored.com/regions/252/tournaments/2/seasons/11141/stages/25544/show/england-premier-league-2026-2027",

    [Parameter(Mandatory = $false)]
    [string]$OutFile = "data/probes/cadence.jsonl",

    [Parameter(Mandatory = $false)]
    [int]$IntervalSeconds = 300,

    [Parameter(Mandatory = $false)]
    [int]$DurationMinutes = 360,

    [Parameter(Mandatory = $false)]
    [string]$Session = "dd-cadence"
)

$ErrorActionPreference = "Stop"

$probePath = Join-Path $PSScriptRoot "cadence_probe.js"
$probe = Get-Content $probePath -Raw
$probeBase64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($probe))

$outDir = Split-Path -Parent $OutFile
if ($outDir -and -not (Test-Path $outDir)) {
    New-Item -ItemType Directory -Path $outDir -Force | Out-Null
}

$env:AGENT_BROWSER_SESSION = $Session

function Open-Page {
    agent-browser open "about:blank" | Out-Null
    agent-browser network route "*fingerprint*" --abort | Out-Null
    agent-browser network route "*podname.com*" --abort | Out-Null
    agent-browser open $StageUrl | Out-Null
    Start-Sleep -Milliseconds 4000
    $title = agent-browser eval "document.title"
    Write-Host "page: $title"
}

Open-Page
$deadline = [DateTime]::UtcNow.AddMinutes($DurationMinutes)
$count = 0

while ([DateTime]::UtcNow -lt $deadline) {
    $stamp = [DateTime]::UtcNow.ToString("o")
    try {
        $line = agent-browser eval -b $probeBase64
        $line = $line -join "`n"
        $line | Add-Content -Path $OutFile -Encoding UTF8
        $count += 1
        $short = $line -replace "\s+", " "
        Write-Host "[$stamp] probe $count ok: $($short.Substring(0, [Math]::Min(220, $short.Length)))"
    }
    catch {
        Write-Warning "[$stamp] probe failed: $($_.Exception.Message); reopening the page"
        try { Open-Page } catch { Write-Warning "reopen failed: $($_.Exception.Message)" }
    }
    Start-Sleep -Seconds $IntervalSeconds
}

Write-Host "done: $count probes -> $OutFile"
