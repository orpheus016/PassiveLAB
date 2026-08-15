"""Proves importing this plugin package actually registers "openems" into the real core registry
(sub-phase 1.4.1) -- distinct from ``core/tests/test_characterization_registry.py``, which tests
the registry mechanics generically with a stub and never imports this package. No openEMS/CSXCAD
needed: registering the class doesn't require constructing or calling it.
"""
from __future__ import annotations

import passivelab.characterization.openems  # noqa: F401 -- import for its registration side effect
from passivelab.characterization.openems.plugin import OpenEMSBackend
from passivelab.core.characterization.backend import SimulationBackend
from passivelab.core.characterization.registry import get


def test_openems_resolves_to_openems_backend():
    assert get("openems") is OpenEMSBackend


def test_openems_backend_satisfies_the_simulation_backend_protocol():
    assert isinstance(OpenEMSBackend, type)
    backend = OpenEMSBackend.__new__(OpenEMSBackend)  # protocol check needs no __init__ args
    assert isinstance(backend, SimulationBackend)
