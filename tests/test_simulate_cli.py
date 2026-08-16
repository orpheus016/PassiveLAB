"""Tests for the `passivelab simulate` CLI (sub-phase 1.4.9): spec.json + solver-config.json ->
characterize -> S-parameters + report.json.

Uses a stub `SimulationBackend` registered under a throwaway solver name -- proves
`simulate_command()`'s dispatch/report-writing logic is solver-agnostic without needing openEMS
installed (mirrors `core/tests/test_characterization_registry.py`'s stub pattern, one layer up).
"""
from __future__ import annotations

import dataclasses
import json
import pathlib

import numpy as np
import pytest

from passivelab.cli import main
from passivelab.characterization.openems.vendor.modules import util_utilities
from passivelab.core.characterization.registry import register
from passivelab.core.geometry.spec_loader import read_spec_json
from passivelab.core.types import SimulationResult
from passivelab.scripts.simulate import simulate_command

EXAMPLE_SPEC = "examples/tcoil.spec.json"

# Real PortDef shapes matching what characterization/openems/ports.py's PortDef._asdict()
# produces -- --plot's _write_characterize_output() reconstructs PortDef(**p) from exactly this
# shape. 3 ports to match the ".s3p" filename below (skrf infers port count from the extension).
_STUB_PORTS = [
    {"portnumber": 1, "source_layernum": 201, "from_layername": "Metal4", "to_layername": "TopMetal2",
     "port_z0": 50.0, "voltage": 1.0, "direction": "z", "reference_plane_offset": 4.0, "de_embedded": False},
    {"portnumber": 2, "source_layernum": 202, "from_layername": "Metal4", "to_layername": "Metal5",
     "port_z0": 50.0, "voltage": 1.0, "direction": "z", "reference_plane_offset": 4.0, "de_embedded": False},
    {"portnumber": 3, "source_layernum": 203, "from_layername": "Metal4", "to_layername": "Metal5",
     "port_z0": 50.0, "voltage": 1.0, "direction": "z", "reference_plane_offset": 4.0, "de_embedded": False},
]


@dataclasses.dataclass
class _StubConfig:
    solver: str = "stub-solver-test"
    fail: bool = False
    write_real_s3p: bool = False


class _StubBackend:
    load_config = staticmethod(lambda path: _StubConfig(**read_spec_json(path)))

    def __init__(self, config, out_dir):
        self.config = config
        self.out_dir = out_dir

    def simulate(self, layout):
        if self.config.fail:
            raise RuntimeError("stub solver failure")
        sample_dir = self.out_dir / "stubsample"
        s3p_path = sample_dir / "result.s3p"
        ports = []
        if self.config.write_real_s3p:
            # --plot needs a real, skrf-readable Touchstone file -- a bare stub path (never
            # written) is enough for the non-plot tests below, but not for this one. 3 ports
            # (matching the .s3p extension skrf infers the port count from) and a grid that
            # decimates evenly onto GOLDEN_TRAINING_N_FREQ (101), same as sparams.py's tests.
            sample_dir.mkdir(parents=True, exist_ok=True)
            f = np.linspace(0, 100e9, 101)
            s = np.full((3, 3, 101), 0.1 + 0.01j, dtype=complex)
            util_utilities.write_snp(s, f, str(s3p_path))
            ports = _STUB_PORTS
        return SimulationResult(backend="stub-solver-test", raw={
            "sample_id": "stubsample", "sim_dir": str(sample_dir),
            "s3p_path": str(s3p_path),
            "ports": ports, "wall_clock_seconds": 0.01,
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


def test_out_dir_is_resolved_to_absolute_before_the_solve(tmp_path, stub_solver_config, monkeypatch):
    # Regression test: scripts/simulate.py used to keep a relative out_dir as-is, so if anything
    # (the vendored solver's own Run(), in the real openEMS path) changed the process's cwd during
    # the solve, this function's own *later* report.json write would land somewhere unexpected --
    # simulated here with a relative out_dir + a cwd change happening mid-solve.
    spec_path = pathlib.Path(EXAMPLE_SPEC).resolve()
    monkeypatch.chdir(tmp_path)
    relative_out = "out_rel"
    report_path = simulate_command(spec_path, stub_solver_config, relative_out)
    assert report_path.is_absolute()
    assert report_path == (tmp_path / relative_out / "simulate" / "tcoil"
                            / "stub-solver-test" / "report.json")


@pytest.fixture
def stub_solver_config_with_real_s3p(tmp_path):
    try:
        register("stub-solver-test", _StubBackend)
    except ValueError:
        pass
    path = tmp_path / "stub.config.json"
    path.write_text(json.dumps({"solver": "stub-solver-test", "write_real_s3p": True}),
                     encoding="utf-8")
    return path


def test_plot_writes_characterize_output_alongside_the_simulate_report(
        tmp_path, stub_solver_config_with_real_s3p):
    pytest.importorskip("plotly")

    report_path = simulate_command(EXAMPLE_SPEC, stub_solver_config_with_real_s3p, tmp_path,
                                    plot=True)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    char_report_path = tmp_path / "characterize" / "tcoil" / "stub-solver-test" / "stubsample" / "report.json"
    assert report["characterize_report_path"] == str(char_report_path)
    assert char_report_path.exists()

    char_report = json.loads(char_report_path.read_text(encoding="utf-8"))
    assert char_report["port_numbers"] == [1, 2, 3]
    assert "s_parameters" in char_report  # full matrix, unlike simulate's own lightweight summary

    plot_path = char_report_path.parent / "sparams.html"
    assert plot_path.exists()
    assert "plotly" in plot_path.read_text(encoding="utf-8").lower()


def test_plot_false_by_default_writes_no_characterize_output(tmp_path, stub_solver_config_with_real_s3p):
    simulate_command(EXAMPLE_SPEC, stub_solver_config_with_real_s3p, tmp_path)
    assert not (tmp_path / "characterize").exists()
