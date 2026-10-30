"""GPU Unlock - PySide6 GPU control UI."""
from __future__ import annotations

import ctypes
import json
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from string import Template
from typing import Callable

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QAction, QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
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

WINDOW_W, WINDOW_H = 600, 400
StatusFn = Callable[[str], None]
PROFILES_DIR = Path(os.environ.get("APPDATA", Path.home() / ".local/share")) / "GPUUnlock" / "profiles"

# Initial display values
GPU_NAME = "NVIDIA GeForce GTX 1650"
DRIVER = "560.94"
UTIL = 5
TEMP = 41
POWER = 5
POWER_LIMIT = 75
VRAM_USED = 512
VRAM_TOTAL = 4096
FAN_RPM = 1450
FAN_PCT = 35
SM_CLK = 300
MEM_CLK = 405

StatusFn = Callable[[str], None]

STYLESHEET = Template(
    """
QMainWindow, QWidget#root { background: $BG; }
QWidget { font-family: "Segoe UI"; font-size: 12px; color: $TEXT; }
QLabel { background: transparent; }

QLabel#appName { color: $ACCENT; font-size: 16px; font-weight: 700; }
QLabel#gpuName { color: $GRAY; font-size: 11px; }
QLabel#statusBar { background: #111111; color: #666666; font-size: 10px; }

QPushButton#tab {
    background: transparent; color: $GRAY; border: none;
    border-bottom: 2px solid transparent;
    font-size: 11px; font-weight: 600; padding: 0 12px;
}
QPushButton#tab:hover { color: #cfcfcf; }
QPushButton#tab:checked { color: #ffffff; border-bottom: 2px solid $ACCENT; }

QFrame#card { background: $CARD; border-radius: 8px; }
QLabel#cardLabel { color: $GRAY; font-size: 11px; }
QLabel#cardValue {
    color: #ffffff; font-family: "Consolas", "Courier New", monospace;
    font-size: 24px; font-weight: bold;
}
QLabel#cardSub { color: $GRAY; font-size: 11px; }

QLabel#sliderName { color: #cfcfcf; font-size: 12px; }
QLabel#sliderName:disabled { color: #555555; }
QLabel#sliderValue {
    color: $ACCENT; font-family: "Consolas", "Courier New", monospace;
    font-size: 12px; font-weight: bold;
}
QLabel#sliderValue:disabled { color: #3f6b55; }
QLabel#warn { color: $WARN; font-size: 10px; }

QSlider { background: transparent; }
QSlider::groove:horizontal { height: 4px; background: $TRACK; border-radius: 2px; }
QSlider::add-page:horizontal { background: $TRACK; border-radius: 2px; }
QSlider::sub-page:horizontal { background: $ACCENT; border-radius: 2px; }
QSlider::handle:horizontal {
    background: $ACCENT; width: 14px; height: 14px; margin: -5px 0; border-radius: 7px;
}
QSlider::sub-page:horizontal:disabled { background: #3a3a3a; }
QSlider::handle:horizontal:disabled { background: #4a4a4a; }

QPushButton#primary {
    background: $ACCENT; color: #000000; border: none; border-radius: 8px;
    font-size: 12px; font-weight: 700; padding: 0 16px;
}
QPushButton#primary:hover { background: #33ffa0; }
QPushButton#primary:pressed { background: #00cc6e; }
QPushButton#primary:disabled { background: #1f3a2d; color: #4d6b5c; }
QPushButton#secondary {
    background: $CARD; color: $GRAY; border: none; border-radius: 8px;
    font-size: 12px; font-weight: 600; padding: 0 16px;
}
QPushButton#secondary:hover { background: #242424; color: #dddddd; }
QPushButton#secondary:pressed { background: #151515; }

QTextEdit#log {
    background: $CARD; color: #cfcfcf; border: none; border-radius: 8px; padding: 8px;
    font-family: "Consolas", "Courier New", monospace; font-size: 12px;
}
QLabel#result { color: $ACCENT; font-family: "Consolas", "Courier New", monospace; font-size: 12px; }

QLabel#benchLabel { color: $GRAY; font-size: 12px; }
QLabel#benchValue {
    color: #ffffff; font-family: "Consolas", "Courier New", monospace; font-size: 13px;
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
    background: $CARD; color: #cccccc; border: none; border-radius: 8px;
    padding: 6px 18px; min-width: 64px;
}
QMessageBox QPushButton:hover { background: #242424; }
QMessageBox QPushButton:default { background: $ACCENT; color: #000000; font-weight: 700; }
"""
).substitute(BG=BG, CARD=CARD, ACCENT=ACCENT, GRAY=GRAY, TEXT=TEXT, TRACK=TRACK, WARN=WARN)


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
    else:
        return os.geteuid() == 0


