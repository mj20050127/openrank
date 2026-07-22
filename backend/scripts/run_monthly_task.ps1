$ErrorActionPreference = "Stop"
$Backend = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Backend

$VenvPython = Join-Path $Backend ".venv\Scripts\python.exe"
$Python = if (Test-Path -LiteralPath $VenvPython) { $VenvPython } else { "python" }

& $Python "scripts\resume_ingestion_jobs.py" --limit 100
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $Python "scripts\refresh_monthly_pipeline.py" --workers 8
exit $LASTEXITCODE