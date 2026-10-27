$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $PSScriptRoot
$python = Join-Path $project '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Create the Python 3.12 virtual environment and install requirements.lock first.' }
Push-Location $project
try {
    & $python scripts/bootstrap_local.py
    docker compose up -d --wait postgres
    if ($LASTEXITCODE -ne 0) { throw 'Database startup failed.' }
    docker compose up -d keycloak
    if ($LASTEXITCODE -ne 0) { throw 'Container startup failed.' }
    & $python scripts/migrate.py
    if ($LASTEXITCODE -ne 0) { throw 'Migration failed. Wait for database readiness, then retry.' }
    $env:PYTHONPATH = Join-Path $project 'src'
    $jobs = @(
        @{name='web'; port=18501; args=@('-m','streamlit','run','app.py')},
        @{name='private-api'; port=18502; args=@('-m','uvicorn','sandhata.private_api:app','--host','127.0.0.1','--port','18502')}
    )
    foreach ($job in $jobs) {
        if (-not (Get-NetTCPConnection -LocalPort $job.port -State Listen -ErrorAction SilentlyContinue)) {
            $process=Start-Process -FilePath $python -ArgumentList $job.args -WorkingDirectory $project -WindowStyle Hidden -PassThru -RedirectStandardOutput "runtime/$($job.name).stdout.log" -RedirectStandardError "runtime/$($job.name).stderr.log"
            $process.Id | Set-Content -LiteralPath "runtime/$($job.name).pid"
        }
    }
    $worker=Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*sandhata.worker*' -and $_.ExecutablePath -eq $python }
    if (-not $worker) {
        $process=Start-Process -FilePath $python -ArgumentList @('-m','sandhata.worker') -WorkingDirectory $project -WindowStyle Hidden -PassThru -RedirectStandardOutput 'runtime/worker.stdout.log' -RedirectStandardError 'runtime/worker.stderr.log'
        $process.Id | Set-Content -LiteralPath 'runtime/worker.pid'
    }
    Write-Output 'SANDHATA: http://localhost:18501 ; access guide: runtime/LOCAL_ACCESS.md'
} finally { Pop-Location }
