"""gen_examples: 設定例HTML→md のリニアライザ。入力HTMLはすべて合成。"""
import unittest

import _path  # noqa: F401
import gen_examples as ge

URL = "https://www.furukawaelectric.com/fitelnet/product/f310/sample.html"


def page(body):
    return f"<html><head><title>t</title></head><body>{body}</body></html>"


class MarkerPageTest(unittest.TestCase):
    HTML = page(
        '<div class="title">サンプル設定</div>'
        '<div class="summary">概要の文です。</div>'
        '<div class="envname">センタ側</div>'
        "<pre>hostname A\n!comment\n interface lan 1</pre>"
        '<div class="additional_title">補足・注意点</div>'
        '<div class="additional_detail">注意その1</div>'
        '<div class="pagetop">top</div><p>フッタ側の段落</p>'
    )

    def test_structure_in_dom_order(self):
        md = ge.linearize(self.HTML, URL)
        order = [md.index(s) for s in
                 ("## サンプル設定", "概要の文です。", "### センタ側", "```", "## 補足・注意点", "注意その1")]
        self.assertEqual(order, sorted(order))

    def test_code_indent_kept(self):
        md = ge.linearize(self.HTML, URL)
        self.assertIn("hostname A\n!comment\n interface lan 1", md)

    def test_marker_page_ignores_plain_p(self):
        md = ge.linearize(self.HTML, URL)
        self.assertNotIn("フッタ側の段落", md)
        md2 = ge.linearize(page('<div class="title">T</div><div class="summary">S</div>'
                                "<p>素の段落</p>"), URL)
        self.assertNotIn("素の段落", md2)

    def test_duplicate_pre_dropped(self):
        h = page('<div class="title">T</div><pre>same\ncfg</pre><pre>same\ncfg</pre>')
        self.assertEqual(ge.linearize(h, URL).count("same\ncfg"), 1)

    def test_empty_heading_removed(self):
        h = page('<div class="title">残る</div><div class="summary">本文</div>'
                 '<div class="envname">空の環境</div>')
        md = ge.linearize(h, URL)
        self.assertIn("## 残る", md)
        self.assertNotIn("空の環境", md)


class ProseFallbackTest(unittest.TestCase):
    def test_p_and_li_are_collected(self):
        h = page("<main><h2>手順</h2><p>説明の段落。</p><ul><li>項目A</li><li>項目B</li></ul></main>")
        md = ge.linearize(h, URL)
        self.assertIn("## 手順", md)
        self.assertIn("説明の段落。", md)
        self.assertIn("- 項目A\n- 項目B", md)

    def test_narrowed_to_main_excluding_header_nav(self):
        h = page('<header><p>ナビの段落</p><ul><li>ナビ項目</li></ul></header>'
                 "<main><h2>手順</h2><p>本文の段落</p></main>"
                 "<footer><p>フッタの段落</p></footer>")
        md = ge.linearize(h, URL)
        self.assertIn("本文の段落", md)
        self.assertNotIn("ナビ", md)
        self.assertNotIn("フッタの段落", md)

    def test_main_narrowing_happens_before_footer_cut(self):
        # フッタ切り落としマーカーがヘッダ側（<main> より前）に在っても、本文は残りナビは混ざらない
        h = page('<header>FITELnetサイトマップ<p>ナビの段落</p></header>'
                 "<main><h2>手順</h2><p>本文の段落</p></main>")
        md = ge.linearize(h, URL)
        self.assertIn("本文の段落", md)
        self.assertNotIn("ナビの段落", md)

    def test_footer_marker_inside_main_cuts_rest(self):
        h = page("<main><p>本文の段落</p><div>ページの先頭へ</div><p>関連リンク段落</p></main>")
        md = ge.linearize(h, URL)
        self.assertIn("本文の段落", md)
        self.assertNotIn("関連リンク段落", md)

    def test_p_inside_table_not_duplicated(self):
        h = page("<main><table><tr><td>キー</td><td><p>値の段落</p></td></tr>"
                 "<tr><td>k2</td><td>v2</td></tr></table></main>")
        self.assertEqual(ge.linearize(h, URL).count("値の段落"), 1)


