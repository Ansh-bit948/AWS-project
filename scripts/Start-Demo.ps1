param([ValidateSet('aws','local')][string]$Mode='aws')
$ErrorActionPreference='Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Test-Path '.venv/Scripts/python.exe')) {
    py -m venv .venv
    & '.venv/Scripts/python.exe' -m pip install -r requirements.txt
}
Write-Host "Open http://127.0.0.1:8000/?mode=$Mode"
& '.venv/Scripts/python.exe' -m uvicorn app.main:app --host 127.0.0.1 --port 8000
