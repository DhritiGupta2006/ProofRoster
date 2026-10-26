$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$taskPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
    $taskPython = Join-Path $PSScriptRoot '..\..\work\proofroster-py\Scripts\python.exe'
}
if (-not (Test-Path -LiteralPath $taskPython)) { throw 'Install requirements using the README quickstart first.' }
& $taskPython -m uvicorn dashboard.app:app --host 127.0.0.1 --port 8765
