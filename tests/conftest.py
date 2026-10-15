import pytest

from tests.qa_report import clock, describe, write

_rows: dict[str, dict] = {}
_labels: dict[str, tuple[str, str]] = {}


def _detail(report) -> str:
    if report.passed or report.skipped or not report.longrepr:
        return ""
    crash = getattr(report.longrepr, "reprcrash", None)
    if crash is not None and crash.message:
        return crash.message.split("Call log:")[0].strip().splitlines()[0][:240]
    text = str(report.longrepr).split("Call log:")[0]
    line = next((item.strip() for item in reversed(text.splitlines()) if item.strip()), "")
    return line[:240]


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    _labels[item.nodeid] = describe(item)
    yield


def pytest_runtest_logreport(report):
    if report.nodeid not in _labels:
        return
    if report.when == "teardown":
        if report.failed and report.nodeid in _rows:
            _rows[report.nodeid].update(result="Fail", detail=_detail(report))
        return
    if report.when == "setup" and report.passed:
        return
    check, area = _labels[report.nodeid]
    if report.passed:
        result = "Pass"
    elif report.skipped:
        result = "Skipped"
    else:
        result = "Fail"
    _rows[report.nodeid] = {
        "check": check,
        "area": area,
        "result": result,
        "seconds": report.duration,
        "time": clock(report.duration),
        "detail": _detail(report),
    }


def pytest_sessionfinish(session, exitstatus):
    if _rows:
        write(list(_rows.values()))


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {
        **browser_context_args,
        "timezone_id": "Asia/Dubai",
    }
