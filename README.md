# CodeEye

A desktop webcam barcode scanner and code generator built with Python and PyQt6.

## Features

- Live webcam scanning through OpenCV and ZXing-C++; recognizes QR Code, Aztec, Codabar, Code 39/93/128, Data Matrix, EAN, ITF, PDF417, UPC and other formats supported by the installed ZXing-C++ build.
- Choose a format filter or scan all supported formats.
- Draw a crop rectangle on the preview to limit scanning to a region; clear it whenever needed.
- Digital zoom (1×–4×), camera device selection, and a bright side-panel screen fill light.
- Scan barcode images from disk.
- Generate QR codes with L/M/Q/H error correction, configurable quiet zone, module size, and foreground/background colors.
- Generate Code 128, Code 39, EAN-13, EAN-8, and ITF linear barcodes.
- Settings for Light, Dark, or Follow system appearance; optional in-app minimize/maximize/restore/close controls; and an on/off switch for local history.
- Load generator input from a UTF-8 text file, or encode any file type (images, PDFs, documents, archives, audio, etc.) as a multi-QR file set. File sets are limited to 10 MiB and exported as a ZIP of QR PNGs; extract it and select every QR image in CodeEye to reassemble and checksum-verify the original file. Text imports are limited to 1 MiB. Single QR codes and linear barcodes still have format-specific capacity limits.
- Local scan/generation history stored in `~/.codeeye/history.json`; settings are stored in `~/.codeeye/settings.json`. Double-click a history entry to copy its data.

## Bug reports and feedback

Found a bug or have an idea to improve CodeEye? Please open an issue in the GitHub repository:

**[Report a bug or request a feature](https://github.com/bigcakeisgood/codeeye/issues/new/choose)**

If no issue templates are available, use [New issue](https://github.com/bigcakeisgood/codeeye/issues/new). Include steps to reproduce the problem, what you expected to happen, what actually happened, your operating system, and any relevant terminal error messages. Remove private information before posting logs or screenshots.

## Install and run

Python 3.10+ is recommended.

```bash
python -m venv .venv
# Windows:
.venv\\Scripts\\activate
# macOS/Linux:
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

Grant camera permission to your terminal/Python application if prompted. If the camera does not open, try another device in the camera dropdown.

## Build a Linux executable with Nuitka

Build on the Linux distribution/architecture you intend to target. A Linux binary built on one system is not guaranteed to run on every other distribution.

Install system build tools first (Debian/Ubuntu example):

```bash
sudo apt update
sudo apt install -y python3-venv python3-dev build-essential patchelf
```

Then run the build script from the repository root. It creates/uses `.venv`, installs the app requirements and Nuitka inside that environment, and builds a standalone distribution:

```bash
chmod +x build_linux.sh
./build_linux.sh
```

The build output is placed under `dist/` (normally `dist/main.dist/`). Launch the executable from its output directory so bundled Qt and library files remain alongside it:

```bash
./dist/main.dist/CodeEye
```

If the executable has a different name, check the contents of `dist/`. The standalone output is a directory containing the executable and required runtime files; distribute the whole directory, not just the executable. Test webcam permissions and scanning on the target machine. This script has been added to the repository, but its output has not been built or runtime-tested in this environment.

## Build a Windows executable with Nuitka

Build on Windows. Install Python 3.10+ and Visual Studio Build Tools with the **Desktop development with C++** workload (including a supported MSVC compiler). Open PowerShell in the repository directory and run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\build_windows.ps1
```

The script creates/uses `.venv`, installs requirements and Nuitka, and builds a standalone app under `dist\main.dist\CodeEye.exe` (the exact output directory can vary by Nuitka version). Distribute the entire `main.dist` directory, not only the EXE. Build on Windows for Windows; a Linux build cannot be used as a Windows executable. The script is committed but has not been built or runtime-tested in this environment.

## Notes

- QR error correction levels are L (about 7%), M (15%), Q (25%), and H (30%). Linear barcode formats have their own symbology rules.
- Quiet zone is the blank margin around a code. For QR codes, four modules is the typical recommended minimum for reliable scanning.
- Decoding/generation support varies by installed library and symbology. Aztec, Codabar, Data Matrix and PDF417 are supported for scanning when ZXing-C++ supports them; this app generates QR and the listed linear formats.
- The side fill light brightens an on-screen panel; it cannot turn on a physical webcam LED or increase the camera sensor's exposure directly.
