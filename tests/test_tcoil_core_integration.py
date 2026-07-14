"""T-coil driven end-to-end through the core interfaces (sub-phase 1.2.3).

The researcher-archetype sweep from ``test_archetypes.py``, replayed with the **real** T-coil
plugin (``TCoilSpec``/``TCoilLayoutGenerator``) instead of fakes for geometry. The solver is still
a fake ``SimulationBackend`` (no real solver exists yet — that's sub-phase 1.4), but it reduces
**real generated geometry** (an actual ``gdstk.Cell``'s polygon count), not invented numbers.

This file deliberately imports only the plugin surface — ``TCoilSpec`` / ``TCoilLayoutGenerator``
— never ``generate_tcoil`` / ``TCoilParams`` directly, demonstrating "no direct calls to
``tcoil.generator`` from outside the plugin boundary." ``test_file_only_imports_plugin_surface``
below enforces that on this file's own source, not just by convention.
"""
from __future__ import annotations

import pathlib
import re

from passivelab.core import Dataset, DatasetPipeline, Metrics, SimulationResult
from passivelab.geometry.tcoil import TCoilLayoutGenerator, TCoilSpec

BASELINE_FIELDS = dict(wid=7, gap=12, sizX=150, sizY=120, firY=10, tapratio=0.5, endratio=0.5,
                       Lext=30, pad_siz=50, includepad=True)


class FakeBackend:
    """A fake SimulationBackend: reduces REAL generated geometry (polygon count from the real
    gdstk.Cell) into a metric, without any real EM/field solver (that's sub-phase 1.4)."""

    def simulate(self, layout):
        return SimulationResult(backend="fake", raw={"num_polygons": len(layout.cell.get_polygons())})


def reduce_result(result: SimulationResult) -> Metrics:
    return Metrics(values=dict(result.raw))


class ListDataset:
    def __init__(self):
        self.rows = []

    def __len__(self) -> int:
        return len(self.rows)


class InMemoryDatasetPipeline:
    def __init__(self):
        self._ds = ListDataset()

    def append(self, spec, metrics) -> None:
        self._ds.rows.append((spec, metrics))

    def load(self) -> Dataset:
        return self._ds


def test_tcoil_sweep_through_core_interfaces():
    """generate() -> characterize() -> dataset, driven entirely through core Protocols with the
    real T-coil plugin. Each nseg variant produces measurably different real geometry."""
    generator = TCoilLayoutGenerator()
    backend = FakeBackend()
    pipe = InMemoryDatasetPipeline()

    sweep = [TCoilSpec(nseg=n, tapseg=1, **BASELINE_FIELDS) for n in (2, 4, 6, 8)]
    polygon_counts = []
    for spec in sweep:
        spec.validate()
        layout = generator.generate(spec)
        metrics = reduce_result(backend.simulate(layout))
        pipe.append(spec, metrics)
        polygon_counts.append(metrics.values["num_polygons"])

    ds = pipe.load()
    assert len(ds) == len(sweep)  # the dataset grows across the sweep
    assert isinstance(pipe, DatasetPipeline) and isinstance(ds, Dataset)
    assert len(set(polygon_counts)) > 1  # nseg measurably changes the REAL generated geometry


def test_file_only_imports_plugin_surface():
    """This file must never import generate_tcoil/TCoilParams directly -- only the plugin
    (TCoilSpec/TCoilLayoutGenerator). Enforced on this file's own source, not just by convention."""
    src = pathlib.Path(__file__).read_text(encoding="utf-8")
    imports = re.findall(r"^\s*(?:import|from)\s+([\w.]+)", src, re.MULTILINE)
    assert not any(m == "passivelab.geometry.tcoil.generator" or m.endswith(".generator")
                  for m in imports if "tcoil" in m)
