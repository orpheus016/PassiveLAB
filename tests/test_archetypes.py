"""Archetype journey tests — "as if these people use the tool" (sub-phase 1.2.2).

The platform must serve three first-class archetypes (VISION.md / Master PRD §3). These tests
prove each archetype's journey is **expressible through the core interfaces** using only
in-memory fakes — no gdstk, no solver, no mlflow. They are also the discovery vehicle: every step
a journey needs that 1.2.2 does not provide is marked ``OUT-OF-SCOPE 1.2.2`` and becomes a board
task (see the vault's PassiveLAB board).

Nothing here imports a device (tcoil) or a geometry kit (gdstk); the fakes conform to the
Protocols structurally, exactly as a real plugin or a third party would.
"""
from __future__ import annotations

from dataclasses import dataclass, field

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
)


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
    """Designer states an Objective (target_value, max_area, min_voltage_margin) and gets an
    optimized, implementable passive. generate + optimize compose through the interfaces."""
    objective = Objective(targets={"inductance": 4e-10},
                          constraints={"max_area": 500.0, "min_voltage_margin": 0.5})
    opt = GridOptimizer([1, 2, 3, 4, 5])
    best_candidate, best_score = run_search(opt, FauxGenerator(), FauxBackend(),
                                            TargetRunner(objective), steps=5)

    assert isinstance(best_candidate, Candidate)
    assert best_candidate.spec.passive_type == "faux"
    # turns=2 hits the target inductance exactly (1e-10 * 2**2 = 4e-10) within the area budget
    assert best_candidate.spec.params["turns"] == 2
    assert best_score.value == 0.0
    # OUT-OF-SCOPE 1.2.2: a real spec.json entry point and PCell/xschem export are not interfaces
    #   this phase provides -> board tasks (spec.json loader/CLI; PCell+xschem export path).


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
