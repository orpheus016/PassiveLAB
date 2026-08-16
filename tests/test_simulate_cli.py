"""Tests for the `passivelab simulate` CLI (sub-phase 1.4.9): spec.json + solver-config.json ->
characterize -> S-parameters + report.json.

Uses a stub `SimulationBackend` registered under a throwaway solver name -- proves
`simulate_command()`'s dispatch/report-writing logic is solver-agnostic without needing openEMS
installed (mirrors `core/tests/test_characterization_registry.py`'s stub pattern, one layer up).
"""
from __future__ import annotations

import dataclasses
import json

import pytest

from passivelab.cli import main
from passivelab.core.characterization.registry import register
from passivelab.core.geometry.spec_loader import read_spec_json
from passivelab.core.types import SimulationResult
from passivelab.scripts.simulate import simulate_command

EXAMPLE_SPEC = "examples/tcoil.spec.json"


@dataclasses.dataclass
class _StubConfig:
    solver: str = "stub-solver-test"
    fail: bool = False


class _StubBackend:
    load_config = staticmethod(lambda path: _StubConfig(**read_spec_json(path)))

    def __init__(self, config, out_dir):
        self.config = config
        self.out_dir = out_dir

    def simulate(self, layout):
        if self.config.fail:
            raise RuntimeError("stub solver failure")
        return SimulationResult(backend="stub-solver-test", raw={
            "sample_id": "stubsample", "sim_dir": str(self.out_dir / "stubsample"),
            "s3p_path": str(self.out_dir / "stubsample" / "result.s3p"),
            "ports": [], "wall_clock_seconds": 0.01,
        })


@pytest.fixture
def stub_solver_config(tmp_path):
    try:
        register("stub-solver-test", _StubBackend)
    except ValueError:
        pass  # already registered by an earlier test in this file
    path = tmp_path / "stub.config.json"
    path.write_text(json.dumps({"solver": "stub-solver-test"}), encoding="utf-8")
    return path


def test_simulate_command_writes_a_report_pointing_at_the_backend_result(tmp_path, stub_solver_config):
    report_path = simulate_command(EXAMPLE_SPEC, stub_solver_config, tmp_path)

    assert report_path.exists()
    assert tmp_path in report_path.parents
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["passive_type"] == "tcoil"
    assert report["solver"] == "stub-solver-test"
    assert report["success"] is True
    assert report["sample_id"] == "stubsample"
    assert report["s3p_path"].endswith("result.s3p")


def test_simulate_command_report_path_is_under_simulate_passive_type_solver(tmp_path, stub_solver_config):
    report_path = simulate_command(EXAMPLE_SPEC, stub_solver_config, tmp_path)
    assert report_path == tmp_path / "simulate" / "tcoil" / "stub-solver-test" / "report.json"


def test_simulate_command_writes_a_failure_report_and_reraises(tmp_path, stub_solver_config):
    stub_solver_config.write_text(json.dumps({"solver": "stub-solver-test", "fail": True}),
                                   encoding="utf-8")

    with pytest.raises(RuntimeError, match="stub solver failure"):
        simulate_command(EXAMPLE_SPEC, stub_solver_config, tmp_path)

    report_path = tmp_path / "simulate" / "tcoil" / "stub-solver-test" / "report.json"
    assert report_path.exists()  # written even on failure, per finally-block design
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["success"] is False
    assert "stub solver failure" in report["error"]


def test_load_solver_config_missing_solver_field_raises(tmp_path):
    path = tmp_path / "bad.config.json"
    path.write_text(json.dumps({"not_solver": "x"}), encoding="utf-8")
    with pytest.raises(ValueError, match="missing required 'solver' field"):
        simulate_command(EXAMPLE_SPEC, path, tmp_path)


def test_main_simulate_exits_zero_and_prints_the_report_path(tmp_path, capsys, stub_solver_config):
    code = main(["simulate", EXAMPLE_SPEC, str(stub_solver_config), "--out-dir", str(tmp_path)])
    assert code == 0
    out = capsys.readouterr().out.strip()
    assert out.endswith("report.json")


def test_main_simulate_reports_unknown_solver_without_a_traceback(tmp_path, capsys):
    path = tmp_path / "unknown.config.json"
    path.write_text(json.dumps({"solver": "not-a-real-solver"}), encoding="utf-8")
    code = main(["simulate", EXAMPLE_SPEC, str(path), "--out-dir", str(tmp_path)])
    assert code == 1
    err = capsys.readouterr().err
    assert err.startswith("error:") and "Traceback" not in err
