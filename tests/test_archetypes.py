"""Archetype journey tests — "as if these people use the tool" (sub-phase 1.2.2).

The platform must serve three first-class archetypes (VISION.md / Master PRD §3). These tests
prove each archetype's journey is **expressible through the core interfaces**. They are also the
discovery vehicle: every step a journey needs that isn't provided yet is marked
``OUT-OF-SCOPE <phase>`` and becomes a board task (see the vault's PassiveLAB board).

Originally (1.2.2) every journey ran on in-memory fakes only, since no real device or backend
existed. 1.3 changed that for geometry: ``test_analog_designer_journey`` (below) now drives the
**real** T-coil plugin through ``spec.json -> generate(spec)`` (1.3.1-1.3.4 built the pieces
needed) — the one deliberate exception to "nothing here imports a device." The other two
archetypes stay fake-only: their backends (``characterize``/``optimize``) are still 1.4/1.7.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

from passivelab.core import (
    Candidate,
    Dataset,
    DatasetPipeline,
    Layout,
    Metrics,
    Objective,
    Optimizer,
    PassiveSpec,
    Score,
    SimulationResult,
    generate,
    load_spec,
)
from passivelab.geometry.tcoil.templates import ALL_LAYERS
import passivelab.geometry.tcoil  # noqa: F401 -- self-registers "tcoil"


# --- fakes: structural implementations of the interfaces (no passivelab base classes) ---------

@dataclass
class FauxSpec:
    """A minimal PassiveSpec stand-in for a device plugin's real spec."""

    passive_type: str = "faux"
    params: dict = field(default_factory=dict)

    def validate(self) -> None:
        if self.params.get("turns", 1) < 1:
            raise ValueError("turns must be >= 1")


class FauxGenerator:
    def generate(self, spec: PassiveSpec) -> Layout:
        turns = spec.params.get("turns", 1)  # type: ignore[attr-defined]
        return Layout(cell=f"cell(turns={turns})", metadata={"area": turns * 100.0},
                      parameter_manifest=dict(spec.params))  # type: ignore[attr-defined]


class FauxBackend:
    def simulate(self, layout: Layout) -> SimulationResult:
        turns = layout.parameter_manifest.get("turns", 1)
        # toy physics: inductance ~ turns**2; carry area through for the constraint check
        return SimulationResult(backend="faux",
                                raw={"inductance": 1e-10 * turns ** 2, "area": layout.metadata["area"]})


def reduce_result(result: SimulationResult) -> Metrics:
    """The SimulationResult -> Metrics reduction (backend/plugin-specific in reality; trivial here)."""
    return Metrics(values=dict(result.raw))


class TargetRunner:
    """A ValidationRunner scoring closeness to an Objective (higher = better; 0.0 = on target)."""

    def __init__(self, objective: Objective):
        self.objective = objective

    def evaluate(self, candidate: Candidate) -> Score:
        target = self.objective.targets.get("inductance", 0.0)
        got = candidate.metrics.values.get("inductance", 0.0)
        err = abs(got - target)
        max_area = self.objective.constraints.get("max_area", float("inf"))
        area = candidate.metrics.values.get("area", 0.0)
        penalty = max(0.0, area - max_area)
        return Score(value=-(err + penalty), breakdown={"err": err, "penalty": penalty})


class GridOptimizer:
    """A baseline ask-tell Optimizer sweeping a fixed grid of ``turns`` values."""

    def __init__(self, turns_grid):
        self._queue = list(turns_grid)
        self.history: list[tuple[Candidate, Score]] = []

    def ask(self) -> PassiveSpec:
        return FauxSpec(params={"turns": self._queue.pop(0)})

    def tell(self, candidate: Candidate, score: Score) -> None:
        self.history.append((candidate, score))

    def best(self) -> tuple[Candidate, Score]:
        return max(self.history, key=lambda cs: cs[1].value)


def run_search(optimizer, generator, backend, runner, steps):
    """The generate -> characterize -> evaluate -> tell loop, composed from the interfaces."""
    for _ in range(steps):
        spec = optimizer.ask()
        spec.validate()
        layout = generator.generate(spec)
        metrics = reduce_result(backend.simulate(layout))
        candidate = Candidate(spec=spec, metrics=metrics)
        score = runner.evaluate(candidate)
        optimizer.tell(candidate, score)
    return optimizer.best()


# --- archetype 1: analog / IC designer -------------------------------------------------------

