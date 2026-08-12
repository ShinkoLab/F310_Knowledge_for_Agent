#!/usr/bin/env python3
"""F310 知識ベースを構築する（取得 → 変換 → 索引生成 → 検証）。

  取得: 公式サイトから マニュアルPDF 10冊 + 設定例HTML 54件
  変換: PDF → ページ番号マーカー付き md、HTML → 構造化 md
  索引: コマンド索引 JSON、設定例 INDEX.md

出力先は $F310_KB_DIR、未設定なら ~/.claude/plugins/data/f310-kb-shinko-lab。
依存は python3 のみ。PDF抽出に使う pypdfium2 だけは KB配下の venv へ自動で用意する
（詳細は pdf_text.py）。外部コマンドは要らない。
"""
import argparse
import shutil
import sys
from pathlib import Path

import build_command_index
import convert_to_md
import fetch_examples
import fetch_manuals
import gen_examples
import gen_examples_index
import kb_paths as kb
import pdf_text

# 既知の網羅性。抽出ロジックを変えたときにここが崩れていないかで気付けるようにする。
EXPECT_PAGES = 3873
EXPECT_COMMANDS = {"cmd_refe_config": 1299, "cmd_refe_ope": 615}
EXPECT_EXAMPLES = 54


def check_pdf_backend(args) -> bool:
    """PDF抽出の準備。38MBを取りに行く前に確認して、駄目なら先に止める。

    変換する対象が無いときは何もしない。--skip-fetch で設定例だけ作り直す場合に、
    使いもしないライブラリの導入（＝ネットワークアクセス）を起こさないため。
    """
    if args.skip_fetch and not any(kb.original_dir().glob("*.pdf")):
        return True
    err = pdf_text.ensure_available()
    if err:
        print(err, file=sys.stderr)
        return False
    return True


def seed_from(path: Path) -> int:
    """既存の手元データからPDFをコピーして再ダウンロードを省く。"""
    src = path / "original" if (path / "original").is_dir() else path
    if not src.is_dir():
        print(f"seed 元が見つかりません: {src}", file=sys.stderr)
        return 0
    dest = kb.original_dir()
    dest.mkdir(parents=True, exist_ok=True)
    n = 0
    for pdf in sorted(src.glob("*.pdf")):
        target = dest / pdf.name
        if not target.exists():
            shutil.copy2(pdf, target)
            n += 1
    print(f"seed: {src} から PDF {n} 冊をコピー（既存はスキップ）")
    return n


def pages_on_disk(only: set = None) -> int:
    """KBのmdに実在するページ数を数える。only を指定するとその stem のmdだけ数える。"""
    n = 0
    for md in kb.md_dir().glob("*.md"):
        if only is not None and md.stem not in only:
            continue
        n += sum(1 for ln in md.read_text(encoding="utf-8").splitlines()
                 if ln.startswith("===== PAGE "))
    return n


