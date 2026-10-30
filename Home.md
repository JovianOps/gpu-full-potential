# GPUUnlock Wiki

Windows desktop GPU control app (PySide6).

## Quick Start
Double-click `START_GUI.bat` or run `dist/GPUUnlock.exe`.

## Tabs
| Tab | Function |
|-----|----------|
| **Dashboard** | Live GPU metrics (util, temp, power, clocks) |
| **Tune** | Manual clock/fan/voltage sliders |
| **Auto Tune** | Algorithmic tuning |
| **Bench** | 30s stress test |
| **Profiles** | Save/load JSON profiles |

## Data Sources
- `nvidia-smi` (subprocess) — primary GPU metrics
- NVAPI (ctypes) — clock/fan/pstate/VF reading
- mVolt+ (optional, runtime PATH detection)

## Platform Support
| Platform | NVAPI | nvidia-smi | mVolt+ |
|----------|-------|-------------|--------|
| Windows  | ✓ | ✓ | ✓ (optional) |
| Linux (Ubuntu/Arch/Mint) | ✗ (DLL only) | ✓ | ✗

## Admin Privileges
- Windows: UAC prompt on launch, auto-relaunch
- Linux: pkexec for privilege escalation
