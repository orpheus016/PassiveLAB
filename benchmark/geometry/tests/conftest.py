"""Session-scoped collector for the cross-device validity+performance report (1.3.3): each test
in this directory appends one result dict to the `report_collector` fixture's list; once every
test using it has finished (session teardown), the accumulated list is written to report.json.
Skipped if nothing was collected, so an unrelated/filtered pytest run doesn't overwrite a real
report with an empty one.
"""
from __future__ import annotations

import datetime
import json
import pathlib

import pytest

REPORT_PATH = pathlib.Path(__file__).parent / "report.json"


@pytest.fixture(scope="session")
def report_collector():
    results: list[dict] = []
    yield results
    if not results:
        return
    REPORT_PATH.write_text(json.dumps({
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "cases": results,
    }, indent=2), encoding="utf-8")
    print(f"\n[report] wrote {len(results)} case(s) to {REPORT_PATH}")
