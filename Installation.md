# Installation

## Windows
1. Download `GPUUnlock.exe` from [Releases](https://github.com/JovianOps/GPUUnlock/releases)
2. Run `START_GUI.bat` or `GPUUnlock.exe` directly
3. Admin privileges required (UAC prompt on first launch)

## Prerequisites
- NVIDIA GPU with drivers installed
- `nvidia-smi` on PATH

## Optional Features
- **mVolt+** — advanced clock/fan/voltage tuning (auto-detected via `shutil.which()`)
- **NVAPI** (nvapi64.dll) — real-time clock/fan/VF reading

## Linux (Ubuntu / Arch / Mint)
```bash
python3 gpuui.py
```
Uses `pkexec` for privilege escalation if not running as root.

## Build from Source
```bash
pip install PySide6
python -m PyInstaller gpuui.py --onefile --windowed --name GPUUnlock
```
