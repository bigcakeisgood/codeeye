# CodeEye Windows standalone build (PowerShell)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if ($env:OS -ne "Windows_NT") {
    throw "This script must be run in Windows PowerShell on Windows."
}

if (Get-Command py -ErrorAction SilentlyContinue) {
    py -3 --version
    if ($LASTEXITCODE -ne 0) { throw "Python 3 was not found. Install Python 3.10+ and enable the Python launcher." }
    if (-not (Test-Path ".venv")) { py -3 -m venv .venv }
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    if (-not (Test-Path ".venv")) { python -m venv .venv }
} else {
    throw "Python 3.10+ is required. Install it from python.org and enable Add Python to PATH."
}

$VenvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
& $VenvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "Could not upgrade pip." }
& $VenvPython -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Could not install requirements." }
& $VenvPython -m pip install --upgrade nuitka zstandard
if ($LASTEXITCODE -ne 0) { throw "Could not install Nuitka." }

# Nuitka normally uses the Visual Studio C/C++ toolchain on Windows.
$NuitkaArgs = @(
    "--standalone",
    "--enable-plugin=pyqt6",
    "--include-qt-plugins=platforms",
    "--include-package=cv2",
    "--include-package=zxingcpp",
    "--include-package=qrcode",
    "--include-package=barcode",
    "--output-dir=dist",
    "--output-filename=CodeEye.exe"
)
& $VenvPython -m nuitka @NuitkaArgs main.py
if ($LASTEXITCODE -ne 0) {
    throw "Build failed. Install Visual Studio Build Tools with the Desktop development with C++ workload, then rerun this script."
}

Write-Host ""
Write-Host "Build finished. Run: .\dist\main.dist\CodeEye.exe"
Write-Host "Distribute the entire main.dist directory, not only the EXE."
