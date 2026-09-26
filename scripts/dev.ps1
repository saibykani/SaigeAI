# Start Saige AI locally: FastAPI on :8000 and Next.js on :3100, each in its own window.
# Usage (from the repo root):  powershell -ExecutionPolicy Bypass -File scripts\dev.ps1
$root = Split-Path -Parent $PSScriptRoot

if (-not (Test-Path "$root\.env")) {
    Write-Error "Missing .env - copy .env.example to .env and fill it in first."
    exit 1
}
if (-not (Test-Path "$root\backend\.venv")) {
    python -m venv "$root\backend\.venv"
    & "$root\backend\.venv\Scripts\python.exe" -m pip install -r "$root\backend\requirements-dev.txt"
}
if (-not (Test-Path "$root\frontend\node_modules")) {
    Push-Location "$root\frontend"; npm install; Pop-Location
}

Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root\backend'; .\.venv\Scripts\uvicorn.exe app.main:app --reload --reload-dir app --port 8000"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root\frontend'; npm run dev -- -p 3100"

Write-Host "Backend:  http://localhost:8000/api/docs"
Write-Host "Frontend: http://localhost:3100"
