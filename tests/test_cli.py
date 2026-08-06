"""Tests for the passivelab CLI (sub-phase 1.3.3): spec.json -> generate(spec) -> GDS (+ PNG)."""
from __future__ import annotations

import json

import gdstk
import pytest

from passivelab.cli import generate_command, main
from passivelab.geometry.tcoil import TCoilLayoutGenerator, TCoilSpec

EXAMPLE_SPEC = "examples/tcoil.spec.json"

BASELINE_FIELDS = dict(wid=7, gap=12, sizX=150, sizY=120, firY=10, tapseg=4, nseg=10,
                       tapratio=0.5, endratio=0.5, Lext=30, pad_siz=50, includepad=True)


def _summary(cell: gdstk.Cell) -> tuple:
    polys = cell.get_polygons()
    points = tuple(sorted(
        (p.layer, p.datatype, tuple((round(x, 6), round(y, 6)) for x, y in p.points))
        for p in polys
    ))
    return len(polys), cell.bounding_box(), points


def test_cli_generates_identical_gds_to_the_direct_call(tmp_path):
    gds_path = generate_command(EXAMPLE_SPEC, tmp_path, png=False)
    assert gds_path.exists()

    via_cli = gdstk.read_gds(str(gds_path)).top_level()[0]
    via_direct = TCoilLayoutGenerator().generate(TCoilSpec(**BASELINE_FIELDS)).cell
    assert _summary(via_cli) == _summary(via_direct)


def test_cli_writes_a_nonempty_png_by_default(tmp_path):
    gds_path = generate_command(EXAMPLE_SPEC, tmp_path, png=True)
    png_path = gds_path.with_suffix(".png")
    assert png_path.exists() and png_path.stat().st_size > 0


def test_out_dir_override_is_respected(tmp_path):
    out_dir = tmp_path / "my_output"
    gds_path = generate_command(EXAMPLE_SPEC, out_dir, png=False)
    assert out_dir in gds_path.parents


def test_main_exits_zero_and_prints_the_gds_path(tmp_path, capsys):
    code = main(["generate", EXAMPLE_SPEC, "--out-dir", str(tmp_path), "--no-png"])
    assert code == 0
    out = capsys.readouterr().out.strip()
    assert out.endswith("tcoil.gds")


def test_main_reports_a_malformed_spec_without_a_traceback(tmp_path, capsys):
    bad_spec = tmp_path / "bad.json"
    bad_spec.write_text(json.dumps({**{"passive_type": "tcoil"}, **BASELINE_FIELDS, "wid": 1}),
                        encoding="utf-8")
    code = main(["generate", str(bad_spec), "--out-dir", str(tmp_path)])
    assert code == 1
    err = capsys.readouterr().err
    assert err.startswith("error:")
    assert "Traceback" not in err


def test_main_reports_unknown_passive_type_without_a_traceback(tmp_path, capsys):
    bad_spec = tmp_path / "bad.json"
    bad_spec.write_text(json.dumps({"passive_type": "not-a-real-device"}), encoding="utf-8")
    code = main(["generate", str(bad_spec), "--out-dir", str(tmp_path)])
    assert code == 1
    err = capsys.readouterr().err
    assert err.startswith("error:") and "Traceback" not in err
