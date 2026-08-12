"""`sweep-spec.json -> N-sample notebook-faithful sweep -> GDS+PNG previews + report.json`, the
installed sibling to `cli.py`'s `generate` command. Mirrors `generate_command()`/`main()`'s
testable-core/thin-argparse-wrapper split.

Today tcoil-only (`sweep_command()` hardcodes `passive_type == "tcoil"` rather than dispatching
through a sampler registry) -- matches `cli.py`'s own documented precedent ("plugin-discovery is
future work, not needed for one device") and `geometry/GOAL.md`'s "don't build `geometry/common/`
until a second device proves what's shared" rule. `run_sweep()` is similarly tcoil-flavored today
(imports `ALL_LAYERS`/`PORT_START` from `geometry/tcoil/templates.py` for its layer-legality/
tap-exercised checks) for the same reason -- a second sweep-capable device would need those checks
generalized onto each `PassiveSpec`'s own contract, not guessed at now.

Moved out of `benchmark/geometry/tcoil/test_sweep.py`'s test body (sub-phase 1.3.4 built it as a
notebook-fidelity regression test; this promotes the same validate/generate/render/report loop to
a real, reusable feature). That test now calls `run_sweep()` too, sharing both the sampler
(`geometry/tcoil/sampling.py`) and this report-writing loop instead of duplicating either.
"""
from __future__ import annotations

import dataclasses
import gdstk
import json
import pathlib
import tempfile
from collections import Counter
from collections.abc import Sequence

from passivelab.core import generate, read_spec_json
from passivelab.geometry.tcoil.sampling import sweep as tcoil_sweep
from passivelab.geometry.tcoil.spec import TCoilSpec
from passivelab.geometry.tcoil.templates import ALL_LAYERS, PORT_START


@dataclasses.dataclass
class SweepSpec:
    """A sweep-spec.json's fields: which device, how many notebook-faithful samples, and the two
    fields the sampler otherwise hardcodes (`includepad`/`pad_siz`) pinned to a user choice.
    Every randomized geometry field (wid/gap/nseg/tapseg/sizX/sizY/tapratio/endratio/firY/Lext) is
    deliberately NOT here -- that's `sample_tcoil_spec()`'s proven notebook-faithful distribution,
    not a user input. Per-field range overrides are a documented future extension (a distribution
    mini-DSL), not built here."""

    passive_type: str
    n: int
    seed: int
    includepad: bool = True
    pad_siz: float = 50


def load_sweep_spec(path: str | pathlib.Path) -> SweepSpec:
    """Read a sweep-spec.json file and construct its ``SweepSpec``. Reuses
    ``read_spec_json()``'s JSON-file-reading behavior (same as ``load_spec()``); doesn't route
    through ``spec_from_dict``/``PassiveSpec`` construction, since a sweep-spec's shape is
    genuinely different (has ``n``/``seed``, omits the randomized geometry fields a ``PassiveSpec``
    requires)."""
    data = read_spec_json(path)
    try:
        return SweepSpec(**data)
    except TypeError as e:
        raise ValueError(f"{path}: malformed sweep-spec.json: {e}") from e