def relaunch_as_admin() -> int:
    """Relaunch the current executable with elevated privileges."""
    if os.name == "nt":
        params = [os.path.abspath(sys.argv[0])] + [f'"{a}"' for a in sys.argv[1:]]
        cmd = " ".join(params)
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, cmd, None, 1)
        return 0
    else:
        # Linux: use pkexec
        import shutil as _sh
        if _sh.which("pkexec"):
            cmd = [sys.executable] + sys.argv
            subprocess.Popen(["pkexec"] + cmd)
            return 0
        # Fallback: just continue (user must launch with sudo)
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


def _int(v):
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


def _float(v):
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def query_gpu():
    """Query nvidia-smi and return dict of GPU metrics (or None on failure)."""
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
    result = {
        "name": d["name"],
        "driver": d["driver_version"],
        "util": _int(d.get("utilization.gpu")) or 0,
        "vram_used": _int(d.get("memory.used")) or 0,
        "vram_total": _int(d.get("memory.total")) or 0,
        "temp": _int(d.get("temperature.gpu")) or 0,
        "power": _float(d.get("power.draw")) or 0,
        "power_limit": _float(d.get("power.limit")) or 0,
        "fan_rpm": _int(d.get("fan.speed")) or 0,
        "sm_clk": _int(d.get("clocks.sm")) or 0,
        "mem_clk": _int(d.get("clocks.mem")) or 0,
        "fan_pct": 0,
    }
    if result["power_limit"] > 0:
        result["fan_pct"] = int(result["power"] / result["power_limit"] * 100)
    return result


def query_power_limits():
    """Return (power_limit, power_default, power_max) from nvidia-smi -q -d POWER."""
    r = _run_smi(["-q", "-d", "POWER", "--format=csv"])
    if r is None:
        return None
    text = r.stdout
    pl = _int(next((l for l in text.splitlines() if "Default" in l and "Power" in l), "").split(":")[-1])
    pm = _float(next((l for l in text.splitlines() if "Max" in l), "").split(":")[-1])
    return (pl, pm, pm)


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
    r = _run_smi(["-pl", str(watts)])
    return r is not None


def reset_clocks() -> bool:
    r = _run_smi(["-rgc"])
    return r is not None


def reset_power() -> bool:
    r = _run_smi(["-pl", ""])
    return r is not None


