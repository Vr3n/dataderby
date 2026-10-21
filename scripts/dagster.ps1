# Launch the Dagster UI with a SQLite instance under data/dagster.
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$dagsterHome = Join-Path $root "data\dagster"
New-Item -ItemType Directory -Force -Path $dagsterHome | Out-Null

Copy-Item -Force (Join-Path $root "config\dagster.yaml") (Join-Path $dagsterHome "dagster.yaml")

# base_dir must be absolute; a relative value resolves against the working directory.
$env:DAGSTER_HOME = $dagsterHome
$env:DAGSTER_SQLITE_BASE_DIR = Join-Path $dagsterHome "history"

Push-Location $root
try {
    uv run dagster dev -m dataderby.fixtures.definitions
}
finally {
    Pop-Location
}
