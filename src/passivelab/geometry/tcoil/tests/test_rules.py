"""Tests for tcoil/rules.py -- valid params pass, out-of-range params raise."""
from __future__ import annotations

import dataclasses

import pytest

from passivelab.geometry.tcoil import TCoilParams
from passivelab.geometry.tcoil.rules import validate

VALID = TCoilParams(wid=7, gap=12, sizX=150, sizY=120, firY=10, tapseg=4, nseg=10,
                     tapratio=0.5, endratio=0.5, Lext=30, pad_siz=50, includepad=True)


def test_valid_params_pass():
    validate(VALID)  # must not raise


@pytest.mark.parametrize("field,bad_value", [
    ("sizX", 10),          # below [20, 200]
    ("sizY", 300),         # above [20, 200]
    ("wid", 1),            # below [3, 12]
    ("gap", 30),           # above [6, 24]
    ("nseg", 30),          # above [2, 24]
    ("tapratio", 0.1),     # below [0.30, 0.80]
    ("endratio", 0.9),     # above [0.20, 0.80]
    ("pad_siz", -5),       # not positive
    ("Lext", 0),           # not positive
])
def test_out_of_range_rejected(field, bad_value):
    params = dataclasses.replace(VALID, **{field: bad_value})
    with pytest.raises(ValueError):
        validate(params)


def test_tapseg_must_be_within_nseg():
    params = dataclasses.replace(VALID, tapseg=VALID.nseg)  # tapseg == nseg, invalid
    with pytest.raises(ValueError):
        validate(params)
