"""Tests for the spec.json -> PassiveSpec loader (sub-phase 1.3.3)."""
from __future__ import annotations

import json

import pytest

import passivelab.geometry.tcoil  # noqa: F401 -- self-registers "tcoil"
from passivelab.core import load_spec, spec_from_dict
from passivelab.geometry.tcoil import TCoilSpec

EXAMPLE_SPEC = "examples/tcoil.spec.json"

BASELINE_FIELDS = dict(wid=7, gap=12, sizX=150, sizY=120, firY=10, tapseg=4, nseg=10,
                       tapratio=0.5, endratio=0.5, Lext=30, pad_siz=50, includepad=True)


def test_example_spec_round_trips_to_an_identical_tcoilspec():
    assert load_spec(EXAMPLE_SPEC) == TCoilSpec(**BASELINE_FIELDS)


def test_spec_from_dict_matches_load_spec():
    data = json.loads(open(EXAMPLE_SPEC, encoding="utf-8").read())
    assert spec_from_dict(data) == TCoilSpec(**BASELINE_FIELDS)


def test_unknown_passive_type_raises_a_clear_error():
    with pytest.raises(KeyError, match="never-registered-device"):
        spec_from_dict({"passive_type": "never-registered-device"})


def test_missing_passive_type_field_raises():
    with pytest.raises(ValueError, match="passive_type"):
        spec_from_dict({"wid": 7})


def test_missing_required_field_raises_a_clear_error():
    incomplete = {k: v for k, v in BASELINE_FIELDS.items() if k != "wid"}
    with pytest.raises(ValueError, match="tcoil"):
        spec_from_dict({"passive_type": "tcoil", **incomplete})


def test_unexpected_field_raises_a_clear_error():
    with pytest.raises(ValueError, match="tcoil"):
        spec_from_dict({"passive_type": "tcoil", **BASELINE_FIELDS, "not_a_real_field": 1})


def test_load_spec_rejects_invalid_json(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid JSON"):
        load_spec(bad)
