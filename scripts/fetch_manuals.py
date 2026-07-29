#!/usr/bin/env python3
"""FITELnet F310 の純正マニュアルPDFを公式サイトから取得して KB に置く。

取得先は data/manuals_manifest.json（URLのみを保持。PDF本体はリポジトリに含まない）。
Last-Modified を .build.json に記録し、更新が無いものは再取得しない。
"""
import argparse
import sys

import httpget
import kb_paths as kb


def fetch_all(force: bool = False, dry_run: bool = False) -> tuple:
    """(failed, stale) を返す。
    failed = 変換に使えるPDFが手元に無い冊数、stale = 取得に失敗して既存ファイルで代用した冊数。
    両者を混ぜると、回線が死んだ状態の --force で1冊も更新できなくても
    「失敗0＝成功」に見えてしまう。"""
    manifest = kb.load_manifest(kb.MANUALS_MANIFEST)
    manuals = manifest["manuals"]
    dest = kb.original_dir()
    if not dry_run:
        dest.mkdir(parents=True, exist_ok=True)

    state = kb.load_state()
    seen = state.get("manuals")
    if not isinstance(seen, dict):
        seen = {}
    state["manuals"] = seen
    failed = stale = 0

    print(f"マニュアルPDF {len(manuals)} 冊 → {dest}")
    for m in manuals:
        name, url = m["file"], m["url"]
        out = dest / name
        existed = out.exists()   # 失敗時、元から在ったのか今回作りかけたのかを区別する
        try:
            if dry_run:
                _, headers = httpget.get(url, head=True)
                size = int(headers.get("Content-Length", 0))
                print(f"  OK      {name:30s} {size/1024/1024:6.1f} MB")
                continue

            prev = seen.get(name, {})
            if out.exists() and not force:
                # HEAD で更新確認。未更新ならダウンロードを省く
                _, headers = httpget.get(url, head=True)
                lm = headers.get("Last-Modified", "")
                if not prev:
                    # 手元にPDFはあるが記録が無い（--seed 直後など）。現物を採用して記録だけ作る。
                    # 手元のPDFが古い可能性はあるので、疑わしいときは --force で取り直す。
                    seen[name] = {"url": url, "last_modified": lm,
                                  "bytes": out.stat().st_size, "adopted": True}
                    print(f"  adopt   {name:30s} 既存ファイルを採用")
                    continue
                if lm and lm == prev.get("last_modified"):
                    print(f"  skip    {name:30s} 更新なし")
                    continue

            body, headers = httpget.get(url)
            # 一時ファイルに書いてから差し替える。直接書くと、途中で失敗したときに
            # 壊れたPDFが残り、それが「既存ファイル」として後段に流れてしまう。
            tmp = out.with_name(out.name + ".part")
            tmp.write_bytes(body)
            tmp.replace(out)
            seen[name] = {
                "url": url,
                "last_modified": headers.get("Last-Modified", ""),
                "bytes": len(body),
            }
            print(f"  fetched {name:30s} {len(body)/1024/1024:6.1f} MB")
        except Exception as e:                      # noqa: BLE001 - 1冊の失敗で全体を止めない
            if not dry_run:
                (dest / (name + ".part")).unlink(missing_ok=True)
            # 元から手元にあったPDFなら、更新確認や再取得の失敗でビルドを止めない。
            # ただし黙って成功にはしない（stale として呼び出し側に返す）。
            if existed and not dry_run:
                stale += 1
                print(f"  warn    {name:30s} 取得に失敗（既存ファイルを使用）: {e}", file=sys.stderr)
            else:
                failed += 1
                print(f"  FAIL    {name:30s} {e}", file=sys.stderr)

    if not dry_run:
        kb.save_state(state)
    return failed, stale


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true", help="更新の有無に関わらず再取得する")
    ap.add_argument("--dry-run", action="store_true", help="URL疎通のみ確認して保存しない")
    args = ap.parse_args()
    failed, stale = fetch_all(force=args.force, dry_run=args.dry_run)
    if failed:
        print(f"\n{failed} 冊が取得できませんでした。", file=sys.stderr)
    if stale:
        print(f"{stale} 冊は取得に失敗し、既存ファイルのままです。", file=sys.stderr)
    return 1 if failed or stale else 0


if __name__ == "__main__":
    raise SystemExit(main())
