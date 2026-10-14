import pytest

from tests.qa_report import clock, label_for, write

_rows = []


def _detail(report) -> str:
    if report.passed or report.skipped or not report.longrepr:
        return ""
    text = str(report.longrepr).split("Call log:")[0]
    line = next((item.strip() for item in reversed(text.splitlines()) if item.strip()), "")
    return line[:240]


def pytest_runtest_logreport(report):
    if report.when == "teardown" or (report.when == "setup" and report.passed):
        return
    if "test_browser.py" not in report.nodeid:
        return
    check, page = label_for(report.nodeid)
    if report.passed:
        result = "Pass"
    elif report.skipped:
        result = "Skipped"
    else:
        result = "Fail"
    _rows.append({
        "check": check,
        "page": page,
        "result": result,
        "seconds": report.duration,
        "time": clock(report.duration),
        "detail": _detail(report),
    })


def pytest_sessionfinish(session, exitstatus):
    if _rows:
        write(_rows)


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {
        **browser_context_args,
        "timezone_id": "Asia/Dubai",
    }
