"""``passivelab.core`` — the stable platform contract (sub-phase 1.2.2).

The seven interfaces (as ``typing.Protocol``, so third parties conform *structurally* without
inheriting anything from us) and the shared value types that flow between them, realizing the four
core APIs — ``generate / characterize / optimize / evaluate``. This package holds **no passive
logic and no geometry-kit imports** (no ``tcoil``, no ``gdstk``); devices attach as plugins that
satisfy these Protocols (the tcoil retrofit is sub-phase 1.2.3).

North star per API: ``core/GOAL.md`` (+ one ``GOAL.md`` per sub-package). Design of record:
``docs/CORE_INTERFACE_DESIGN.md`` (= vault artifact ``ART-core-interface-design-0005``).
"""
from passivelab.core.benchmark.validation import ValidationRunner
from passivelab.core.characterization.backend import SimulationBackend
from passivelab.core.characterization.dataset import DatasetPipeline
from passivelab.core.characterization.surrogate import Model, ModelTrainer
from passivelab.core.geometry.generator import LayoutGenerator
from passivelab.core.geometry.spec import PassiveSpec
from passivelab.core.optimization.optimizer import Optimizer
from passivelab.core.types import (
    Candidate,
    Dataset,
    Layout,
    Metrics,
    Objective,
    Score,
    SimulationResult,
)

__all__ = [
    # value types
    "Layout",
    "Metrics",
    "SimulationResult",
    "Objective",
    "Candidate",
    "Score",
    "Dataset",
    # interfaces (7)
    "PassiveSpec",
    "LayoutGenerator",
    "SimulationBackend",
    "DatasetPipeline",
    "ModelTrainer",
    "Model",
    "Optimizer",
    "ValidationRunner",
]
