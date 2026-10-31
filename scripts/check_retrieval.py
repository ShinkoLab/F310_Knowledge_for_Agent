#!/usr/bin/env python3
"""構築済みKBに対する検索回帰テスト。

  check_retrieval.py                 全ケースを評価し、失敗を一覧表示（失敗があれば終了コード1）
  check_retrieval.py --list          ケース一覧（題材・ページ依存か）
  check_retrieval.py --id ID [...]   指定ケースだけ実行
  check_retrieval.py --cases FILE    既定の tests/retrieval_cases.json 以外を使う

build.py は件数しか見ないので、「語を変えると0件になる」「modeに表が混ざる」といった
検索結果の退行は拾えない。ここでは lookup.py の cmd_* をそのまま呼び、既知の質問が既知の
答えを返すかを確かめる。ケースにはマニュアル本文を入れない（マニュアル名・ページ番号・
コマンド名・設定例のファイル名・件数の下限・出力の構造だけを書く）。

ケース形式（tests/retrieval_cases.json の "cases" の要素）:
  id, title        識別子と題材
  sub              cmd / grep / ex / page
  args             サブコマンドの位置引数（cmd: [パターン]、grep: [パターン, マニュアル…]、
                   ex: [キーワード]、page: [マニュアル, "N" または "N-M"]）
  opts             full / desc / manual / case / limit（lookup.py の同名オプション）
  page_dependent   ページ番号に依存する期待を含むか（refs / command_refs / pages を使うと true）
  expect           下表。書いた項目だけ検査する

  rc                 終了コード（既定 0。「ヒットしないこと」の確認は 1）
  min_hits           ヒット件数の下限（grep: 行数、cmd: コマンド数、ex: ファイル数、page: ページ数）
  manuals            grep/cmd のヒットがこれらのマニュアルすべてに当たる
  files              ex の結果にこれらの設定例ファイルが含まれる
  top_k              files がすべて結果の先頭 K 件に入る（省略時は含まれれば可）
  commands           cmd の結果にこれらのコマンド名が含まれる
  refs               ["manual:ページ"] grep のヒットに完全一致する出典がある（ページ依存）
  command_refs       ["コマンド名@manual:ページ"] cmd の結果に完全一致がある（ページ依存）
  pages              page の出力にこれらのページ見出しがある（ページ依存）
  contains           出力全体に現れるべき正規表現（行単位、構造を表す語のみ）
  not_contains       出力全体に現れてはならない正規表現
  heading_not_contains  cmd の見出し行（コマンド名と動作モード）に現れてはならない正規表現
"""
import argparse
import contextlib
import io
import json
import re
import shlex
import sys
import time
import types
from pathlib import Path

import kb_paths as kb
import lookup

DEFAULT_CASES = kb.REPO / "tests" / "retrieval_cases.json"

SUBS = {"cmd": lookup.cmd_cmd, "grep": lookup.cmd_grep, "page": lookup.cmd_page, "ex": lookup.cmd_ex}

GREP_RE = re.compile(r"^(\w+)\.pdf p\.(\d+): ")
# 見出し行: "<コマンド>  [<動作モード>]  — <manual>.pdf p.<N>"（モードが空なら括弧なし）
CMD_RE = re.compile(r"^(\S.*?)\s{2,}(?:\[(.*)\]\s+)?— (\w+)\.pdf p\.(\d+)\s*$")
EX_BODY_RE = re.compile(r"^(\S+\.md)  \(\d+件\)")
EX_INDEX_RE = re.compile(r"\[`([^`]+\.md)`\]")
PAGE_RE = re.compile(r"^===== (\w+)\.pdf p\.(\d+) =====$")


def build_ns(case: dict) -> types.SimpleNamespace:
    """lookup.py の argparse が作るのと同じ既定値で Namespace を組む。"""
    sub, a, o = case["sub"], case.get("args", []), case.get("opts", {})
    if sub == "cmd":
        return types.SimpleNamespace(pattern=a[0], full=o.get("full", False), desc=o.get("desc", False),
                                     manual=o.get("manual"), limit=o.get("limit", 20))
    if sub == "grep":
        return types.SimpleNamespace(pattern=a[0], manuals=a[1:], case=o.get("case", False),
                                     limit=o.get("limit", 40))
    if sub == "page":
        return types.SimpleNamespace(manual=a[0], pages=a[1])
    return types.SimpleNamespace(keyword=a[0], limit=o.get("limit", 15))


