# Features

## Tabs

### Dashboard
- Live cards: GPU utilization, temperature, power, core clock, memory clock
- Updates every 2 seconds via `nvidia-smi` subprocess polling

### Tune
- Sliders for power limit, core clock, memory clock, fan speed
- Apply via `nvidia-smi -pl` (power) + mVolt+ CLI (clocks/fan)
- mVolt+ detected at runtime via `shutil.which()`

### Auto Tune
- Algorithm scans clock offsets under stress (`nvidia-smi dmon`)
- Finds highest stable overclock per domain

### Bench
- 30-second stress test with `nvidia-smi dmon`
- Records baseline + peak temps/power/utilization

### Profiles
- Save/load JSON configs
- Cross-platform: `%APPDATA%/GPUUnlock/profiles/` (Windows)
- `~/.local/share/GPUUnlock/` (Linux)

## Data Flow
1. `query_gpu()` calls `nvidia-smi -q -d POWER,TEMPERATURE,CLOCKS,UTILIZATION,FAN`
2. NVAPI ctypes reads real-time clocks/fan via `nvapi64.dll`
3. Tune Apply → `nvidia-smi -pl <watts>` + `mvolt+ cli setclock <domain> <offset>`
4. Stress → `nvidia-smi dmon -s u -d 1` (utilization monitoring)

## Error Handling
- Every subprocess checks returncode
- Errors surfaced in status bar
- NVAPI gracefully degrades (AttributeError → unavailable)
