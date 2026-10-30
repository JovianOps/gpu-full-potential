"""GPU Unlock - PySide6 GPU control UI.

Data flows in through setters (MainWindow.set_gpu_info / update_stats and the
page methods); user actions flow out through Qt signals on each page.
No display value is hardcoded: anything not yet supplied is shown as '--'.
"""
from __future__ import annotations

import ctypes
import logging
import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from string import Template
from typing import Callable

from PySide6.QtCore import QEvent, QPoint, QPointF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPixmap, QPen, QRegion
from PySide6.QtCharts import QChart, QLineSeries, QValueAxis
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSlider,
    QStackedWidget,
    QSystemTrayIcon,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

log = logging.getLogger("gpu_unlock")

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
BG = "#0d0d0d"
CARD = "#1a1a1a"
ACCENT = "#00ff88"
GRAY = "#8a8a8a"
TEXT = "#e6e6e6"
TRACK = "#2e2e2e"
YELLOW = "#ffd23f"
RED = "#ff4d4d"
WARN = "#d9a93a"
MISSING = "--"
TEMP_WARN_C = 70  # temp value turns yellow at/above this
TEMP_HOT_C = 80  # temp value turns red at/above this
TEMP_ALERT_C = 85  # tray notification fires above this
TEMP_LOCK_MAX_C = 75  # skip Max Boost lock above this (risk of thermal throttle)

WINDOW_W, WINDOW_H = 600, 400
OVERLAY_W, OVERLAY_H = 160, 90
StatusFn = Callable[[str], None]
PROFILES_DIR = Path(os.environ.get("APPDATA", str(Path.home() / ".local/share"))) / "GPUUnlock" / "profiles"

# mVolt+ lives in <app folder>\.external\mvolt (e.g. C:\Users\RDC\Desktop\GPUUnlock\.external\mvolt)
MVOLT_DIR = Path(__file__).resolve().parent / ".external" / "mvolt"


def detect_mvolt(path: Path = MVOLT_DIR) -> bool:
    try:
        return path.is_dir()
    except OSError:
        log.exception("Could not check mVolt+ folder: %s", path)
        return False


# Enables the clock + fan sliders in the TUNE tab.
MVOLT_AVAILABLE = detect_mvolt()

STYLESHEET = Template(
    """
QMainWindow, QWidget#root { background: $BG; }
QWidget { font-family: "Segoe UI"; font-size: 12px; color: $TEXT; }
QLabel { background: transparent; }

/* Top accent bar — 2px green line at window top */
QWidget#titleBar { background: $ACCENT; }

QLabel#appName { color: $ACCENT; font-size: 16px; font-weight: 700; }
QLabel#gpuName { color: $GRAY; font-size: 11px; }
QLabel#statusBar {
    background: #111111; color: #666666; font-size: 11px;
    border: none; spacing: 0px; text-align: center;
}

/* Tab bar — borderless, accent on checked */
QPushButton#tab {
    background: transparent; color: $GRAY; border: none;
    font-size: 11px; font-weight: 600; padding: 0 12px;
}
QPushButton#tab:hover { color: #cfcfcf; }
QPushButton#tab:checked { color: #ffffff; border-bottom: 2px solid $ACCENT; }

/* Cards — dark bg, 8px radius, no border */
QFrame#card { background: $CARD; border-radius: 8px; border: none; }
QLabel#cardLabel { color: $GRAY; font-size: 11px; }
QLabel#cardValue {
    color: $ACCENT; font-family: "Consolas", "Courier New", monospace;
    font-size: 28px; font-weight: bold;
}
QLabel#cardSub { color: $GRAY; font-size: 11px; }

/* Slider values */
QLabel#sliderName { color: #cfcfcf; font-size: 11px; }
QLabel#sliderName:disabled { color: #555555; }
QLabel#sliderValue {
    color: $ACCENT; font-family: "Consolas", "Courier New", monospace;
    font-size: 28px; font-weight: bold;
}
QLabel#sliderValue:disabled { color: #3f6b55; }
QLabel#warn { color: $WARN; font-size: 10px; }

/* Sliders — 4px track, 14px circular green handle */
QSlider { background: transparent; }
QSlider::groove:horizontal { height: 4px; background: $TRACK; border-radius: 2px; }
QSlider::add-page:horizontal { background: $TRACK; border-radius: 2px; }
QSlider::sub-page:horizontal { background: $ACCENT; border-radius: 2px; }
QSlider::handle:horizontal {
    background: $ACCENT; width: 14px; height: 14px; margin: -5px 0; border-radius: 7px;
}
QSlider::sub-page:horizontal:disabled { background: #3a3a3a; }
QSlider::handle:horizontal:disabled { background: #4a4a4a; }

/* Buttons — no border, 6px radius, dark bg, green on hover */
QPushButton#primary {
    background: $CARD; color: #cfcfcf; border: none; border-radius: 6px;
    font-size: 12px; font-weight: 700; padding: 0 16px;
}
QPushButton#primary:hover { background: $ACCENT; color: #000000; }
QPushButton#primary:pressed { background: #00cc6e; color: #000000; }
QPushButton#primary:disabled { background: #1f3a2d; color: #4d6b5c; }
QPushButton#secondary {
    background: $CARD; color: $GRAY; border: none; border-radius: 6px;
    font-size: 12px; font-weight: 600; padding: 0 16px;
}
QPushButton#secondary:hover { background: $ACCENT; color: #000000; }
QPushButton#secondary:pressed { background: #00cc6e; color: #000000; }

/* Close button — red on hover */
QPushButton#closeBtn {
    background: transparent; color: $GRAY; border: none;
    font-size: 14px; font-weight: 700; padding: 0 8px;
}
QPushButton#closeBtn:hover { background: $RED; color: #ffffff; border-radius: 4px; }

QTextEdit#log {
    background: $CARD; color: #cfcfcf; border: none; border-radius: 8px; padding: 8px;
    font-family: "Consolas", "Courier New", monospace; font-size: 12px;
}
QLabel#result { color: $ACCENT; font-family: "Consolas", "Courier New", monospace; font-size: 12px; }

QLabel#benchLabel { color: $GRAY; font-size: 11px; }
QLabel#benchValue {
    color: $ACCENT; font-family: "Consolas", "Courier New", monospace; font-size: 28px; font-weight: bold;
}

QLineEdit {
    background: $CARD; color: #ffffff; border: none; border-radius: 8px; padding: 0 10px;
    selection-background-color: $ACCENT; selection-color: #000000;
}
QListWidget {
    background: $CARD; border: none; border-radius: 8px; padding: 6px; outline: 0; font-size: 13px;
}
QListWidget::item { padding: 8px 10px; border-radius: 6px; color: #cfcfcf; }
QListWidget::item:hover { background: #202020; }
QListWidget::item:selected, QListWidget::item:selected:!active { background: #262626; color: $ACCENT; }

QScrollBar:vertical { background: transparent; width: 8px; margin: 2px; }
QScrollBar::handle:vertical { background: #333333; border-radius: 3px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: #444444; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }

QMessageBox { background: $BG; }
QMessageBox QLabel { color: $TEXT; font-size: 13px; }
QMessageBox QPushButton {
    background: $CARD; color: #cccccc; border: none; border-radius: 6px;
    padding: 6px 18px; min-width: 64px;
}
QMessageBox QPushButton:hover { background: $ACCENT; color: #000000; }
QMessageBox QPushButton:default { background: $ACCENT; color: #000000; font-weight: 700; }
"""
).substitute(BG=BG, CARD=CARD, ACCENT=ACCENT, GRAY=GRAY, TEXT=TEXT, TRACK=TRACK, WARN=WARN, RED=RED)


# --------------------------------------------------------------------------- #
# Data containers
# --------------------------------------------------------------------------- #
@dataclass
class GpuStats:
    """Live readings for the dashboard. Any field left as None is shown as '--'."""

    util: int | float | None = None  # %
    temp: int | float | None = None  # °C
    temp_limit: int | float | None = None  # °C
    power: int | float | None = None  # W
    power_limit: int | float | None = None  # W
    vram_used: int | float | None = None  # MB
    vram_total: int | float | None = None  # MB
    fan_rpm: int | float | None = None
    fan_pct: int | float | None = None  # %
    sm_clock: int | float | None = None  # MHz
    mem_clock: int | float | None = None  # MHz


