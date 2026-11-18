import unittest

from simple_ignore_match import IgnoreMatcher, Rule, match


class TestBasicMatching(unittest.TestCase):
    def test_simple_glob(self):
        m = IgnoreMatcher(["*.log"])
        self.assertTrue(m.is_ignored("app.log"))
        self.assertTrue(m.is_ignored("nested/app.log"))
        self.assertFalse(m.is_ignored("app.txt"))

    def test_question_mark(self):
        m = IgnoreMatcher(["file?.txt"])
        self.assertTrue(m.is_ignored("file1.txt"))
        self.assertFalse(m.is_ignored("file10.txt"))

    def test_character_class(self):
        m = IgnoreMatcher(["file[0-9].txt"])
        self.assertTrue(m.is_ignored("file3.txt"))
        self.assertFalse(m.is_ignored("filex.txt"))

    def test_negated_class(self):
        m = IgnoreMatcher(["file[!0-9].txt"])
        self.assertTrue(m.is_ignored("filex.txt"))
        self.assertFalse(m.is_ignored("file3.txt"))


class TestAnchoring(unittest.TestCase):
    def test_unanchored_matches_anywhere(self):
        m = IgnoreMatcher(["build"])
        self.assertTrue(m.is_ignored("build"))
        self.assertTrue(m.is_ignored("src/build"))
        self.assertTrue(m.is_ignored("src/build/output.o"))

    def test_leading_slash_anchors(self):
        m = IgnoreMatcher(["/build"])
        self.assertTrue(m.is_ignored("build"))
        self.assertFalse(m.is_ignored("src/build"))

    def test_internal_slash_anchors(self):
        m = IgnoreMatcher(["src/build"])
        self.assertTrue(m.is_ignored("src/build"))
        self.assertFalse(m.is_ignored("other/src/build"))


class TestDirectoryOnly(unittest.TestCase):
    def test_trailing_slash_requires_directory(self):
        m = IgnoreMatcher(["cache/"])
        self.assertTrue(m.is_ignored("cache", is_dir=True))
        self.assertFalse(m.is_ignored("cache", is_dir=False))
        self.assertTrue(m.is_ignored("cache/data", is_dir=False))

    def test_directory_contents_ignored(self):
        m = IgnoreMatcher(["logs/"])
        self.assertTrue(m.is_ignored("logs", is_dir=True))
        self.assertTrue(m.is_ignored("logs/app.log", is_dir=False))


class TestDoubleStar(unittest.TestCase):
    def test_double_star_matches_zero_segments(self):
        m = IgnoreMatcher(["**/foo"])
        self.assertTrue(m.is_ignored("foo"))
        self.assertTrue(m.is_ignored("a/foo"))
        self.assertTrue(m.is_ignored("a/b/foo"))

    def test_double_star_in_middle(self):
        m = IgnoreMatcher(["a/**/b"])
        self.assertTrue(m.is_ignored("a/b"))
        self.assertTrue(m.is_ignored("a/x/b"))
        self.assertTrue(m.is_ignored("a/x/y/b"))
        self.assertFalse(m.is_ignored("a/x/c"))

    def test_double_star_at_end(self):
        m = IgnoreMatcher(["logs/**"])
        self.assertTrue(m.is_ignored("logs/a"))
        self.assertTrue(m.is_ignored("logs/a/b"))


class TestPrecedence(unittest.TestCase):
    def test_later_rule_wins(self):
        m = IgnoreMatcher(["*.log", "!important.log"])
        self.assertTrue(m.is_ignored("app.log"))
        self.assertFalse(m.is_ignored("important.log"))

    def test_negation_can_be_negated_back(self):
        m = IgnoreMatcher(["*.log", "!important.log", "important.log"])
        self.assertTrue(m.is_ignored("important.log"))

    def test_negation_of_directory_contents(self):
        m = IgnoreMatcher(["build/", "!build/keep.txt"])
        self.assertTrue(m.is_ignored("build", is_dir=True))
        self.assertTrue(m.is_ignored("build/other.txt"))
        self.assertFalse(m.is_ignored("build/keep.txt"))


class TestCommentsAndBlankLines(unittest.TestCase):
    def test_comments_ignored(self):
        m = IgnoreMatcher(["# comment", "", "  ", "*.tmp"])
        self.assertTrue(m.is_ignored("x.tmp"))
        self.assertFalse(m.is_ignored("# comment"))

    def test_escaped_hash_is_literal(self):
        m = IgnoreMatcher(["\\#literal"])
        self.assertTrue(m.is_ignored("#literal"))


class TestNormalisation(unittest.TestCase):
    def test_repeated_slashes(self):
        m = IgnoreMatcher(["a/b"])
        self.assertTrue(m.is_ignored("a//b"))
        self.assertTrue(m.is_ignored("./a/b"))

    def test_backslashes_become_slashes(self):
        m = IgnoreMatcher(["a/b"])
        self.assertTrue(m.is_ignored("a\\b"))

    def test_root_is_never_ignored(self):
        m = IgnoreMatcher(["*"])
        self.assertFalse(m.is_ignored(""))
        self.assertFalse(m.is_ignored("/"))


class TestFilter(unittest.TestCase):
    def test_filter_returns_ignored_paths(self):
        m = IgnoreMatcher(["*.log"])
        got = m.filter(["a.log", "b.txt", "c.log"])
        self.assertEqual(got, ["a.log", "c.log"])

    def test_filter_infers_directory_from_trailing_slash(self):
        m = IgnoreMatcher(["cache/"])
        got = m.filter(["cache/", "cache/file"])
        self.assertEqual(got, ["cache/", "cache/file"])


class TestConvenienceFunction(unittest.TestCase):
    def test_match(self):
        self.assertTrue(match("x.log", ["*.log"]))
        self.assertFalse(match("x.txt", ["*.log"]))
        self.assertTrue(match("build", ["build/"], is_dir=True))


class TestRuleDataclass(unittest.TestCase):
    def test_rule_fields(self):
        m = IgnoreMatcher(["!foo/"])
        self.assertEqual(len(m.rules), 1)
        rule = m.rules[0]
        self.assertIsInstance(rule, Rule)
        self.assertEqual(rule.pattern, "foo")
        self.assertTrue(rule.negated)
        self.assertTrue(rule.directory_only)
        self.assertFalse(rule.anchored)


if __name__ == "__main__":
    unittest.main()
