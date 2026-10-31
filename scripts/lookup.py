#!/usr/bin/env python3
"""F310 知識ベース検索ヘルパ。

  lookup.py status                 KB が構築済みか・規模・生成日
  lookup.py cmd <regex>            コマンド索引を引く（構文・動作モード・出典ページ）
  lookup.py grep <pat> [manual…]   マニュアル本文を検索（出典ページ付きで返る）
  lookup.py page <manual> <N[-M]>  該当ページの本文をそのまま出す（原本確認はこれ）
  lookup.py ex <keyword>           公式設定例を検索

ページ番号は PDF物理ページ。md は PDF のテキスト層をそのまま抽出したものなので、
原本を確認したいときも PDF を開かず `page` で足りる（同じテキストが返る）。
図・写真などテキストに無いものを人が見たいときだけ PDF を開く。
"""
import argparse
import json
import re
import sys
import unicodedata

import kb_paths as kb
import validated

BUILD_HINT = (
    "知識ベースが未構築です。次のコマンドで構築してください（公式サイトから約48MBを取得します）:\n"
    "    python3 {script}\n"
    "  出力先: {root}"
)


def require_kb() -> None:
    if not kb.is_built():
        hint = kb.legacy_hint()
        if hint:
            print(hint, file=sys.stderr)
        print(
            BUILD_HINT.format(script=kb.REPO / "scripts" / "build.py", root=kb.kb_root()),
            file=sys.stderr,
        )
        raise SystemExit(2)


def load_index() -> dict:
    return json.loads((kb.md_dir() / "command_index.json").read_text(encoding="utf-8"))


def manual_stem(name: str) -> str:
    return re.sub(r"\.(md|pdf)$", "", name)


def available_manuals() -> list[str]:
    return sorted(p.stem for p in kb.md_dir().glob("*.md"))


def trim(s: str, n: int = 200) -> str:
    s = s.strip()
    return s if len(s) <= n else s[: n - 1] + "…"


# 英数字 ⇔ 日本語の境目に空白を許容する。PDFのテキスト層は「v6 プラス」のように
# 境目へ空白を挟むため、利用者が「v6プラス」と書くと当たらない（逆も同様）。
# 入力の全角英数字は半角にも当たるようにする（1字ずつ NFKC で半角化し、元の字との文字クラスにする）。
# 逆向き（半角の入力で本文の全角に当てる）はしない。本文の全角英数字はごく少ないため。
_META = set("\\.^$*+?{}[]|()")
_JA = "\u3040-\u30ff\u3400-\u9fff\uff66-\uff9f"  # かな・漢字・半角カナ
_JA_RE = re.compile("[" + _JA + "]")


def _is_ascii_alnum(ch: str) -> bool:
    return ch.isascii() and ch.isalnum()


def fuzzy_pattern(text: str) -> str:
    """利用者の入力を、境目の空白ゆれを許す正規表現文字列にして返す。

    正規表現メタ文字を含む入力は利用者が構文を書いたものとして一切変換しない
    （`\\s*` を足すと意味が変わりうるため、安全に変換できる素の語句に限定）。
    """
    if any(c in _META for c in text):
        return text
    # 前後の空白は利用者が意図して付けたもの（例: "no "）なので触らない
    body = text.strip()
    if not body:
        return re.escape(text)
    lead, trail = text[: len(text) - len(text.lstrip())], text[len(text.rstrip()):]
    out = [re.escape(lead)]
    prev = ""  # 直前の非空白文字の種別: "a"(英数) / "j"(日本語) / ""
    gap = False  # 直前に空白があった
    for ch in body:
        if ch.isspace():
            gap = True
            continue
        n = unicodedata.normalize("NFKC", ch)
        kind = "a" if len(n) == 1 and _is_ascii_alnum(n) else ("j" if _JA_RE.match(ch) else "")
        if prev and gap:
            # 元々空白があった箇所。英数⇔日本語の境目なら空白なしも許す、
            # それ以外（英語の語間など）は元の空白を保つ。
            out.append("\\s*" if {prev, kind} == {"a", "j"} else r"\s+")
        elif {prev, kind} == {"a", "j"}:
            out.append("\\s*")
        if kind == "a":
            out.append("[" + re.escape(n) + re.escape(ch) + "]" if n != ch else re.escape(n))
        else:
            out.append(re.escape(ch))
        prev, gap = kind, False
    out.append(re.escape(trail))
    return "".join(out)


