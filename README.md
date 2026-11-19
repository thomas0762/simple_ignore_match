# simple_ignore_match

Match paths against gitignore-style rules, with last-match-wins precedence.

```python
from simple_ignore_match import IgnoreMatcher

matcher = IgnoreMatcher([
    "*.log",
    "!important.log",
    "build/",
    "!build/keep.txt",
])

matcher.is_ignored("app.log")            # True
matcher.is_ignored("important.log")      # False
matcher.is_ignored("build", is_dir=True) # True
matcher.is_ignored("build/keep.txt")     # False
```

## Why this exists

Gitignore matching is deceptively hard: the ordering of rules matters, a
negation can re-include a file that an earlier rule ignored, and a trailing
slash silently changes a rule from "this file" to "this directory and
everything under it". Most small implementations either ignore precedence
entirely or invent a compromise that fails on real repositories.

This library picks one interpretation and sticks to it: rules are evaluated
in order, and the last rule that matches a path decides whether it is
ignored. That is what git documents, and it is the behaviour the tests
exercise. The trade-off is that we do not support every corner of gitignore
syntax (for example, ``**`` in the middle of a segment, or nested
``.gitignore`` files); we support the common cases and handle the awkward
edges that trip people up.

## The awkward edge

A rule like ``build/`` ignores the directory ``build`` and everything below
it, but it does *not* ignore a regular file named ``build``. You have to
pass ``is_dir=True`` when you are testing a directory. The ``filter`` helper
infers directory-ness from a trailing slash in the input string, which is
the convention git itself uses when it lists paths.

## API

* ``IgnoreMatcher(lines)`` — compile an iterable of pattern lines.
* ``IgnoreMatcher.from_file(path)`` — read patterns from a file.
* ``IgnoreMatcher.is_ignored(path, is_dir=False)`` — test one path.
* ``IgnoreMatcher.filter(paths)`` — return the ignored subset.
* ``match(path, patterns, is_dir=False)`` — one-shot convenience function.
* ``Rule`` — the parsed form of a single rule, exposed on
  ``IgnoreMatcher.rules`` for introspection.

Paths are normalised before matching: backslashes become forward slashes,
repeated slashes are collapsed, and leading ``./`` segments are removed.
