"""Self-check: _on_tune_lock skips locking when GPU is too hot."""
import gpuui


def test_lock_skipped_when_hot() -> None:
    """When GPU temp >= TEMP_LOCK_MAX_C, the lock must be skipped entirely."""
    hot_stats = gpuui.GpuStats(temp=gpuui.TEMP_LOCK_MAX_C, sm_clock=1410)
    calls: list[str] = []

    class FakeMainWindow:
        status_msg: str = ""
        def set_status(self, msg: str) -> None: self.status_msg = msg

    # Wire module-level functions to spies
    orig_query_gpu = gpuui.query_gpu
    orig_lock_g = gpuui.lock_gpu_clocks
    orig_lock_m = gpuui.lock_mem_clocks
    orig_clocks = gpuui.query_supported_clocks

    gpuui.query_gpu = lambda: hot_stats
    gpuui.lock_gpu_clocks = lambda *a, **k: (calls.append("lock_gpu"), True)[1]
    gpuui.lock_mem_clocks = lambda *a, **k: (calls.append("lock_mem"), True)[1]
    gpuui.query_supported_clocks = lambda: (calls.append("query_clocks"), gpuui.SupportedClocks(2205, 6001))[1]

    try:
        mw = FakeMainWindow()
        gpuui.MainWindow._on_tune_lock(mw)  # call unbound method with fake self
        assert calls == [], f"Should not have called any lock functions, got: {calls}"
        assert "too hot" in mw.status_msg, f"Status should warn about heat, got: {mw.status_msg}"
        assert str(gpuui.TEMP_LOCK_MAX_C) in mw.status_msg
        print(f"PASS: lock skipped when hot — status: {mw.status_msg}")
    finally:
        gpuui.query_gpu = orig_query_gpu
        gpuui.lock_gpu_clocks = orig_lock_g
        gpuui.lock_mem_clocks = orig_lock_m
        gpuui.query_supported_clocks = orig_clocks


def test_lock_applied_when_cool() -> None:
    """When GPU temp < TEMP_LOCK_MAX_C, the lock should proceed normally."""
    cool_stats = gpuui.GpuStats(temp=49, sm_clock=1410)
    calls: list[str] = []

    class FakeMainWindow:
        status_msg: str = ""
        def set_status(self, msg: str) -> None: self.status_msg = msg

    orig_query_gpu = gpuui.query_gpu
    orig_lock_g = gpuui.lock_gpu_clocks
    orig_lock_m = gpuui.lock_mem_clocks
    orig_clocks = gpuui.query_supported_clocks

    gpuui.query_gpu = lambda: cool_stats
    gpuui.lock_gpu_clocks = lambda *a, **k: (calls.append("lock_gpu"), True)[1]
    gpuui.lock_mem_clocks = lambda *a, **k: (calls.append("lock_mem"), True)[1]
    gpuui.query_supported_clocks = lambda: (calls.append("query_clocks"), gpuui.SupportedClocks(2205, 6001))[1]

    try:
        mw = FakeMainWindow()
        gpuui.MainWindow._on_tune_lock(mw)
        assert "query_clocks" in calls, "Should query supported clocks when cool"
        assert "lock_gpu" in calls, "Should lock GPU clocks when cool"
        assert "locked" in mw.status_msg.lower(), f"Status should confirm lock, got: {mw.status_msg}"
        print(f"PASS: lock applied when cool — status: {mw.status_msg}")
    finally:
        gpuui.query_gpu = orig_query_gpu
        gpuui.lock_gpu_clocks = orig_lock_g
        gpuui.lock_mem_clocks = orig_lock_m
        gpuui.query_supported_clocks = orig_clocks


def test_lock_applied_when_temp_unknown() -> None:
    """When GPU temp is None (query failed), the lock should still proceed."""
    stats = gpuui.GpuStats(temp=None)
    calls: list[str] = []

    class FakeMainWindow:
        status_msg: str = ""
        def set_status(self, msg: str) -> None: self.status_msg = msg

    orig = (gpuui.query_gpu, gpuui.lock_gpu_clocks, gpuui.lock_mem_clocks, gpuui.query_supported_clocks)
    gpuui.query_gpu = lambda: stats
    gpuui.lock_gpu_clocks = lambda *a, **k: (calls.append("lock_gpu"), True)[1]
    gpuui.lock_mem_clocks = lambda *a, **k: (calls.append("lock_mem"), True)[1]
    gpuui.query_supported_clocks = lambda: (calls.append("query_clocks"), gpuui.SupportedClocks(2205, 6001))[1]

    try:
        mw = FakeMainWindow()
        gpuui.MainWindow._on_tune_lock(mw)
        assert "lock_gpu" in calls, "Should lock when temp is unknown"
        assert "locked" in mw.status_msg.lower(), f"Status should confirm lock, got: {mw.status_msg}"
        print(f"PASS: lock applied when temp unknown — status: {mw.status_msg}")
    finally:
        gpuui.query_gpu, gpuui.lock_gpu_clocks, gpuui.lock_mem_clocks, gpuui.query_supported_clocks = orig


if __name__ == "__main__":
    test_lock_skipped_when_hot()
    test_lock_applied_when_cool()
    test_lock_applied_when_temp_unknown()
    print("\nAll 3 temperature guard tests passed.")