# ---------------------------------------------------------------- status
def cmd_status(args) -> int:
    root = kb.kb_root()
    if not kb.is_built():
        print(f"未構築  KB: {root}")
        hint = kb.legacy_hint()
        if hint:
            print(hint)
        print(BUILD_HINT.format(script=kb.REPO / "scripts" / "build.py", root=root))
        return 2
    idx = load_index()
    n_ex = kb.example_count()
    state = kb.load_state()
    print(f"構築済み  KB: {root}")
    print(f"  マニュアル  {len(available_manuals())} 冊 / {state.get('pages', '?')} ページ")
    print(f"  コマンド    {idx['total']}  {idx['counts']}")
    print(f"  設定例      {n_ex} 件" + ("  ※未生成。build.py で再構築してください" if not n_ex else ""))
    print(f"  索引生成日  {idx.get('generated', '?')}")
    if not kb.original_dir().exists() or not any(kb.original_dir().glob("*.pdf")):
        print("  ※ PDF原本は保持していません（図の確認が必要なら再取得が要ります）")
    # ネットワークを使わない鮮度の判定。古くても検索はできるので、案内だけして 0 を返す
    notes = validated.local_status(validated.load())
    stale = validated.contact_note(state)
    if notes or stale:
        print("  更新の案内:")
        for n in notes + ([stale] if stale else []):
            print(f"    - {n}")
        build = kb.REPO / "scripts" / "build.py"
        if notes:
            print(f"    更新するには: python3 {build}（Claude Code では /f310-kb:update）")
        else:
            print(f"    公式サイトの更新を確認するには: python3 {build} --check-updates"
                  "（Claude Code では /f310-kb:update）")
    return 0


# ---------------------------------------------------------------- cmd
def cmd_cmd(args) -> int:
    require_kb()
    idx = load_index()
    try:
        pat = re.compile(fuzzy_pattern(args.pattern), re.I)
    except re.error as e:
        print(f"正規表現エラー: {e}", file=sys.stderr)
        return 1

    hits = []
    for c in idx["commands"]:
        if args.manual and c["manual"] != manual_stem(args.manual):
            continue
        # 旧い索引には description が無いので .get。params は語が多すぎて当たりが散るため対象外
        if pat.search(c["command"]) or (
                args.desc and (pat.search(c["function"]) or pat.search(c.get("description", "")))):
            hits.append(c)

    if not hits:
        print(f"該当なし: {args.pattern}（--desc で【機能】【説明】本文も対象にできます）")
        return 1

    shown = hits[: args.limit]
    for c in shown:
        # モードは長いと折り返されて複数行になる。英字どうしの境目だけ空白に戻して1行にする
        mode = re.sub(r"(?<=[\x21-\x7e])\n(?=[\x21-\x7e])", " ", c["mode"]).replace("\n", "")
        mode = f"[{mode}]" if mode else ""
        print(f"\n{c['command']}  {mode}  — {c['ref']}")
        if args.full:
            if c["function"]:
                print(f"  【機能】{trim(c['function'], 300)}")
            if c["syntax"]:
                for ln in c["syntax"].splitlines():
                    print(f"  {ln}")
            for label, key, n in (("説明", "description", 500), ("未設定時", "default", 300)):
                if c.get(key):
                    print(f"  【{label}】" + trim(c[key], n).replace("\n", "\n  "))
            if c.get("params"):
                print("  【パラメータ】")
                for ln in c["params"].splitlines():
                    print(f"    {ln}" if ln.strip() else "")
        else:
            first = c["syntax"].splitlines()[0] if c["syntax"] else ""
            if first:
                print(f"  {trim(first)}")
    if len(hits) > len(shown):
        print(f"\n… 他 {len(hits) - len(shown)} 件（--limit で増やせます）")
    return 0


# ---------------------------------------------------------------- grep
PAGE_RE = re.compile(r"^===== PAGE (\d+) =====$")


def cmd_grep(args) -> int:
    require_kb()
    try:
        pat = re.compile(fuzzy_pattern(args.pattern), 0 if args.case else re.I)
    except re.error as e:
        print(f"正規表現エラー: {e}", file=sys.stderr)
        return 1

    stems = [manual_stem(m) for m in args.manuals] or available_manuals()
    total = 0
    for stem in stems:
        f = kb.md_dir() / f"{stem}.md"
        if not f.exists():
            print(f"マニュアルがありません: {stem}（利用可能: {', '.join(available_manuals())}）", file=sys.stderr)
            continue
        page = 0
        for line in f.read_text(encoding="utf-8").splitlines():
            m = PAGE_RE.match(line)
            if m:
                page = int(m.group(1))
                continue
            if pat.search(line):
                total += 1
                if total > args.limit:
                    print(f"\n… 打ち切り（--limit {args.limit}）。語を絞るかマニュアルを指定してください。")
                    return 0
                print(f"{stem}.pdf p.{page}: {trim(line)}")
    if total == 0:
        print(f"該当なし: {args.pattern}")
        return 1
    print(f"\n{total} 件。前後の文脈は `lookup.py page <manual> <N>` で読めます。")
    return 0