def command_line(case: dict) -> str:
    """失敗時に手で再現するための lookup.py コマンド行。"""
    o = case.get("opts", {})
    parts = ["lookup.py", case["sub"]] + [shlex.quote(x) for x in case.get("args", [])]
    for k in ("full", "desc", "case"):
        if o.get(k):
            parts.append(f"--{k}")
    if o.get("manual"):
        parts += ["--manual", o["manual"]]
    if "limit" in o:
        parts += ["--limit", str(o["limit"])]
    return " ".join(parts)


def run_case(case: dict) -> tuple:
    """lookup.py のサブコマンドを in-process で実行し (終了コード, 出力) を返す。"""
    buf = io.StringIO()
    rc = 0
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            rc = SUBS[case["sub"]](build_ns(case))
    except SystemExit as e:
        rc = e.code if isinstance(e.code, int) else 1
    return rc, buf.getvalue()


def parse_hits(sub: str, out: str) -> dict:
    """出力から、期待の判定に使う構造（ヒット一覧）を取り出す。"""
    lines = out.splitlines()
    r = {"hits": [], "files": [], "commands": [], "headings": [], "pages": []}
    if sub == "grep":
        r["hits"] = [(m.group(1), int(m.group(2))) for m in map(GREP_RE.match, lines) if m]
    elif sub == "cmd":
        for ln in lines:
            m = CMD_RE.match(ln)
            if m:
                r["commands"].append((m.group(1), m.group(3), int(m.group(4))))
                r["headings"].append(ln)
        r["hits"] = [(man, page) for _, man, page in r["commands"]]
    elif sub == "ex":
        for ln in lines:
            r["files"] += EX_INDEX_RE.findall(ln) if ln.startswith("|") else []
            m = EX_BODY_RE.match(ln)
            if m:
                r["files"].append(m.group(1))
        r["files"] = list(dict.fromkeys(r["files"]))
        r["hits"] = r["files"]
    elif sub == "page":
        r["pages"] = [(m.group(1), int(m.group(2))) for m in map(PAGE_RE.match, lines) if m]
        r["hits"] = r["pages"]
    return r


def evaluate(case: dict, rc: int, out: str) -> list:
    """期待との差を文字列のリストで返す（空なら成功）。"""
    exp = case.get("expect", {})
    fails = []
    want_rc = exp.get("rc", 0)
    if rc != want_rc:
        fails.append(f"終了コード {rc}（期待 {want_rc}）")
    r = parse_hits(case["sub"], out)

    if "min_hits" in exp and len(r["hits"]) < exp["min_hits"]:
        fails.append(f"ヒット {len(r['hits'])} 件（{exp['min_hits']} 件以上のはず）")
    for man in exp.get("manuals", []):
        if not any(h[0] == man for h in r["hits"]):
            fails.append(f"マニュアル {man} に当たっていない（当たった先: {sorted({h[0] for h in r['hits']}) or 'なし'}）")
    for ref in exp.get("refs", []):
        man, _, page = ref.partition(":")
        if (man, int(page)) not in r["hits"]:
            fails.append(f"出典 {man}.pdf p.{page} が無い")
    names = [c[0] for c in r["commands"]]
    for name in exp.get("commands", []):
        if name not in names:
            fails.append(f"コマンド「{name}」が結果に無い")
    for ref in exp.get("command_refs", []):
        name, _, loc = ref.partition("@")
        man, _, page = loc.partition(":")
        if (name, man, int(page)) not in r["commands"]:
            fails.append(f"コマンド「{name}」が {man}.pdf p.{page} に無い")
    for p in exp.get("pages", []):
        man, _, page = p.partition(":")
        if (man, int(page)) not in r["pages"]:
            fails.append(f"ページ見出し {man}.pdf p.{page} が無い")
    files = exp.get("files", [])
    top_k = exp.get("top_k")
    for f in files:
        if f not in r["files"]:
            fails.append(f"設定例 {f} が結果に無い")
        elif top_k and r["files"].index(f) >= top_k:
            fails.append(f"設定例 {f} が {r['files'].index(f) + 1} 番目（先頭 {top_k} 件に入るはず）")
    for pat in exp.get("contains", []):
        if not re.search(pat, out, re.M):
            fails.append(f"出力に /{pat}/ が無い")
    for pat in exp.get("not_contains", []):
        if re.search(pat, out, re.M):
            fails.append(f"出力に /{pat}/ が現れた")
    for pat in exp.get("heading_not_contains", []):
        bad = [h for h in r["headings"] if re.search(pat, h)]
        if bad:
            fails.append(f"見出し行に /{pat}/ が混入 {len(bad)} 件（例: {bad[0][:80]}）")
    return fails


