"""Shared value types for the passivelab core interfaces (sub-phase 1.2.2).

These are the *nouns* that flow between the four core APIs (generate / characterize / optimize /
evaluate) and the seven interfaces defined alongside them. They are deliberately generic:

- **no passive-specific fields** — a T-coil's 11 parameters live in the tcoil plugin's spec, not
  here (the core level must not reference any one device);
- **no backend-specific fields** — a given solver's raw output lives in ``SimulationResult.raw``,
  keyed by that backend.

See ``docs/CORE_INTERFACE_DESIGN.md`` (= vault artifact ``ART-core-interface-design-0005``).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Mapping, Protocol, runtime_checkable

if TYPE_CHECKING:  # avoid any import cycle: PassiveSpec is only referenced in an annotation
    from passivelab.core.geometry.spec import PassiveSpec


@dataclass(frozen=True)
class Layout:
    """A generated layout: the geometry handle plus the metadata needed to characterize it.

    ``cell`` is intentionally untyped (``Any``) so ``core/`` never imports a geometry kit — the
    tcoil plugin puts a ``gdstk.Cell`` here, a future backend puts something else.
    """

    cell: Any = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    parameter_manifest: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SimulationResult:
    """Raw output of a ``SimulationBackend.simulate()``, before reduction to :class:`Metrics`.

    ``raw`` is keyed by the backend; ``characterize()`` (or a plugin) reduces it to Metrics. Kept
    separate from Metrics so the lossy reduction step is explicit, not hidden inside the solver.
    """

    backend: str = ""
    raw: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Metrics:
    """Characterization results as named values (capacitance, ESR, Q, S-parameters, ...).

    Generic ``key -> value``; *which* keys exist is a backend/passive concern, not fixed here.
    """

    values: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Objective:
    """What ``optimize()`` is asked to hit: ``targets`` (values to reach, e.g. inductance) and
    ``constraints`` (bounds, e.g. ``max_area``, ``min_voltage_margin``). Both generic maps — the
    analog-designer archetype's ``target_value / max_area / min_voltage_margin`` are just keys."""

    targets: Mapping[str, float] = field(default_factory=dict)
    constraints: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class Candidate:
    """A proposed design point: a :class:`PassiveSpec` and the :class:`Metrics` it achieved."""

    spec: "PassiveSpec"
    metrics: Metrics = field(default_factory=Metrics)


@dataclass(frozen=True)
class Score:
    """A :class:`ValidationRunner`'s verdict on a :class:`Candidate`: a scalar for ranking plus an
    optional breakdown of the sub-scores that produced it."""

    value: float = 0.0
    breakdown: Mapping[str, Any] = field(default_factory=dict)


@runtime_checkable
class Dataset(Protocol):
    """A characterization dataset accumulated by a :class:`DatasetPipeline` — at minimum, sized
    (the researcher archetype checks it grows across a sweep). Concrete storage (Parquet, ...) is
    a later-phase concern; this is only the shape a surrogate trainer consumes."""

    def __len__(self) -> int: ...
