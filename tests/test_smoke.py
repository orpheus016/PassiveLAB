"""Smoke test: proves the package imports and the test harness runs in CI.

Real tests arrive with the Phase-1 interfaces (sub-phase 1.2 onward). Each sub-phase in
`docs/PRD/` states its own validation criteria; add the tests that enforce them next to the
code that satisfies them.
"""
import passivelab


def test_package_imports():
    assert passivelab.__version__
