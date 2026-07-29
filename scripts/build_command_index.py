#!/usr/bin/env python3
"""FITELnet F310 コマンドリファレンス(md)から、コマンド索引 JSON を生成する。

各コマンド定義ブロック（コマンド名 → 【機能】→【入力形式】→【動作モード】…）を解析し、
  command / manual / page / function / syntax / mode / ref
を持つ JSON を出力する。AI がコマンド構文をピンポイント参照するための索引。

純正PDFのレイアウト揺れへの個別対応（版数見出しの読み飛ばし、節番号・モード括弧の除去、
日本語括弧修飾の保持、ページ跨ぎ時の名前補完）が入っている。抽出ロジックを変えたときは
build.py の網羅性チェック（構成定義編 1,299 / 運用管理編 615）が崩れていないか必ず確認すること。
"""
import json
import re
import sys
from datetime import date

import kb_paths as kb

# 対象マニュアルと分類ラベル
TARGETS = {
    "cmd_refe_config": "構成定義編",
    "cmd_refe_ope": "運用管理編",
}

PAGE_RE = re.compile(r"^===== PAGE (\d+) =====$")
MARK_RE = re.compile(r"^【(.+?)】\s*$")          # 【機能】など単独行の見出し
# コマンド名らしさ: ASCII英字始まり・日本語を含まない・句点で終わらない
JP_RE = re.compile(r"[ぁ-んァ-ヶ一-龠、。：]")
SECNO_RE = re.compile(r"^\d+(?:\.\d+)+\s+")      # 先頭の節番号 例: "10.10.1 "
MODEPAREN_RE = re.compile(r"\s*[（(][^）)]*モード[^）)]*[）)]\s*$")  # 末尾の(〜モード)
VERSION_RE = re.compile(r"^V?\d+(?:\.\d+)+$")    # 版数/節番号のみの行 例: V01.00 / 6.1.54


def normalize_name(s: str) -> str:
    s = s.strip()
    s = SECNO_RE.sub("", s)          # 節番号を除去
    s = MODEPAREN_RE.sub("", s)      # 末尾のモード括弧を除去
    return s.strip()


QUALIFIER_RE = re.compile(r"\s*[（(][^）)]*[）)]\s*$")  # 末尾の括弧修飾 例:（IPv4 標準設定）


def is_command_name(s: str) -> bool:
    if not s or len(s) > 80:
        return False
    base = QUALIFIER_RE.sub("", s).strip()   # 末尾の括弧修飾は判定から除外(名前自体は保持)
    if not re.match(r"^[A-Za-z]", base):     # 英字始まり
        return False
    if JP_RE.search(base):                    # 日本語混在は説明文
        return False
    if VERSION_RE.match(base):                # 版数のみは除外
        return False
    return True


def name_from_syntax(syntax: str) -> str:
    """入力形式の先頭行から、パラメータ(< [ { ( )開始まで の固定キーワード列を名前として抽出。
    ページ跨ぎで名前行が取れなかった場合のフォールバック。"""
    for line in syntax.splitlines():
        line = line.strip()
        if not line:
            continue
        line = re.sub(r"^no\s+", "", line)   # 否定形は除く
        toks = []
        for t in line.split():
            if t[0] in "<[{(" or JP_RE.search(t):
                break
            toks.append(t)
        name = " ".join(toks).strip()
        if is_command_name(name):
            return name
        return ""
    return ""


def find_command_name(lines, func_idx):
    """【機能】(func_idx) から上方向に走査してコマンド名を返す。無ければ None。
    版数ブロック(【対応ファームウェアバージョン】とその値)や節番号行は読み飛ばし、
    別の見出し(前コマンドの終端)に達したら打ち切る。"""
    j = func_idx - 1
    steps = 0
    while j >= 0 and steps < 12:
        raw = lines[j]
        s = raw.strip()
        if not s or PAGE_RE.match(raw):
            j -= 1
            continue
        m = MARK_RE.match(s)
        if m:
            if "ファーム" in m.group(1):       # 版数見出し(対応/対象の誤記含む) → 飛ばす
                j -= 1
                continue
            return None                        # 別見出し = 前コマンド領域 → 打ち切り
        name = normalize_name(s)
        if is_command_name(name):
            return name
        # 版数値・節番号・説明断片 → さらに上へ
        j -= 1
        steps += 1
    return None


def parse(stem: str, label: str) -> list[dict]:
    lines = (kb.md_dir() / f"{stem}.md").read_text(encoding="utf-8").splitlines()

    # 行→ページ番号の対応表を作る
    page_at = [0] * len(lines)
    cur = 0
    for i, ln in enumerate(lines):
        m = PAGE_RE.match(ln)
        if m:
            cur = int(m.group(1))
        page_at[i] = cur

    # 1) 全【機能】位置をブロック境界にする
    marks = [i for i, ln in enumerate(lines) if ln.strip() == "【機能】"]

    # 2) 各ブロック（【機能】→ 次の【機能】の手前）でセクション抽出＋名前決定
    entries = []
    for k, func_marker in enumerate(marks):
        end = marks[k + 1] if k + 1 < len(marks) else len(lines)
        block = lines[func_marker:end]
        sections = extract_sections(block)

        # 名前: 上方向スキャン。取れなければ入力形式の先頭語で補完(ページ跨ぎ対策)
        name = find_command_name(lines, func_marker)
        if not name:
            name = name_from_syntax(sections.get("入力形式", ""))
        if not name:
            continue  # 凡例など非コマンド

        entries.append({
            "command": name,
            "manual": stem,
            "category": label,
            "page": page_at[func_marker],
            "function": sections.get("機能", ""),
            "syntax": sections.get("入力形式", ""),
            "mode": sections.get("動作モード", ""),
            "ref": f"{stem}.pdf p.{page_at[func_marker]}",
        })
    return entries


