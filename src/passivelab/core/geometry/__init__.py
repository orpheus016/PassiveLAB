"""Core geometry interfaces (L1-L3): the spec and the generator behind ``generate(spec)``."""
from passivelab.core.geometry.generator import LayoutGenerator
from passivelab.core.geometry.spec import PassiveSpec

__all__ = ["PassiveSpec", "LayoutGenerator"]
