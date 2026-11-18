"""Gitignore-style path matching with precedence.

This module implements a deliberately small subset of gitignore semantics:

* Blank lines and lines starting with ``#`` are ignored.
* A leading ``!`` negates the rule.
* A trailing ``/`` restricts the rule to directories.
* A leading ``/`` anchors the rule to the root of the tree.
* A pattern containing a ``/`` anywhere other than a trailing ``/`` is
  anchored to the root, mirroring git's behaviour.
* ``*`` matches any run of characters except ``/``.
* ``?`` matches a single character except ``/``.
* ``**`` matches any number of path segments.
* Character classes (``[abc]``, ``[a-z]``, ``[!abc]``) are supported.

Precedence is last-match-wins: rules are evaluated in order and the last
rule that matches a path decides whether it is ignored. This matches the
documented git behaviour and is the single interpretation this library
commits to.

Paths are normalised to use ``/`` separators and have no leading or trailing
separators. Matching is done on the normalised string; callers are expected
to pass paths relative to the root of the tree being matched.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple


__all__ = ["IgnoreMatcher", "Rule", "match"]


@dataclass(frozen=True)
class Rule:
    """A single parsed ignore rule.

    Attributes:
        pattern: The original pattern text (without the leading ``!`` or
            trailing ``/``).
        negated: True if the rule starts with ``!``.
        directory_only: True if the rule only applies to directories.
        anchored: True if the rule is anchored to the root.
        regex: The compiled regular expression used for matching.
    """

    pattern: str
    negated: bool
    directory_only: bool
    anchored: bool
    regex: re.Pattern


# Characters that are special in a regex and need escaping when they appear
# literally in a gitignore pattern.
_REGEX_SPECIAL = set(".^$+{}()|")


def _translate(pattern: str, anchored: bool) -> str:
    """Translate a gitignore pattern body into a regular expression string.

    The returned regex is meant to be used with ``re.fullmatch`` against a
    normalised path. The translation handles ``*``, ``?``, ``**`` and
    character classes. Anything else is escaped so that it matches literally.
    """
    i = 0
    n = len(pattern)
    out: List[str] = []

    while i < n:
        c = pattern[i]
        if c == "*":
            # ``**`` matches across path separators; a single ``*`` does not.
            if i + 1 < n and pattern[i + 1] == "*":
                # Consume all consecutive stars.
                while i < n and pattern[i] == "*":
                    i += 1
                # ``**/`` at the start or middle matches zero or more leading
                # segments. ``/**`` at the end matches everything below.
                if i < n and pattern[i] == "/":
                    out.append("(?:.*/)?")
                    i += 1
                else:
                    out.append(".*")
            else:
                out.append("[^/]*")
                i += 1
        elif c == "?":
            out.append("[^/]")
            i += 1
        elif c == "[":
            j = i + 1
            if j < n and pattern[j] in ("!", "^"):
                j += 1
            if j < n and pattern[j] == "]":
                j += 1
            while j < n and pattern[j] != "]":
                j += 1
            if j >= n:
                # Unterminated class: treat ``[`` as a literal.
                out.append(re.escape("["))
                i += 1
            else:
                body = pattern[i + 1 : j]
                if body.startswith("!"):
                    body = "^" + body[1:]
                elif body.startswith("^"):
                    body = "\\" + body
                out.append("[" + body + "]")
                i = j + 1
        else:
            if c in _REGEX_SPECIAL:
                out.append(re.escape(c))
            else:
                out.append(c)
            i += 1

    # A pattern matches the whole path or, for a directory match, any path
    # below it. The ``(?:/.*)?`` suffix lets a rule like ``build`` match
    # ``build`` and ``build/x``, which is what git does for unanchored rules.
    # When the pattern is anchored, a leading ``^`` keeps the match at the
    # root; otherwise the pattern may begin at any segment boundary.
    if anchored:
        out.insert(0, "^")
    else:
        out.insert(0, "(?:^|.*/)")
    out.append("(?:/.*)?$")
    return "".join(out)


def _parse_rule(line: str) -> Optional[Rule]:
    """Parse a single non-blank, non-comment line into a Rule.

    Returns None for lines that should be skipped (blank or comment-only).
    """
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None

    negated = False
    if stripped.startswith("!"):
        negated = True
        stripped = stripped[1:]

    # A trailing backslash escapes the following character; handle the common
    # case of an escaped space or ``!`` by unescaping before parsing.
    body = _unescape(stripped)
    if not body:
        return None

    directory_only = body.endswith("/")
    if directory_only:
        body = body[:-1]

    # A pattern with a slash anywhere except a trailing one is anchored.
    anchored = "/" in body
    if body.startswith("/"):
        body = body[1:]

    if not body:
        return None

    regex = re.compile(_translate(body, anchored))
    return Rule(
        pattern=body,
        negated=negated,
        directory_only=directory_only,
        anchored=anchored,
        regex=regex,
    )


def _unescape(text: str) -> str:
    """Remove backslash escapes from a pattern body.

    Gitignore allows backslashes to escape special characters. We only need
    to unescape the characters that would otherwise change parsing: ``!``,
    ``#``, space, and backslash itself. Other backslashes are left alone so
    that they can be interpreted by the regex translator (which escapes
    regex-special characters itself).
    """
    out: List[str] = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c == "\\" and i + 1 < n:
            nxt = text[i + 1]
            if nxt in ("!", "#", " ", "\\"):
                out.append(nxt)
                i += 2
                continue
        out.append(c)
        i += 1
    return "".join(out)


def _normalise(path: str) -> str:
    """Return a canonical form of ``path`` for matching.

    Backslashes are converted to forward slashes, repeated slashes are
    collapsed, and leading/trailing slashes are removed. An empty result
    stands for the root directory.
    """
    if not path:
        return ""
    path = path.replace("\\", "/")
    parts = [p for p in path.split("/") if p not in ("", ".")]
    return "/".join(parts)


class IgnoreMatcher:
    """Compile a sequence of gitignore-style patterns and match paths.

    Example:
        matcher = IgnoreMatcher(["*.log", "!important.log", "build/"])
        matcher.is_ignored("app.log")        # True
        matcher.is_ignored("important.log")  # False
        matcher.is_ignored("build")          # True
        matcher.is_ignored("build/x")        # True
    """

    def __init__(self, lines: Iterable[str]):
        self.rules: List[Rule] = []
        for line in lines:
            rule = _parse_rule(line)
            if rule is not None:
                self.rules.append(rule)

    @classmethod
    def from_file(cls, path: str) -> "IgnoreMatcher":
        """Build a matcher from a file containing one pattern per line."""
        with open(path, "r", encoding="utf-8") as fh:
            return cls(fh)

    def is_ignored(self, path: str, is_dir: bool = False) -> bool:
        """Return True if ``path`` is ignored by the compiled rules.

        Args:
            path: A path relative to the root of the tree.
            is_dir: True if the path refers to a directory. Directory-only
                rules only match when this is True.

        The last matching rule wins, so negated rules can re-include a path
        that an earlier rule ignored.
        """
        normalised = _normalise(path)
        if not normalised:
            # The root itself is never ignored by path rules.
            return False
        ignored = False
        for rule in self.rules:
            if rule.regex.fullmatch(normalised):
                if rule.directory_only and not is_dir:
                    # A directory-only rule matches a directory, and also
                    # matches the contents of that directory (which are
                    # never directories themselves at the point of match).
                    # Only the exact directory path requires is_dir=True.
                    if normalised == rule.pattern:
                        continue
                ignored = not rule.negated
        return ignored

    def filter(self, paths: Sequence[str]) -> List[str]:
        """Return the subset of ``paths`` that are ignored.

        Directory-ness is inferred from a trailing slash on the input string.
        """
        result: List[str] = []
        for p in paths:
            is_dir = p.endswith("/")
            if self.is_ignored(p, is_dir=is_dir):
                result.append(p)
        return result


def match(path: str, patterns: Iterable[str], is_dir: bool = False) -> bool:
    """Convenience wrapper: compile ``patterns`` and test ``path``."""
    return IgnoreMatcher(patterns).is_ignored(path, is_dir=is_dir)
