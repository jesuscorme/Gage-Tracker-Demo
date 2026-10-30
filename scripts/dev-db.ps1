<#
  Local PostgreSQL for development WITHOUT Docker, using an installed PostgreSQL 16.
  Creates a private cluster in .local/pgdata (git-ignored) listening on localhost:5433,
  with role/password gagetracker/gagetracker and databases gagetracker + gagetracker_test.

  Usage:  powershell -File scripts/dev-db.ps1 [start|stop|status]
  Note:   the cluster uses "trust" auth on localhost only. Development use only.
#>
param([ValidateSet("start", "stop", "status")] [string]$Action = "start",
      [string]$PgBin = "C:\Program Files\PostgreSQL\16\bin",
      [int]$Port = 5433)

$root = Split-Path -Parent $PSScriptRoot
$data = Join-Path $root ".local\pgdata"
$log = Join-Path $root ".local\pg.log"

switch ($Action) {
  "stop"   { & "$PgBin\pg_ctl.exe" -D $data stop; return }
  "status" { & "$PgBin\pg_ctl.exe" -D $data status; return }
}

if (-not (Test-Path $data)) {
  New-Item -ItemType Directory -Force (Split-Path $data) | Out-Null
  & "$PgBin\initdb.exe" -D $data -U postgres --auth=trust -E UTF8 --locale=C | Out-Null
  $init = $true
}
& "$PgBin\pg_ctl.exe" -D $data -l $log -o "-p $Port -c listen_addresses=localhost" -w start
if ($init) {
  $psql = "$PgBin\psql.exe"
  & $psql -h localhost -p $Port -U postgres -c "CREATE ROLE gagetracker LOGIN CREATEDB PASSWORD 'gagetracker'"
  & $psql -h localhost -p $Port -U postgres -c "CREATE DATABASE gagetracker OWNER gagetracker"
  & $psql -h localhost -p $Port -U postgres -c "CREATE DATABASE gagetracker_test OWNER gagetracker"
}
