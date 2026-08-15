"""``OpenEMSBackend`` integration test -- runs the *actual* reference sweep against a known T-coil
geometry, satisfying 1.4.1's own validation text: "the backend runs the reference sweep on a known
T-coil geometry and produces S-parameters." Requires the real ``openEMS``/``CSXCAD`` packages (the
``sim`` extra, ``pip install -e ".[sim]"``) -- a compiled FDTD solver, not part of the default
``.[dev]`` CI gate (mirrors how ``benchmark/`` is excluded from the fast gate: run on demand,
wherever openEMS is actually installed). ``pytest.importorskip`` is the standard mechanism for
this -- no new convention, no ``pytest.ini``/``testpaths`` change needed.
"""
from __future__ import annotations

import pathlib

import pytest

pytest.importorskip("openEMS")
pytest.importorskip("CSXCAD")
pytest.importorskip("gdspy")

import passivelab.geometry.tcoil  # noqa: E402 -- self-registers "tcoil"
from passivelab.characterization.openems.config import OpenEMSConfig  # noqa: E402
from passivelab.characterization.openems.plugin import OpenEMSBackend  # noqa: E402
from passivelab.core import generate  # noqa: E402
from passivelab.geometry.tcoil.spec import TCoilSpec  # noqa: E402

_VENDOR_DIR = pathlib.Path(__file__).resolve().parent.parent / "vendor"


def test_openems_backend_runs_the_reference_sweep_on_a_known_tcoil(tmp_path):
    spec = TCoilSpec(wid=7, gap=12, sizX=150, sizY=120, firY=10, tapseg=4, nseg=10,
                      tapratio=0.5, endratio=0.5, Lext=30, pad_siz=50, includepad=True)
    layout = generate(spec)

    config = OpenEMSConfig(xml_path=str(_VENDOR_DIR / "SG13G2.xml"))
    backend = OpenEMSBackend(config, out_dir=tmp_path)

    result = backend.simulate(layout)

    assert result.backend == "openems"
    assert result.raw["success"] is True
    assert len(result.raw["ports"]) == 3  # this baseline spec is known to exercise the tap

    s3p_path = pathlib.Path(result.raw["s3p_path"])
    assert s3p_path.exists()
    assert s3p_path.read_text(encoding="utf-8").startswith("#")  # Touchstone header

    manifest_path = pathlib.Path(result.raw["sim_dir"]) / "manifest.json"
    assert manifest_path.exists()
