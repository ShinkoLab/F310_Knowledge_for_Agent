#!/usr/bin/env python3
"""「パーサを検証した時点の公式サイトの版」を記録・照会する。

data/validated_versions.json に、検証したときの版を本文なしで持つ:
  manuals  冊ごとの Last-Modified / バイト数 / ページ数（コマンド索引を持つ冊はコマンド数も）
  examples 設定例ページごとの本文の指紋（fetch_examples.fingerprint）
  example_count  生成される設定例md件数

用途は2つ。
  - build.py の網羅性チェック: 手元の版が検証済みの版と同じなのに数が違えば抽出の退行、
    版が違うなら数が変わるのは想定どおり（検証し直して更新する）、と区別できる。
  - build.py --check-updates: 公式サイトが検証済みの版から変わっていないかをKBに触れず調べる。

更新は build.py --accept-current（手元のKBの現状を検証済みの版にする）。
"""
import json
import sys

import fetch_examples
import httpget
import kb_paths as kb


def load() -> dict:
    """検証済みの版。ファイルが無い・壊れている場合は空 dict。"""
    try:
        return json.loads(kb.VALIDATED.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def manual_changed(cur: dict, ver: dict) -> bool:
    """手元のPDF（.build.json の記録 cur）が検証済みの版 ver と違うか。
    記録が無ければ「違う」とは言えないので False（その場合の数の不一致は退行扱い）。"""
    if not cur:
        return False
    return (cur.get("last_modified") != ver.get("last_modified")
            or cur.get("bytes") != ver.get("bytes"))


def examples_changed(state_examples: dict, ver_examples: dict) -> bool:
    """手元の設定例が検証済みの版と1件でも違うか（指紋の差・件の増減）。"""
    cur = {k: v.get("sha256") for k, v in state_examples.items() if isinstance(v, dict)}
    return cur != ver_examples


def accept_current(pages_by_book: dict, counts: dict, example_count: int) -> int:
    """手元のKBの現状（.build.json と生成結果）を検証済みの版として書き出す。"""
    state = kb.load_state()
    seen = state.get("manuals") if isinstance(state.get("manuals"), dict) else {}
    ex_seen = state.get("examples") if isinstance(state.get("examples"), dict) else {}
    old = load()

    manuals, problems = {}, []
    for m in kb.load_manifest(kb.MANUALS_MANIFEST)["manuals"]:
        name = m["file"]
        rec, stem = seen.get(name), name[:-4]
        if not rec or not rec.get("last_modified"):
            problems.append(f"{name}: 取得の記録（Last-Modified）が無い")
            continue
        if not pages_by_book.get(stem):
            problems.append(f"{name}: 変換済みmdが無い")
            continue
        e = {"last_modified": rec["last_modified"], "bytes": rec["bytes"],
             "pages": pages_by_book[stem]}
        if stem in counts:
            e["commands"] = counts[stem]
        manuals[name] = e

    examples = {}
    for u in fetch_examples.target_urls():
        name = kb.page_key(u) + ".html"
        fp = (ex_seen.get(name) or {}).get("sha256")
        if fp:
            examples[name] = fp
        else:
            problems.append(f"{name}: 本文の指紋が無い")
    if problems:
        print("検証済みの版を更新できません。--skip-fetch なしで build.py を一度実行してください:",
              file=sys.stderr)
        for p in problems:
            print(f"    - {p}", file=sys.stderr)
        return 1

    new = {"note": ("パーサを検証した時点の公式サイトの版（本文は含まない）。"
                    "build.py --accept-current で手元のKBの現状から書き直す。手で編集しない。"),
           "manuals": manuals, "examples": examples, "example_count": example_count}
    # 差分を見せる。意図しない版を受け入れていないか、コミット前に確認できるように
    for name, e in manuals.items():
        o = old.get("manuals", {}).get(name)
        if o is None:
            print(f"  追加  {name}")
        elif o != e:
            print(f"  更新  {name}: {o.get('pages')} → {e['pages']} ページ")
    n = sum(1 for k, v in examples.items() if old.get("examples", {}).get(k) != v)
    if n:
        print(f"  更新  設定例 {n} 件の指紋")
    if old == new:
        print("  変更なし")
    kb.VALIDATED.write_text(json.dumps(new, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"検証済みの版を書き出しました: {kb.VALIDATED}")
    return 0


def check_updates() -> int:
    """公式サイトを検証済みの版と突き合わせる。KBには書かない。変化・リンク切れがあれば 1。

    マニュアルは HEAD（Last-Modified / Content-Length）、設定例は GET して指紋を比べる
    （設定例のページは更新日時を返さないため）。
    """
    ver = load()
    if not ver.get("manuals"):
        print(f"検証済みの版がありません: {kb.VALIDATED}", file=sys.stderr)
        return 1
    bad = 0

    print("== マニュアルPDF（HEAD）==")
    listed = set()
    for m in kb.load_manifest(kb.MANUALS_MANIFEST)["manuals"]:
        name = m["file"]
        listed.add(name)
        v = ver["manuals"].get(name)
        try:
            _, h = httpget.get(m["url"], head=True)
        except Exception as e:                      # noqa: BLE001 - 1冊の失敗で全体を止めない
            bad += 1
            print(f"  BROKEN  {name:30s} {e}")
            continue
        lm, size = h.get("Last-Modified", ""), h.get("Content-Length")
        if not v:
            bad += 1
            print(f"  NEW     {name:30s} 検証済みの版に無い冊です")
        elif lm != v["last_modified"] or (size and int(size) != v["bytes"]):
            bad += 1
            print(f"  CHANGED {name:30s} {v['last_modified']} ({v['bytes']}B) → {lm} ({size}B)")
        else:
            print(f"  ok      {name}")
    for name in sorted(set(ver["manuals"]) - listed):
        bad += 1
        print(f"  GONE    {name:30s} マニフェストから無くなっています")

    print("\n== 設定例ページ（GET して本文の指紋を比較）==")
    listed = set()
    for u in fetch_examples.target_urls():
        name = kb.page_key(u) + ".html"
        listed.add(name)
        try:
            body, _ = httpget.get(u)
        except Exception as e:                      # noqa: BLE001
            bad += 1
            print(f"  BROKEN  {name}  {e}")
            continue
        want = ver.get("examples", {}).get(name)
        if want is None:
            bad += 1
            print(f"  NEW     {name}  検証済みの版に無いページです")
        elif fetch_examples.fingerprint(body) != want:
            bad += 1
            print(f"  CHANGED {name}  本文が検証済みの版と違います")
    for name in sorted(set(ver.get("examples", {})) - listed):
        bad += 1
        print(f"  GONE    {name}  マニフェストから無くなっています")
    if not bad:
        print("  すべて検証済みの版と同じ")

    if bad:
        print(f"\n変化・リンク切れ: {bad} 件。パーサの検証が必要かもしれません。"
              "\n  1) python3 scripts/build.py で取り直す  2) 抽出結果と網羅性チェックを確認"
              "\n  3) python3 scripts/build.py --accept-current で検証済みの版を更新")
        return 1
    print("\n公式サイトは検証済みの版から変わっていません。")
    return 0
