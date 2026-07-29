#!/usr/bin/env python3
"""公式サイトの「設定例」ページHTMLを取得し、UTF-8化して KB に置く。

取得対象は data/examples_manifest.json の kind=="detail"（F310を対象装置に含む設定例）。
元ページは Shift_JIS なので、後段のリニアライザが読めるよう UTF-8 に変換して保存する。
"""
import argparse
import sys

import httpget
import kb_paths as kb


def _decode(body: bytes, headers: dict) -> str:
    """Shift_JIS前提。機種依存文字を含むため cp932 で解釈する。"""
    ctype = headers.get("Content-Type", "").lower()
    enc = "cp932"
    if "charset=" in ctype:
        declared = ctype.split("charset=")[-1].split(";")[0].strip()
        if declared in ("shift_jis", "shift-jis", "sjis", "cp932", "windows-31j"):
            enc = "cp932"
        elif declared:
            enc = declared
    try:
        return body.decode(enc, errors="replace")
    except LookupError:
        return body.decode("cp932", errors="replace")


def target_urls() -> list[str]:
    items = kb.load_manifest(kb.EXAMPLES_MANIFEST)
    urls = []
    for it in items:
        if it.get("kind") != "detail":
            continue
        u = it["url"].split("#")[0]
        if u not in urls:
            urls.append(u)
    return sorted(urls)


def fetch_all(force: bool = False, dry_run: bool = False) -> tuple:
    """(failed, stale) を返す。
    failed = 手元にHTMLが無い件数、stale = 取得に失敗して既存ファイルで代用した件数。"""
    urls = target_urls()
    dest = kb.html_dir()
    if not dry_run:
        dest.mkdir(parents=True, exist_ok=True)

    state = kb.load_state()
    # 旧版は同じキーに生成件数(int)を書いていた。そのままだと代入で TypeError になるので均す。
    seen = state.get("examples")
    if not isinstance(seen, dict):
        seen = {}
    state["examples"] = seen
    failed = stale = 0

    print(f"設定例ページ {len(urls)} 件 → {dest}")
    for u in urls:
        name = kb.page_key(u) + ".html"
        out = dest / name
        existed = out.exists()   # 失敗時、元から在ったのか今回作りかけたのかを区別する
        try:
            if dry_run:
                httpget.get(u, head=True)
                print(f"  OK      {name}")
                continue
            if out.exists() and not force:
                print(f"  skip    {name}")
                continue
            body, headers = httpget.get(u)
            text = _decode(body, headers)
            # 一時ファイル経由で差し替える（直接書くと失敗時に途切れたHTMLが残る）
            tmp = out.with_name(out.name + ".part")
            tmp.write_text(text, encoding="utf-8")
            tmp.replace(out)
            seen[name] = {"url": u, "bytes": len(body)}
            print(f"  fetched {name}")
        except Exception as e:                      # noqa: BLE001 - 1件の失敗で全体を止めない
            if not dry_run:
                (dest / (name + ".part")).unlink(missing_ok=True)
            # 元から取得済みのHTMLがあるなら、再取得の失敗は致命的ではない。
            # ただし黙って成功にはしない（stale として呼び出し側に返す）。
            if existed and not dry_run:
                stale += 1
                print(f"  warn    {name}  取得に失敗（既存ファイルを使用）: {e}", file=sys.stderr)
            else:
                failed += 1
                print(f"  FAIL    {name}  {e}", file=sys.stderr)

    if not dry_run:
        kb.save_state(state)
    return failed, stale


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true", help="取得済みでも再取得する")
    ap.add_argument("--dry-run", action="store_true", help="URL疎通のみ確認して保存しない")
    args = ap.parse_args()
    failed, stale = fetch_all(force=args.force, dry_run=args.dry_run)
    if failed:
        print(f"\n{failed} 件が取得できませんでした。", file=sys.stderr)
    if stale:
        print(f"{stale} 件は取得に失敗し、既存ファイルのままです。", file=sys.stderr)
    return 1 if failed or stale else 0


if __name__ == "__main__":
    raise SystemExit(main())
