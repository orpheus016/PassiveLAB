"""Tests for the interactive S-parameter plot (``simulate --plot``). Needs the ``viz`` extra
(plotly) -- ``pytest.importorskip``-guarded, same convention as ``test_plugin.py``'s openEMS gate,
so default CI (no ``viz`` extra) stays green."""
from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("plotly")

from passivelab.characterization.openems.ports import PortDef  # noqa: E402
from passivelab.characterization.openems.sparams import sparams_to_metrics  # noqa: E402
from passivelab.characterization.openems.viz import plot_sparams_interactive  # noqa: E402
from passivelab.characterization.openems.vendor.modules import util_utilities  # noqa: E402

_PORT_DEFS = [
    PortDef(portnumber=1, source_layernum=201, from_layername="Metal4", to_layername="TopMetal2"),
    PortDef(portnumber=2, source_layernum=202, from_layername="Metal4", to_layername="Metal5"),
]


def _write_synthetic_s2p(tmp_path):
    f = np.linspace(0, 100e9, 101)  # matches GOLDEN_TRAINING_N_FREQ so it decimates onto itself
    smatrix = np.zeros((2, 2, 101), dtype=complex)
    for i in range(2):
        for j in range(2):
            smatrix[i, j] = (i + 1) * 0.1 + 1j * (j + 1) * 0.01
    path = tmp_path / "synthetic.s2p"
    util_utilities.write_snp(smatrix, f, str(path))
    return path


def test_plot_sparams_interactive_writes_a_self_contained_html_file(tmp_path):
    s3p_path = _write_synthetic_s2p(tmp_path)
    metrics = sparams_to_metrics(s3p_path, _PORT_DEFS)

    out_path = plot_sparams_interactive(metrics, tmp_path / "plot" / "sparams.html")

    assert out_path.exists()
    html = out_path.read_text(encoding="utf-8")
    assert "<html" in html.lower()
    assert "plotly" in html.lower()
    # every S_ij trace label present, response-then-source per sparams.py's documented convention
    for label in ("S11", "S12", "S21", "S22"):
        assert label in html