class TableAsCodeTest(unittest.TestCase):
    def test_single_cell_with_br_becomes_code(self):
        t = "<table><tr><th>ラベル</th></tr><tr><td>line1<br>\n  line2<br>\nline3</td></tr></table>"
        label, code = ge.table_as_code(t)
        self.assertEqual(label, "ラベル")
        self.assertEqual(code, "line1\n  line2\nline3")

    def test_without_th_label_is_empty(self):
        label, code = ge.table_as_code("<table><tr><td>a<br>b</td></tr></table>")
        self.assertEqual((label, code), ("", "a\nb"))

    def test_ordinary_tables_are_not_code(self):
        self.assertIsNone(ge.table_as_code(
            "<table><tr><td>a</td><td>b<br>c</td></tr></table>"))      # セルが2つ
        self.assertIsNone(ge.table_as_code(
            "<table><tr><td>one line only</td></tr></table>"))          # <br>なし
        self.assertIsNone(ge.table_as_code("<table><tr><td>x<br></td></tr></table>"))  # 1行だけ

    def test_linearize_emits_fence_not_joined_line(self):
        h = page('<div class="title">T</div><table><tr><td>a 1<br>b 2<br>c 3</td></tr></table>')
        md = ge.linearize(h, URL)
        self.assertIn("```\na 1\nb 2\nc 3\n```", md)

    def test_ordinary_table_is_markdown(self):
        h = page('<div class="title">T</div>'
                 "<table><tr><th>項目</th><th>値</th></tr><tr><td>a</td><td>1</td></tr>"
                 "<tr><td>b</td><td>2</td></tr></table>")
        md = ge.linearize(h, URL)
        self.assertIn("| 項目 | 値 |\n|---|---|\n| a | 1 |\n| b | 2 |", md)


class LboLabelTest(unittest.TestCase):
    def test_profile_labels_from_id(self):
        self.assertEqual(ge.pre_label("command_app_dns_teams", None),
                         "**DNS snooping ／ app-profile（新コマンド体系）**:")
        self.assertEqual(ge.pre_label("command_dns_teams", None),
                         "**DNS snooping ／ lbo-profile（旧コマンド体系）**:")
        self.assertEqual(ge.pre_label("command_lbo_http_x", None),
                         "**HTTP snooping ／ lbo-profile（旧コマンド体系）**:")

    def test_side_labels(self):
        self.assertEqual(ge.pre_label("command_center", None), "**センタ側**:")
        self.assertEqual(ge.pre_label("command_kyoten-1", None), "**拠点1側**:")
        self.assertEqual(ge.pre_label("command_CENTERA", None), "**センタA側**:")
        self.assertEqual(ge.pre_label("command_center_2", None), "**センタ2側**:")

    def test_side_label_not_duplicated_when_heading_has_it(self):
        self.assertIsNone(ge.pre_label("command_center", "センタ側の設定"))
        self.assertIsNone(ge.pre_label("command_kyoten", "拠点側"))

    def test_unrelated_suffix_is_not_a_side(self):
        self.assertIsNone(ge.pre_label("command_centers", None))
        self.assertIsNone(ge.pre_label("command_kyotens", None))
        self.assertIsNone(ge.pre_label("other", None))
        self.assertIsNone(ge.pre_label(None, None))

    def test_linearize_labels_textarea_pre(self):
        h = page('<div class="title">LBO</div>'
                 '<textarea id="command_app_dns_teams"><pre>cfg A</pre></textarea>'
                 '<textarea id="command_dns_teams"><pre>cfg B</pre></textarea>')
        md = ge.linearize(h, URL)
        a = md.index("**DNS snooping ／ app-profile（新コマンド体系）**:")
        b = md.index("**DNS snooping ／ lbo-profile（旧コマンド体系）**:")
        self.assertLess(a, md.index("cfg A"))
        self.assertLess(md.index("cfg A"), b)
        self.assertLess(b, md.index("cfg B"))


class HelperTest(unittest.TestCase):
    def test_outname_and_category(self):
        base = "https://www.furukawaelectric.com/fitelnet/"
        self.assertEqual(ge.outname(base + "ipoe/v6plus.html"), "ipoe_v6plus.md")
        self.assertEqual(ge.outname(base + "cloud-connect/aws.html"), "cloud_aws.md")
        self.assertEqual(ge.outname(base + "product/f310/a+b.html"), "f310_aplusb.md")
        self.assertEqual(ge.outname(base + "product/container/lxc/ztp.html"), "container_ztp.md")
        self.assertEqual(ge.category(base + "product/container/lxc/ztp.html"), "コンテナ（LXC）")
        self.assertEqual(ge.category(base + "ipoe/v6plus.html"), "IPoE / IPv6インターネット")
        self.assertEqual(ge.category(base + "unknown/x.html"), "その他")

    def test_abs_url(self):
        base = "https://example.test/a/b/page.html"
        self.assertEqual(ge.abs_url("img/x.png", base), "https://example.test/a/b/img/x.png")
        self.assertEqual(ge.abs_url("../x.png", base), "https://example.test/a/x.png")
        self.assertEqual(ge.abs_url("//cdn.test/x.png", base), "https://cdn.test/x.png")
        self.assertEqual(ge.abs_url("/x.png", base), ge.SITE + "/x.png")
        self.assertEqual(ge.abs_url("", base), "")

    def test_strip_js_artifact(self):
        self.assertEqual(ge.strip_js("見出し'); subwindow.document.write('"), "見出し")


if __name__ == "__main__":
    unittest.main()