# ---------------------------------------------------------------- page
def cmd_page(args) -> int:
    require_kb()
    stem = manual_stem(args.manual)
    f = kb.md_dir() / f"{stem}.md"
    if not f.exists():
        print(f"マニュアルがありません: {stem}（利用可能: {', '.join(available_manuals())}）", file=sys.stderr)
        return 1

    m = re.fullmatch(r"(\d+)(?:-(\d+))?", args.pages)
    if not m:
        print("ページ指定は N または N-M の形式です", file=sys.stderr)
        return 1
    lo = int(m.group(1))
    hi = int(m.group(2) or lo)

    out, page, printed = [], 0, False
    for line in f.read_text(encoding="utf-8").splitlines():
        pm = PAGE_RE.match(line)
        if pm:
            page = int(pm.group(1))
            if lo <= page <= hi:
                out.append(f"===== {stem}.pdf p.{page} =====")
                printed = True
            continue
        if lo <= page <= hi:
            out.append(line)
    if not printed:
        print(f"p.{args.pages} は範囲外です（{stem}）", file=sys.stderr)
        return 1
    print("\n".join(out).rstrip())
    return 0


# ---------------------------------------------------------------- ex
def cmd_ex(args) -> int:
    require_kb()
    ex_dir = kb.examples_dir()
    index = ex_dir / "INDEX.md"
    if not index.exists():
        print("設定例が未生成です。build.py を実行してください。", file=sys.stderr)
        return 2
    try:
        pat = re.compile(fuzzy_pattern(args.keyword), re.I)
    except re.error as e:
        print(f"正規表現エラー: {e}", file=sys.stderr)
        return 1

    # 1) 索引の行（タイトル・対象装置）で拾う
    rows = [ln for ln in index.read_text(encoding="utf-8").splitlines()
            if ln.startswith("|") and pat.search(ln) and "---" not in ln]
    if rows:
        print("== 索引での一致 ==")
        for ln in rows[: args.limit]:
            # 索引に載っていても本文が未生成のことがある。存在しないファイルを
            # そのまま案内しないよう、行から参照先を拾って実在を確かめる。
            refs = re.findall(r"\[`([^`]+\.md)`\]", ln)
            missing = [r for r in refs if not (ex_dir / r).exists()]
            print(trim(ln, 240) + ("  ← 本文未生成" if missing else ""))

    # 2) 本文で拾う（完成コンフィグ内のコマンド名などに当たる）
    body = []
    for f in sorted(ex_dir.glob("*.md")):
        if f.name == "INDEX.md":
            continue
        text = f.read_text(encoding="utf-8")
        if not pat.search(text):
            continue
        lines = text.splitlines()
        title = lines[0].lstrip("# ").strip() if lines else f.stem
        src = next((ln.split("**出典**:")[-1].strip() for ln in lines[:10] if "**出典**" in ln), "")
        body.append((f.name, title, src, len(pat.findall(text))))
    if body:
        print(f"\n== 本文での一致（{len(body)} ファイル）==")
        for name, title, src, n in sorted(body, key=lambda x: -x[3])[: args.limit]:
            print(f"{name}  ({n}件)  {title}")
            if src:
                print(f"    出典: {src}")
    if not rows and not body:
        print(f"該当なし: {args.keyword}")
        return 1
    print(f"\n本文を読む: {ex_dir}/<file>")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="sub", required=True)

    s = sub.add_parser("status", help="KBの構築状況")
    s.set_defaults(func=cmd_status)

    s = sub.add_parser("cmd", help="コマンド索引を引く")
    s.add_argument("pattern", help="コマンド名の正規表現（部分一致・大小無視）")
    s.add_argument("--full", action="store_true", help="【機能】・入力形式・【説明】・【未設定時】・パラメータ表を表示")
    s.add_argument("--desc", action="store_true", help="【機能】【説明】本文も検索対象にする（パラメータ表は対象外）")
    s.add_argument("--manual", help="cmd_refe_config / cmd_refe_ope に絞る")
    s.add_argument("--limit", type=int, default=20)
    s.set_defaults(func=cmd_cmd)

    s = sub.add_parser("grep", help="マニュアル本文検索")
    s.add_argument("pattern")
    s.add_argument("manuals", nargs="*", help="対象マニュアル（省略時は全冊）")
    s.add_argument("--case", action="store_true", help="大小を区別する")
    s.add_argument("--limit", type=int, default=40)
    s.set_defaults(func=cmd_grep)

    s = sub.add_parser("page", help="ページ本文を表示")
    s.add_argument("manual")
    s.add_argument("pages", help="N または N-M")
    s.set_defaults(func=cmd_page)

    s = sub.add_parser("ex", help="公式設定例を検索")
    s.add_argument("keyword")
    s.add_argument("--limit", type=int, default=15)
    s.set_defaults(func=cmd_ex)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
