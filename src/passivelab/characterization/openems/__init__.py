"""openEMS (FDTD) ``SimulationBackend`` (sub-phase 1.4.1, see ``plugin.py``'s module docstring).

Importing this package self-registers ``OpenEMSBackend`` into the core registry under
``solver="openems"`` -- the same "importing the plugin registers it" pattern as
``geometry/tcoil/__init__.py``, one layer up. Unlike that registry, this one holds the *class*, not
a ready instance (see ``core/characterization/registry.py``'s module docstring for why) -- a caller
resolves it via ``passivelab.core.characterization.registry.get("openems")`` and constructs it with
their own ``OpenEMSConfig``/output directory.
"""
from passivelab.characterization.openems.config import OpenEMSConfig, load_openems_config
from passivelab.characterization.openems.plugin import OpenEMSBackend
from passivelab.core.characterization.registry import register

__all__ = ["OpenEMSBackend", "OpenEMSConfig", "load_openems_config"]

try:
    register("openems", OpenEMSBackend)
except ValueError:
    pass  # already registered (e.g. re-imported in a test/reload scenario)
