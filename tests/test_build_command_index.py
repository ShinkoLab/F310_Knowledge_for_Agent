"""build_command_index: コマンド名抽出・mode打ち切り・パラメータ表の割当・ページヘッダ除去。

入力はすべて合成データ（実マニュアルの文章は使わない）。parse() はKBのmdを読むので、
$F310_KB_DIR を一時ディレクトリに向けて小さなmdを置く。
"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _path  # noqa: F401
import build_command_index as bci


class NameNormalizeTest(unittest.TestCase):
    def test_section_number_and_mode_paren_removed(self):
        self.assertEqual(bci.normalize_name("10.10.1 ip address"), "ip address")
        self.assertEqual(bci.normalize_name("ip address （基本設定モード）"), "ip address")
        self.assertEqual(bci.normalize_name("ip address (基本設定モード)"), "ip address")

    def test_japanese_qualifier_is_kept_as_part_of_name(self):
        name = bci.normalize_name("access-list（IPv4 標準設定）")
        self.assertEqual(name, "access-list（IPv4 標準設定）")
        self.assertTrue(bci.is_command_name(name))

    def test_is_command_name(self):
        self.assertTrue(bci.is_command_name("set mtu"))
        self.assertFalse(bci.is_command_name(""))
        self.assertFalse(bci.is_command_name("V01.00"))          # 版数のみ
        self.assertFalse(bci.is_command_name("6.1.54"))
        self.assertFalse(bci.is_command_name("説明文です"))       # 日本語
        self.assertFalse(bci.is_command_name("show 設定。"))      # 日本語混在
        self.assertFalse(bci.is_command_name("x" * 81))

    def test_name_from_syntax_takes_leading_keywords(self):
        self.assertEqual(bci.name_from_syntax("alpha cmd <value> [x]"), "alpha cmd")
        self.assertEqual(bci.name_from_syntax("no alpha cmd"), "alpha cmd")   # 否定形のnoは除く
        self.assertEqual(bci.name_from_syntax("\n  beta {a|b}"), "beta")
        self.assertEqual(bci.name_from_syntax(""), "")
        self.assertEqual(bci.name_from_syntax("<value> only"), "")


class FindCommandNameTest(unittest.TestCase):
    def find(self, text):
        lines = text.split("\n")
        return bci.find_command_name(lines, lines.index("【機能】"))

    def test_plain(self):
        self.assertEqual(self.find("1.1\nalpha cmd\n\n【機能】\nx"), "alpha cmd")

    def test_version_heading_is_skipped(self):
        for mark in ("【対応ファームウェアバージョン】", "【対象ファームウェアバージョン】"):
            t = f"alpha cmd\n\n{mark}\n\nV01.00\n\n【機能】\nx"
            self.assertEqual(self.find(t), "alpha cmd", mark)

    def test_mode_paren_and_secno_removed_when_scanning(self):
        self.assertEqual(self.find("10.2.3 alpha cmd（基本設定モード）\n【機能】\nx"), "alpha cmd")

    def test_stops_at_previous_section_marker(self):
        # 直前が別コマンドの終端（【未設定時】の本文）なら名前なし
        self.assertIsNone(self.find("【未設定時】\n\n無効\n\n【機能】\nx"))

    def test_page_markers_and_blanks_are_skipped(self):
        self.assertEqual(self.find("alpha cmd\n\n===== PAGE 9 =====\n\n【機能】\nx"), "alpha cmd")


class FirstParagraphTest(unittest.TestCase):
    def test_cut_at_blank_line(self):
        lines = ["", "基本設定モード", "インターフェース設定モード", "", "余計な段落"]
        self.assertEqual(bci.first_paragraph(lines),
                         "基本設定モード\nインターフェース設定モード")

    def test_wrap_across_blank_line_is_joined(self):
        lines = ["", "基本設定モード、甲インタフェー", "", "ス設定モード", "", "余計な段落"]
        self.assertEqual(bci.first_paragraph(lines),
                         "基本設定モード、甲インタフェー\nス設定モード")

    def test_unterminated_mode_stops_at_param_head(self):
        lines = ["甲のコマンドレベル", "", "パラメータ", "設定内容"]
        self.assertEqual(bci.first_paragraph(lines), "甲のコマンドレベル")

    def test_cut_at_page_marker(self):
        lines = ["基本設定モード", "===== PAGE 3 =====", "続き"]
        self.assertEqual(bci.first_paragraph(lines), "基本設定モード")

    def test_empty(self):
        self.assertEqual(bci.first_paragraph([]), "")


TABLE = ["パラメータ", "設定内容", "設定範囲", "省略時", "", "{n}", "説明です。", "1 ～6", "常時"]


def table_lines(first_cell):
    return [ln.replace("{n}", first_cell) for ln in TABLE]


class ParamTableTest(unittest.TestCase):
    def test_find_param_tables_ranges(self):
        lines = ["前文", ""] + table_lines("foo") + ["", "【説明】", "本文"]
        (s, e), = bci.find_param_tables(lines)
        self.assertEqual(lines[s], "パラメータ")
        self.assertTrue(e <= lines.index("【説明】"))

    def test_consecutive_tables_are_split(self):
        lines = table_lines("foo") + [""] + table_lines("bar")
        self.assertEqual(len(bci.find_param_tables(lines)), 2)

    def test_table_ends_at_page_break(self):
        lines = table_lines("foo") + ["===== PAGE 4 =====", "次ページ"]
        (s, e), = bci.find_param_tables(lines)
        self.assertEqual(lines[e], "===== PAGE 4 =====")

    def test_header_word_alone_is_not_a_table(self):
        self.assertEqual(bci.find_param_tables(["パラメータ", "別の語", "x"]), [])

    def test_table_first_cell_skips_header_words(self):
        self.assertEqual(bci.table_first_cell("\n".join(table_lines("foo"))), "foo")

    def test_squash(self):
        self.assertEqual(bci.squash("a <b> [c] {d|e}, （f）"), "abcdef")


def rec(page, syn, heading=True, named=True, tables=()):
    return {"named": named, "heading": heading, "syn": bci.squash(syn), "page": page,
            "tables": list(tables), "params": []}


class AssignTablesTest(unittest.TestCase):
    def test_own_block_table(self):
        recs = [rec(1, "alpha <value>", tables=[(1, "T-value")])]
        bci.assign_tables(recs)
        self.assertEqual(recs[0]["params"], ["T-value"])

    def test_spilled_tables_go_to_owners_by_first_cell(self):
        # 表が2つとも後続コマンド(beta)のブロックに出る。先頭セルが構文に含まれる側が持ち主。
        recs = [
            rec(1, "alpha <value>"),
            rec(1, "beta <name>", tables=[(2, "value\n..."), (2, "name\n...")]),
        ]
        bci.assign_tables(recs)
        self.assertEqual(recs[0]["params"], ["value\n..."])
        self.assertEqual(recs[1]["params"], ["name\n..."])

    def test_spilled_into_third_command(self):
        recs = [
            rec(1, "alpha <value>"),
            rec(1, "beta <name>"),
            rec(2, "gamma", heading=False, tables=[(2, "value\n..."), (2, "name\n...")]),
        ]
        bci.assign_tables(recs)
        self.assertEqual(recs[0]["params"], ["value\n..."])
        self.assertEqual(recs[1]["params"], ["name\n..."])
        self.assertEqual(recs[2]["params"], [])

    def test_no_syntax_hit_falls_back_to_queue_head(self):
        recs = [rec(1, "alpha <x>"), rec(1, "beta <y>", tables=[(1, "zzz\n...")])]
        bci.assign_tables(recs)
        self.assertEqual(recs[0]["params"], ["zzz\n..."])

    def test_too_far_pages_are_not_candidates(self):
        recs = [rec(1, "alpha <value>"), rec(9, "beta <name>", tables=[(9, "value\n...")])]
        bci.assign_tables(recs)
        self.assertEqual(recs[0]["params"], [])
        self.assertEqual(recs[1]["params"], ["value\n..."])

    def test_unnamed_record_never_owns(self):
        recs = [rec(1, "legend <x>", named=False, tables=[(1, "x\n...")])]
        bci.assign_tables(recs)
        self.assertEqual(recs[0]["params"], [])

    def test_heading_less_command_can_receive_table(self):
        recs = [rec(1, "enable <level>", heading=False),
                rec(1, "beta", heading=False, tables=[(1, "level\n...")])]
        bci.assign_tables(recs)
        self.assertEqual(recs[0]["params"], ["level\n..."])


def section(*lines):
    return "\n".join(lines)


# 合成マニュアル。3コマンド:
#   alpha cmd : 版数見出し付き・modeが2行+後続段落・表が後続(beta)のブロックへ出る・説明がページを跨ぐ
#   beta cmd  : 自分の表を持つ
#   (無名)    : 直前が別コマンドの終端で名前が取れない → 入力形式の先頭語から補完
SYNTH = section(
    "===== PAGE 1 =====",
    "",
    "1.1",
    "alpha cmd",
    "",
    "【対応ファームウェアバージョン】",
    "",
    "V01.00",
    "",
    "【機能】",
    "",
    "alphaの機能",
    "",
    "【入力形式】",
    "",
    "alpha cmd <value>",
    "no alpha cmd",
    "",
    "【パラメータ】",
    "",
    "【動作モード】",
    "",
    "基本設定モード",
    "インターフェース設定モード",
    "",
    "備考の段落",
    "",
    "【説明】",
    "",
    "前半の説明。",
    "",
    "===== PAGE 2 =====",
    "",
    "2",
    "",
    "コマンドリファレンス - 第1 章 設定",
    "",
    "第1 章 設定",
    "",
    "1.1 節見出し",
    "",
    "後半の説明。",
    "",
    "【未設定時】",
    "",
    "無効",
    "",
    "1.2",
    "beta cmd",
    "",
    "【機能】",
    "",
    "betaの機能",
    "",
    "【入力形式】",
    "",
    "beta cmd <name>",
    "",
    "【パラメータ】",
    "",
    "【動作モード】",
    "",
    "基本設定モード",
    "",
    *table_lines("value"),    # alpha の表が beta のブロックに出ている
    "",
    *table_lines("name"),
    "",
    "【未設定時】",
    "",
    "無効",
    "",
    "【機能】",
    "",
    "名前が取れないコマンド",
    "",
    "【入力形式】",
    "",
    "gamma cmd <z>",
    "",
    "【動作モード】",
    "",
    "特権モード",
    "",
)


class ParseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        md = Path(cls.tmp.name) / "md"
        md.mkdir()
        (md / "cmd_refe_config.md").write_text(SYNTH, encoding="utf-8")
        with mock.patch.dict(os.environ, {"F310_KB_DIR": cls.tmp.name}):
            cls.entries = bci.parse("cmd_refe_config", "構成定義編")
        cls.by = {e["command"]: e for e in cls.entries}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_commands_found(self):
        self.assertEqual([e["command"] for e in self.entries],
                         ["alpha cmd", "beta cmd", "gamma cmd"])

    def test_entry_schema(self):
        self.assertEqual(set(self.by["alpha cmd"]),
                         {"command", "manual", "category", "page", "function", "syntax",
                          "mode", "params", "description", "default", "ref"})
        a = self.by["alpha cmd"]
        self.assertEqual((a["manual"], a["category"], a["page"], a["ref"]),
                         ("cmd_refe_config", "構成定義編", 1, "cmd_refe_config.pdf p.1"))
        self.assertEqual(a["function"], "alphaの機能")
        self.assertEqual(a["syntax"], "alpha cmd <value>\nno alpha cmd")

    def test_mode_is_first_paragraph_only(self):
        self.assertEqual(self.by["alpha cmd"]["mode"], "基本設定モード\nインターフェース設定モード")
        self.assertNotIn("備考", self.by["alpha cmd"]["mode"])

    def test_page_header_removed_from_description(self):
        d = self.by["alpha cmd"]["description"]
        self.assertEqual(d, "前半の説明。\n後半の説明。")

    def test_next_command_header_not_in_previous_block(self):
        a = self.by["alpha cmd"]
        self.assertEqual(a["default"], "無効")
        for f in ("description", "default", "mode"):
            self.assertNotIn("beta cmd", a[f])
            self.assertNotIn("1.2", a[f])

    def test_spilled_tables_assigned_to_owners(self):
        self.assertTrue(self.by["alpha cmd"]["params"].startswith("パラメータ"))
        self.assertIn("value", self.by["alpha cmd"]["params"])
        self.assertNotIn("name", self.by["alpha cmd"]["params"])
        self.assertIn("name", self.by["beta cmd"]["params"])
        self.assertNotIn("value", self.by["beta cmd"]["params"])
        self.assertEqual(self.by["gamma cmd"]["params"], "")

    def test_table_not_leaked_into_mode(self):
        self.assertEqual(self.by["beta cmd"]["mode"], "基本設定モード")

    def test_name_completed_from_syntax(self):
        g = self.by["gamma cmd"]
        self.assertEqual(g["mode"], "特権モード")
        self.assertEqual(g["syntax"], "gamma cmd <z>")


class ExtractSectionsTest(unittest.TestCase):
    def test_sections_and_page_markers(self):
        block = ["【機能】", "f", "【入力形式】", "a", "", "", "b", "===== PAGE 2 =====", "c"]
        out = bci.extract_sections(block)
        self.assertEqual(out["機能"], "f")
        self.assertEqual(out["入力形式"], "a\nb\nc")


if __name__ == "__main__":
    unittest.main()
