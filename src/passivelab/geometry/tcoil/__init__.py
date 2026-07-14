"""T-coil geometry generator (gdstk backend, see docs/GENERATOR_COMPARISON_MATRIX.md) and its
PassiveSpec/LayoutGenerator plugin wrap (sub-phase 1.2.3, see docs/CORE_INTERFACE_DESIGN.md)."""
from passivelab.geometry.tcoil.generator import generate_tcoil
from passivelab.geometry.tcoil.plugin import TCoilLayoutGenerator
from passivelab.geometry.tcoil.spec import TCoilParams, TCoilSpec

__all__ = ["TCoilParams", "generate_tcoil", "TCoilSpec", "TCoilLayoutGenerator"]
