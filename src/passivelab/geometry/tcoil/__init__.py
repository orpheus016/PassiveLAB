"""T-coil geometry generator (gdstk backend, see docs/GENERATOR_COMPARISON_MATRIX.md) and its
PassiveSpec/LayoutGenerator plugin wrap (sub-phase 1.2.3, see docs/CORE_INTERFACE_DESIGN.md).

Importing this package self-registers ``TCoilLayoutGenerator`` into the core registry under
``passive_type="tcoil"`` (sub-phase 1.3.1) — the standard "importing the plugin registers it"
pattern, so a caller who imports ``passivelab.geometry.tcoil`` to reach ``TCoilSpec`` gets
dispatch through ``passivelab.core.generate(spec)`` for free, with no explicit registration call.
"""
from passivelab.core.geometry.registry import register
from passivelab.geometry.tcoil.generator import generate_tcoil
from passivelab.geometry.tcoil.plugin import TCoilLayoutGenerator
from passivelab.geometry.tcoil.spec import TCoilParams, TCoilSpec

__all__ = ["TCoilParams", "generate_tcoil", "TCoilSpec", "TCoilLayoutGenerator"]

try:
    register("tcoil", TCoilLayoutGenerator())
except ValueError:
    pass  # already registered (e.g. re-imported in a test/reload scenario)
