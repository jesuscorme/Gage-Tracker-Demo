<#
.SYNOPSIS
  Backup of Gage Tracker: PostgreSQL (custom-format dump) + document storage + manifest with SHA-256.

.EXAMPLE
  powershell -File scripts/backup.ps1 -DatabaseUrl "postgresql://gagetracker:***@localhost:5433/gagetracker" `
      -StorageDir backend\var\storage -OutDir D:\backups
#>
param(
  [Parameter(Mandatory)] [string]$DatabaseUrl,
  [Parameter(Mandatory)] [string]$StorageDir,
  [Parameter(Mandatory)] [string]$OutDir,
  [string]$PgBin = "C:\Program Files\PostgreSQL\16\bin"
)
$ErrorActionPreference = "Stop"
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$dest = Join-Path $OutDir "gagetracker-$stamp"
New-Item -ItemType Directory -Force $dest | Out-Null

& "$PgBin\pg_dump.exe" --format=custom --no-owner --file "$dest\database.dump" --dbname $DatabaseUrl
if ($LASTEXITCODE -ne 0) { throw "pg_dump failed" }
if (Test-Path $StorageDir) {
  Compress-Archive -Path (Join-Path $StorageDir "*") -DestinationPath "$dest\storage.zip" -CompressionLevel Optimal
}
$files = Get-ChildItem $dest -File | ForEach-Object {
  [ordered]@{ file = $_.Name; bytes = $_.Length; sha256 = (Get-FileHash $_.FullName -Algorithm SHA256).Hash }
}
$revision = & "$PgBin\psql.exe" --dbname $DatabaseUrl -At -c "select version_num from alembic_version"
[ordered]@{ created = (Get-Date).ToString("o"); schema_revision = "$revision".Trim(); files = $files } |
  ConvertTo-Json -Depth 4 | Set-Content -Encoding utf8 "$dest\manifest.json"
Write-Output $dest