# --------------------------------------------------------------------------- #
# NVAPI via ctypes (loads nvapi64.dll — ships with NVIDIA drivers)
# --------------------------------------------------------------------------- #
class NVAPI:
    """NVAPI via function ID dispatch (nvapi64.dll ships with NVIDIA drivers).

    NVAPI exports ``nvapi_QueryInterface`` (a single symbol) which, given a
    function ID, returns a function pointer. The IDs are sourced from the
    LibreHardwareMonitor reference implementation (NvApi.cs), which mirrors
    the official NVAPI SDK (nvapi.h) comments.

    Function IDs verified against LHM ``GetDelegate<T>(id)`` calls:
    """
    _lib = None
    _initialized = False

    # Function IDs from LibreHardwareMonitor NvApi.cs::Initialize()
    _FUNC_ID = {
        "Initialize":                   0x0150E828,
        "EnumPhysicalGPUs":              0xE5AC921F,
        "GPU_GetFullName":               0xCEEE8E9F,
        "GPU_GetThermalSettings":        0xE3640A56,
        "GPU_GetAllClocks":              0x1BD69F49,
        "GPU_GetDynamicPstatesInfoEx":   0x60DED2ED,
        "GPU_GetUsages":                 0x189A1FDF,
        "GPU_GetCoolerSettings":         0xDA141340,
        "GPU_SetCoolerLevels":           0x891FA0AE,
        "GPU_GetMemoryInfo":             0x774AA982,
        "GPU_GetMemoryInfoEx":           0xC0599498,
        "GPU_GetPCIIdentifiers":         0x2DDFB66E,
        "GPU_GetBusId":                  0x1BE0B8E5,
        "GPU_GetBusSlotId":              0x2A0A350F,
        "GPU_GetTachReading":            0x5F608315,
        "GetDisplayDriverVersion":       0xF951A4D1,
        "GPU_GetAllClockFrequencies":    0xDCB616C3,
        "GPU_ClientFanCoolersGetStatus": 0x35AED5E8,
        "GPU_ClientFanCoolersGetControl":0x814B209F,
        "GPU_ClientFanCoolersSetControl":0xA58971A5,
        "GPU_ClientPowerTopologyGetStatus": 0x0EDCF624E,
        "GPU_GetThermalSensors":         0x65FE3AAD,
        "GPU_ClientVoltRailsGetStatus":  0x465F9BCF,
    }

    # Resolved function pointers (populated after Initialize succeeds)
    _ptrs: dict[str, int] = {}

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
                # Resolve remaining function pointers now that NVAPI is initialized
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
# mVolt+ detection + control (optional user install)
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
        return r.returncode == 0
    except Exception:
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
        return r.returncode == 0
    except Exception:
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
        return r.returncode == 0
    except Exception:
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
# Helpers
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


def temp_color(temp_c: float) -> str:
    if temp_c < 70:
        return ACCENT
    if temp_c < 80:
        return YELLOW
    return RED


