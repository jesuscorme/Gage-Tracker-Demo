<#
.SYNOPSIS
  Rebuild the DEMO database from scratch (drop, migrate, seed fictitious data).
  Only touches the database named in -DemoDb (must contain "demo"); never production data.

.EXAMPLE
  powershell -File scripts/demo-reset.ps1
#>
param(
  [string]$DemoDb = "gagetracker_demo",
  [string]$PgHost = "localhost", [int]$Port = 5433, [string]$User = "gagetracker", [string]$Password = "gagetracker",
  [string]$PgBin = "C:\Program Files\PostgreSQL\16\bin",
  [string]$StorageDir = "var\demo-storage"
)
$ErrorActionPreference = "Stop"
if ($DemoDb -notmatch "demo") { throw "Refusing: the demo database name must contain 'demo'" }
$env:PGPASSWORD = $Password
& "$PgBin\dropdb.exe" -h $PgHost -p $Port -U $User --if-exists $DemoDb
& "$PgBin\createdb.exe" -h $PgHost -p $Port -U $User $DemoDb
$root = Split-Path $PSScriptRoot -Parent
Set-Location (Join-Path $root "backend")
if (Test-Path $StorageDir) { Remove-Item -Recurse -Force $StorageDir }
$env:DATABASE_URL = "postgresql+psycopg://${User}:${Password}@${PgHost}:${Port}/$DemoDb"
$env:STORAGE_DIR = $StorageDir
$env:SCHEDULER_ENABLED = "false"
& .\.venv\Scripts\python.exe -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw "migration failed" }
& .\.venv\Scripts\python.exe -m scripts.seed_demo
if ($LASTEXITCODE -ne 0) { throw "seed failed" }