def run_sweep(specs: Sequence[TCoilSpec], out_dir: str | pathlib.Path, *, seed: int | None = None,
              png: bool = True, max_renders: int = 12) -> dict:
    """Validate+generate every spec in ``specs``, write ``out_dir/report.json`` (sample count,
    TAP-exercised rate, rules.py-pass rate, per-sample entries), and GDS+PNG for one illustrative
    sample per distinct ``(nseg, includepad)`` combo, up to ``max_renders``. Returns the report
    dict.

    Raises ``RuntimeError`` immediately on a foreign-layer polygon or a failed GDS round-trip --
    unlike the notebook-fidelity test this now backs, a real "generate my dataset" run should
    never silently produce garbage (a bare ``assert`` here would be stripped under ``python -O``).

    ``png=True`` degrades gracefully (report still written, previews skipped) if matplotlib
    (the ``viz``/``bench`` extra) isn't installed -- deliberately more lenient than
    ``generate_command()``'s single-GDS+PNG case: the report.json is this feature's primary
    deliverable across N samples, losing a handful of illustrative previews shouldn't fail the
    whole run. Pass ``png=False`` to skip the attempt outright.
    """
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    render_png = None
    if png:
        try:
            from passivelab.utils.preview import render_png
        except ImportError:
            render_png = None  # `viz`/`bench` extra not installed; report still gets written

    pdk_layer_datatypes = {(layer, 0) for layer in ALL_LAYERS}
    rendered_combos: set[tuple[int, bool]] = set()
    results = []
    tap_exercised = 0
    rules_pass = 0
    rules_failure_fields: Counter[str] = Counter()

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = pathlib.Path(tmp)
        for i, spec in enumerate(specs):
            entry = {"index": i, "params": dataclasses.asdict(spec)}

            try:
                spec.validate()
                entry["rules_pass"] = True
                rules_pass += 1
            except ValueError as e:
                entry["rules_pass"] = False
                entry["rules_error"] = str(e)
                for field in ("sizX", "sizY", "wid", "gap", "nseg", "tapratio", "endratio",
                              "tapseg", "pad_siz", "Lext"):
                    if f"{field}=" in str(e):
                        rules_failure_fields[field] += 1

            # Generate regardless of rules_pass: generate_tcoil()/core.generate() don't call
            # validate() themselves (the established "callers validate before generating"
            # convention) -- the point of a sweep is checking generation against the notebook's
            # *real* distribution, which can fall outside rules.py's ranges; gating on rules_pass
            # would hide exactly that.
            layout = generate(spec)
            polys = layout.cell.get_polygons()
            entry["polygon_count"] = len(polys)
            inventory = {(p.layer, p.datatype) for p in polys}
            entry["layer_legal"] = inventory <= pdk_layer_datatypes

            ports_cell = layout.metadata["ports_cell"]
            tap_present = any(p.layer == PORT_START + 2 for p in ports_cell.get_polygons())
            entry["tap_exercised"] = tap_present
            if tap_present:
                tap_exercised += 1

            combo = (spec.nseg, spec.includepad)
            if (render_png is not None and combo not in rendered_combos
                    and len(rendered_combos) < max_renders):
                rendered_combos.add(combo)
                stem = out_dir / f"nseg{spec.nseg}_pad{spec.includepad}"
                lib = gdstk.Library()
                lib.add(layout.cell)
                lib.write_gds(str(stem.with_suffix(".gds")))
                render_png(layout.cell, stem.with_suffix(".png"),
                          title=f"nseg={spec.nseg} includepad={spec.includepad}")
                entry["rendered"] = True
            else:
                entry["rendered"] = False

            gds_path = tmp_path / f"sweep_{i}.gds"
            lib = gdstk.Library()
            lib.add(layout.cell)
            lib.write_gds(str(gds_path))
            read_back = gdstk.read_gds(str(gds_path))
            entry["gds_round_trip_ok"] = len(read_back.top_level()[0].get_polygons()) == len(polys)

            results.append(entry)
            if not entry["layer_legal"]:
                raise RuntimeError(
                    f"sample {i} produced a foreign layer: {inventory - pdk_layer_datatypes}"
                )
            if not entry["gds_round_trip_ok"]:
                raise RuntimeError(f"sample {i} failed a GDS round trip")

    n = len(specs)
    report = {
        "n_samples": n,
        "seed": seed,
        "tap_exercised_rate": (tap_exercised / n) if n else 0.0,
        "rules_pass_rate": (rules_pass / n) if n else 0.0,
        "rules_failure_field_counts": dict(rules_failure_fields),
        "cases": results,
    }
    (out_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def sweep_command(spec_path: str | pathlib.Path, out_dir: str | pathlib.Path, *,
                   png: bool = True) -> pathlib.Path:
    """Load `spec_path`, generate `SweepSpec.n` notebook-faithful tcoil samples, run them through
    `run_sweep()`, and return the written `out_dir/report.json` path."""
    sweep_spec = load_sweep_spec(spec_path)
    if sweep_spec.passive_type != "tcoil":
        raise ValueError(
            f"passive_type {sweep_spec.passive_type!r} not supported by sweep yet (only 'tcoil')"
        )
    specs = list(tcoil_sweep(sweep_spec.n, sweep_spec.seed,
                              includepad=sweep_spec.includepad, pad_siz=sweep_spec.pad_siz))
    run_sweep(specs, out_dir, seed=sweep_spec.seed, png=png)
    return pathlib.Path(out_dir) / "report.json"
