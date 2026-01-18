# create venv if it doesn't exist
if (-not (Test-Path "venv")) {
    python -m venv venv
}

# activate venv
. .\venv\Scripts\Activate.ps1
