#!/usr/bin/env python3
"""2つの command_index.json を (manual, page, command) 単位で突き合わせる。

  diff_index.py old.json new.json [--examples N] [--width W]

build_command_index.py の抽出ロジックを触ったときに、何が増減・変化したかを確かめる道具。
追加・削除されたコマンドと、欄（function / syntax / mode / …）ごとの変化件数と例を出す。
片方にしか無い欄（例: 新しい索引で増えた params）は、変化ではなく「欄の増減」として別に示す。
同じキーが複数あるとき（同ページに同名コマンド）は、出現順で対応づける。

差があれば終了コード1、同一なら0（diff と同じ）。
"""
import argparse
import json
import sys
from collections import defaultdict, OrderedDict
from pathlib import Path

KEY_FIELDS = ("manual", "page", "command")


def load(path: Path) -> list:
    try:
        return json.loads(path.read_text(encoding="utf-8"))["commands"]
    except (OSError, ValueError, KeyError) as e:
        raise SystemExit(f"{path} を読めません: {e}")


def keyed(cmds: list) -> "OrderedDict":
    """(manual, page, command, 出現順) → エントリ。"""
    seen = defaultdict(int)
    out = OrderedDict()
    for c in cmds:
        k = (c.get("manual", ""), c.get("page", 0), c.get("command", ""))
        out[k + (seen[k],)] = c
        seen[k] += 1
    return out


def fmt_key(k: tuple) -> str:
    suffix = f" #{k[3] + 1}" if k[3] else ""
    return f"{k[0]} p.{k[1]} {k[2]}{suffix}"


def clip(v, width: int) -> str:
    s = str(v).replace("\n", "⏎")
    return s if len(s) <= width else s[: width - 1] + "…"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("old", type=Path)
    ap.add_argument("new", type=Path)
    ap.add_argument("--examples", type=int, default=5, help="各項目で示す例の数（既定 5）")
    ap.add_argument("--width", type=int, default=90, help="例の値を切り詰める文字数（既定 90）")
    args = ap.parse_args()

    old_list, new_list = load(args.old), load(args.new)
    old, new = keyed(old_list), keyed(new_list)
    print(f"旧 {len(old)} 件 ({args.old.name})  新 {len(new)} 件 ({args.new.name})")

    added = [k for k in new if k not in old]
    removed = [k for k in old if k not in new]
    common = [k for k in new if k in old]
    differs = bool(added or removed)

    for label, keys, src in (("追加", added, new), ("削除", removed, old)):
        print(f"\n{label}: {len(keys)} 件")
        for k in keys[: args.examples]:
            print(f"  {fmt_key(k)}  [{clip(src[k].get('mode', ''), 40)}]")
        if len(keys) > args.examples:
            print(f"  … 他 {len(keys) - args.examples} 件")

    # 欄の有無は、両方の索引の先頭エントリの欄で判定する（空文字の欄と「欄が無い」を区別する）
    old_fields = set().union(*(c.keys() for c in old_list)) if old_list else set()
    new_fields = set().union(*(c.keys() for c in new_list)) if new_list else set()
    only_new, only_old = sorted(new_fields - old_fields), sorted(old_fields - new_fields)
    if only_new or only_old:
        differs = True
        print("\n欄の増減:")
        for f in only_new:
            n = sum(1 for k in common if new[k].get(f))
            print(f"  + {f}: 新のみ（共通 {len(common)} 件中 {n} 件が非空）")
        for f in only_old:
            n = sum(1 for k in common if old[k].get(f))
            print(f"  - {f}: 旧のみ（共通 {len(common)} 件中 {n} 件が非空）")

    changes = defaultdict(list)
    for k in common:
        for f in sorted((old_fields & new_fields) - set(KEY_FIELDS)):
            if old[k].get(f) != new[k].get(f):
                changes[f].append(k)
    print(f"\n共通 {len(common)} 件の欄ごとの変化:")
    if not changes:
        print("  なし")
    for f, keys in sorted(changes.items(), key=lambda kv: -len(kv[1])):
        differs = True
        print(f"  {f}: {len(keys)} 件")
        for k in keys[: args.examples]:
            print(f"    {fmt_key(k)}")
            print(f"      旧: {clip(old[k].get(f), args.width)}")
            print(f"      新: {clip(new[k].get(f), args.width)}")
        if len(keys) > args.examples:
            print(f"    … 他 {len(keys) - args.examples} 件")
    return 1 if differs else 0


if __name__ == "__main__":
    sys.exit(main())