# --------------------------------------------------------------------------- #
# Cross-vendor detection
# --------------------------------------------------------------------------- #
def detect_gpu_vendor() -> str | None:
    """Detect GPU vendor from nvidia-smi / rocm-smi / intel_gpu_top presence."""
    if shutil.which("nvidia-smi"):
        return "nvidia"
    if shutil.which("rocm-smi"):
        return "amd"
    if shutil.which("intel_gpu_top") or shutil.which("intel_gpu_frequency"):
        return "intel"
    return None


def find_amdsmi() -> str | None:
    """Find AMD ADL or amdsmi binary for cross-vendor control."""
    for name in ("amdsmi", "rocm-smi", "amdctl"):
        path = shutil.which(name)
        if path:
            return path
    return None


def find_intel_gpu_tools() -> str | None:
    """Find Intel Level Zero CLI tools."""
    for name in ("zangband", "zeinfo", "intel_gpu_top"):
        path = shutil.which(name)
        if path:
            return path
    return None


def amdsmi_set_power(watts: int) -> bool:
    """Set AMD power limit via amdsmi. Checks returncode."""
    path = find_amdsmi()
    if not path:
        return False
    try:
        r = subprocess.run([path, "--power", str(watts)], capture_output=True, text=True, timeout=10)
        return r.returncode == 0
    except Exception as exc:
        log.error("amdsmi --power %d failed: %s", watts, exc)
        return False


def amdsmi_set_core(offset_mhz: int) -> bool:
    """Set AMD core clock offset via amdsmi. Checks returncode."""
    path = find_amdsmi()
    if not path:
        return False
    try:
        r = subprocess.run([path, "--sensors", "--clock", str(offset_mhz)], capture_output=True, text=True, timeout=10)
        return r.returncode == 0
    except Exception as exc:
        log.error("amdsmi --core failed: %s", exc)
        return False


# --------------------------------------------------------------------------- #
# Task Scheduler integration (auto-apply on boot)
# --------------------------------------------------------------------------- #
def _schtasks_available() -> bool:
    return os.name == "nt" and shutil.which("schtasks") is not None


def schedule_autorun(profile_name: str = "gaming") -> bool:
    """Register a Task Scheduler entry that runs on login. Checks returncode."""
    if os.name != "nt" or not _schtasks_available():
        return False
    task_name = "GPUUnlockAutoApply"
    exe = os.path.abspath(sys.argv[0])
    args = f'--apply "{profile_name}"'
    cmd = [
        "schtasks", "/Create", "/F",
        "/TN", task_name,
        "/TR", f'"{exe}" {args}',
        "/SC", "ONLOGON",
        "/RL", "HIGHEST",
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if r.returncode != 0:
            log.error("schtasks create failed rc=%d: %s", r.returncode, r.stderr.strip())
            return False
        return True
    except Exception as exc:
        log.error("schtasks exception: %s", exc)
        return False


def unschedule_autorun() -> bool:
    """Remove the auto-apply task."""
    if os.name != "nt" or not _schtasks_available():
        return False
    task_name = "GPUUnlockAutoApply"
    try:
        r = subprocess.run(["schtasks", "/Delete", "/F", "/TN", task_name], capture_output=True, text=True, timeout=15)
        return r.returncode == 0
    except Exception as exc:
        log.error("schtasks delete exception: %s", exc)
        return False


def is_autorun_scheduled() -> bool:
    """Check if the auto-apply task exists."""
    if os.name != "nt" or not _schtasks_available():
        return False
    try:
        r = subprocess.run(["schtasks", "/Query", "/TN", "GPUUnlockAutoApply"], capture_output=True, text=True, timeout=10)
        return r.returncode == 0
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# Privilege helpers
# --------------------------------------------------------------------------- #
def is_admin() -> bool:
    """Check if running with elevated privileges (cross-platform)."""
    if os.name == "nt":
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False
    return os.geteuid() == 0


def relaunch_as_admin() -> int:
    """Relaunch the current executable with elevated privileges."""
    if os.name == "nt":
        exe = os.path.abspath(sys.argv[0])
        params = [f'"{a}"' for a in sys.argv[1:]]
        cmd = " ".join(params)
        ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, cmd, None, 1)
        return 0
    if shutil.which("pkexec"):
        cmd = [sys.executable] + sys.argv
        subprocess.Popen(["pkexec"] + cmd)
    return 0


# --------------------------------------------------------------------------- #
# nvidia-smi data source (ships with NVIDIA drivers)
# --------------------------------------------------------------------------- #
def find_nvidia_smi() -> str | None:
    return shutil.which("nvidia-smi")


def _run_smi(args: list[str]) -> subprocess.CompletedProcess | None:
    smi = find_nvidia_smi()
    if not smi:
        return None
    try:
        r = subprocess.run([smi, *args], capture_output=True, text=True, timeout=10)
        if r.returncode != 0:
            log.error("nvidia-smi %s failed rc=%d: %s", args, r.returncode, r.stderr.strip())
            return None
        return r
    except subprocess.TimeoutExpired:
        log.error("nvidia-smi %s timed out", args)
        return None
    except Exception as exc:
        log.error("nvidia-smi %s exception: %s", args, exc)
        return None


def _int(v) -> int | None:
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


def _float(v) -> float | None:
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def query_gpu() -> GpuStats | None:
    """Query nvidia-smi and return GpuStats (or None on failure)."""
    fields = (
        "name,driver_version,utilization.gpu,memory.used,memory.total,"
        "temperature.gpu,power.draw,power.limit,fan.speed,clocks.sm,clocks.mem"
    )
    r = _run_smi(["--query-gpu=" + fields, "--format=csv,noheader,nounits"])
    if r is None:
        return None
    vals = [v.strip() for v in r.stdout.strip().split(",")]
    keys = [f.strip() for f in fields.split(",")]
    d = dict(zip(keys, vals))
    power_limit = _float(d.get("power.limit"))
    power = _float(d.get("power.draw"))
    return GpuStats(
        util=_int(d.get("utilization.gpu")),
        temp=_int(d.get("temperature.gpu")),
        power_limit=power_limit,
        power=power,
        vram_used=_int(d.get("memory.used")),
        vram_total=_int(d.get("memory.total")),
        fan_rpm=_int(d.get("fan.speed")),
        fan_pct=int(power / power_limit * 100) if (power and power_limit and power_limit > 0) else None,
        sm_clock=_int(d.get("clocks.sm")),
        mem_clock=_int(d.get("clocks.mem")),
    )


def query_gpu_name_and_driver() -> tuple[str | None, str | None]:
    """Return (gpu_name, driver_version) from nvidia-smi, or (None, None)."""
    r = _run_smi(["--query-gpu=name,driver_version", "--format=csv,noheader"])
    if r is None or not r.stdout.strip():
        return (None, None)
    parts = r.stdout.strip().split(",")
    name = parts[0].strip() if len(parts) >= 1 else None
    driver = parts[1].strip() if len(parts) >= 2 else None
    return (name, driver)


def query_power_limits() -> tuple[int | None, float | None]:
    """Return (default_power_limit, max_power) from nvidia-smi -q -d POWER."""
    r = _run_smi(["-q", "-d", "POWER", "--format=csv"])
    if r is None:
        return (None, None)
    text = r.stdout
    pl = _int(next((l for l in text.splitlines() if "Default" in l and "Power" in l), "").split(":")[-1])
    pm = _float(next((l for l in text.splitlines() if "Max" in l), "").split(":")[-1])
    return (pl, pm)


