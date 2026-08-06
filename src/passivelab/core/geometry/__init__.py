"""Core geometry interfaces (L1-L3): the spec and the generator behind ``generate(spec)``."""
from passivelab.core.geometry.generator import LayoutGenerator
from passivelab.core.geometry.registry import generate, get, get_spec, register, register_spec
from passivelab.core.geometry.spec import PassiveSpec
from passivelab.core.geometry.spec_loader import load_spec, spec_from_dict

__all__ = ["PassiveSpec", "LayoutGenerator", "register", "get", "generate",
           "register_spec", "get_spec", "load_spec", "spec_from_dict"]
