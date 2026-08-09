<#
.SYNOPSIS
    Route 1: drive the panel in the running Home Assistant, with real clicks.

.DESCRIPTION
    The layer that renders ha-form, and the only one that can say whether a
    control accepts a touch. Everything else — pytest, npm test, npm run
    test:layout — is blind to that.

    Needs the test instance up and .env in the repository root with HA_URL and
    HA_TOKEN, the same two scripts/ha_check.py reads.

    It writes to the instance it points at. Every row it creates is named
    PLAYWRIGHT TESTRIJ and is deleted again; if a run dies half way, that is the
    row to remove by hand on Apparaten.

.EXAMPLE
    .\scripts\browsertest.ps1
    Run the whole route headless.

.EXAMPLE
    .\scripts\browsertest.ps1 --headed
    Watch it happen in a real window. Every argument is passed to Playwright.

.EXAMPLE
    .\scripts\browsertest.ps1 --debug
    Step through it, with the inspector.
#>

[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PlaywrightArgs
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot

if (-not (Test-Path (Join-Path $repoRoot '.env'))) {
    throw "No .env in $repoRoot. Route 1 talks to the running Home Assistant and needs HA_URL and HA_TOKEN."
}

if (-not (Test-Path (Join-Path $repoRoot 'node_modules\@playwright\test'))) {
    Write-Host 'Installing the test dependencies (once)...'
    & npm --prefix $repoRoot install
    if ($LASTEXITCODE -ne 0) { throw 'npm install failed' }
}

# The browser binary lives outside node_modules and is downloaded separately.
# Doing it here keeps "one command" true on a fresh machine.
& npx --prefix $repoRoot playwright install chromium | Out-Null

Push-Location $repoRoot
try {
    & npx playwright test --config tests/browser/live.config.mjs @PlaywrightArgs
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
