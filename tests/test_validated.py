"""validated.local_status: 手元のKBが検証済みの版に追いついているかの判定。"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _path  # noqa: F401
import validated

VER = {
    "manuals": {"alpha.pdf": {"last_modified": "Mon, 05 Oct 2026 00:00:00 GMT", "bytes": 100, "pages": 3}},
    "examples": {"p__one.html": "aaa", "p__two.html": "bbb"},
    "example_count": 2,
}


class LocalStatusTest(unittest.TestCase):
    def make_kb(self, manuals=None, examples=None, params=True, built=True):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        patcher = mock.patch.dict(os.environ, {"F310_KB_DIR": str(root)})
        patcher.start()
        self.addCleanup(patcher.stop)
        if built:
            md = root / "md"
            md.mkdir()
            (md / "alpha.md").write_text("===== PAGE 1 =====\n", encoding="utf-8")
            entry = {"command": "x", "params": ""} if params else {"command": "x"}
            (md / "command_index.json").write_text(json.dumps({"commands": [entry]}), encoding="utf-8")
        state = {"manuals": manuals if manuals is not None else
                 {"alpha.pdf": {"last_modified": "Mon, 05 Oct 2026 00:00:00 GMT", "bytes": 100}},
                 "examples": examples if examples is not None else
                 {"p__one.html": {"sha256": "aaa"}, "p__two.html": {"sha256": "bbb"}}}
        (root / ".build.json").write_text(json.dumps(state), encoding="utf-8")

    def test_up_to_date(self):
        self.make_kb()
        self.assertEqual(validated.local_status(VER), [])

    def test_not_built(self):
        self.make_kb(built=False)
        self.assertEqual(validated.local_status(VER), ["知識ベースが未構築です"])

    def test_old_manual(self):
        self.make_kb(manuals={"alpha.pdf": {"last_modified": "Tue, 26 May 2026 00:00:00 GMT", "bytes": 90}})
        out = validated.local_status(VER)
        self.assertEqual(len(out), 1)
        self.assertIn("alpha", out[0])

    def test_manual_without_record_counts_as_behind(self):
        # build.py の網羅性チェック（manual_changed）は記録なしを「違う」と見なさないが、
        # 手元の鮮度の判定では、記録が無ければ追いついているとは言えない
        self.make_kb(manuals={})
        self.assertEqual(len(validated.local_status(VER)), 1)

    def test_examples_without_fingerprint(self):
        # 2.3.0 より前のKBは設定例の sha256 を記録していない
        self.make_kb(examples={"p__one.html": {"bytes": 1}, "p__two.html": {"bytes": 1}})
        out = validated.local_status(VER)
        self.assertEqual(len(out), 1)
        self.assertIn("2 件", out[0])

    def test_example_fingerprint_differs(self):
        self.make_kb(examples={"p__one.html": {"sha256": "aaa"}, "p__two.html": {"sha256": "zzz"}})
        out = validated.local_status(VER)
        self.assertEqual(len(out), 1)
        self.assertIn("1 件の本文", out[0])

    def test_old_index_format(self):
        self.make_kb(params=False)
        out = validated.local_status(VER)
        self.assertEqual(len(out), 1)
        self.assertIn("旧形式", out[0])


if __name__ == "__main__":
    unittest.main()
