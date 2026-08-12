"""Cross-cutting helpers shared across ``core``/plugins/``benchmark`` -- infra, not an interface
layer (no ``GOAL.md``, unlike ``core/*``'s L1-L10 packages). Anything implemented in 2+ places
in this codebase belongs here instead of a third copy -- see ``registry.py``'s docstring for the
concrete case that motivated this package, and ``.claude/agents/utils-reviewer.md`` for the
check this is meant to make routine.
"""
