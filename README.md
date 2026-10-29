# GPU Unlock

Windows desktop GPU control app (PySide6) with 5 tabs: Dashboard, Tune, Auto Tune, Bench, Profiles.

## Quick Start
Double-click `START_GUI.bat` or run `dist/GPUUnlock.exe` directly.

## Features
- Live GPU metrics (util, temp, power, clocks)
- Clock/fan/voltage tuning (mVolt+ optional)
- Auto-tune algorithm
- 30s stress benchmark
- JSON profile management

## Build
```bash
python -m PyInstaller gpuui.py --onefile --windowed --name GPUUnlock
```

## Platform
- **Windows**: NVIDIA GPU + nvidia-smi, UAC admin required
- **Linux**: Ubuntu/Arch/Mint support, pkexec for privileges
- NVAPI ctypes for clock/fan/VF reading
