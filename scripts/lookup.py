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

import kb_paths as kb

BUILD_HINT = (
    "知識ベースが未構築です。次のコマンドで構築してください（公式サイトから約38MBを取得します）:\n"
    "    python3 {script}\n"
    "  出力先: {root}"
)


def require_kb() -> None:
    if not kb.is_built():
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


# ---------------------------------------------------------------- status
def cmd_status(args) -> int:
    root = kb.kb_root()
    if not kb.is_built():
        print(f"未構築  KB: {root}")
        print(BUILD_HINT.format(script=kb.REPO / "scripts" / "build.py", root=root))
        return 2
    idx = load_index()
    ex = sorted(kb.examples_dir().glob("*.md"))
    state = kb.load_state()
    print(f"構築済み  KB: {root}")
    print(f"  マニュアル  {len(available_manuals())} 冊 / {state.get('pages', '?')} ページ")
    print(f"  コマンド    {idx['total']}  {idx['counts']}")
    print(f"  設定例      {len([p for p in ex if p.name != 'INDEX.md'])} 件")
    print(f"  索引生成日  {idx.get('generated', '?')}")
    if not kb.original_dir().exists() or not any(kb.original_dir().glob("*.pdf")):
        print("  ※ PDF原本は保持していません（図の確認が必要なら再取得が要ります）")
    return 0


# ---------------------------------------------------------------- cmd
def cmd_cmd(args) -> int:
    require_kb()
    idx = load_index()
    try:
        pat = re.compile(args.pattern, re.I)
    except re.error as e:
        print(f"正規表現エラー: {e}", file=sys.stderr)
        return 1

    hits = []
    for c in idx["commands"]:
        if args.manual and c["manual"] != manual_stem(args.manual):
            continue
        if pat.search(c["command"]) or (args.desc and pat.search(c["function"])):
            hits.append(c)

    if not hits:
        print(f"該当なし: {args.pattern}（--desc で【機能】本文も対象にできます）")
        return 1

    shown = hits[: args.limit]
    for c in shown:
        mode = f"[{c['mode']}]" if c["mode"] else ""
        print(f"\n{c['command']}  {mode}  — {c['ref']}")
        if args.full:
            if c["function"]:
                print(f"  【機能】{trim(c['function'], 300)}")
            if c["syntax"]:
                for ln in c["syntax"].splitlines():
                    print(f"  {ln}")
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
        pat = re.compile(args.pattern, 0 if args.case else re.I)
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
        pat = re.compile(args.keyword, re.I)
    except re.error as e:
        print(f"正規表現エラー: {e}", file=sys.stderr)
        return 1

    # 1) 索引の行（タイトル・対象装置）で拾う
    rows = [ln for ln in index.read_text(encoding="utf-8").splitlines()
            if ln.startswith("|") and pat.search(ln) and "---" not in ln]
    if rows:
        print("== 索引での一致 ==")
        for ln in rows[: args.limit]:
            print(trim(ln, 240))

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
    s.add_argument("--full", action="store_true", help="【機能】と入力形式を全文表示")
    s.add_argument("--desc", action="store_true", help="【機能】本文も検索対象にする")
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
