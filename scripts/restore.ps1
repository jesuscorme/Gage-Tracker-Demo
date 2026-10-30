<#
.SYNOPSIS
  Restore a backup produced by backup.ps1 into an EMPTY database and storage folder.
  Verifies the manifest checksums first. Never restores over a non-empty target.

.EXAMPLE
  powershell -File scripts/restore.ps1 -BackupDir D:\backups\gagetracker-20261030-120000 `
      -DatabaseUrl "postgresql://gagetracker:***@localhost:5433/gagetracker_restore" -StorageDir D:\gt\storage
#>
param(
  [Parameter(Mandatory)] [string]$BackupDir,
  [Parameter(Mandatory)] [string]$DatabaseUrl,
  [Parameter(Mandatory)] [string]$StorageDir,
  [string]$PgBin = "C:\Program Files\PostgreSQL\16\bin"
)
$ErrorActionPreference = "Stop"
$manifest = Get-Content (Join-Path $BackupDir "manifest.json") -Raw | ConvertFrom-Json
foreach ($f in $manifest.files) {
  $hash = (Get-FileHash (Join-Path $BackupDir $f.file) -Algorithm SHA256).Hash
  if ($hash -ne $f.sha256) { throw "Checksum mismatch for $($f.file)" }
}
$tables = & "$PgBin\psql.exe" --dbname $DatabaseUrl -At -c "select count(*) from information_schema.tables where table_schema='public'"
if ([int]"$tables".Trim() -gt 0) { throw "Target database is not empty; restore into a new database" }
if ((Test-Path $StorageDir) -and (Get-ChildItem $StorageDir -Recurse -File | Select-Object -First 1)) {
  throw "Target storage folder is not empty"
}
& "$PgBin\pg_restore.exe" --no-owner --exit-on-error --dbname $DatabaseUrl (Join-Path $BackupDir "database.dump")
if ($LASTEXITCODE -ne 0) { throw "pg_restore failed" }
# Fresh planner statistics: without them the first queries after a restore can be orders of magnitude slower.
& "$PgBin\psql.exe" --dbname $DatabaseUrl -q -c "ANALYZE" 2>$null
$zip = Join-Path $BackupDir "storage.zip"
if (Test-Path $zip) { New-Item -ItemType Directory -Force $StorageDir | Out-Null; Expand-Archive $zip -DestinationPath $StorageDir }
Write-Output "Restored schema revision $($manifest.schema_revision)"
