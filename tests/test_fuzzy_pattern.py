"""lookup.fuzzy_pattern: 英数字⇔日本語の境目の空白ゆれ吸収。"""
import re
import unittest

import _path  # noqa: F401
import lookup


def match(query, text):
    return re.search(lookup.fuzzy_pattern(query), text, re.I) is not None


class FuzzyPatternTest(unittest.TestCase):
    def test_space_between_ascii_and_japanese_both_directions(self):
        self.assertTrue(match("v6プラス", "v6 プラス"))
        self.assertTrue(match("v6 プラス", "v6プラス"))
        self.assertTrue(match("v6プラス", "v6プラス"))
        self.assertTrue(match("v6 プラス", "v6 プラス"))

    def test_japanese_then_ascii(self):
        self.assertTrue(match("設定ip", "設定 ip"))
        self.assertTrue(match("設定 ip", "設定ip"))

    def test_fullwidth_alnum_equals_halfwidth(self):
        self.assertTrue(match("ｖ６プラス", "v6プラス"))
        self.assertTrue(match("ｖ６プラス", "ｖ６プラス"))

    @unittest.skip("既知の片方向: 半角で入力した語は、本文側の全角英数字に当たらない"
                   "（全角入力→半角本文のみ吸収。fuzzy_pattern が半角 ch を NFKC 逆変換しないため）")
    def test_halfwidth_query_matches_fullwidth_text(self):
        self.assertTrue(match("v6プラス", "ｖ６プラス"))

    def test_regex_meta_is_untouched(self):
        for q in ("ip.*addr", "^show", "a|b", "x[0-9]", "ip(v4)", "a+"):
            self.assertEqual(lookup.fuzzy_pattern(q), q)

    def test_leading_trailing_whitespace_preserved(self):
        self.assertTrue(match("no ", "no ip"))
        self.assertFalse(match("no ", "noip"))
        self.assertTrue(match(" ip", "show ip"))
        self.assertFalse(match(" ip", "ipv4"))

    def test_english_word_gap_keeps_whitespace(self):
        self.assertTrue(match("ip address", "ip address"))
        self.assertTrue(match("ip address", "ip   address"))
        self.assertFalse(match("ip address", "ipaddress"))

    def test_no_space_between_ascii_not_inserted(self):
        self.assertFalse(match("ipaddr", "ip addr"))

    def test_blank_input_is_escaped_as_is(self):
        self.assertEqual(lookup.fuzzy_pattern("  "), re.escape("  "))

    def test_result_always_compiles(self):
        for q in ("v6プラス", "ｖ６ プラス", "a b c", "日本語 ABC 設定"):
            re.compile(lookup.fuzzy_pattern(q))


if __name__ == "__main__":
    unittest.main()