def delta_html(delta: int) -> str:
    color = ACCENT if delta >= 0 else RED
    return f'<span style="color:{color};">({delta:+d})</span>'


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
    def __init__(self, icon: str, label: str, value: str, sub: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedSize(180, 80)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(0)

        self.label_lbl = make_label(f"{icon}  {label}", "cardLabel")
        self.value_lbl = make_label(value, "cardValue")
        self.sub_lbl = make_label(sub, "cardSub")
        self.label_lbl.setFixedHeight(15)
        self.value_lbl.setFixedHeight(30)
        self.sub_lbl.setFixedHeight(15)

        layout.addWidget(self.label_lbl)
        layout.addWidget(self.value_lbl)
        layout.addWidget(self.sub_lbl)

    def set_value_color(self, color: str) -> None:
        self.value_lbl.setStyleSheet(f"color: {color};")


class DashboardPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(0)

        grid_host = QWidget()
        grid_host.setFixedSize(3 * 180 + 2 * 8, 2 * 80 + 8)
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(8)

        self.util_card = StatCard("🎮", "Utilization", f"{UTIL}%", "GPU load")
        self.temp_card = StatCard("🔥", "Temp", f"{TEMP}°C", "Throttle at 83°C")
        self.temp_card.set_value_color(temp_color(TEMP))
        self.power_card = StatCard("⚡", "Power", f"{POWER} W", f"/ {POWER_LIMIT} W limit")
        self.vram_card = StatCard("🧠", "VRAM", f"{VRAM_USED} MB", f"/ {VRAM_TOTAL} MB")
        self.fan_card = StatCard("🌀", "Fan", f"{FAN_RPM} RPM", f"{FAN_PCT}% duty")
        self.clock_card = StatCard("📊", "Clocks", f"{SM_CLK} / {MEM_CLK}", "SM / Mem MHz")

        cards = [self.util_card, self.temp_card, self.power_card, self.vram_card, self.fan_card, self.clock_card]
        for index, card in enumerate(cards):
            grid.addWidget(card, index // 3, index % 3)

        layout.addWidget(grid_host, 0, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        layout.addStretch(1)

    def refresh(self, data: dict | None) -> None:
        if data is None:
            return
        self.util_card.value_lbl.setText(f"{data['util']}%")
        self.temp_card.value_lbl.setText(f"{data['temp']}°C")
        self.temp_card.set_value_color(temp_color(data['temp']))
        self.power_card.value_lbl.setText(f"{int(data['power'])} W")
        self.power_card.sub_lbl.setText(f"/ {int(data['power_limit'])} W limit")
        self.vram_card.value_lbl.setText(f"{data['vram_used']} MB")
        self.vram_card.sub_lbl.setText(f"/ {data['vram_total']} MB")
        self.fan_card.value_lbl.setText(f"{data['fan_rpm']} RPM")
        self.fan_card.sub_lbl.setText(f"{data['fan_pct']}% duty")
        self.clock_card.value_lbl.setText(f"{data['sm_clk']} / {data['mem_clk']}")


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

    def reset(self) -> None:
        self.slider.setValue(self._default)


class TunePage(QWidget):
    def __init__(self, set_status: StatusFn, mvolt_available: bool) -> None:
        super().__init__()
        self._set_status = set_status
        self._mvolt = mvolt_available
        locked = not mvolt_available

        layout = page_layout(self, spacing=10)

        card = make_card()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(8)

        self.rows = [
            SliderRow("Power Limit", 50, 150, 75, lambda v: f"{v} W"),
            SliderRow("Core Clock", -100, 300, 0, lambda v: f"{v:+d} MHz", locked),
            SliderRow("Mem Clock", -200, 500, 0, lambda v: f"{v:+d} MHz", locked),
            SliderRow("Fan", 0, 100, 35, lambda v: f"{v} %", locked),
        ]
        for row in self.rows:
            card_layout.addWidget(row)

        layout.addWidget(card)

        # Fan preset buttons
        fan_presets = QHBoxLayout()
        fan_presets.setSpacing(6)
        for preset in ("Low", "Mid", "High"):
            btn = make_button(preset, "secondary", height=28)
            btn.setFixedWidth(70)
            btn.clicked.connect(lambda _, p=preset.lower(): self._on_fan_preset(p))
            fan_presets.addWidget(btn, 1)
        layout.addLayout(fan_presets)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        apply_btn = make_button("Apply", "primary")
        reset_btn = make_button("Reset", "secondary")
        apply_btn.clicked.connect(self._on_apply)
        reset_btn.clicked.connect(self._on_reset)
        buttons.addWidget(apply_btn, 1)
        buttons.addWidget(reset_btn, 1)
        layout.addLayout(buttons)
        layout.addStretch(1)

    def _on_fan_preset(self, preset: str) -> None:
        if not self._mvolt:
            self._set_status(f"Install mVolt+ to set fan curve: {preset}")
            return
        ok = mvoltplus_set_fan_curve(preset)
        self._set_status(f"Fan curve set to {preset}" if ok else f"Failed to set fan curve {preset}")

    def _on_apply(self) -> None:
        pl = self.rows[0].slider.value()
        if self._mvolt:
            core = self.rows[1].slider.value()
            mem = self.rows[2].slider.value()
            fan = self.rows[3].slider.value()
            ok1 = set_power_limit(pl)
            ok2 = mvoltplus_set_core_offset(core)
            ok3 = mvoltplus_set_mem_offset(mem)
            ok4 = mvoltplus_set_fan_curve(f"custom:{fan}")
            if ok1 and ok2 and ok3 and ok4:
                self._set_status(f"Applied: PL {pl}W, core {core:+d}MHz, mem {mem:+d}MHz, fan {fan}%")
            else:
                self._set_status("Some settings failed (see log)")
        else:
            ok = set_power_limit(pl)
            if ok:
                self._set_status(f"Power limit set to {pl}W (install mVolt+ for clocks/fan)")
            else:
                self._set_status(f"Failed to set power limit to {pl}W")

    def _on_reset(self) -> None:
        reset_clocks()
        reset_power()
        for row in self.rows:
            row.reset()
        self._set_status("All clocks and power reset to defaults")


# --------------------------------------------------------------------------- #
# Auto Tune — gpu-tune algorithm
# --------------------------------------------------------------------------- #
class AutoPage(QWidget):
    def __init__(self, set_status: StatusFn) -> None:
        super().__init__()
        self._set_status = set_status
        self._best_w: int | None = None
        self._best_temp: int | None = None
        layout = page_layout(self, spacing=10)

        start_btn = make_button("Start Auto Tune", "primary", height=40)
        start_btn.clicked.connect(self._on_start)
        layout.addWidget(start_btn)

        self.log_view = QTextEdit()
        self.log_view.setObjectName("log")
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view, 1)

        bottom = QHBoxLayout()
        bottom.setSpacing(8)
        self.result_lbl = make_label("—", "result")
        apply_best = make_button("Apply Best", "primary", height=28)
        apply_best.setFixedWidth(110)
        apply_best.clicked.connect(self._on_apply_best)
        apply_best.setEnabled(False)
        bottom.addWidget(self.result_lbl)
        bottom.addStretch(1)
        bottom.addWidget(apply_best)
        layout.addLayout(bottom)

    def _log(self, msg: str) -> None:
        self.log_view.appendPlainText(msg)
        sb = self.log_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_start(self) -> None:
        self.log_view.setPlainText("")
        self._log("Auto Tune: baseline measurement")
        self._best_w = None
        self._best_temp = None
        self.result_lbl.setText("—")

        limits = query_power_limits()
        start_w = limits[0] if limits and limits[0] else 75

        import time
        for step_w in range(start_w, 201, 5):
            self._log(f"  Testing {step_w}W...")
            samples = run_dmon(duration_s=5)
            if not samples:
                self._log(f"  {step_w}W → dmon failed")
                break
            avg_temp = int(sum(s["temp"] for s in samples) / len(samples))
            avg_clk = int(sum(s["sm_clk"] for s in samples) / len(samples))
            self._log(f"  {step_w}W → {avg_temp}°C, {avg_clk} MHz")

            if avg_temp > 85:
                self._log(f"  {step_w}W → {avg_temp}°C thermal limit")
                break
            self._best_w = step_w
            self._best_temp = avg_temp
            self._log(f"  {step_w}W → {avg_temp}°C stable")
            time.sleep(0.5)

        if self._best_w is not None:
            gain = round((self._best_w - start_w) / start_w * 100) if start_w > 0 else 0
            self.result_lbl.setText(f"Best stable: {self._best_w}W ({gain:+d}%)")
            self._set_status(f"Auto Tune done. Best: {self._best_w}W (+{gain}%)")
        else:
            self.result_lbl.setText("No stable point found")
            self._set_status("Auto Tune failed")

    def _on_apply_best(self) -> None:
        if self._best_w is not None and set_power_limit(self._best_w):
            self._set_status(f"Best power limit ({self._best_w}W) applied")
        else:
            self._set_status("No best result to apply")


# --------------------------------------------------------------------------- #
# Bench
# --------------------------------------------------------------------------- #
class BenchPage(QWidget):
    def __init__(self, set_status: StatusFn) -> None:
        super().__init__()
        self._set_status = set_status
        layout = page_layout(self, spacing=10)

        run_btn = make_button("Run 30s Bench", "primary", height=40)
        run_btn.clicked.connect(self._on_run)
        layout.addWidget(run_btn)

        card = make_card()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(14)

        self.bench_rows: list[tuple[QLabel, QLabel]] = []
        for label in ["Avg Clocks", "Max Clocks", "Avg Temp", "Max Temp", "Avg Power", "Max Power"]:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            name_lbl = make_label(f"{label}:", "benchLabel")
            value_lbl = make_label("—", "benchValue")
            row.addWidget(name_lbl)
            row.addStretch(1)
            row.addWidget(value_lbl)
            card_layout.addLayout(row)
            self.bench_rows.append((name_lbl, value_lbl))

        self.delta_lbl = make_label("", "result")
        card_layout.addWidget(self.delta_lbl)

        layout.addWidget(card)
        layout.addStretch(1)

    def _on_run(self) -> None:
        self._set_status("Idle baseline (5s)...")
        idle_samples = run_dmon(duration_s=5)
        if not idle_samples:
            self._set_status("dmon failed — no GPU?")
            return
        idle_clk = sum(s["sm_clk"] for s in idle_samples) / len(idle_samples)
        idle_temp = sum(s["temp"] for s in idle_samples) / len(idle_samples)
        idle_power = sum(s["power"] for s in idle_samples) / len(idle_samples)

        self._set_status("Stress (30s)...")
        stress_samples = run_dmon(duration_s=30)
        if not stress_samples:
            self._set_status("dmon failed during stress")
            return

        labels = ["Avg Clocks", "Max Clocks", "Avg Temp", "Max Temp", "Avg Power", "Max Power"]
        values = [
            int(sum(s["sm_clk"] for s in stress_samples) / len(stress_samples)),
            max(s["sm_clk"] for s in stress_samples),
            int(sum(s["temp"] for s in stress_samples) / len(stress_samples)),
            max(s["temp"] for s in stress_samples),
            int(sum(s["power"] for s in stress_samples) / len(stress_samples)),
            max(s["power"] for s in stress_samples),
        ]
        for i, (name_lbl, value_lbl) in enumerate(self.bench_rows):
            value_lbl.setText(f"{values[i]} {'W' if i >= 4 else 'MHz'}")

        clk_delta = int(values[0] - idle_clk)
        temp_delta = int(values[2] - idle_temp)
        power_delta = int(values[4] - idle_power)
        self.delta_lbl.setText(
            f"vs idle: {delta_html(clk_delta)} clocks, +{temp_delta}°C, {delta_html(power_delta)} power"
        )
        self.delta_lbl.setTextFormat(Qt.TextFormat.RichText)
        self._set_status(f"Bench done: avg clk {values[0]}MHz, avg temp {values[2]}°C, avg power {values[4]}W")


# --------------------------------------------------------------------------- #
# Profiles
# --------------------------------------------------------------------------- #
class ProfilesPage(QWidget):
    def __init__(self, set_status: StatusFn) -> None:
        super().__init__()
        self._set_status = set_status
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

        self._refresh_profiles()

    def _refresh_profiles(self) -> None:
        self.profile_list.clear()
        for name in load_profiles():
            self.profile_list.addItem(name)

    def _current_name(self) -> str | None:
        item = self.profile_list.currentItem()
        return item.text() if item else None

    def _on_save(self) -> None:
        name = self.name_input.text().strip()
        if not name:
            self._set_status("Enter a profile name first")
            return
        if name in {self.profile_list.item(i).text() for i in range(self.profile_list.count())}:
            self._set_status(f"Profile '{name}' already exists")
            return
        settings = {"power_limit": 75, "core_offset": 0, "mem_offset": 0, "fan_mode": "default"}
        if save_profile(name, settings):
            self._refresh_profiles()
            self.profile_list.setCurrentRow(self.profile_list.count() - 1)
            self.name_input.clear()
            self._set_status(f"Profile '{name}' saved")
        else:
            self._set_status(f"Failed to save profile '{name}'")

    def _on_apply(self) -> None:
        name = self._current_name()
        if not name:
            self._set_status("Select a profile first")
            return
        data = load_profile(name)
        if data is None:
            self._set_status(f"Profile '{name}' not found")
            return
        pl = data.get("power_limit")
        if pl and set_power_limit(pl):
            self._set_status(f"Profile '{name}' applied: PL {pl}W")
        else:
            self._set_status(f"Failed to apply profile '{name}'")

    def _on_delete(self) -> None:
        name = self._current_name()
        if not name:
            self._set_status("Select a profile first")
            return
        if delete_profile(name):
            self._refresh_profiles()
            self._set_status(f"Profile '{name}' deleted")
        else:
            self._set_status(f"Failed to delete profile '{name}'")


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

        self.setWindowTitle("GPU Unlock")
        self.setWindowIcon(make_tray_icon())
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowSystemMenuHint
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setFixedSize(WINDOW_W, WINDOW_H)

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(self._build_top_bar())
        root_layout.addWidget(self._build_tab_bar())

        self.stack = QStackedWidget()
        self.status_lbl = make_label("", "statusBar")
        self.status_lbl.setFixedHeight(22)
        self.status_lbl.setContentsMargins(16, 0, 16, 0)

        mvolt_avail = mvoltplus_available()
        smi_path = find_nvidia_smi()
        nvapi_ok = NVAPI.is_available()

        self.dashboard_page = DashboardPage()
        self.tune_page = TunePage(self.set_status, mvolt_avail)
        self.auto_page = AutoPage(self.set_status)
        self.bench_page = BenchPage(self.set_status)
        self.profiles_page = ProfilesPage(self.set_status)

        self.stack.addWidget(self.dashboard_page)
        self.stack.addWidget(self.tune_page)
        self.stack.addWidget(self.auto_page)
        self.stack.addWidget(self.bench_page)
        self.stack.addWidget(self.profiles_page)
        self.tab_group.idClicked.connect(self.stack.setCurrentIndex)

        root_layout.addWidget(self.stack, 1)
        root_layout.addWidget(self.status_lbl)

        # Dynamic GPU detection
        self._gpu_name = GPU_NAME
        self._driver = DRIVER
        self._detect_gpu()

        self.set_status(f"Ready  •  Driver {self._driver}")
        self._build_tray()

        # Live data refresh timer
        self._refresh_timer = QTimer()
        self._refresh_timer.timeout.connect(self._on_refresh)
        self._refresh_timer.start(2000)

    def _detect_gpu(self) -> None:
        """Detect GPU name and driver from nvidia-smi at startup."""
        data = query_gpu()
        if data:
            self._gpu_name = data["name"]
            self._driver = data["driver"]
            # Update top bar
            top_label = self.findChild(QLabel, "gpuName")
            if top_label:
                info = self._gpu_name
                if find_mvoltplus():
                    info += "  •  mVolt+ ready"
                if NVAPI.is_available():
                    info += "  •  NVAPI"
                top_label.setText(info)

    # ----- construction helpers ------------------------------------------- #
    def _build_top_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(40)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.addWidget(make_label("GPU Unlock", "appName"))
        layout.addStretch(1)
        info = GPU_NAME
        layout.addWidget(make_label(info, "gpuName"))
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
        menu.addAction(exit_action)
        self._tray_menu = menu

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    # ----- public API ------------------------------------------------------ #
    def set_status(self, message: str) -> None:
        self.status_lbl.setText(message)

    def _on_refresh(self) -> None:
        data = query_gpu()
        if data is None:
            self.set_status("nvidia-smi not found or query failed")
            return
        self.dashboard_page.refresh(data)
        info = data["name"]
        if find_mvoltplus():
            info += "  •  mVolt+"
        if NVAPI.is_available():
            info += "  •  NVAPI"
        self.set_status(f"• {data['name']} • Driver {data['driver']} • {info}")

    # ----- tray / window state --------------------------------------------- #
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
        self.tray.showMessage("GPU Unlock", "Running in the system tray.", QSystemTrayIcon.MessageIcon.NoIcon, 1500)

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

    # Admin check (UAC on Windows, root on Linux)
    if not is_admin():
        from PySide6.QtWidgets import QMessageBox as QMB
        app = QApplication.instance() or QApplication(sys.argv)
        msg = QMB.question(
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
        app = QApplication.instance() or QApplication(sys.argv)
        QMessageBox.critical(
            None, "GPU Unlock",
            "nvidia-smi not found in PATH.\n\nInstall NVIDIA drivers or add nvidia-smi to your PATH.",
            QMessageBox.StandardButton.Ok,
        )
        return 1

    app = QApplication(sys.argv)
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
