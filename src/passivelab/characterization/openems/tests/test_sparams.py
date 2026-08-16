"""Tests for S-parameter post-processing (sub-phase 1.4.4). Pure ``skrf``/``numpy``, no
openEMS/CSXCAD needed -- runs in every CI build, matching the board task's own framing ("consumes
an already-captured .s3p ... doesn't need a fresh solve")."""
from __future__ import annotations

import json

import numpy as np
import pytest

from passivelab.characterization.openems.ports import PortDef
from passivelab.characterization.openems.sparams import (
    decimate_to_training_grid,
    flatten_training_vector,
    metrics_summary_for_report,
    sparams_to_metrics,
)
from passivelab.characterization.openems.vendor.modules import util_utilities

_PORT_DEFS = [
    PortDef(portnumber=1, source_layernum=201, from_layername="Metal4", to_layername="TopMetal2"),
    PortDef(portnumber=2, source_layernum=202, from_layername="Metal4", to_layername="Metal5"),
    PortDef(portnumber=3, source_layernum=203, from_layername="Metal4", to_layername="Metal5"),
]


def _write_synthetic_s3p(tmp_path, n=3, numfreq=1001):
    """A 3-port .s3p over the golden reference's exact raw grid (0-100 GHz, 1001 points), with
    asymmetric per-(i,j) values -- asymmetric on purpose, so a row/column mixup (transpose) is
    actually detectable, unlike a near-symmetric real reciprocal T-coil response."""
    f = np.linspace(0, 100e9, numfreq)
    smatrix = np.zeros((n, n, numfreq), dtype=complex)
    ramp = np.linspace(0, 1e-3, numfreq)
    for i in range(n):
        for j in range(n):
            smatrix[i, j] = (i + 1) * 0.1 + 1j * (j + 1) * 0.01 + ramp
    path = tmp_path / "synthetic.s3p"
    util_utilities.write_snp(smatrix, f, str(path))
    return path, f, smatrix


def test_sparams_to_metrics_round_trips_the_written_matrix(tmp_path):
    path, f, smatrix = _write_synthetic_s3p(tmp_path)

    metrics = sparams_to_metrics(path, _PORT_DEFS)

    assert metrics.values["port_numbers"] == [1, 2, 3]
    np.testing.assert_allclose(metrics.values["frequency_hz"], f)
    # Convention-regression test (see sparams.py's module docstring): skrf's row axis is the
    # *source* port and column axis the *response* port for this repo's write_snp()+skrf
    # combination -- s_parameters[k] == smatrix[:, :, k].T, not smatrix[:, :, k] directly.
    for k in (0, len(f) // 2, len(f) - 1):
        np.testing.assert_allclose(metrics.values["s_parameters"][k], smatrix[:, :, k].T)


def test_sparams_to_metrics_rejects_port_count_mismatch(tmp_path):
    path, _, _ = _write_synthetic_s3p(tmp_path)

    with pytest.raises(ValueError, match="port count/ordering mismatch"):
        sparams_to_metrics(path, _PORT_DEFS[:2])


def test_training_vector_matches_golden_reference_dimensionality(tmp_path):
    path, _, _ = _write_synthetic_s3p(tmp_path)

    metrics = sparams_to_metrics(path, _PORT_DEFS)

    assert len(metrics.values["training_frequency_hz"]) == 101
    assert len(metrics.values["training_vector"]) == 101 * 3 * 3 * 2  # golden reference: 1818


def test_decimate_to_training_grid_picks_every_tenth_point_for_the_reference_grid():
    f = np.linspace(0, 100e9, 1001)
    s = np.zeros((1001, 1, 1), dtype=complex)
    s[:, 0, 0] = np.arange(1001)  # index-as-value makes the picked indices obvious

    decimated_f, decimated_s = decimate_to_training_grid(f, s, n_freq=101)

    assert len(decimated_f) == 101
    np.testing.assert_allclose(decimated_s[:, 0, 0].real, np.arange(0, 1001, 10))
    assert decimated_f[0] == 0
    assert decimated_f[-1] == 100e9


def test_decimate_to_training_grid_rejects_a_non_evenly_divisible_raw_grid():
    f = np.linspace(0, 100e9, 950)  # (950-1) doesn't divide by (101-1)=100
    s = np.zeros((950, 1, 1), dtype=complex)

    with pytest.raises(ValueError, match="cannot decimate"):
        decimate_to_training_grid(f, s, n_freq=101)


def test_flatten_training_vector_matches_golden_reference_flatten_order():
    # Golden reference's load_sparameters(): per frequency, s[k].flatten() (row-major) then
    # concatenate(real, imag), concatenated across frequencies.
    s = np.array([[[1 + 2j, 3 + 4j], [5 + 6j, 7 + 8j]]])  # shape (1, 2, 2)

    vector = flatten_training_vector(s)

    np.testing.assert_allclose(vector, [1, 3, 5, 7, 2, 4, 6, 8])


def test_metrics_summary_for_report_is_json_serializable_and_excludes_the_full_matrix(tmp_path):
    path, _, _ = _write_synthetic_s3p(tmp_path)
    metrics = sparams_to_metrics(path, _PORT_DEFS)

    summary = metrics_summary_for_report(metrics)
    json.loads(json.dumps(summary))  # must not raise

    assert "s_parameters" not in summary
    assert "frequency_hz" not in summary
    assert summary["port_numbers"] == [1, 2, 3]
    assert len(summary["training_vector"]) == 1818
