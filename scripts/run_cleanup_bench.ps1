# Start the local Ollama server (127.0.0.1 only), pull two small models, benchmark cleanup LLMs.
# Output also goes to data\bench_run.log
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
New-Item -ItemType Directory -Force data | Out-Null
$log = Join-Path $root "data\bench_run.log"
Start-Transcript -Path $log -Force | Out-Null
$ollama = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"

function Test-Ollama { try { Invoke-RestMethod http://127.0.0.1:11434/api/version -TimeoutSec 2 | Out-Null; $true } catch { $false } }
if (-not (Test-Ollama)) {
    Write-Host "Starting Ollama server..."
    Start-Process $ollama -ArgumentList "serve" -WindowStyle Hidden
    for ($i = 0; $i -lt 30 -and -not (Test-Ollama); $i++) { Start-Sleep 1 }
}
if (-not (Test-Ollama)) { throw "Ollama server did not start" }
Write-Host "Ollama version:" (Invoke-RestMethod http://127.0.0.1:11434/api/version).version

foreach ($m in "qwen3:4b", "llama3.2:3b") {
    Write-Host "`n=== Pulling $m ==="
    & $ollama pull $m
    if ($LASTEXITCODE -ne 0) { throw "pull failed for $m" }
}
& $ollama list

Write-Host "`n=== Benchmark ==="
$env:PYTHONUTF8 = "1"
& .\.venv\Scripts\python.exe scripts\bench_cleanup.py phi3 llama3.2:3b qwen3:4b mistral
Write-Host "`nBENCHMARK DONE (exit $LASTEXITCODE)"
Stop-Transcript | Out-Null
