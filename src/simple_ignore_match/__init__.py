"""Public API for simple_ignore_match.

Exports:
    IgnoreMatcher: compile gitignore-style patterns and match paths.
    Rule: a single parsed rule (pattern, negated, directory_only, anchored).
    match: convenience function that returns True if a path is ignored.
"""

from .core import IgnoreMatcher, Rule, match

__all__ = ["IgnoreMatcher", "Rule", "match"]