def test_analog_designer_journey():
    """States a device declaratively (spec.json), generates it through the real platform path,
    and confirms the result is layer-legal and that sweeping the spec produces multiple,
    genuinely distinct, inspectable geometries -- the real path now that 1.3.1-1.3.4 exist
    (was a FauxSpec/FauxGenerator/GridOptimizer stub before 1.3)."""
    spec = load_spec("examples/tcoil.spec.json")
    spec.validate()
    layout = generate(spec)  # real registry dispatch (1.3.1) through the real T-coil plugin

    # Layer-legal GDS: the automatable stand-in for "matches the notebook" this repo has used
    # since 1.3.2/1.3.4 (a live gdspy diff isn't possible -- see rules.py's docstring).
    legal = {(l, 0) for l in ALL_LAYERS}
    inventory = {(p.layer, p.datatype) for p in layout.cell.get_polygons()}
    assert inventory <= legal, f"foreign (layer, datatype) pairs: {inventory - legal}"

    # Inspectable sweep: multiple, genuinely distinct geometries from the same declarative shape
    # (rendering them to PNG for actual human inspection is covered separately, by test_cli.py
    # and 1.3.4's benchmark/geometry/tcoil/test_sweep.py -- this test proves the composition).
    # Full fingerprint, not just polygon count -- different nseg values can coincidentally
    # produce the same polygon count while the actual geometry (vertex coordinates) differs.
    def _fingerprint(cell):
        return tuple(sorted(
            (p.layer, p.datatype, tuple((round(x, 6), round(y, 6)) for x, y in p.points))
            for p in cell.get_polygons()
        ))

    swept = [generate(replace(spec, nseg=n)) for n in (6, 10, 14)]
    assert all(len(l.cell.get_polygons()) > 0 for l in swept)
    assert len({_fingerprint(l.cell) for l in swept}) == len(swept)

    # OUT-OF-SCOPE 1.3: optimize()/characterize() have no real backend yet (1.4/1.7) -- a
    # real objective -> optimized-candidate leg of this journey is still fake-only, tracked as
    # its own board work; PCell/xschem export is a separate, later task regardless.


# --- archetype 2: device researcher ----------------------------------------------------------

class ListDataset:
    def __init__(self):
        self.rows: list[tuple[PassiveSpec, Metrics]] = []

    def __len__(self) -> int:
        return len(self.rows)


class InMemoryDatasetPipeline:
    def __init__(self):
        self._ds = ListDataset()

    def append(self, spec: PassiveSpec, metrics: Metrics) -> None:
        self._ds.rows.append((spec, metrics))

    def load(self) -> Dataset:
        return self._ds


def test_researcher_sweep_journey():
    """Researcher states a parameter sweep and gets an accumulating dataset + characterization.
    generate + characterize + dataset compose through the interfaces."""
    sweep = [FauxSpec(params={"turns": t}) for t in range(1, 6)]
    gen, backend, pipe = FauxGenerator(), FauxBackend(), InMemoryDatasetPipeline()

    characterized = []
    for spec in sweep:
        metrics = reduce_result(backend.simulate(gen.generate(spec)))
        pipe.append(spec, metrics)
        characterized.append(metrics)

    ds = pipe.load()
    assert len(ds) == len(sweep)  # the dataset grows across the sweep
    assert all("inductance" in m.values for m in characterized)  # characterization retrievable
    assert isinstance(pipe, DatasetPipeline) and isinstance(ds, Dataset)
    # OUT-OF-SCOPE 1.2.2: mlflow experiment tracking, and the real Parquet dataset / ANN training
    #   code, are sub-phases 1.5/1.6 -> board tasks (adopt-mlflow adr; ingestion noted on 1.5/1.6).


# --- archetype 3: algorithm developer --------------------------------------------------------

class ForeignOptimizer:
    """A third party's optimizer that inherits NOTHING from passivelab — it conforms to the
    Optimizer Protocol purely structurally. This is why the interface is a Protocol, not an ABC."""

    def __init__(self, turns_list):
        self._q = list(turns_list)
        self.history: list[tuple[Candidate, Score]] = []

    def ask(self) -> PassiveSpec:
        return FauxSpec(params={"turns": self._q.pop(0)})

    def tell(self, candidate: Candidate, score: Score) -> None:
        self.history.append((candidate, score))

    def best(self) -> tuple[Candidate, Score]:
        return max(self.history, key=lambda cs: cs[1].value)


def _benchmark(optimizer, objective, steps):
    _, score = run_search(optimizer, FauxGenerator(), FauxBackend(), TargetRunner(objective), steps)
    return score.value


def test_algo_developer_benchmark_journey():
    """Algo dev brings an optimizer and gets a fair benchmark score vs a baseline. The foreign
    optimizer plugs in with no inheritance from passivelab (structural typing)."""
    objective = Objective(targets={"inductance": 4e-10}, constraints={"max_area": 1e9})
    baseline = GridOptimizer([1, 2, 3])
    contender = ForeignOptimizer([4, 2, 5])

    # both conform to the Optimizer Protocol; the contender has no passivelab base class
    assert isinstance(baseline, Optimizer) and isinstance(contender, Optimizer)
    assert ForeignOptimizer.__mro__[1:] == (object,)

    scores = {"baseline": _benchmark(baseline, objective, 3),
              "contender": _benchmark(contender, objective, 3)}
    # a comparable score comes out for each; both find turns=2 (exact target) within budget
    assert set(scores) == {"baseline", "contender"}
    assert scores["baseline"] == 0.0 and scores["contender"] == 0.0
    # OUT-OF-SCOPE 1.2.2: the common-centroid / interdigitization algorithm benchmark suite and the
    #   gdspy-vs-gdstk generation-backend harness are algo-dev tooling -> board tasks.
