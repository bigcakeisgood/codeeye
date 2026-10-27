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
- Local scan/generation history stored in `~/.codeeye/history.json`; double-click a history entry to copy its data.

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

## Notes

- QR error correction levels are L (about 7%), M (15%), Q (25%), and H (30%). Linear barcode formats have their own symbology rules.
- Quiet zone is the blank margin around a code. For QR codes, four modules is the typical recommended minimum for reliable scanning.
- Decoding/generation support varies by installed library and symbology. Aztec, Codabar, Data Matrix and PDF417 are supported for scanning when ZXing-C++ supports them; this app generates QR and the listed linear formats.
- The side fill light brightens an on-screen panel; it cannot turn on a physical webcam LED or increase the camera sensor's exposure directly.
