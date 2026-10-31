"""Tests for profile save/load and GPU detection fallback logic."""
import json, os, sys, tempfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent))
import gpuui


# --- Profile save/load --- #
def test_profile_save_load_roundtrip(tmp_path):
    with mock.patch.object(gpuui, "PROFILES_DIR", tmp_path):
        settings = {"power_limit": 120, "core_offset": 100, "mem_offset": 200, "fan_pct": 70}
        assert gpuui.save_profile("gaming", settings)
        data = gpuui.load_profile("gaming")
        assert data == settings


def test_profile_load_missing(tmp_path):
    with mock.patch.object(gpuui, "PROFILES_DIR", tmp_path):
        assert gpuui.load_profile("nonexistent") is None


def test_profile_delete(tmp_path):
    with mock.patch.object(gpuui, "PROFILES_DIR", tmp_path):
        gpuui.save_profile("test", {"power_limit": 100})
        assert gpuui.delete_profile("test")
        assert gpuui.load_profile("test") is None


def test_load_profiles_sorted(tmp_path):
    with mock.patch.object(gpuui, "PROFILES_DIR", tmp_path):
        gpuui.save_profile("zebra", {})
        gpuui.save_profile("alpha", {})
        names = gpuui.load_profiles()
        assert names == ["alpha", "zebra"]


# --- GPU detection fallback --- #
def test_detect_gpu_vendor_nvidia():
    with mock.patch("gpuui.shutil") as m:
        m.which.return_value = "/usr/bin/nvidia-smi"
        assert gpuui.detect_gpu_vendor() == "nvidia"


def test_detect_gpu_vendor_amd():
    with mock.patch("gpuui.shutil") as m:
        m.which.side_effect = lambda x: "/usr/bin/" + x if x == "rocm-smi" else None
        assert gpuui.detect_gpu_vendor() == "amd"


def test_detect_gpu_vendor_none():
    with mock.patch("gpuui.shutil") as m:
        m.which.return_value = None
        assert gpuui.detect_gpu_vendor() is None


# --- nvidia-smi parsing --- #
def test_query_gpu_parses_output():
    sample = "NVIDIA GeForce GTX 1650, 621.01, 7, 1690, 4096, 50.20, 22.15, 120.00, 26, 1410, 6201"
    with mock.patch.object(gpuui, "_run_smi") as m:
        m.return_value = mock.Mock(stdout=sample, returncode=0)
        stats = gpuui.query_gpu()
        assert stats is not None
        assert stats.util == 7
        assert stats.temp == 50
        assert stats.power == 22.15
        assert stats.sm_clock == 1410
        assert stats.mem_clock == 6201


def test_query_gpu_none_when_smi_missing():
    with mock.patch.object(gpuui, "_run_smi", return_value=None):
        assert gpuui.query_gpu() is None


def test_query_supported_clocks_parsing():
    output = """
    Graphics : 2205 MHz
    Memory   : 6001 MHz
    """
    with mock.patch.object(gpuui, "_run_smi") as m:
        m.return_value = mock.Mock(stdout=output, returncode=0)
        clocks = gpuui.query_supported_clocks()
        assert clocks is not None
        assert clocks.max_graphics == 2205
        assert clocks.max_memory == 6001


def test_query_supported_clocks_none_when_smi_missing():
    with mock.patch.object(gpuui, "_run_smi", return_value=None):
        assert gpuui.query_supported_clocks() is None


# --- Temperature thresholds --- #
def test_temp_color_warm():
    assert gpuui.temp_color(50) == gpuui.ACCENT


def test_temp_color_hot():
    assert gpuui.temp_color(75) == gpuui.YELLOW


def test_temp_color_critical():
    assert gpuui.temp_color(85) == gpuui.RED


def test_temp_lock_guard_below_threshold():
    # Lock should be allowed when temp < TEMP_LOCK_MAX_C
    assert gpuui.TEMP_LOCK_MAX_C == 75
    assert 70 < gpuui.TEMP_LOCK_MAX_C  # below threshold


def test_temp_lock_guard_above_threshold():
    # Lock should be blocked when temp >= TEMP_LOCK_MAX_C
    assert 80 >= gpuui.TEMP_LOCK_MAX_C  # above threshold