def validate(case: dict) -> list:
    """ケース定義そのものの不整合。page_dependent の申告と期待の中身を突き合わせる。"""
    errs = []
    exp = case.get("expect", {})
    if case.get("sub") not in SUBS:
        return [f"sub が不正: {case.get('sub')}"]
    derived = bool(exp.get("refs") or exp.get("command_refs") or exp.get("pages"))
    if bool(case.get("page_dependent")) != derived:
        errs.append(f"page_dependent={case.get('page_dependent')} だが期待の中身は {derived}"
                    "（refs / command_refs / pages を使うなら true）")
    return errs


def load_cases(path: Path) -> list:
    return json.loads(path.read_text(encoding="utf-8"))["cases"]


def run(cases_path: Path = None, only: list = None, quiet: bool = False) -> tuple:
    """全ケースを評価して (件数, 失敗のリスト) を返す。失敗 = [(case, 理由のリスト)]。"""
    cases = load_cases(cases_path or DEFAULT_CASES)
    if only:
        cases = [c for c in cases if c["id"] in only]
    failures = []
    for c in cases:
        reasons = validate(c)
        if not reasons:
            rc, out = run_case(c)
            reasons = evaluate(c, rc, out)
        if reasons:
            failures.append((c, reasons))
    if not quiet:
        print_report(len(cases), failures)
    return len(cases), failures


def as_warnings() -> list:
    """build.py 用。失敗を網羅性チェックの警告と同じ「1行の文字列」にして返す。"""
    try:
        total, failures = run(quiet=True)
    except Exception as e:  # ケースJSONの破損などで構築全体を落とさない
        return [f"検索回帰テストを実行できません: {type(e).__name__}: {e}"]
    if not failures:
        print(f"  検索回帰    {total}/{total} 件成功")
    out = []
    for c, reasons in failures:
        dep = "（ページ依存）" if c.get("page_dependent") else ""
        out.append(f"検索回帰 {c['id']}{dep}: {c['title']} — {'; '.join(reasons)}  [$ {command_line(c)}]")
    return out


def print_report(total: int, failures: list) -> None:
    for c, reasons in failures:
        dep = "  [ページ依存: 改版でずれただけの可能性]" if c.get("page_dependent") else ""
        print(f"  NG {c['id']}  {c['title']}{dep}")
        print(f"       $ {command_line(c)}")
        for why in reasons:
            print(f"       - {why}")
    print(f"検索回帰テスト: {total - len(failures)}/{total} 件成功")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cases", type=Path, help="ケースJSON（既定 tests/retrieval_cases.json）")
    ap.add_argument("--id", nargs="+", help="指定IDのケースだけ実行")
    ap.add_argument("--list", action="store_true", help="ケース一覧を表示して終了")
    args = ap.parse_args()

    path = args.cases or DEFAULT_CASES
    if args.list:
        for c in load_cases(path):
            print(f"{c['id']:28} {'p' if c.get('page_dependent') else '-'}  {c['title']}")
        return 0
    lookup.require_kb()
    t0 = time.time()
    total, failures = run(path, args.id)
    print(f"所要 {time.time() - t0:.1f} 秒")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
