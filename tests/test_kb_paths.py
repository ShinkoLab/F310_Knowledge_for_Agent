"""kb_paths: page_key / plugin_data_id / KBの位置の解決。"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _path  # noqa: F401
import kb_paths as kb


class PageKeyTest(unittest.TestCase):
    def test_conversion(self):
        base = "https://www.furukawaelectric.com/fitelnet/"
        self.assertEqual(kb.page_key(base + "ipoe/v6plus.html"), "ipoe__v6plus")
        self.assertEqual(kb.page_key(base + "product/container/lxc/ztp-script.html"),
                         "product__container__lxc__ztp-script")
        self.assertEqual(kb.page_key(base + "lbo/a+b.html"), "lbo__aplusb")

    def test_fragment_ignored(self):
        base = "https://www.furukawaelectric.com/fitelnet/ipoe/x.html"
        self.assertEqual(kb.page_key(base + "#sec2"), kb.page_key(base))


class PluginDataIdTest(unittest.TestCase):
    def with_repo(self, plugin, market):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        d = Path(tmp.name) / ".claude-plugin"
        d.mkdir()
        if plugin is not None:
            (d / "plugin.json").write_text(json.dumps({"name": plugin}), encoding="utf-8")
        if market is not None:
            (d / "marketplace.json").write_text(json.dumps({"name": market}), encoding="utf-8")
        return mock.patch.object(kb, "REPO", Path(tmp.name))

    def test_derived_from_definitions(self):
        with self.with_repo("f310-kb", "shinko-lab"):
            self.assertEqual(kb.plugin_data_id(), "f310-kb-shinko-lab")

    def test_rename_follows_and_symbols_replaced(self):
        with self.with_repo("My Plugin.v2", "mk/t"):
            self.assertEqual(kb.plugin_data_id(), "My-Plugin-v2-mk-t")

    def test_fallback_when_unreadable(self):
        with self.with_repo(None, None):
            self.assertEqual(kb.plugin_data_id(), kb.FALLBACK_ID)

    def test_fallback_when_key_missing_or_broken(self):
        with self.with_repo("x", None):
            self.assertEqual(kb.plugin_data_id(), kb.FALLBACK_ID)
        with self.with_repo("x", "y") as _:
            (kb.REPO / ".claude-plugin" / "plugin.json").write_text("{broken", encoding="utf-8")
            self.assertEqual(kb.plugin_data_id(), kb.FALLBACK_ID)

    def test_real_repo_definition_matches_default_kb(self):
        self.assertEqual(kb.DEFAULT_KB.name, kb.plugin_data_id())
        self.assertEqual(kb.DEFAULT_KB.parent, Path.home() / ".claude" / "plugins" / "data")


class KbRootTest(unittest.TestCase):
    def test_env_var_wins(self):
        with tempfile.TemporaryDirectory() as t, mock.patch.dict(os.environ, {"F310_KB_DIR": t}):
            self.assertEqual(kb.kb_root(), Path(t).resolve())
            self.assertEqual(kb.md_dir(), Path(t).resolve() / "md")
            self.assertEqual(kb.examples_dir(), Path(t).resolve() / "md" / "setting_examples")

    def test_default_when_unset_or_empty(self):
        with mock.patch.dict(os.environ, {"F310_KB_DIR": ""}):
            self.assertEqual(kb.kb_root(), kb.DEFAULT_KB)
        env = {k: v for k, v in os.environ.items() if k != "F310_KB_DIR"}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(kb.kb_root(), kb.DEFAULT_KB)

    def test_claude_plugin_data_is_never_read(self):
        # 他プラグインが書き出した値が環境に居ても、そこへKBを置いてはいけない
        with tempfile.TemporaryDirectory() as other:
            env = {k: v for k, v in os.environ.items() if k != "F310_KB_DIR"}
            env["CLAUDE_PLUGIN_DATA"] = other
            with mock.patch.dict(os.environ, env, clear=True):
                self.assertEqual(kb.kb_root(), kb.DEFAULT_KB)
                self.assertNotEqual(kb.kb_root(), Path(other).resolve())

    def test_is_built_needs_index_and_md(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            self.assertFalse(kb.is_built(root))
            (root / "md").mkdir()
            (root / "md" / "command_index.json").write_text("{}", encoding="utf-8")
            self.assertFalse(kb.is_built(root))
            (root / "md" / "a.md").write_text("x", encoding="utf-8")
            self.assertTrue(kb.is_built(root))

    def test_legacy_hint_silent_for_arbitrary_kb_dir(self):
        with tempfile.TemporaryDirectory() as t, mock.patch.dict(os.environ, {"F310_KB_DIR": t}):
            self.assertEqual(kb.legacy_hint(), "")


if __name__ == "__main__":
    unittest.main()
