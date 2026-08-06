"""Tests for the plugin registry / ``generate(spec)`` dispatcher (sub-phase 1.3.1).

Device-agnostic, like the rest of ``core/tests/``: uses a structural stub, never imports a device
package (``tcoil``) or a geometry kit (``gdstk``) — that would defeat the point of a test proving
the registry itself is device-agnostic.
"""
from __future__ import annotations

import pytest

from passivelab.core.geometry.registry import generate, get, register
from passivelab.core.types import Layout


class _StubSpec:
    def __init__(self, passive_type: str = "stub"):
        self.passive_type = passive_type

    def validate(self) -> None:
        ...


class _StubGenerator:
    def __init__(self, tag: str):
        self.tag = tag

    def generate(self, spec) -> Layout:
        return Layout(metadata={"handled_by": self.tag})


def test_register_then_get_returns_the_same_instance():
    gen = _StubGenerator("a")
    register("registry-test-roundtrip", gen)
    assert get("registry-test-roundtrip") is gen


def test_register_duplicate_passive_type_raises():
    register("registry-test-dup", _StubGenerator("first"))
    with pytest.raises(ValueError, match="registry-test-dup"):
        register("registry-test-dup", _StubGenerator("second"))


def test_get_unknown_passive_type_raises_with_known_types_listed():
    register("registry-test-known", _StubGenerator("known"))
    with pytest.raises(KeyError, match="registry-test-known"):
        get("registry-test-unknown-xyz")


def test_generate_dispatches_by_spec_passive_type():
    register("registry-test-dispatch", _StubGenerator("dispatch"))
    layout = generate(_StubSpec(passive_type="registry-test-dispatch"))
    assert layout.metadata == {"handled_by": "dispatch"}


def test_generate_unknown_passive_type_raises():
    with pytest.raises(KeyError):
        generate(_StubSpec(passive_type="registry-test-never-registered"))
