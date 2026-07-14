"""``LayoutGenerator`` — the L3 interface behind ``generate(spec) -> Layout``.

A generator turns a :class:`~passivelab.core.geometry.spec.PassiveSpec` into a
:class:`~passivelab.core.types.Layout` (geometry handle + metadata + parameter manifest). The
tcoil plugin (sub-phase 1.2.3) wraps the existing ``generate_tcoil()`` behind this — the wrap
returns a ``Layout`` around the ``gdstk.Cell`` it already produces, without changing geometry.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from passivelab.core.geometry.spec import PassiveSpec
from passivelab.core.types import Layout


@runtime_checkable
class LayoutGenerator(Protocol):
    def generate(self, spec: PassiveSpec) -> Layout: ...