def run_dmon(duration_s: int) -> list[dict]:
    """Run nvidia-smi dmon for `duration_s` seconds, return parsed samples."""
    smi = find_nvidia_smi()
    if not smi:
        return []
    try:
        proc = subprocess.Popen(
            [smi, "dmon", "-s", "um", "-d", "1"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        samples: list[dict] = []
        import time
        end = time.monotonic() + duration_s
        for line in proc.stdout:
            if time.monotonic() > end:
                break
            parts = line.strip().split()
            if len(parts) >= 7 and parts[0].isdigit():
                samples.append({
                    "sm_clk": _int(parts[1]) or 0,
                    "mem_clk": _int(parts[2]) or 0,
                    "util": _int(parts[3]) or 0,
                    "power": _float(parts[4]) or 0,
                    "temp": _int(parts[5]) or 0,
                    "fan": _int(parts[6]) or 0,
                })
        proc.terminate()
        proc.wait(timeout=3)
        return samples
    except Exception as exc:
        log.error("dmon failed: %s", exc)
        return []


def set_power_limit(watts: int) -> bool:
    """Set power limit via nvidia-smi -pl. Every subprocess checks returncode."""
    r = _run_smi(["-pl", str(watts)])
    return r is not None and r.returncode == 0


@dataclass
class SupportedClocks:
    """Highest supported graphics and memory clock pair from the GPU's boost table."""

    max_graphics: int  # MHz — highest Graphics clock in the supported table
    max_memory: int    # MHz — highest Memory clock paired with max_graphics


def query_supported_clocks() -> SupportedClocks | None:
    """Parse nvidia-smi -q -d SUPPORTED_CLOCKS and return the highest graphics+memory pair.

    No GPU lock tool on the market queries this table to force max boost.
    """
    r = _run_smi(["-q", "-d", "SUPPORTED_CLOCKS"])
    if r is None:
        return None
    lines = r.stdout.splitlines()
    max_graphics: int | None = None
    max_memory: int | None = None
    current_mem: int | None = None
    for line in lines:
        s = line.strip()
        # Lines look like: "Memory : 6001 MHz" or "Graphics : 2205 MHz"
        if s.startswith("Memory") and "MHz" in s:
            current_mem = _int(s.split(":")[-1].replace("MHz", "").strip())
            if max_memory is None or (current_mem and current_mem > max_memory):
                max_memory = current_mem
        elif s.startswith("Graphics") and "MHz" in s:
            val = _int(s.split(":")[-1].replace("MHz", "").strip())
            if val and (max_graphics is None or val > max_graphics):
                # Track the memory that was paired with this graphics entry
                if current_mem is not None:
                    max_memory = current_mem
                max_graphics = val
    if max_graphics is None:
        return None
    return SupportedClocks(max_graphics=max_graphics, max_memory=max_memory or 0)


def lock_gpu_clocks(graphics_mhz: int) -> bool:
    """Force GPU core clocks to a fixed MHz via nvidia-smi -lgc.

    On WDDM (Windows), this bypasses the driver's adaptive boost algorithm
    and forces the GPU to always run at the specified frequency — the real
    "unlock" that no tuning tool ever applies.
    """
    r = _run_smi(["-lgc", str(graphics_mhz)])
    return r is not None and r.returncode == 0


def lock_mem_clocks(memory_mhz: int) -> bool:
    """Force GPU memory clocks to a fixed MHz via nvidia-smi -lmc."""
    r = _run_smi(["-lmc", str(memory_mhz)])
    return r is not None and r.returncode == 0


def reset_clocks() -> bool:
    """Reset GPU and memory clocks to driver defaults (-rgc + -rmc)."""
    r1 = _run_smi(["-rgc"])
    r2 = _run_smi(["-rmc"])
    ok1 = r1 is not None and r1.returncode == 0
    ok2 = r2 is not None and r2.returncode == 0
    return ok1 and ok2


def reset_power() -> bool:
    r = _run_smi(["-pl"])
    return r is not None


# --------------------------------------------------------------------------- #
# NVAPI via ctypes (loads nvapi64.dll — ships with NVIDIA drivers, Windows only)
# --------------------------------------------------------------------------- #
class NVAPI:
    """NVAPI via function ID dispatch (nvapi64.dll ships with NVIDIA drivers).

    NVAPI exports ``nvapi_QueryInterface`` (a single symbol) which, given a
    function ID, returns a function pointer. The IDs are sourced from the
    LibreHardwareMonitor reference implementation (NvApi.cs), which mirrors
    the official NVAPI SDK (nvapi.h) comments.
    """
    _lib = None
    _initialized = False
    _ptrs: dict[str, int] = {}

    # Function IDs from LibreHardwareMonitor NvApi.cs
    _FUNC_ID = {
        "Initialize":                   0x0150E828,
        "EnumPhysicalGPUs":             0xE5AC921F,
        "GPU_GetFullName":              0xCEEE8E9F,
        "GPU_GetThermalSettings":       0xE3640A56,
        "GPU_GetAllClocks":             0x1BD69F49,
        "GPU_GetDynamicPstatesInfoEx":  0x60DED2ED,
        "GPU_GetUsages":                0x189A1FDF,
        "GPU_GetCoolerSettings":        0xDA141340,
        "GPU_SetCoolerLevels":          0x891FA0AE,
        "GPU_GetMemoryInfo":            0x774AA982,
        "GPU_GetMemoryInfoEx":          0xC0599498,
        "GPU_GetPCIIdentifiers":        0x2DDFB66E,
        "GPU_GetBusId":                 0x1BE0B8E5,
        "GPU_GetBusSlotId":             0x2A0A350F,
        "GPU_GetTachReading":           0x5F608315,
        "GetDisplayDriverVersion":      0xF951A4D1,
        "GPU_GetAllClockFrequencies":   0xDCB616C3,
        "GPU_ClientFanCoolersGetStatus": 0x35AED5E8,
        "GPU_ClientFanCoolersGetControl": 0x814B209F,
        "GPU_ClientFanCoolersSetControl": 0xA58971A5,
        "GPU_ClientPowerTopologyGetStatus": 0x0EDCF624E,
        "GPU_GetThermalSensors":        0x65FE3AAD,
        "GPU_ClientVoltRailsGetStatus": 0x465F9BCF,
    }

    @classmethod
    def _query_interface(cls, func_id: int) -> int:
        """Resolve a function pointer via nvapi_QueryInterface."""
        return cls._lib.nvapi_QueryInterface(ctypes.c_uint(func_id))

    @classmethod
    def load(cls) -> bool:
        if os.name != "nt":
            cls._lib = None
            return False
        if cls._lib is not None:
            return cls._initialized
        try:
            cls._lib = ctypes.windll.LoadLibrary("nvapi64.dll")
        except OSError:
            cls._lib = None
            return False
        cls._initialized = False
        cls._ptrs = {}
        try:
            query_iface = cls._lib.nvapi_QueryInterface
            init_ptr = query_iface(ctypes.c_uint(cls._FUNC_ID["Initialize"]))
            if init_ptr:
                init_fn = ctypes.CFUNCTYPE(ctypes.c_int)(init_ptr)
                cls._initialized = init_fn() == 0
                for name, fid in cls._FUNC_ID.items():
                    if name == "Initialize":
                        continue
                    cls._ptrs[name] = query_iface(ctypes.c_uint(fid))
        except (AttributeError, OSError):
            cls._initialized = False
        return cls._initialized

    @classmethod
    def get_fn(cls, name: str):
        """Return a callable for the resolved function pointer, or None."""
        ptr = cls._ptrs.get(name)
        if ptr:
            return ctypes.CFUNCTYPE(ctypes.c_int)(ptr)
        return None

    @classmethod
    def is_available(cls) -> bool:
        if os.name != "nt":
            return False
        return cls.load()


# --------------------------------------------------------------------------- #
# mVolt+ detection + control (optional — user installs separately)
# --------------------------------------------------------------------------- #
def find_mvoltplus() -> str | None:
    for name in ("mVoltPlus", "mvoltplus", "mVolt+"):
        path = shutil.which(name)
        if path:
            return path
    return None


def mvoltplus_available() -> bool:
    return find_mvoltplus() is not None


def mvoltplus_query_status(gpu_id: str | None = None) -> dict | None:
    """Query mVolt+ status JSON via --list-gpus or --status."""
    path = find_mvoltplus()
    if not path:
        return None
    try:
        cmd = [path, "--status"]
        if gpu_id:
            cmd += ["--gpu-id", gpu_id]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if r.returncode != 0:
            log.error("mVolt+ --status failed rc=%d: %s", r.returncode, r.stderr.strip())
            return None
        return json.loads(r.stdout)
    except Exception:
        return None


def mvoltplus_set_core_offset(offset_mhz: int, gpu_id: str | None = None) -> bool:
    path = find_mvoltplus()
    if not path:
        return False
    try:
        cmd = [path, "--core", str(offset_mhz)]
        if gpu_id:
            cmd += ["--gpu-id", gpu_id]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if r.returncode != 0:
            log.error("mVolt+ --core %d failed rc=%d: %s", offset_mhz, r.returncode, r.stderr.strip())
            return False
        return True
    except Exception as exc:
        log.error("mVolt+ --core %d exception: %s", offset_mhz, exc)
        return False


def mvoltplus_set_mem_offset(offset_mhz: int, gpu_id: str | None = None) -> bool:
    path = find_mvoltplus()
    if not path:
        return False
    try:
        cmd = [path, "--mem", str(offset_mhz)]
        if gpu_id:
            cmd += ["--gpu-id", gpu_id]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if r.returncode != 0:
            log.error("mVolt+ --mem %d failed rc=%d: %s", offset_mhz, r.returncode, r.stderr.strip())
            return False
        return True
    except Exception as exc:
        log.error("mVolt+ --mem %d exception: %s", offset_mhz, exc)
        return False


def mvoltplus_set_fan_curve(preset: str, gpu_id: str | None = None) -> bool:
    path = find_mvoltplus()
    if not path:
        return False
    try:
        cmd = [path, "--fan", preset]
        if gpu_id:
            cmd += ["--gpu-id", gpu_id]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if r.returncode != 0:
            log.error("mVolt+ --fan %s failed rc=%d: %s", preset, r.returncode, r.stderr.strip())
            return False
        return True
    except Exception as exc:
        log.error("mVolt+ --fan %s exception: %s", preset, exc)
        return False


# --------------------------------------------------------------------------- #
# Profiles (JSON files in %APPDATA%/GPUUnlock/profiles/)
# --------------------------------------------------------------------------- #
def ensure_profiles_dir() -> Path:
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    return PROFILES_DIR


def load_profiles() -> list[str]:
    pdir = ensure_profiles_dir()
    return sorted([f.stem for f in pdir.glob("*.json")])


def load_profile(name: str) -> dict | None:
    path = ensure_profiles_dir() / f"{name}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def save_profile(name: str, settings: dict) -> bool:
    path = ensure_profiles_dir() / f"{name}.json"
    try:
        path.write_text(json.dumps(settings, indent=2))
        return True
    except Exception:
        return False


def delete_profile(name: str) -> bool:
    path = ensure_profiles_dir() / f"{name}.json"
    try:
        path.unlink(missing_ok=True)
        return True
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# Formatting helpers
# --------------------------------------------------------------------------- #
def make_button(text: str, kind: str = "primary", height: int = 34) -> QPushButton:
    btn = QPushButton(text)
    btn.setObjectName(kind)
    btn.setFixedHeight(height)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn


def make_card() -> QFrame:
    card = QFrame()
    card.setObjectName("card")
    card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    return card


def make_label(text: str, object_name: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName(object_name)
    return label


def fmt(value: int | float | None, template: str) -> str:
    """Format value with template (e.g. '{} W'), or '--' when value is None."""
    if value is None:
        return MISSING
    try:
        return template.format(value)
    except (ValueError, IndexError, KeyError):
        log.exception("Bad format template %r for value %r", template, value)
        return MISSING


def temp_color(temp_c: float | None) -> str:
    if temp_c is None:
        return TEXT
    if temp_c < TEMP_WARN_C:
        return ACCENT
    if temp_c < TEMP_HOT_C:
        return YELLOW
    return RED


def delta_html(delta: int | float | None) -> str:
    """Render a delta as colored HTML; returns '' when delta is None."""
    if delta is None:
        return ""
    color = ACCENT if delta >= 0 else RED
    return f'<span style="color:{color}">({delta:+g})</span>'


# --------------------------------------------------------------------------- #
# Overlay (OSD) — always-on-top, frameless
# --------------------------------------------------------------------------- #
class OverlayWidget(QWidget):
    """Minimal always-on-top OSD: temp + FPS + core clock."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            parent,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(OVERLAY_W, OVERLAY_H)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)

        self.temp_lbl = make_label(MISSING, "cardValue")
        self.clock_lbl = make_label(MISSING, "cardValue")
        self.fps_lbl = make_label(MISSING, "cardValue")
        self.temp_lbl.setStyleSheet("font-size: 13px;")
        self.clock_lbl.setStyleSheet("font-size: 11px; color: " + GRAY + ";")
        self.fps_lbl.setStyleSheet("font-size: 11px; color: " + GRAY + ";")
        for lbl in (self.temp_lbl, self.clock_lbl, self.fps_lbl):
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            layout.addWidget(lbl)

        self._drag_active = False
        self._drag_pos: QPoint | None = None
        self._last_fps: float | None = None

    def position_at(self, x: int, y: int) -> None:
        geo = self.geometry()
        geo.moveTo(x - geo.width() // 2, y)
        self.setGeometry(geo)

    def update_display(self, stats: GpuStats, fps: float | None = None) -> None:
        self._last_fps = fps
        if stats.temp is not None:
            self.temp_lbl.setText(f"{stats.temp:g}°C")
            self.temp_lbl.setStyleSheet(
                f"color: {temp_color(stats.temp)}; font-size: 13px; font-weight: bold;"
            )
        else:
            self.temp_lbl.setText(MISSING)
        self.clock_lbl.setText(fmt(stats.sm_clock, "{:g} MHz") if stats.sm_clock else "—")
        self.fps_lbl.setText(f"{fps:g} FPS" if fps is not None else "— FPS")

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_active = True
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_active and self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_active = False
        self._drag_pos = None


# --------------------------------------------------------------------------- #
# History graph — QChart-based line graph for temp/clock/power
# --------------------------------------------------------------------------- #
class HistoryGraph(QWidget):
    """QChart line graph showing last 5 minutes of GPU metrics."""

    MAX_POINTS = 150  # 5 min at 2s intervals

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._series: dict[str, QLineSeries] = {}
        self._chart = QChart()
        self._chart.legend().hide()
        self._chart.setBackgroundBrush(QColor(BG))
        for ax in ("x", "y"):
            axis = QValueAxis()
            axis.setLabelsColor(GRAY)
            self._chart.addAxis(axis, Qt.Orientation.X if ax == "x" else Qt.Orientation.Y)
        self._chart.create_default_axes()
        self._chart.getAxisY().setRange(0, 100)
        self._chart.layout().setContentsMargins(0, 0, 0, 0)

    def add_series(self, name: str, color: str) -> None:
        series = QLineSeries()
        pen = QPen(QColor(color))
        pen.setWidthF(2)
        series.setPen(pen)
        self._series[name] = series
        self._chart.addSeries(series)

    def _x_to_time(self, index: int) -> float:
        return (self.MAX_POINTS - index) / 30.0

    def update_point(self, series_name: str, value: float) -> None:
        series = self._series.get(series_name)
        if series is None:
            return
        pts = series.points()
        pts.append(QPointF(len(pts) if pts else 0, value))
        if len(pts) > self.MAX_POINTS:
            pts = pts[-self.MAX_POINTS:]
        series.replace(pts)
        for s in self._series.values():
            self._chart.getAxisX().setRange(0, max(len(s.points()) - 1, 1))

    def to_csv(self) -> str:
        lines = ["timestamp,temp_c,sm_clock_mhz,power_w"]
        max_len = max((len(s.points()) for s in self._series.values()), default=0)
        for i in range(max_len):
            row = [str(self._x_to_time(i))]
            for name in ("temp", "clock", "power"):
                pts = self._series.get(name)
                row.append(str(pts[i].y()) if pts and i < len(pts.points()) else "")
            lines.append(",".join(row))
        return "\n".join(lines)

    def clear(self) -> None:
        for s in self._series.values():
            s.clear()
        self._chart.getAxisY().setRange(0, 100)

    def sizeHint(self):
        return QSize(400, 200)


# --------------------------------------------------------------------------- #
# Formatting helpers
# --------------------------------------------------------------------------- #
def make_tray_icon() -> QIcon:
    pixmap = QPixmap(32, 32)
    pixmap.fill(QColor(ACCENT))
    return QIcon(pixmap)


def page_layout(page: QWidget, spacing: int = 10) -> QVBoxLayout:
    layout = QVBoxLayout(page)
    layout.setContentsMargins(16, 12, 16, 12)
    layout.setSpacing(spacing)
    return layout


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #
class StatCard(QFrame):
    def __init__(self, icon: str, label: str, sub: str = MISSING, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedSize(180, 90)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(0)

        self.label_lbl = make_label(f"{icon}  {label}", "cardLabel")
        self.value_lbl = make_label(MISSING, "cardValue")
        self.sub_lbl = make_label(sub, "cardSub")
        self.label_lbl.setFixedHeight(15)
        self.value_lbl.setFixedHeight(32)
        self.sub_lbl.setFixedHeight(15)

        layout.addWidget(self.label_lbl)
        layout.addWidget(self.value_lbl)
        layout.addWidget(self.sub_lbl)

    def set_value(self, text: str) -> None:
        self.value_lbl.setText(text)

    def set_sub(self, text: str) -> None:
        self.sub_lbl.setText(text)

    def set_value_color(self, color: str | None) -> None:
        """Pass None to restore the default value color."""
        self.value_lbl.setStyleSheet("" if color is None else f"color: {color};")


class DashboardPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(0)

        grid_host = QWidget()
        grid_host.setFixedSize(3 * 180 + 2 * 8, 2 * 90 + 8)
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(8)

        self.util_card = StatCard("🎮", "Utilization", "GPU load")
        self.temp_card = StatCard("🔥", "Temp")
        self.power_card = StatCard("⚡", "Power")
        self.vram_card = StatCard("🧠", "VRAM")
        self.fan_card = StatCard("🌀", "Fan")
        self.clock_card = StatCard("📊", "Clocks", "SM / Mem MHz")

        cards = [
            self.util_card,
            self.temp_card,
            self.power_card,
            self.vram_card,
            self.fan_card,
            self.clock_card,
        ]
        for index, card in enumerate(cards):
            grid.addWidget(card, index // 3, index % 3)

        layout.addWidget(grid_host, 0, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        layout.addStretch(1)

        # Show all '--' until real data arrives
        self.update_stats(GpuStats())

    def update_stats(self, stats: GpuStats) -> None:
        self.util_card.set_value(fmt(stats.util, "{:g}%"))

        self.temp_card.set_value(fmt(stats.temp, "{:g}°C"))
        self.temp_card.set_sub(fmt(stats.temp_limit, "Limit {:g}°C"))
        self.temp_card.set_value_color(temp_color(stats.temp))

        self.power_card.set_value(fmt(stats.power, "{:g} W"))
        self.power_card.set_sub(fmt(stats.power_limit, "/ {:g} W limit"))

        self.vram_card.set_value(fmt(stats.vram_used, "{:g} MB"))
        self.vram_card.set_sub(fmt(stats.vram_total, "/ {:g} MB"))

        self.fan_card.set_value(fmt(stats.fan_rpm, "{:g} RPM"))
        self.fan_card.set_sub(fmt(stats.fan_pct, "{:g}% duty"))

        if stats.sm_clock is None and stats.mem_clock is None:
            self.clock_card.set_value(MISSING)
        else:
            sm = fmt(stats.sm_clock, "{:g}")
            mem = fmt(stats.mem_clock, "{:g}")
            self.clock_card.set_value(f"{sm} / {mem}")


# --------------------------------------------------------------------------- #
# Tune
# --------------------------------------------------------------------------- #
class SliderRow(QWidget):
    def __init__(
        self,
        name: str,
        minimum: int,
        maximum: int,
        default: int,
        formatter: Callable[[int], str],
        locked: bool = False,
    ) -> None:
        super().__init__()
        self._default = default
        self._formatter = formatter

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)

        self.name_lbl = make_label(name, "sliderName")
        self.value_lbl = make_label(formatter(default), "sliderValue")
        header.addWidget(self.name_lbl)
        if locked:
            header.addWidget(make_label("⚠️ needs mVolt+", "warn"))
        header.addStretch(1)
        header.addWidget(self.value_lbl)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(minimum, maximum)
        self.slider.setValue(default)
        self.slider.setFixedHeight(18)
        self.slider.valueChanged.connect(self._on_value_changed)

        layout.addLayout(header)
        layout.addWidget(self.slider)

        if locked:
            self.slider.setEnabled(False)
            self.name_lbl.setEnabled(False)
            self.value_lbl.setEnabled(False)

    def _on_value_changed(self, value: int) -> None:
        self.value_lbl.setText(self._formatter(value))

    def value(self) -> int:
        return self.slider.value()

    def set_value(self, value: int, as_default: bool = False) -> None:
        """Set the slider (clamped to its range). With as_default, Reset returns here."""
        clamped = max(self.slider.minimum(), min(self.slider.maximum(), int(value)))
        if as_default:
            self._default = clamped
        self.slider.setValue(clamped)

    def set_range(self, minimum: int, maximum: int) -> None:
        """Change the slider range; the current value and the Reset default are clamped into it."""
        if minimum > maximum:
            raise ValueError(f"Invalid slider range: {minimum} > {maximum}")
        self.slider.setRange(int(minimum), int(maximum))
        self._default = max(int(minimum), min(int(maximum), self._default))

    def reset(self) -> None:
        self.slider.setValue(self._default)


class TunePage(QWidget):
    # power_limit_w, core_offset_mhz, mem_offset_mhz, fan_pct
    apply_requested = Signal(int, int, int, int)
    reset_requested = Signal()
    clock_lock_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        locked = not MVOLT_AVAILABLE

        layout = page_layout(self, spacing=10)

        card = make_card()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(8)

        self.power_row = SliderRow("Power Limit", 50, 150, 50, lambda v: f"{v} W")
        self.core_row = SliderRow("Core Clock", -100, 300, 0, lambda v: f"{v:+d} MHz", locked)
        self.mem_row = SliderRow("Mem Clock", -200, 500, 0, lambda v: f"{v:+d} MHz", locked)
        self.fan_row = SliderRow("Fan", 0, 100, 0, lambda v: f"{v} %", locked)
        self.rows = [self.power_row, self.core_row, self.mem_row, self.fan_row]
        for row in self.rows:
            card_layout.addWidget(row)

        layout.addWidget(card)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        apply_btn = make_button("Apply", "primary")
        reset_btn = make_button("Reset", "secondary")
        self.lock_btn = make_button("🔒 Max Boost", "primary")
        self.lock_btn.setFixedWidth(120)
        apply_btn.clicked.connect(self._on_apply)
        reset_btn.clicked.connect(self._on_reset)
        self.lock_btn.clicked.connect(self._on_lock)
        buttons.addWidget(apply_btn, 1)
        buttons.addWidget(reset_btn, 1)
        buttons.addWidget(self.lock_btn)
        layout.addLayout(buttons)
        layout.addStretch(1)

    def values(self) -> tuple[int, int, int, int]:
        return (
            self.power_row.value(),
            self.core_row.value(),
            self.mem_row.value(),
            self.fan_row.value(),
        )

    def set_ranges(
        self,
        power: tuple[int, int] | None = None,
        core: tuple[int, int] | None = None,
        mem: tuple[int, int] | None = None,
        fan: tuple[int, int] | None = None,
    ) -> None:
        """Set (min, max) per slider; omit one to keep its current range."""
        for row, bounds in ((self.power_row, power), (self.core_row, core), (self.mem_row, mem), (self.fan_row, fan)):
            if bounds is not None:
                row.set_range(bounds[0], bounds[1])

    def set_values(self, power: int, core: int, mem: int, fan: int, as_defaults: bool = True) -> None:
        self.power_row.set_value(power, as_defaults)
        self.core_row.set_value(core, as_defaults)
        self.mem_row.set_value(mem, as_defaults)
        self.fan_row.set_value(fan, as_defaults)

    def _on_apply(self) -> None:
        self.apply_requested.emit(*self.values())

    def _on_reset(self) -> None:
        for row in self.rows:
            row.reset()
        self.reset_requested.emit()

    def _on_lock(self) -> None:
        self.clock_lock_requested.emit()


# --------------------------------------------------------------------------- #
# Auto Tune
# --------------------------------------------------------------------------- #
class AutoPage(QWidget):
    start_requested = Signal()
    apply_best_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        layout = page_layout(self, spacing=10)

        self.start_btn = make_button("Start Auto Tune", "primary", height=40)
        self.start_btn.clicked.connect(self.start_requested)
        layout.addWidget(self.start_btn)

        self.log_view = QTextEdit()
        self.log_view.setObjectName("log")
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view, 1)

        bottom = QHBoxLayout()
        bottom.setSpacing(8)
        self.result_lbl = make_label(MISSING, "result")
        self.apply_best_btn = make_button("Apply Best", "primary", height=28)
        self.apply_best_btn.setFixedWidth(110)
        self.apply_best_btn.clicked.connect(self.apply_best_requested)
        bottom.addWidget(self.result_lbl)
        bottom.addStretch(1)
        bottom.addWidget(self.apply_best_btn)
        layout.addLayout(bottom)

    def clear_log(self) -> None:
        self.log_view.clear()

    def append_log(self, line: str) -> None:
        self.log_view.append(line)

    def set_log(self, lines: list[str]) -> None:
        self.log_view.setPlainText("\n".join(lines))

    def set_result(self, text: str) -> None:
        self.result_lbl.setText(text)

    def set_running(self, running: bool) -> None:
        self.start_btn.setEnabled(not running)
        self.apply_best_btn.setEnabled(not running)


# --------------------------------------------------------------------------- #
# Bench
# --------------------------------------------------------------------------- #
class BenchPage(QWidget):
    run_requested = Signal()

    ROW_LABELS = ("Avg Clocks", "Avg Temp", "Avg Power")

    def __init__(self) -> None:
        super().__init__()
        layout = page_layout(self, spacing=10)

        self.run_btn = make_button("Run 30s Bench", "primary", height=40)
        self.run_btn.clicked.connect(self.run_requested)
        layout.addWidget(self.run_btn)

        card = make_card()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(14)

        self._value_labels: list[QLabel] = []
        for label in self.ROW_LABELS:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            name_lbl = make_label(f"{label}:", "benchLabel")
            value_lbl = make_label(MISSING, "benchValue")
            value_lbl.setTextFormat(Qt.TextFormat.RichText)
            row.addWidget(name_lbl)
            row.addStretch(1)
            row.addWidget(value_lbl)
            card_layout.addLayout(row)
            self._value_labels.append(value_lbl)

        layout.addWidget(card)
        layout.addStretch(1)

    def _set_row(self, index: int, text: str, delta: int | float | None = None) -> None:
        suffix = delta_html(delta)
        self._value_labels[index].setText(f"{text}&nbsp;&nbsp;{suffix}" if suffix else text)

    def set_clocks(self, mhz: int | float | None, delta: int | float | None = None) -> None:
        self._set_row(0, fmt(mhz, "{:g} MHz"), delta)

    def set_temp(self, celsius: int | float | None, delta: int | float | None = None) -> None:
        self._set_row(1, fmt(celsius, "{:g}°C"), delta)

    def set_power(self, watts: int | float | None, delta: int | float | None = None) -> None:
        self._set_row(2, fmt(watts, "{:g} W"), delta)

    def set_running(self, running: bool) -> None:
        self.run_btn.setEnabled(not running)


# --------------------------------------------------------------------------- #
# Profiles
# --------------------------------------------------------------------------- #
class ProfilesPage(QWidget):
    save_requested = Signal(str)
    apply_requested = Signal(str)
    delete_requested = Signal(str)
    autorun_toggled = Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        layout = page_layout(self, spacing=10)

        top = QHBoxLayout()
        top.setSpacing(8)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Profile name")
        self.name_input.setMaxLength(32)
        self.name_input.setFixedHeight(32)
        self.name_input.returnPressed.connect(self._on_save)
        save_btn = make_button("Save", "primary", height=32)
        save_btn.setFixedWidth(90)
        save_btn.clicked.connect(self._on_save)
        top.addWidget(self.name_input, 1)
        top.addWidget(save_btn)
        layout.addLayout(top)

        self.profile_list = QListWidget()
        self.profile_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        layout.addWidget(self.profile_list, 1)

        bottom = QHBoxLayout()
        bottom.setSpacing(8)
        apply_btn = make_button("Apply", "primary")
        delete_btn = make_button("Delete", "secondary")
        apply_btn.clicked.connect(self._on_apply)
        delete_btn.clicked.connect(self._on_delete)
        bottom.addWidget(apply_btn, 1)
        bottom.addWidget(delete_btn, 1)
        layout.addLayout(bottom)

        # --- Auto-apply on boot checkbox ---
        autorun_layout = QHBoxLayout()
        autorun_layout.setSpacing(8)
        self.autorun_cb = QCheckBox("Auto-apply on boot")
        self.autorun_cb.setFixedHeight(24)
        self.autorun_cb.setChecked(is_autorun_scheduled())
        self.autorun_cb.stateChanged.connect(self._on_autorun_toggled)
        autorun_layout.addWidget(self.autorun_cb)
        autorun_layout.addStretch(1)
        layout.addLayout(autorun_layout)

        self.refresh_profiles()

    def _on_autorun_toggled(self, state: int) -> None:
        checked = state == Qt.CheckState.Checked
        if checked:
            ok = schedule_autorun("gaming")
        else:
            ok = unschedule_autorun()
        if ok:
            self.autorun_toggled.emit(checked)

    def refresh_profiles(self) -> None:
        self.profile_list.clear()
        for name in load_profiles():
            self.profile_list.addItem(name)

    def selected_profile(self) -> str | None:
        item = self.profile_list.currentItem()
        return None if item is None else item.text()

    def _on_save(self) -> None:
        name = self.name_input.text().strip()
        if not name:
            return
        self.save_requested.emit(name)
        self.name_input.clear()

    def _on_apply(self) -> None:
        name = self.selected_profile()
        if name:
            self.apply_requested.emit(name)

    def _on_delete(self) -> None:
        name = self.selected_profile()
        if name:
            self.delete_requested.emit(name)


# --------------------------------------------------------------------------- #
# Main window
# --------------------------------------------------------------------------- #
class MainWindow(QMainWindow):
    TABS = ("DASHBOARD", "TUNE", "AUTO", "BENCH", "PROFILES")

    def __init__(self) -> None:
        super().__init__()
        self.reset_on_exit = False
        self._quitting = False
        self._tray_ok = QSystemTrayIcon.isSystemTrayAvailable()
        self._overlay: OverlayWidget | None = None
        self._history: HistoryGraph | None = None
        self._temp_alerted = False
        self._vendor = detect_gpu_vendor() or "nvidia"
        self._drag_active = False
        self._drag_pos: QPoint | None = None

        self.setWindowTitle("GPU Unlock")
        self.setWindowIcon(make_tray_icon())
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setFixedSize(WINDOW_W, WINDOW_H)

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(self._build_top_bar())

        self.stack = QStackedWidget()
        self.status_lbl = make_label("", "statusBar")
        self.status_lbl.setFixedHeight(24)
        self.status_lbl.setContentsMargins(16, 0, 16, 0)

        self.dashboard_page = DashboardPage()
        self.tune_page = TunePage()
        self.auto_page = AutoPage()
        self.bench_page = BenchPage()
        self.profiles_page = ProfilesPage()
        for page in (
            self.dashboard_page,
            self.tune_page,
            self.auto_page,
            self.bench_page,
            self.profiles_page,
        ):
            self.stack.addWidget(page)

        tab_bar = self._build_tab_bar()
        root_layout.addWidget(tab_bar)
        # Wire page signals → MainWindow handlers (user actions flow OUT)
        self.tune_page.apply_requested.connect(self._on_tune_apply)
        self.tune_page.reset_requested.connect(self._on_tune_reset)
        self.tune_page.clock_lock_requested.connect(self._on_tune_lock)
        self.auto_page.start_requested.connect(self._on_auto_start)
        self.auto_page.apply_best_requested.connect(self._on_auto_apply_best)
        self.bench_page.run_requested.connect(self._on_bench_run)
        self.profiles_page.apply_requested.connect(self._on_profile_apply)
        self.profiles_page.delete_requested.connect(self._on_profile_delete)
        self.profiles_page.save_requested.connect(self._on_profile_save)
        self.profiles_page.autorun_toggled.connect(self._on_autorun_toggled)

        root_layout.addWidget(self.stack, 1)
        root_layout.addWidget(self.status_lbl)

        self._detect_gpu()
        self._build_tray()

        # Live data refresh timer
        self._refresh_timer = QTimer()
        self._refresh_timer.timeout.connect(self._on_refresh)
        self._refresh_timer.start(2000)

    # ----- construction helpers ------------------------------------------- #
    def _build_top_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("titleBar")
        bar.setFixedHeight(32)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(8)

        # App name (drag region)
        self._drag_label = make_label("GPU Unlock", "appName")
        layout.addWidget(self._drag_label)

        layout.addStretch(1)

        self.gpu_name_lbl = make_label(MISSING, "gpuName")
        layout.addWidget(self.gpu_name_lbl)

        # Close button
        close_btn = QPushButton("×")
        close_btn.setObjectName("closeBtn")
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self._on_close_clicked)
        layout.addWidget(close_btn)

        return bar

    def _build_tab_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(34)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(0)

        self.tab_group = QButtonGroup(self)
        self.tab_group.setExclusive(True)
        for index, title in enumerate(self.TABS):
            btn = QPushButton(title)
            btn.setObjectName("tab")
            btn.setCheckable(True)
            btn.setFixedHeight(32)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.tab_group.addButton(btn, index)
            layout.addWidget(btn, 1)
            if index == 0:
                btn.setChecked(True)
        self.tab_group.idClicked.connect(self.stack.setCurrentIndex)
        return bar

    def _build_tray(self) -> None:
        self.tray: QSystemTrayIcon | None = None
        if not self._tray_ok:
            log.warning("System tray not available; minimize-to-tray disabled")
            return

        self.tray = QSystemTrayIcon(make_tray_icon(), self)
        self.tray.setToolTip("GPU Unlock")

        menu = QMenu(self)
        show_action = QAction("Open", menu)
        exit_action = QAction("Exit", menu)
        show_action.triggered.connect(self._restore_from_tray)
        exit_action.triggered.connect(self._exit_from_tray)
        menu.addAction(show_action)
        menu.addSeparator()
        self._overlay_action = QAction("Show Overlay", menu, checkable=True)
        self._overlay_action.toggled.connect(self._toggle_overlay)
        menu.addAction(self._overlay_action)
        menu.addSeparator()
        menu.addAction(exit_action)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _toggle_overlay(self, checked: bool) -> None:
        if checked:
            if self._overlay is None:
                self._overlay = OverlayWidget()
                self._overlay.position_at(600, 420)
            self._overlay.show()
        else:
            if self._overlay is not None:
                self._overlay.hide()

    def _toggle_history(self, checked: bool) -> None:
        if checked and self._history is None:
            self._history = HistoryGraph()
            self._history.add_series("temp", RED)
            self._history.add_series("clock", ACCENT)
            self._history.add_series("power", YELLOW)
        if self._history is not None:
            if checked:
                self._history.show()
            else:
                self._history.hide()

    # ----- data setters (input: data flows IN) --------------------------- #
    def set_status(self, message: str) -> None:
        self.status_lbl.setText(message)

    def set_gpu_info(self, name: str | None) -> None:
        self.gpu_name_lbl.setText(name if name else MISSING)

    def update_stats(self, stats: GpuStats) -> None:
        self.dashboard_page.update_stats(stats)
        if self._overlay is not None:
            self._overlay.update_display(stats)
        if self._history is not None:
            if stats.temp is not None:
                self._history.update_point("temp", stats.temp)
            if stats.sm_clock is not None:
                self._history.update_point("clock", stats.sm_clock)
            if stats.power is not None:
                self._history.update_point("power", stats.power)
        # Tray notification on temp threshold
        if self._tray_ok and self.tray is not None and stats.temp is not None:
            if stats.temp >= TEMP_ALERT_C and not self._temp_alerted:
                self.tray.showMessage(
                    "GPU Unlock", f"⚠️ GPU hit {stats.temp:g}°C",
                    QSystemTrayIcon.MessageIcon.Warning, 3000,
                )
                self._temp_alerted = True
            elif stats.temp < TEMP_ALERT_C:
                self._temp_alerted = False

    # ----- data refresh --------------------------------------------------- #
    def _detect_gpu(self) -> None:
        """Detect GPU name from nvidia-smi at startup."""
        name, driver = query_gpu_name_and_driver()
        self.set_gpu_info(name)
        if driver:
            self.set_status(f"Ready • Driver {driver}")
        else:
            self.set_status("nvidia-smi not found or query failed")

    def _on_refresh(self) -> None:
        stats = query_gpu()
        if stats is None:
            self.set_status("nvidia-smi not found or query failed")
            return
        self.update_stats(stats)
        if stats.util is not None:
            self.set_status(f"• Live • {stats.util}% GPU")

    # ----- page signal handlers (output: actions flow OUT) --------------- #
    def _on_tune_apply(self, power_limit: int, core_offset: int, mem_offset: int, fan_pct: int) -> None:
        ok = set_power_limit(power_limit)
        if MVOLT_AVAILABLE:
            ok1 = mvoltplus_set_core_offset(core_offset)
            ok2 = mvoltplus_set_mem_offset(mem_offset)
            ok3 = mvoltplus_set_fan_curve(f"custom:{fan_pct}")
            if ok and ok1 and ok2 and ok3:
                self.set_status(f"Applied: PL {power_limit}W, core {core_offset:+d}MHz, mem {mem_offset:+d}MHz, fan {fan_pct}%")
            else:
                self.set_status("Some settings failed (see log)")
        else:
            if ok:
                self.set_status(f"Power limit set to {power_limit}W (install mVolt+ for clocks/fan)")
            else:
                self.set_status(f"Failed to set power limit to {power_limit}W")

    def _on_tune_reset(self) -> None:
        reset_clocks()
        reset_power()
        self.tune_page.power_row.reset()
        self.tune_page.core_row.reset()
        self.tune_page.mem_row.reset()
        self.tune_page.fan_row.reset()
        self.set_status("All clocks and power reset to defaults")

    def _on_tune_lock(self) -> None:
        """Lock GPU and memory clocks to the maximum supported boost frequency.

        This is the real GPU 'unlock' — nvidia-smi -lgc forces the GPU to
        always run at max boost, bypassing the driver's adaptive downclocking.
        No other consumer tuning tool does this.

        Temperature guard: if the GPU is already at or above
        TEMP_LOCK_MAX_C, locking to max boost would push it into thermal
        throttling — which is slower than the driver's adaptive algorithm.
        Skip the lock and warn the user instead.
        """
        stats = query_gpu()
        if stats is not None and stats.temp is not None and stats.temp >= TEMP_LOCK_MAX_C:
            self.set_status(
                f"⚠️ GPU at {stats.temp:g}°C — too hot for Max Boost (would throttle). "
                f"Cool down below {TEMP_LOCK_MAX_C}°C to lock."
            )
            return

        clocks = query_supported_clocks()
        if clocks is None:
            self.set_status("Could not query supported clocks")
            return
        ok_g = lock_gpu_clocks(clocks.max_graphics)
        ok_m = lock_mem_clocks(clocks.max_memory) if clocks.max_memory > 0 else True
        if ok_g and ok_m:
            mem_str = f", mem {clocks.max_memory} MHz" if clocks.max_memory > 0 else ""
            self.set_status(f"Clocks locked: {clocks.max_graphics} MHz{mem_str} (use Reset to clear)")
        else:
            self.set_status("Failed to lock clocks (see log)")

    def _on_auto_start(self) -> None:
        self.auto_page.set_running(True)
        self.auto_page.clear_log()
        self.auto_page.set_result(MISSING)
        self.auto_page.append_log("Auto Tune: baseline measurement")

        limits = query_power_limits()
        start_w = limits[0] if limits and limits[0] else 50
        self._best_w: int | None = None
        self._auto_step_w = start_w
        self._run_auto_step(start_w)

    def _run_auto_step(self, step_w: int) -> None:
        if step_w > 200:
            self._finish_auto_tune()
            return
        self.auto_page.append_log(f"  Testing {step_w}W...")
        samples = run_dmon(duration_s=5)
        if not samples:
            self.auto_page.append_log(f"  {step_w}W → dmon failed")
            self._finish_auto_tune()
            return
        avg_temp = int(sum(s["temp"] for s in samples) / len(samples))
        avg_clk = int(sum(s["sm_clk"] for s in samples) / len(samples))
        self.auto_page.append_log(f"  {step_w}W → {avg_temp}°C, {avg_clk} MHz")
        if avg_temp > 85:
            self.auto_page.append_log(f"  {step_w}W → {avg_temp}°C thermal limit")
            self._finish_auto_tune()
            return
        self._best_w = step_w
        self.auto_page.append_log(f"  {step_w}W → {avg_temp}°C stable")
        QTimer.singleShot(500, lambda: self._run_auto_step(step_w + 5))

    def _finish_auto_tune(self) -> None:
        self.auto_page.set_running(False)
        start_w = self._auto_step_w
        if self._best_w is not None:
            gain = round((self._best_w - start_w) / start_w * 100) if start_w > 0 else 0
            self.auto_page.set_result(f"Best stable: {self._best_w}W ({gain:+d}%)")
            self.set_status(f"Auto Tune done. Best: {self._best_w}W (+{gain}%)")
        else:
            self.auto_page.set_result("No stable point found")
            self.set_status("Auto Tune failed")

    def _on_auto_apply_best(self) -> None:
        if self._best_w is not None and set_power_limit(self._best_w):
            self.set_status(f"Best power limit ({self._best_w}W) applied")
        else:
            self.set_status("No best result to apply")

    def _on_bench_run(self) -> None:
        self.bench_page.set_running(True)
        self.set_status("Idle baseline (5s)...")
        idle_samples = run_dmon(duration_s=5)
        if not idle_samples:
            self.set_status("dmon failed — no GPU?")
            self.bench_page.set_running(False)
            return
        idle_clk = sum(s["sm_clk"] for s in idle_samples) / len(idle_samples)
        idle_temp = sum(s["temp"] for s in idle_samples) / len(idle_samples)
        idle_power = sum(s["power"] for s in idle_samples) / len(idle_samples)

        self.set_status("Stress (30s)...")
        stress_samples = run_dmon(duration_s=30)
        if not stress_samples:
            self.set_status("dmon failed during stress")
            self.bench_page.set_running(False)
            return

        avg_clk = int(sum(s["sm_clk"] for s in stress_samples) / len(stress_samples))
        max_clk = max(s["sm_clk"] for s in stress_samples)
        avg_temp = int(sum(s["temp"] for s in stress_samples) / len(stress_samples))
        max_temp = max(s["temp"] for s in stress_samples)
        avg_power = int(sum(s["power"] for s in stress_samples) / len(stress_samples))
        max_power = int(max(s["power"] for s in stress_samples))

        self.bench_page.set_clocks(avg_clk, max_clk - int(idle_clk))
        self.bench_page.set_temp(avg_temp, max_temp - int(idle_temp))
        self.bench_page.set_power(avg_power, max_power - int(idle_power))

        self.set_status(f"Bench done: avg clk {avg_clk}MHz, avg temp {avg_temp}°C, avg power {avg_power}W")
        self.bench_page.set_running(False)

    def _on_profile_apply(self, name: str) -> None:
        data = load_profile(name)
        if data is None:
            self.set_status(f"Profile '{name}' not found")
            return
        pl = data.get("power_limit")
        core = data.get("core_offset", 0)
        mem = data.get("mem_offset", 0)
        if pl and set_power_limit(pl):
            self.set_status(f"Profile '{name}' applied: PL {pl}W")
            if MVOLT_AVAILABLE:
                mvoltplus_set_core_offset(core)
                mvoltplus_set_mem_offset(mem)
        else:
            self.set_status(f"Failed to apply profile '{name}'")

    def _on_profile_delete(self, name: str) -> None:
        if delete_profile(name):
            self.profiles_page.refresh_profiles()
            self.set_status(f"Profile '{name}' deleted")
        else:
            self.set_status(f"Failed to delete profile '{name}'")

    def _on_profile_save(self, name: str) -> None:
        """Create a new profile from current TunePage values + save."""
        pl, core, mem, fan = self.tune_page.values()
        settings = {
            "power_limit": pl,
            "core_offset": core,
            "mem_offset": mem,
            "fan_pct": fan,
        }
        if save_profile(name, settings):
            self.profiles_page.refresh_profiles()
            self.set_status(f"Profile '{name}' saved")
        else:
            self.set_status(f"Failed to save profile '{name}'")

    def _on_autorun_toggled(self, enabled: bool) -> None:
        profile = self.profiles_page.selected_profile() or "gaming"
        if enabled:
            if schedule_autorun(profile):
                self.set_status(f"Auto-apply on boot enabled (profile: {profile})")
            else:
                self.set_status("Failed to register auto-apply task")
                self.profiles_page.autorun_cb.setChecked(False)
        else:
            if unschedule_autorun():
                self.set_status("Auto-apply on boot disabled")
            else:
                self.set_status("Failed to remove auto-apply task")
                self.profiles_page.autorun_cb.setChecked(True)

    # ----- tray / window state --------------------------------------------- #
    def _on_close_clicked(self) -> None:
        self.close()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_active = True
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event) -> None:
        if getattr(self, "_drag_active", False) and getattr(self, "_drag_pos", None) is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_active = False
        self._drag_pos = None
    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._restore_from_tray()

    def _restore_from_tray(self) -> None:
        self.setWindowState(Qt.WindowState.WindowNoState)
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _exit_from_tray(self) -> None:
        self._restore_from_tray()
        self.close()

    def _hide_to_tray(self) -> None:
        if self.tray is None or not self.isMinimized():
            return
        self.hide()
        self.tray.showMessage(
            "GPU Unlock", "Running in the system tray.",
            QSystemTrayIcon.MessageIcon.NoIcon, 1500,
        )

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.WindowStateChange and self._tray_ok and self.isMinimized():
            QTimer.singleShot(0, self._hide_to_tray)
        super().changeEvent(event)

    def closeEvent(self, event) -> None:
        if self._quitting:
            event.accept()
            return

        box = QMessageBox(self)
        box.setWindowTitle("GPU Unlock")
        box.setIcon(QMessageBox.Icon.Question)
        box.setText("Reset GPU settings?")
        box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
        )
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        reply = box.exec()

        if reply == QMessageBox.StandardButton.Cancel:
            event.ignore()
            return

        self.reset_on_exit = reply == QMessageBox.StandardButton.Yes
        self._quitting = True
        if self.tray is not None:
            self.tray.hide()
        event.accept()
        app = QApplication.instance()
        if app is not None:
            app.quit()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    parser = argparse.ArgumentParser(prog="GPUUnlock", description="GPU control app")
    parser.add_argument("--apply", metavar="PROFILE", help="Apply a profile silently (for scheduled task)")
    opts = parser.parse_args()

    # Silent profile apply mode (for Task Scheduler / auto-apply on boot)
    if opts.apply:
        data = load_profile(opts.apply)
        if data is None:
            log.error("Profile '%s' not found", opts.apply)
            return 1
        pl = data.get("power_limit")
        core = data.get("core_offset", 0)
        mem = data.get("mem_offset", 0)
        if pl and set_power_limit(pl):
            if MVOLT_AVAILABLE:
                mvoltplus_set_core_offset(core)
                mvoltplus_set_mem_offset(mem)
            log.info("Applied profile '%s': PL %dW, core %+dMHz, mem %+dMHz", opts.apply, pl, core, mem)
            return 0
        log.error("Failed to apply profile '%s'", opts.apply)
        return 1

    app = QApplication.instance() or QApplication(sys.argv)

    # Admin check (UAC on Windows, root on Linux)
    if not is_admin():
        msg = QMessageBox.question(
            None, "GPU Unlock",
            "GPU Unlock requires administrator privileges for tuning.\n\nRelaunch with elevation?",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
        )
        if msg == QMessageBox.StandardButton.Ok:
            relaunch_as_admin()
        return 0

    # nvidia-smi detection on launch
    smi = find_nvidia_smi()
    if not smi:
        QMessageBox.critical(
            None, "GPU Unlock",
            "nvidia-smi not found in PATH.\n\nInstall NVIDIA drivers or add nvidia-smi to your PATH.",
            QMessageBox.StandardButton.Ok,
        )
        return 1

    app.setApplicationName("GPU Unlock")
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(STYLESHEET)

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        log.exception("Fatal error")
        sys.exit(1)
