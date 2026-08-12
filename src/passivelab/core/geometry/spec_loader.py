"""``spec.json -> PassiveSpec`` loader (sub-phase 1.3.3).

Flat JSON: a top-level ``passive_type`` field plus the device spec's own field names verbatim
(e.g. a T-coil's ``wid``/``gap``/... at the top level, not nested under a ``params`` wrapper) --
round-trips to the spec class with zero translation, dispatched via
``registry.get_spec(passive_type)`` the same way ``registry.generate()`` dispatches generators.

Does not call ``spec.validate()`` -- matches the established "callers validate before
generating" convention (see ``geometry/tcoil/plugin.py``'s docstring, the archetype tests in
``tests/test_archetypes.py``). The CLI (1.3.3) is the caller that validates.
"""
from __future__ import annotations

import json
import pathlib

from passivelab.core.geometry.registry import get_spec
from passivelab.core.geometry.spec import PassiveSpec


def spec_from_dict(data: dict) -> PassiveSpec:
    """Construct a ``PassiveSpec`` from a parsed ``spec.json`` dict."""
    fields = dict(data)
    passive_type = fields.pop("passive_type", None)
    if passive_type is None:
        raise ValueError("spec.json is missing the required 'passive_type' field")
    spec_cls = get_spec(passive_type)
    try:
        return spec_cls(**fields)
    except TypeError as e:
        raise ValueError(f"malformed spec.json for passive_type {passive_type!r}: {e}") from e


def read_spec_json(path: str | pathlib.Path) -> dict:
    """Read and parse a JSON spec file into a dict, without constructing a ``PassiveSpec`` --
    shared by ``load_spec()`` and ``scripts/sweep.py``'s sweep-spec loader, which need the same
    "read this file, raise a clean ValueError on bad JSON/shape" behavior but only one of them
    builds a ``PassiveSpec`` from the result."""
    path = pathlib.Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"{path}: invalid JSON: {e}") from e
    if not isinstance(data, dict):
        raise ValueError(f"{path}: spec.json must be a JSON object, got {type(data).__name__}")
    return data


def load_spec(path: str | pathlib.Path) -> PassiveSpec:
    """Read a ``spec.json`` file and construct its ``PassiveSpec``."""
    return spec_from_dict(read_spec_json(path))
