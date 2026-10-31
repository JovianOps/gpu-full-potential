# GPU Unlock

![GPU Unlock Logo](logo.jpg)

Windows desktop GPU control app (PySide6) with 5 tabs: Dashboard, Tune, Auto Tune, Bench, Profiles.

## Quick Start

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Then run the app:

```bash
python gpuui.py
```

Double-click `START_GUI.bat` or run `dist/GPUUnlock.exe` directly.

## Features
- Live GPU metrics (util, temp, power, clocks)
- Clock/fan/voltage tuning (mVolt+ optional)
- Auto-tune algorithm
- 30s stress benchmark
- JSON profile management
- OSD overlay (always-on-top temp/FPS/clock display, toggle via tray)
- History graph (QChart, 5-min window, CSV export)
- Cross-vendor support (AMD ADL/amdsmi, Intel Level Zero)
- Auto-apply on boot (Task Scheduler)
- Tray notifications (temp threshold alerts)

## Build
```bash
python -m PyInstaller gpuui.py --onefile --windowed --name GPUUnlock
```

## Platform
- **Windows**: NVIDIA GPU + nvidia-smi, UAC admin required
- **Linux**: Ubuntu/Arch/Mint support, pkexec for privileges
- **NVAPI ctypes for clock/fan/VF reading**