def extract_sections(block: list[str]) -> dict:
    """ブロック内の 【見出し】→本文 を辞書化。本文は次の見出しまでを連結。"""
    out, key, buf = {}, None, []

    def flush():
        if key is not None:
            text = "\n".join(buf).strip()
            text = re.sub(r"\n{2,}", "\n", text)
            out[key] = text

    for ln in block:
        m = MARK_RE.match(ln.strip())
        if m:
            flush()
            key, buf = m.group(1), []
        elif key is not None and not PAGE_RE.match(ln):
            buf.append(ln.rstrip())
    flush()
    return out


def load_existing(out) -> dict:
    """既存の索引を {manual: [entry, ...]} で返す。無い・壊れている場合は空。"""
    if not out.exists():
        return {}
    try:
        doc = json.loads(out.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"  既存の索引を読めません（無視します）: {e}", file=sys.stderr)
        return {}
    # JSONとしては読めても構造が想定外（リスト、commands が null、要素が非dict等）の
    # ことがある。ここで落ちると復旧ビルド自体が止まるので、壊れた索引として無視する。
    commands = doc.get("commands") if isinstance(doc, dict) else None
    if not isinstance(commands, list):
        print(f"  既存の索引の形式が想定と違います（無視します）: {out.name}", file=sys.stderr)
        return {}
    by_manual = {}
    for c in commands:
        if isinstance(c, dict):
            by_manual.setdefault(c.get("manual", ""), []).append(c)
    return by_manual


def run() -> dict:
    md = kb.md_dir()
    md.mkdir(parents=True, exist_ok=True)

    out = md / "command_index.json"
    present = [s for s in TARGETS if (md / f"{s}.md").exists()]
    missing = [s for s in TARGETS if s not in present]
    # 「索引ファイルがある＝索引が完全」ではない。存在だけを根拠に丸ごと保持すると、
    # 片方の冊が復旧しても新しく読めたコマンドがいつまでも索引に入らない。
    # 読める冊は作り直し、欠けている冊だけ既存索引のエントリを引き継ぐ。
    kept = load_existing(out) if missing else {}
    if missing:
        detail = ", ".join(
            f"{s}（既存索引から {len(kept[s])} 件を引き継ぎ）" if kept.get(s) else s
            for s in missing)
        print(f"  コマンドリファレンスのmdがありません: {detail}", file=sys.stderr)

    if not present:
        # 解析できるmdが1冊も無い。既存の索引があるならそれが最善なので触らない。
        # このとき返すのは既存索引の実件数。0 を返すと呼び出し側が
        # 「抽出が全崩壊した」と誤認し、.build.json の基準値まで壊れる。
        counts = {s: len(v) for s, v in kept.items() if s in TARGETS and v}
        if counts:
            print(f"  解析できるmdがないため既存の索引をそのまま使います"
                  f": {sum(counts.values())} コマンド {counts}", file=sys.stderr)
        else:
            print("  索引を作れません（コマンドリファレンスのmdが1冊もありません）", file=sys.stderr)
        return counts

    per_manual = {}
    commands = []
    for stem, label in TARGETS.items():
        if stem in present:
            e = parse(stem, label)
            print(f"  {stem:20s} {len(e):5d} commands")
        else:
            e = kept.get(stem, [])
            if not e:
                continue
            print(f"  {stem:20s} {len(e):5d} commands（既存索引から引き継ぎ）")
        per_manual[stem] = len(e)
        commands.extend(e)

    if not commands:
        # 空の索引を書くと is_built() だけ満たしてしまい、lookup が黙って「該当なし」を
        # 返すKBができあがる。それなら書かない方がよい。
        print("  コマンドを1件も抽出できませんでした。索引は更新しません。", file=sys.stderr)
        return per_manual

    doc = {
        "generated": date.today().isoformat(),
        "device": "FITELnet F310",
        "note": "コマンド索引。page は PDF物理ページ。本文は <KB>/md/<manual>.md、原本は <KB>/original/<manual>.pdf",
        "counts": per_manual,
        "total": len(commands),
        "commands": commands,
    }
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n合計 {len(commands)} コマンド → {out} ({out.stat().st_size/1024:.1f} KB)")
    return per_manual


def main() -> int:
    """終了コードは「使える索引がKBに在るか」で決める。
    返り値の真偽で判定すると、意図的な引き継ぎ(=正常)で 1、抽出全崩壊(=異常)で 0 と
    両方向に反転してしまう。"""
    counts = run()
    if not (kb.md_dir() / "command_index.json").exists():
        return 1
    return 0 if sum(counts.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
