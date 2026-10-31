#!/usr/bin/env python3
"""「パーサを検証した時点の公式サイトの版」を記録・照会する。

data/validated_versions.json に、検証したときの版を本文なしで持つ:
  manuals  冊ごとの Last-Modified / バイト数 / ページ数（コマンド索引を持つ冊はコマンド数も）
  examples 設定例ページごとの本文の指紋（fetch_examples.fingerprint）
  example_count  生成される設定例md件数

用途は2つ。
  - build.py の網羅性チェック: 手元の版が検証済みの版と同じなのに数が違えば抽出の退行、
    版が違うなら数が変わるのは想定どおり（検証し直して更新する）、と区別できる。
  - build.py --check-updates: 公式サイトを、検証済みの版と手元のKBのそれぞれと突き合わせる。
  - lookup.py status: 手元のKBが検証済みの版より古くないかを、ネットワークを使わずに調べる。

更新は build.py --accept-current（手元のKBの現状を検証済みの版にする）。
"""
import json
import sys
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

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


STALE_DAYS = 30   # 公式サイトとの最後の突き合わせからこれだけ経ったら、更新の確認を勧める


def _http_date(s: str):
    try:
        return parsedate_to_datetime(s) if s else None
    except (TypeError, ValueError):
        return None


def _index_problem() -> str:
    try:
        idx = json.loads((kb.md_dir() / "command_index.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "コマンド索引が読めません"
    if idx.get("commands") and "params" not in idx["commands"][0]:
        return "コマンド索引が旧形式です（パラメータ表・説明・未設定時の欄が無い）"
    return ""


def local_status(ver: dict) -> list:
    """手元のKBが検証済みの版より古い理由のリスト（ネットワークを使わない判定。古くなければ空）。

    検証済みの版より新しい版を取り込んだKB（サイトが先に改版した）は古いとは言えないので、
    マニュアルは Last-Modified の前後で判定する。設定例の指紋は新旧の順が分からないので、
    記録が無いことだけを見る（中身の新旧はネットワークありの check_updates が見る）。
    """
    if not kb.is_built():
        return ["知識ベースが未構築です"]
    state = kb.load_state()
    seen = state.get("manuals") if isinstance(state.get("manuals"), dict) else {}
    ex_seen = state.get("examples") if isinstance(state.get("examples"), dict) else {}
    out = []
    old = []
    for n, v in ver.get("manuals", {}).items():
        cur = seen.get(n)
        if not cur:
            old.append(n)
            continue
        mine, want = _http_date(cur.get("last_modified", "")), _http_date(v.get("last_modified", ""))
        try:
            is_old = mine < want if mine and want else manual_changed(cur, v)
        except TypeError:   # タイムゾーンの有無が混在。日付で比べられないので違いだけで判断する
            is_old = manual_changed(cur, v)
        if is_old:
            old.append(n)
    if old:
        out.append(f"マニュアルPDF {len(old)} 冊が検証済みの版より古いか、取得の記録がありません"
                   f"（{', '.join(n[:-4] for n in old)}）")
    unrecorded = [n for n in ver.get("examples", {}) if not (ex_seen.get(n) or {}).get("sha256")]
    if unrecorded:
        # 2.3.0 より前に取得したKBは指紋を記録していない。中身が同じかは判断できないので取り直させる
        out.append(f"設定例 {len(unrecorded)} 件に本文の指紋の記録がありません（2.3.0 より前に取得したKB）")
    problem = _index_problem()
    if problem:
        out.append(problem)
    return out


def last_contact(state: dict):
    """公式サイトと最後に突き合わせた日時（取得か --check-updates）。記録が無ければ None。"""
    times = []
    for key in ("last_fetch", "last_checked"):
        try:
            times.append(datetime.fromisoformat(state[key]))
        except (KeyError, TypeError, ValueError):
            pass
    return max(times) if times else None


def contact_note(state: dict, now: datetime = None) -> str:
    """最後の突き合わせから STALE_DAYS 日を超えていれば、更新の確認を勧める1行。それ以外は空。"""
    last = last_contact(state)
    if last is None:
        return "公式サイトと突き合わせた日時の記録がありません（2.4.0 より前に構築したKB）"
    days = ((now or datetime.now(timezone.utc)) - last).days
    if days > STALE_DAYS:
        return f"公式サイトとの最後の突き合わせから {days} 日経っています（{last.date()}）"
    return ""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def check_updates() -> int:
    """公式サイトを、検証済みの版と手元のKBのそれぞれと突き合わせる。

    マニュアルは HEAD（Last-Modified / Content-Length）、設定例は GET して指紋を比べる
    （設定例のページは更新日時を返さないため）。KBの中身には書かない。全件に問い合わせられたら
    突き合わせた日時（last_checked）だけを .build.json に記録する。
    サイトが検証済みの版から変わっているか、取得できないものがあるか、手元のKBがサイトより古ければ 1。
    """
    ver = load()
    if not ver.get("manuals"):
        print(f"検証済みの版がありません: {kb.VALIDATED}", file=sys.stderr)
        return 1
    built = kb.is_built()
    state = kb.load_state()
    seen = state.get("manuals") if isinstance(state.get("manuals"), dict) else {}
    ex_seen = state.get("examples") if isinstance(state.get("examples"), dict) else {}
    newer = broken = 0
    local_old_m, local_old_e = [], []

    print("== マニュアルPDF（HEAD）==")
    listed = set()
    for m in kb.load_manifest(kb.MANUALS_MANIFEST)["manuals"]:
        name = m["file"]
        listed.add(name)
        v = ver["manuals"].get(name)
        try:
            _, h = httpget.get(m["url"], head=True)
        except Exception as e:                      # noqa: BLE001 - 1冊の失敗で全体を止めない
            broken += 1
            print(f"  BROKEN  {name:30s} {e}")
            continue
        lm, size = h.get("Last-Modified", ""), h.get("Content-Length")
        site = {"last_modified": lm, "bytes": int(size) if size else None}
        cur = seen.get(name)
        if built and (not cur or cur.get("last_modified") != lm
                      or (site["bytes"] and cur.get("bytes") != site["bytes"])):
            local_old_m.append(name)
        if not v:
            newer += 1
            print(f"  NEW     {name:30s} 検証済みの版に無い冊です")
        elif lm != v["last_modified"] or (site["bytes"] and site["bytes"] != v["bytes"]):
            newer += 1
            print(f"  CHANGED {name:30s} {v['last_modified']} ({v['bytes']}B) → {lm} ({size}B)")
        else:
            print(f"  ok      {name}")
    for name in sorted(set(ver["manuals"]) - listed):
        broken += 1
        print(f"  GONE    {name:30s} マニフェストから無くなっています")

    print("\n== 設定例ページ（GET して本文の指紋を比較）==")
    listed = set()
    ex_bad = 0
    for u in fetch_examples.target_urls():
        name = kb.page_key(u) + ".html"
        listed.add(name)
        try:
            body, _ = httpget.get(u)
        except Exception as e:                      # noqa: BLE001
            broken += 1
            ex_bad += 1
            print(f"  BROKEN  {name}  {e}")
            continue
        fp = fetch_examples.fingerprint(body)
        if built and (ex_seen.get(name) or {}).get("sha256") != fp:
            local_old_e.append(name)
        want = ver.get("examples", {}).get(name)
        if want is None:
            newer += 1
            ex_bad += 1
            print(f"  NEW     {name}  検証済みの版に無いページです")
        elif fp != want:
            newer += 1
            ex_bad += 1
            print(f"  CHANGED {name}  本文が検証済みの版と違います")
    for name in sorted(set(ver.get("examples", {})) - listed):
        broken += 1
        ex_bad += 1
        print(f"  GONE    {name}  マニフェストから無くなっています")
    if not ex_bad:
        print("  すべて検証済みの版と同じ")

    # 手元のKBは「いまの公式サイト」と比べる。検証済みの版と比べると、サイトが先に改版して
    # それを取り込んだKBが、いつまでも古いと言われ続けてしまう。
    behind = []
    if not built:
        behind.append("知識ベースが未構築です")
    else:
        if local_old_m:
            behind.append(f"マニュアルPDF {len(local_old_m)} 冊が公式サイトより古いか、取得の記録がありません"
                          f"（{', '.join(n[:-4] for n in local_old_m)}）")
        if local_old_e:
            behind.append(f"設定例 {len(local_old_e)} 件が公式サイトの本文と違うか、指紋の記録がありません")
        problem = _index_problem()
        if problem:
            behind.append(problem)
    print(f"\n== 手元のKB（{kb.kb_root()}）==")
    for why in behind:
        print(f"  OLD     {why}")
    if not behind:
        print("  公式サイトと同じ")

    # 1件でも問い合わせに失敗したら、突き合わせたとは言えないので記録しない
    if built and not broken:
        state["last_checked"] = now_iso()
        kb.save_state(state)

    build = kb.REPO / "scripts" / "build.py"
    print("\n== 結果 ==")
    if newer:
        print(f"  公式サイト: このプラグインが検証した版より新しいものが {newer} 件あります。"
              + (f"\n    取り込むには python3 {build} を実行します（未検証の版なので、件数の注記が出ることがあります）。"
                 if behind else "\n    手元のKBは取り込み済みです（このプラグインでは未検証の版）。")
              + f"\n    保守者向け: 抽出結果と網羅性チェックを確認し、python3 {build} --accept-current で検証済みの版を更新する。")
    elif not broken:
        print("  公式サイト: このプラグインが検証した版から変わっていません。")
    if broken:
        print(f"  公式サイト: 取得できないもの・マニフェストから無くなったものが {broken} 件あります"
              "（ネットワークの不調か、公式サイトの構成変更）。")
    if behind:
        print(f"  手元のKB:   公式サイトより古いところがあります。次のコマンドで更新してください（取得あり）:"
              f"\n    python3 {build}")
    elif not broken:
        print("  手元のKB:   最新です（公式サイトと同じ）。")
    else:
        print("  手元のKB:   問い合わせに失敗したものがあるため、最新かどうかは判断できません。")
    return 1 if newer or broken or behind else 0
