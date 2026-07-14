"""``DatasetPipeline`` — the L6 interface that accumulates (spec, metrics) rows for training.

Not a nice-to-have: this is *why* ``optimize()`` can run fast. Without a dataset feeding a
surrogate (L7), every optimizer iteration would pay for a slow EM/field-solver run (L5). The
concrete Parquet-backed implementation and the ingestion of the golden notebook's real
dataset-generation code are sub-phase 1.5 (see the vault's ``1.5 Dataset pipeline`` board task);
here we fix only the shape.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from passivelab.core.geometry.spec import PassiveSpec
from passivelab.core.types import Dataset, Metrics


@runtime_checkable
class DatasetPipeline(Protocol):
    def append(self, spec: PassiveSpec, metrics: Metrics) -> None: ...

    def load(self) -> Dataset: ...
