"""``ModelTrainer`` + ``Model`` — the L7 interface: a fast surrogate for characterization.

Together with :class:`~passivelab.core.characterization.dataset.DatasetPipeline` this is the
surrogate that lets an :class:`~passivelab.core.optimization.optimizer.Optimizer` iterate against a
fast approximate ``characterize()`` instead of a slow EM solve each time. The concrete model (the
notebook's 5-layer MLP) and the ingestion of its real training code are sub-phase 1.6 (see the
vault's ``1.6 ANN pipeline`` board task); here we fix only the shape.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from passivelab.core.geometry.spec import PassiveSpec
from passivelab.core.types import Dataset, Metrics


@runtime_checkable
class Model(Protocol):
    """A trained surrogate: predicts :class:`Metrics` for a spec without a full solver run."""

    def predict(self, spec: PassiveSpec) -> Metrics: ...


@runtime_checkable
class ModelTrainer(Protocol):
    def train(self, dataset: Dataset) -> Model: ...
