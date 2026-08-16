"""Tests for ``OpenEMSConfig``/``load_openems_config`` (sub-phase 1.4.1). No openEMS/CSXCAD
needed -- pure dataclass + JSON, runs in every CI build."""
from __future__ import annotations

import json

import pytest

from passivelab.characterization.openems.config import (
    DEFAULT_BOUNDARY_CONDITIONS,
    OpenEMSConfig,
    load_openems_config,
)


def test_defaults_match_the_golden_reference_hardcoded_constants():
    config = OpenEMSConfig(xml_path="SG13G2.xml")
    assert config.solver == "openems"
    assert config.freq_start == 0
    assert config.freq_stop == 100e9
    assert config.numfreq == 1001
    assert config.boundary_conditions == DEFAULT_BOUNDARY_CONDITIONS == ("PEC",) * 6
    assert config.margin == 200
    assert config.refined_cellsize == 1.0
    assert config.cells_per_wavelength == 20
    assert config.energy_limit_db == -50
    assert config.merge_polygon_size == 1.5
    assert config.preprocess_gds is True
    # 1.4.3: silence was the bug this sub-phase fixes -- non-silent is the default, not opt-in.
    assert config.install_path is None
    assert config.verbose == 3
    assert config.dump_statistics is True


def test_no_gpu_field():
    # openEMS has no supported GPU/CUDA path (confirmed during 1.4.1 planning) -- a reserved-but-
    # inert flag would be dead weight; a future GPU-capable solver carries its own field on its
    # own config schema instead.
    assert not hasattr(OpenEMSConfig(xml_path="x"), "gpu")


def test_load_openems_config_overrides_defaults(tmp_path):
    path = tmp_path / "openems.config.json"
    path.write_text(json.dumps({
        "solver": "openems",
        "xml_path": "custom_stackup.xml",
        "num_cpus": 32,
        "boundary_conditions": ["MUR", "MUR", "PEC", "PEC", "PEC", "PEC"],
        "install_path": "C:/opt/openEMS/openEMS",
        "verbose": 1,
        "dump_statistics": False,
    }), encoding="utf-8")

    config = load_openems_config(path)

    assert config.xml_path == "custom_stackup.xml"
    assert config.num_cpus == 32
    assert config.boundary_conditions == ("MUR", "MUR", "PEC", "PEC", "PEC", "PEC")
    assert config.install_path == "C:/opt/openEMS/openEMS"
    assert config.verbose == 1
    assert config.dump_statistics is False
    assert config.numfreq == 1001  # untouched fields keep their default


def test_load_openems_config_malformed_field_raises_value_error(tmp_path):
    path = tmp_path / "openems.config.json"
    path.write_text(json.dumps({"xml_path": "x", "not_a_real_field": 1}), encoding="utf-8")

    with pytest.raises(ValueError, match="malformed openems.config.json"):
        load_openems_config(path)


def test_load_openems_config_missing_xml_path_raises_value_error(tmp_path):
    path = tmp_path / "openems.config.json"
    path.write_text(json.dumps({"solver": "openems"}), encoding="utf-8")

    with pytest.raises(ValueError, match="malformed openems.config.json"):
        load_openems_config(path)
