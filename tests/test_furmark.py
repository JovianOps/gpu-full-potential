"""Tests for FurMark stress integration and workload detection."""
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent))
import gpuui


# --- FurMark path detection --- #
def test_find_furmark_returns_none_when_not_installed():
    """When FurMark is neither on PATH nor in .external/furmark/, find_furmark returns None."""
    fake_dir = Path("/nonexistent/furmark")
    with (
        mock.patch.object(gpuui, "FURMARK_DIR", fake_dir),
        mock.patch("gpuui.shutil.which", return_value=None),
    ):
        assert gpuui.find_furmark() is None


def test_find_furmark_checks_path_first():
    """When FurMark is on PATH, it should return the PATH result."""
    with mock.patch("gpuui.shutil.which", return_value="/usr/local/bin/FurMark"):
        result = gpuui.find_furmark()
        assert result == "/usr/local/bin/FurMark"


# --- run_dmon with stress parameter --- #
def _mock_popen_empty():
    """Return a mock Popen that yields no output lines."""
    proc = mock.Mock()
    proc.stdout = iter([])
    proc.returncode = 0
    return proc


def test_run_dmon_without_stress_does_not_call_furmark():
    """run_dmon with stress_ms=0 should not call furmark_stress."""
    with (
        mock.patch.object(gpuui, "furmark_stress") as mock_stress,
        mock.patch.object(gpuui, "furmark_available", return_value=True),
        mock.patch.object(gpuui, "find_nvidia_smi", return_value="/fake/smi"),
        mock.patch("gpuui.subprocess.Popen", return_value=_mock_popen_empty()),
    ):
        gpuui.run_dmon(duration_s=1)
        mock_stress.assert_not_called()


def test_run_dmon_with_stress_calls_furmark():
    """run_dmon with stress_ms > 0 should call furmark_stress."""
    with (
        mock.patch.object(gpuui, "furmark_available", return_value=True),
        mock.patch.object(gpuui, "furmark_stress", return_value=None) as mock_stress,
        mock.patch.object(gpuui, "find_nvidia_smi", return_value="/fake/smi"),
        mock.patch("gpuui.subprocess.Popen", return_value=_mock_popen_empty()),
    ):
        gpuui.run_dmon(duration_s=1, stress_ms=5000)
        mock_stress.assert_called_once_with(duration_ms=5000)


def test_run_dmon_no_furmark_falls_back_to_idle():
    """run_dmon with stress_ms > 0 but no FurMark should not crash."""
    with (
        mock.patch.object(gpuui, "furmark_available", return_value=False),
        mock.patch.object(gpuui, "furmark_stress") as mock_stress,
        mock.patch.object(gpuui, "find_nvidia_smi", return_value="/fake/smi"),
        mock.patch("gpuui.subprocess.Popen", return_value=_mock_popen_empty()),
    ):
        samples = gpuui.run_dmon(duration_s=1, stress_ms=5000)
        mock_stress.assert_not_called()
        assert samples == []