def verify(pages: int, counts: dict, examples: int) -> list[str]:
    warn = []
    if pages != EXPECT_PAGES:
        warn.append(f"総ページ数 {pages}（想定 {EXPECT_PAGES}）")
    for stem, want in EXPECT_COMMANDS.items():
        got = counts.get(stem, 0)
        if got != want:
            warn.append(f"{stem} のコマンド数 {got}（想定 {want}）")
    if examples != EXPECT_EXAMPLES:
        warn.append(f"設定例md {examples} 件（想定 {EXPECT_EXAMPLES}）")
    return warn


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skip-fetch", action="store_true", help="取得を省き、手元のPDF/HTMLから再生成のみ行う")
    ap.add_argument("--force", action="store_true", help="取得済みでも再取得する")
    ap.add_argument("--dry-run", action="store_true", help="全URLの疎通確認のみ（保存も生成もしない）")
    ap.add_argument("--seed", metavar="DIR", help="既存の original/*.pdf をコピーしてDLを省く")
    ap.add_argument("--prune-pdf", action="store_true", help="変換後にPDFを削除して容量を空ける")
    args = ap.parse_args()

    root = kb.kb_root()
    print(f"KB: {root}\n")

    # 旧パスに構築済みKBが残っているなら、38MBを取り直す前に移行を促して止める。
    # dry-run はURLを見るだけでKBに触らないので対象外。
    hint = kb.legacy_hint()
    if hint and not args.dry_run:
        print(hint, file=sys.stderr)
        print("移行後にもう一度 build.py を実行してください。"
              "新規に作り直す場合は旧パスを削除してから再実行してください。", file=sys.stderr)
        return 2

    if args.dry_run:
        print("== URL疎通確認 ==")
        f1, _ = fetch_manuals.fetch_all(dry_run=True)
        f2, _ = fetch_examples.fetch_all(dry_run=True)
        total = f1 + f2
        print(f"\n到達不可: {total} 件")
        return 1 if total else 0

    # seed が先。check_pdf_backend は「変換する対象があるか」を見るので、
    # 手元PDFを流し込む前に判定すると --skip-fetch --seed で確認を素通りしてしまう。
    if args.seed:
        seed_from(Path(args.seed).expanduser().resolve())

    if not check_pdf_backend(args):
        return 1

    man_failed = ex_failed = man_stale = ex_stale = 0
    if not args.skip_fetch:
        print("== 取得 ==")
        # 取得できなかったものがあっても止めない。1冊のURLが恒久的に死んだだけで
        # KB全体が作れなくなるより、9冊分でも使える状態にして理由を明示する方がよい。
        man_failed, man_stale = fetch_manuals.fetch_all(force=args.force)
        print()
        ex_failed, ex_stale = fetch_examples.fetch_all(force=args.force)
        print()

    print("== PDF → Markdown ==")
    pages = convert_to_md.run()
    if pages is not None:
        # PDFが一部だけ欠けた場合、その冊は変換されないがmdは前回分が残っていて
        # KBとしては使える。変換段の実績値だけを記録すると status と verify が
        # 過少なページ数で退行を誤検知するため、残存冊のページを加算する
        # （取得失敗自体は man_failed/stale として別途警告される）。
        # --prune-pdf でPDFが消える前にここで確定させること。
        retained = ({p.stem for p in kb.md_dir().glob("*.md")}
                    - {p.stem for p in kb.original_dir().glob("*.pdf")})
        if retained:
            pages += pages_on_disk(only=retained)
            print(f"  ほか {len(retained)} 冊はPDFが無いため既存mdを維持", file=sys.stderr)

    print("\n== コマンド索引 ==")
    counts = build_command_index.run()

    print("\n== 設定例 Markdown ==")
    examples = gen_examples.run(quiet=True)
    gen_examples_index.run()

    if args.prune_pdf:
        for pdf in kb.original_dir().glob("*.pdf"):
            pdf.unlink()
        print("\nPDFを削除しました（再ビルド時は再取得されます）")

    # 補完するのは「段が動けなかった」ときだけ（PDFが無く変換をスキップした場合）。
    # 段が動いた結果の 0 をKBの実物や前回値で埋めると、生成に失敗した回でも
    # 検証が通ってしまう。索引・設定例は必ず走るので補完しない。
    if pages is None:
        pages = pages_on_disk()

    # 記録用のキーは取得メタデータ（manuals / examples）と衝突させないこと。
    state = kb.load_state()
    state.pop("commands", None)                       # 旧キー名
    if not isinstance(state.get("examples"), dict):   # 旧版が生成件数(int)を書いていた
        state.pop("examples", None)
    state["pages"] = pages
    state["command_counts"] = counts
    state["example_count"] = examples
    kb.save_state(state)

    print("\n== 結果 ==")
    print(f"  ページ数    {pages}")
    print(f"  コマンド    {sum(counts.values())}  {counts}")
    print(f"  設定例md    {examples} 件")
    if man_stale or ex_stale:
        print(f"  既存で代用  マニュアル {man_stale} 冊 / 設定例 {ex_stale} 件（取得に失敗）")
    warn = verify(pages, counts, examples)
    # --force は「取り直せ」という明示の指示。1件も更新できていないのに件数が揃っている
    # だけで成功と表示すると、回線断やサイト改編に気付けない。
    if args.force and (man_stale or ex_stale):
        warn.insert(0, f"--force 指定だが マニュアル {man_stale} 冊 / 設定例 {ex_stale} 件 は"
                       "取得に失敗し、既存ファイルのままです")
    # 取得失敗は先頭に出す。数が合わない理由がこれなら、まずそれを見せる。
    if ex_failed:
        warn.insert(0, f"設定例ページの取得に {ex_failed} 件失敗")
    if man_failed:
        warn.insert(0, f"マニュアルPDFの取得に {man_failed} 冊失敗"
                       "（ネットワークとURLを確認し --force で取り直してください）")
    if warn:
        print("\n⚠ 想定値と一致しません。取得漏れか抽出ロジックの退行が疑われます:")
        for w in warn:
            print(f"    - {w}")
        return 1
    print("\n網羅性チェック OK。知識ベースの構築が完了しました。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
