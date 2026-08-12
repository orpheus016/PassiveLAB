"""Generic dict-backed registry: ``register(key, value)`` raises on a duplicate key,
``get(key)`` raises (listing what *is* registered) on a miss.

Extracted because the identical shape was independently implemented three times before this:
``core/geometry/registry.py``'s ``LayoutGenerator`` registry (``register``/``get``) and its
``PassiveSpec``-class registry (``register_spec``/``get_spec``), plus
``benchmark/geometry/registry.py``'s benchmark-case registry (``register_cases``/``all_cases``) --
the latter's own docstring said outright it "mirrors" the former. All three now hold one
:class:`Registry` instance internally instead of re-deriving this logic; their existing public
function names are unchanged; see [Registry] and its docstring below for the current API.
"""
from __future__ import annotations

from typing import Generic, TypeVar

T = TypeVar("T")


class Registry(Generic[T]):
    """A named, dict-backed registry keyed by string. ``label`` identifies the registry in error
    messages (e.g. ``"LayoutGenerator"``) -- distinguishes which registry raised when several are
    in play (as in ``core/geometry/registry.py``, which holds two)."""

    def __init__(self, label: str):
        self._label = label
        self._items: dict[str, T] = {}

    def register(self, key: str, value: T) -> None:
        """Raises if ``key`` is already registered -- a silent overwrite would hide a naming
        collision rather than surface it."""
        if key in self._items:
            raise ValueError(
                f"{key!r} is already registered to {self._items[key]!r} "
                f"in the {self._label} registry"
            )
        self._items[key] = value

    def get(self, key: str) -> T:
        try:
            return self._items[key]
        except KeyError:
            raise KeyError(
                f"no {self._label} registered for {key!r}; "
                f"registered keys: {sorted(self._items)}"
            ) from None

    def items(self) -> dict[str, T]:
        """A copy of the current registrations, keyed by their registration key."""
        return dict(self._items)
