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

Double-click `GPUUnlock.exe` directly — no `START_GUI.bat` needed.

### Auto Tune & Benchmark
Auto Tune and the 30s stress benchmark require a real GPU workload. If FurMark
is not installed, the app auto-downloads FurMark 2 (portable, ~32MB from
geeks3d.com) into `.external/furmark/` on first use. Alternatively, install
FurMark manually from https://geeks3d.com/furmark/ and the app will find it on
PATH.

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
