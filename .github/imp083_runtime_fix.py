from pathlib import Path

core_path = Path("src/doll/lite_measurement.py")
core = core_path.read_text(encoding="utf-8")
old = '''    try:
        import resource

        usage = resource.getrusage(resource.RUSAGE_SELF)
        raw_peak = int(usage.ru_maxrss)
    except (ImportError, OSError, ValueError):
        return ProcessRssSnapshot(
            source="unavailable",
            current_bytes=None,
            peak_bytes=None,
        )
    if raw_peak < 0:
        raise LiteClientMeasurementError("Lite measurement peak RSS is invalid")
    peak_bytes = raw_peak if sys.platform == "darwin" else raw_peak * 1024
    current_bytes = _linux_current_rss_bytes() if sys.platform.startswith("linux") else None
    return ProcessRssSnapshot(
        source="resource-ru_maxrss",
        current_bytes=current_bytes,
        peak_bytes=peak_bytes,
    )
'''
new = '''    current_bytes = _linux_current_rss_bytes() if sys.platform.startswith("linux") else None
    try:
        import resource

        usage = resource.getrusage(resource.RUSAGE_SELF)
        raw_peak = int(usage.ru_maxrss)
    except (ImportError, OSError, ValueError):
        return ProcessRssSnapshot(
            source="unavailable",
            current_bytes=None,
            peak_bytes=None,
        )
    if raw_peak < 0:
        raise LiteClientMeasurementError("Lite measurement peak RSS is invalid")
    peak_bytes = raw_peak if sys.platform == "darwin" else raw_peak * 1024
    if current_bytes is not None:
        peak_bytes = max(peak_bytes, current_bytes)
    return ProcessRssSnapshot(
        source="resource-ru_maxrss",
        current_bytes=current_bytes,
        peak_bytes=peak_bytes,
    )
'''
if core.count(old) != 1:
    raise SystemExit(f"RSS snapshot marker count={core.count(old)}")
core_path.write_text(core.replace(old, new, 1), encoding="utf-8")

test_path = Path("tests/test_imp_083_lite_client_measurement.py")
test = test_path.read_text(encoding="utf-8")
old_test = "    values = iter((10, 9))\n"
new_test = "    values = iter((10, 9, 8))\n"
if test.count(old_test) != 1:
    raise SystemExit(f"clock fixture marker count={test.count(old_test)}")
test_path.write_text(test.replace(old_test, new_test, 1), encoding="utf-8")
