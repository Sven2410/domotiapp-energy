# Run the DomotiApp Energy test suite inside the Docker test container.
#
# Every argument is forwarded verbatim to pytest:
#
#   .\scripts\test.ps1
#   .\scripts\test.ps1 tests/test_storage.py -k revision
#   .\scripts\test.ps1 --cov=custom_components/domotiapp_energy --cov-report=term-missing
#
# This script deliberately has no param() block, so PowerShell does not try to
# bind pytest flags such as -k or -x as its own parameters.

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$composeFile = Join-Path $repoRoot 'docker-compose.test.yml'

& docker compose --project-directory $repoRoot -f $composeFile `
    run --rm --build tests pytest @args

exit $LASTEXITCODE
