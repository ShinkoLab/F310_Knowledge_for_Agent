#!/usr/bin/env python3
"""「パーサを検証した時点の公式サイトの版」を記録・照会する。

data/validated_versions.json に、検証したときの版を本文なしで持つ:
  manuals  冊ごとの Last-Modified / バイト数 / ページ数（コマンド索引を持つ冊はコマンド数も）
  examples 設定例ページごとの本文の指紋（fetch_examples.fingerprint）
  example_count  生成される設定例md件数

用途は2つ。
  - build.py の網羅性チェック: 手元の版が検証済みの版と同じなのに数が違えば抽出の退行、
    版が違うなら数が変わるのは想定どおり（検証し直して更新する）、と区別できる。
  - build.py --check-updates: 公式サイトと手元のKBのそれぞれが検証済みの版と同じかを、KBに書かずに調べる。

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


def local_status(ver: dict) -> list:
    """手元のKBが検証済みの版に追いついていない理由のリスト（追いついていれば空）。

    --check-updates はサイトと検証済みの版を比べるだけなので、それが「変化なし」でも
    手元のKBが旧版のことがある。その取り違えを防ぐために、手元の記録（.build.json）と索引も見る。
    """
    if not kb.is_built():
        return ["知識ベースが未構築です"]
    state = kb.load_state()
    seen = state.get("manuals") if isinstance(state.get("manuals"), dict) else {}
    ex_seen = state.get("examples") if isinstance(state.get("examples"), dict) else {}
    out = []
    old = [n for n, v in ver.get("manuals", {}).items()
           if not seen.get(n) or manual_changed(seen.get(n), v)]
    if old:
        out.append(f"マニュアルPDF {len(old)} 冊が検証済みの版と違うか、取得の記録がありません"
                   f"（{', '.join(n[:-4] for n in old)}）")
    want = ver.get("examples", {})
    unrecorded = [n for n in want if not (ex_seen.get(n) or {}).get("sha256")]
    if unrecorded:
        # 2.3.0 より前に取得したKBは指紋を記録していない。中身が同じかは判断できないので取り直させる
        out.append(f"設定例 {len(unrecorded)} 件に本文の指紋の記録がありません（2.3.0 より前に取得したKB）")
    stale = [n for n in want if n not in unrecorded and ex_seen[n]["sha256"] != want[n]]
    if stale:
        out.append(f"設定例 {len(stale)} 件の本文が検証済みの版と違います")
    try:
        idx = json.loads((kb.md_dir() / "command_index.json").read_text(encoding="utf-8"))
        if idx.get("commands") and "params" not in idx["commands"][0]:
            out.append("コマンド索引が旧形式です（パラメータ表・説明・未設定時の欄が無い）")
    except (OSError, json.JSONDecodeError):
        out.append("コマンド索引が読めません")
    return out


def check_updates() -> int:
    """公式サイトと手元のKBを、それぞれ検証済みの版と突き合わせる。KBには書かない。

    マニュアルは HEAD（Last-Modified / Content-Length）、設定例は GET して指紋を比べる
    （設定例のページは更新日時を返さないため）。手元のKBは .build.json と索引だけを見る。
    サイトに変化・リンク切れがあるか、手元のKBが追いついていなければ 1。
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

    behind = local_status(ver)
    print(f"\n== 手元のKB（{kb.kb_root()}）==")
    for why in behind:
        print(f"  OLD     {why}")
    if not behind:
        print("  検証済みの版と同じ")

    build = kb.REPO / "scripts" / "build.py"
    print("\n== 結果 ==")
    if bad:
        print(f"  公式サイト: 検証済みの版から変化・リンク切れが {bad} 件あります（パーサの検証が要るかもしれません）。"
              f"\n    保守者は 1) python3 {build} で取り直す  2) 抽出結果と網羅性チェックを確認"
              f"\n    3) python3 {build} --accept-current で検証済みの版を更新")
    else:
        print("  公式サイト: 検証済みの版から変わっていません。")
    if behind:
        print(f"  手元のKB:   検証済みの版に追いついていません。次のコマンドで更新してください（取得あり）:"
              f"\n    python3 {build}")
    else:
        print("  手元のKB:   最新です（検証済みの版と同じ）。")
    return 1 if bad or behind else 0
