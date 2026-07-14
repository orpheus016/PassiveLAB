"""Core characterization interfaces (L4-L7): the solver backend, dataset pipeline, and surrogate
trainer behind ``characterize(layout)`` and the fast-surrogate path that keeps ``optimize()`` cheap."""
from passivelab.core.characterization.backend import SimulationBackend
from passivelab.core.characterization.dataset import DatasetPipeline
from passivelab.core.characterization.surrogate import Model, ModelTrainer

__all__ = ["SimulationBackend", "DatasetPipeline", "ModelTrainer", "Model"]
