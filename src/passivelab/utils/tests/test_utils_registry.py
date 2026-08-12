"""Tests for the generic `Registry[T]` (sub-phase 1.3 refactor pass). `core/tests/test_registry.py`
and `benchmark/geometry/tests/` cover the two thin call sites built on top of this; these tests
cover the shared implementation directly.
"""
from __future__ import annotations

import pytest

from passivelab.utils.registry import Registry


def test_register_then_get_returns_the_same_instance():
    reg: Registry[str] = Registry("thing")
    reg.register("a", "value-a")
    assert reg.get("a") == "value-a"


def test_register_duplicate_key_raises():
    reg: Registry[str] = Registry("thing")
    reg.register("dup", "first")
    with pytest.raises(ValueError, match="dup"):
        reg.register("dup", "second")


def test_get_unknown_key_raises_with_known_keys_listed():
    reg: Registry[str] = Registry("thing")
    reg.register("known", "value")
    with pytest.raises(KeyError, match="known"):
        reg.get("unknown")


def test_items_returns_a_copy():
    reg: Registry[str] = Registry("thing")
    reg.register("a", "value-a")
    snapshot = reg.items()
    assert snapshot == {"a": "value-a"}
    snapshot["b"] = "value-b"
    assert reg.items() == {"a": "value-a"}  # mutation of the copy doesn't leak back
