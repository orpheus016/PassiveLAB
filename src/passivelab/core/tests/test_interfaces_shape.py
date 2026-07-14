"""Shape tests for the core interfaces (sub-phase 1.2.2 validation bar).

Each Protocol is satisfiable by a minimal structural stub, and the value types construct with
sensible defaults. This is the literal "unit-tested for shape (instantiable stub implementations
satisfy each Protocol)" acceptance criterion from the 1.2.2 task.
"""
from __future__ import annotations

from passivelab.core import (
    Candidate,
    Dataset,
    DatasetPipeline,
    Layout,
    LayoutGenerator,
    Metrics,
    Model,
    ModelTrainer,
    Objective,
    Optimizer,
    PassiveSpec,
    Score,
    SimulationBackend,
    SimulationResult,
    ValidationRunner,
)


def test_value_types_construct_with_defaults():
    assert Layout().metadata == {}
    assert Layout().parameter_manifest == {}
    assert Metrics().values == {}
    assert SimulationResult().backend == ""
    assert Objective().targets == {} and Objective().constraints == {}
    assert Score().value == 0.0
    # Candidate requires a spec; Metrics defaults
    class _S:
        passive_type = "x"

        def validate(self):
            ...

    assert Candidate(spec=_S()).metrics == Metrics()


def test_each_interface_accepts_a_structural_stub():
    class Spec:
        passive_type = "x"

        def validate(self):
            ...

    class Gen:
        def generate(self, spec):
            return Layout()

    class Backend:
        def simulate(self, layout):
            return SimulationResult()

    class DS:
        def __len__(self):
            return 0

    class Pipe:
        def append(self, spec, metrics):
            ...

        def load(self):
            return DS()

    class Mdl:
        def predict(self, spec):
            return Metrics()

    class Trainer:
        def train(self, dataset):
            return Mdl()

    class Opt:
        def ask(self):
            return Spec()

        def tell(self, candidate, score):
            ...

    class Runner:
        def evaluate(self, candidate):
            return Score()

    assert isinstance(Spec(), PassiveSpec)
    assert isinstance(Gen(), LayoutGenerator)
    assert isinstance(Backend(), SimulationBackend)
    assert isinstance(DS(), Dataset)
    assert isinstance(Pipe(), DatasetPipeline)
    assert isinstance(Mdl(), Model)
    assert isinstance(Trainer(), ModelTrainer)
    assert isinstance(Opt(), Optimizer)
    assert isinstance(Runner(), ValidationRunner)


def test_missing_method_fails_the_protocol():
    class NotAGenerator:  # no generate()
        pass

    class NotAnOptimizer:  # ask() but no tell()
        def ask(self):
            ...

    assert not isinstance(NotAGenerator(), LayoutGenerator)
    assert not isinstance(NotAnOptimizer(), Optimizer)
