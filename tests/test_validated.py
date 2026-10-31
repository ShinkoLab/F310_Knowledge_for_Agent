"""validated.local_status: 手元のKBが検証済みの版に追いついているかの判定。"""
import contextlib
import io
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
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

    def test_newer_manual_than_validated_is_not_old(self):
        # サイトが先に改版し、それを取り込んだKB。検証済みの版と違っても古くはない
        self.make_kb(manuals={"alpha.pdf": {"last_modified": "Fri, 01 Jan 2027 00:00:00 GMT", "bytes": 120}})
        self.assertEqual(validated.local_status(VER), [])

    def test_unparsable_date_falls_back_to_difference(self):
        self.make_kb(manuals={"alpha.pdf": {"last_modified": "?", "bytes": 90}})
        self.assertEqual(len(validated.local_status(VER)), 1)

    def test_example_fingerprint_difference_is_not_judged_offline(self):
        # 指紋には新旧の順が無いので、ネットワーク無しでは古いと言えない（check_updates が見る）
        self.make_kb(examples={"p__one.html": {"sha256": "aaa"}, "p__two.html": {"sha256": "zzz"}})
        self.assertEqual(validated.local_status(VER), [])

    def test_old_index_format(self):
        self.make_kb(params=False)
        out = validated.local_status(VER)
        self.assertEqual(len(out), 1)
        self.assertIn("旧形式", out[0])


class ContactNoteTest(unittest.TestCase):
    NOW = datetime(2026, 12, 31, tzinfo=timezone.utc)

    def test_no_record(self):
        self.assertIn("記録がありません", validated.contact_note({}, self.NOW))

    def test_recent(self):
        self.assertEqual(validated.contact_note({"last_fetch": "2026-12-20T00:00:00+00:00"}, self.NOW), "")

    def test_old(self):
        note = validated.contact_note({"last_fetch": "2026-10-01T00:00:00+00:00"}, self.NOW)
        self.assertIn("91 日", note)

    def test_latest_of_fetch_and_check_is_used(self):
        state = {"last_fetch": "2026-10-01T00:00:00+00:00", "last_checked": "2026-12-30T00:00:00+00:00"}
        self.assertEqual(validated.contact_note(state, self.NOW), "")

    def test_broken_value_is_ignored(self):
        self.assertIn("記録がありません", validated.contact_note({"last_fetch": "yesterday"}, self.NOW))


class CheckUpdatesTest(unittest.TestCase):
    """ネットワークは偽物（httpget.get の差し替え）。サイト・検証済みの版・手元のKBの組み合わせを見る。"""
    URL = "https://www.furukawaelectric.com/fitelnet/p/one.html"
    LM = "Mon, 05 Oct 2026 00:00:00 GMT"
    BODY = b"<main>hello</main>"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        fp = validated.fetch_examples.fingerprint(self.BODY)
        self.fp = fp
        ver = {"manuals": {"alpha.pdf": {"last_modified": self.LM, "bytes": 100, "pages": 1}},
               "examples": {"p__one.html": fp}, "example_count": 1}
        vfile = self.root / "validated.json"
        vfile.write_text(json.dumps(ver), encoding="utf-8")
        kbdir = self.root / "kb"
        (kbdir / "md").mkdir(parents=True)
        (kbdir / "md" / "alpha.md").write_text("===== PAGE 1 =====\n", encoding="utf-8")
        (kbdir / "md" / "command_index.json").write_text(
            json.dumps({"commands": [{"command": "x", "params": ""}]}), encoding="utf-8")
        self.kbdir = kbdir
        for p in (mock.patch.dict(os.environ, {"F310_KB_DIR": str(kbdir)}),
                  mock.patch.object(validated.kb, "VALIDATED", vfile),
                  mock.patch.object(validated.kb, "load_manifest",
                                    return_value={"manuals": [{"file": "alpha.pdf", "url": "u1"}]}),
                  mock.patch.object(validated.fetch_examples, "target_urls", return_value=[self.URL])):
            p.start()
            self.addCleanup(p.stop)

    def write_state(self, lm, fp):
        state = {"manuals": {"alpha.pdf": {"last_modified": lm, "bytes": 100}},
                 "examples": {"p__one.html": {"sha256": fp}}}
        (self.kbdir / ".build.json").write_text(json.dumps(state), encoding="utf-8")

    def run_check(self, site_lm=None, body=None, fail=False):
        def fake_get(url, head=False, **kw):
            if fail:
                raise RuntimeError("offline")
            if head:
                return b"", {"Last-Modified": site_lm or self.LM, "Content-Length": "100"}
            return body or self.BODY, {}
        out = io.StringIO()
        with mock.patch.object(validated.httpget, "get", side_effect=fake_get), \
                contextlib.redirect_stdout(out):
            rc = validated.check_updates()
        return rc, out.getvalue()

    def state(self):
        return json.loads((self.kbdir / ".build.json").read_text(encoding="utf-8"))

    def test_all_latest(self):
        self.write_state(self.LM, self.fp)
        rc, out = self.run_check()
        self.assertEqual(rc, 0)
        self.assertIn("手元のKB:   最新です", out)
        self.assertIn("last_checked", self.state())

    def test_local_behind_site(self):
        self.write_state("Tue, 26 May 2026 00:00:00 GMT", self.fp)
        rc, out = self.run_check()
        self.assertEqual(rc, 1)
        self.assertIn("公式サイトより古いところがあります", out)
        self.assertIn("検証した版から変わっていません", out)

    def test_site_newer_than_validated_and_local_already_has_it(self):
        newer = "Fri, 01 Jan 2027 00:00:00 GMT"
        self.write_state(newer, self.fp)
        rc, out = self.run_check(site_lm=newer)
        self.assertEqual(rc, 1)   # 保守者には検証のしなおしが要る合図
        self.assertIn("取り込み済み", out)
        self.assertIn("手元のKB:   最新です", out)
        self.assertNotIn("取り込むには", out)

    def test_site_newer_and_local_old(self):
        self.write_state(self.LM, self.fp)
        rc, out = self.run_check(body=b"<main>changed</main>")
        self.assertEqual(rc, 1)
        self.assertIn("取り込むには", out)

    def test_network_failure_is_not_recorded_as_checked(self):
        self.write_state(self.LM, self.fp)
        rc, out = self.run_check(fail=True)
        self.assertEqual(rc, 1)
        self.assertIn("判断できません", out)
        self.assertNotIn("last_checked", self.state())


if __name__ == "__main__":
    unittest.main()
