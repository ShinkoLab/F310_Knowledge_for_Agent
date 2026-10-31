#!/usr/bin/env python3
"""FITELnet F310 コマンドリファレンス(md)から、コマンド索引 JSON を生成する。

各コマンド定義ブロック（コマンド名 → 【機能】→【入力形式】→【動作モード】…）を解析し、
  command / manual / page / function / syntax / mode / params / description / default / ref
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
SECNO_ONLY_RE = re.compile(r"^\d+(?:\.\d+)+$")   # 節番号のみの行 例: 10.7.1
CHAPTER_RE = re.compile(r"^第\d+ 章")             # ページヘッダの章見出し 例: 第10 章 IPv4 の設定
PARAM_HEAD = ("パラメータ", "パラメーター")        # パラメータ表の先頭行（次の非空行が「設定内容」）


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
    """【機能】(func_idx) から上方向に走査してコマンド名を返す。無ければ None。"""
    return find_command_name_at(lines, func_idx)[0]


def find_command_name_at(lines, func_idx):
    """find_command_name の本体。(名前, 名前行の位置) を返す。見つからなければ (None, None)。
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
            return None, None                  # 別見出し = 前コマンド領域 → 打ち切り
        name = normalize_name(s)
        if is_command_name(name):
            return name, j
        # 版数値・節番号・説明断片 → さらに上へ
        j -= 1
        steps += 1
    return None, None


def next_nonblank(lines, i):
    while i < len(lines) and not lines[i].strip():
        i += 1
    return i


def strip_page_debris(lines):
    """ページ区切り直後のヘッダ（ページ番号・「コマンドリファレンス - …」・章見出し・節見出し）を落とす。
    区切り行（===== PAGE n =====）自体は残す。表やセクションの終端判定に使うため。"""
    out, i, n = [], 0, len(lines)
    while i < n:
        out.append(lines[i])
        m = PAGE_RE.match(lines[i])
        i += 1
        if not m:
            continue
        j = next_nonblank(lines, i)
        if j >= n or lines[j].strip() != m.group(1):
            continue
        j = next_nonblank(lines, j + 1)
        if j >= n or not lines[j].strip().startswith("コマンドリファレンス"):
            continue
        j = next_nonblank(lines, j + 1)
        if j < n and CHAPTER_RE.match(lines[j].strip()):
            j = next_nonblank(lines, j + 1)          # 章の下の節見出し（無いこともある）
            if j < n and not MARK_RE.match(lines[j].strip()):
                j += 1
        i = j
    return out


def next_header_start(lines, func_idx):
    """次のコマンドの見出し群（節番号・コマンド名）が始まる行を返す。
    ブロックは次の【機能】までなので、末尾に次コマンドの "10.7.1 / ip address" が混ざる。
    それを説明や表に取り込まないための切り落とし位置。名前が取れなければ func_idx。"""
    name, j = find_command_name_at(lines, func_idx)
    if name is None:
        return func_idx
    cut, seen, k = j, 0, j - 1
    while k >= 0 and seen < 6:
        s = lines[k].strip()
        if MARK_RE.match(s) or PAGE_RE.match(lines[k]):
            break
        if s:
            seen += 1
            if SECNO_ONLY_RE.match(s) or CHAPTER_RE.match(s):
                cut = k
        k -= 1
    return cut


def find_param_tables(lines):
    """パラメータ表（「パラメータ」「設定内容」…で始まる表）の範囲 [(start, end), ...] を返す。
    表は次の【見出し】・ページ区切り・次の表の先頭までで、別コマンドの表が連続することがある。"""
    def is_head(i):
        if lines[i].strip() not in PARAM_HEAD:
            return False
        j = next_nonblank(lines, i + 1)
        return j < len(lines) and lines[j].strip() == "設定内容"

    out, i, n = [], 0, len(lines)
    while i < n:
        if is_head(i):
            e = i + 1
            while (e < n and not PAGE_RE.match(lines[e]) and not MARK_RE.match(lines[e].strip())
                   and not is_head(e)):
                e += 1
            out.append((i, e))
            i = e
        else:
            i += 1
    return out


def table_first_cell(table: str) -> str:
    """表の先頭データ行の1セル目（パラメータ名）。見出し行の4語は読み飛ばす。"""
    for ln in table.splitlines():
        s = ln.strip()
        if s and s not in PARAM_HEAD and s not in ("設定内容", "設定範囲", "省略時"):
            return s
    return ""


def squash(s: str) -> str:
    return re.sub(r"[\s<>\[\]{}()|（）,]", "", s)


MODE_END_RE = re.compile(r"(モード|）|\))$")


def first_paragraph(lines) -> str:
    """最初の段落（空行かページ区切りまで）。複数モードの折り返しは同じ段落に入る。

    折り返しの途中に空行が挟まることがある（「…インタフェー」⏎⏎「ス設定モード」）。
    空行の手前がモード名の終わりに見えないときは、表の見出しが来ない限り次の段落へ続ける。
    """
    out, gap = [], False
    for ln in lines:
        s = ln.strip()
        if PAGE_RE.match(ln):
            break
        if not s:
            if out:
                if MODE_END_RE.search(out[-1]):
                    break
                gap = True
            continue
        if gap and s in PARAM_HEAD:
            break
        out.append(s)
        gap = False
    return "\n".join(out)


def section_text(lines, keep_blank=False) -> str:
    body = [ln.rstrip() for ln in lines if not PAGE_RE.match(ln)]
    text = "\n".join(body).strip()
    return re.sub(r"\n{2,}", "\n\n" if keep_blank else "\n", text)


def split_raw(lines) -> dict:
    """【見出し】→ 本文の行リスト。extract_sections と違い空行を保つ（段落判定のため）。"""
    out, key = {}, None
    for ln in lines:
        m = MARK_RE.match(ln.strip())
        if m:
            key = m.group(1)
            out[key] = []
        elif key is not None:
            out[key].append(ln)
    return out


def assign_tables(recs) -> None:
    """パラメータ表を持ち主のコマンドに割り当て、recs[i]["params"] に入れる。

    PDFのテキスト抽出では表が自分のブロックに収まらず、後ろのコマンドの【入力形式】の後ろや
    ページ末尾に回ることがある（約4割）。【パラメータ】見出しは持ち主側に残るので、
    「見出しがあって表がまだ無いコマンド」の待ち行列と、表の先頭セル（パラメータ名）が
    構文に含まれるかで持ち主を決める。決め手が無ければ待ち行列の先頭、それも無ければ現在のブロック。"""
    pend = []
    for k, r in enumerate(recs):
        if r["named"] and r["heading"]:
            pend.append(k)
        for page, text in r["tables"]:
            pend = [p for p in pend if page - recs[p]["page"] <= 2]
            # 見出しの無いコマンド（enable 等）の表も後ろへ回ることがあるので、直近の見出し無しも候補に足す
            bare = [j for j in range(max(0, k - 6), k + 1)
                    if recs[j]["named"] and not recs[j]["heading"] and not recs[j]["params"]
                    and page - recs[j]["page"] <= 2]
            cands = pend + bare + ([k] if k not in pend + bare and r["named"] else [])
            first = squash(table_first_cell(text))
            pick = next((c for c in cands if first and first in recs[c]["syn"]), None)
            if pick is None:
                pick = pend[0] if pend else (k if r["named"] else None)
            if pick is None:
                continue
            recs[pick]["params"].append(text)
            if pick in pend:
                pend.remove(pick)


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
    recs = []
    for k, func_marker in enumerate(marks):
        end = marks[k + 1] if k + 1 < len(marks) else len(lines)
        block = lines[func_marker:end]
        sections = extract_sections(block)

        # 名前: 上方向スキャン。取れなければ入力形式の先頭語で補完(ページ跨ぎ対策)
        name = find_command_name(lines, func_marker)
        if not name:
            name = name_from_syntax(sections.get("入力形式", ""))

        # 動作モード・説明・未設定時・パラメータ表は、ページヘッダと次コマンドの見出しを落とし、
        # 表を本文から切り出した上で読む（表の見出しが【動作モード】の本文に流れ込むため）。
        if k + 1 < len(marks):
            block = block[:max(1, next_header_start(lines, marks[k + 1]) - func_marker)]
        block = strip_page_debris(block)
        ranges = find_param_tables(block)
        cut = {i for s, e in ranges for i in range(s, e)}
        rest = split_raw([ln for i, ln in enumerate(block) if i not in cut])
        tables = []
        for s, e in ranges:
            text = section_text(block[s:e], keep_blank=True)
            if len(text.splitlines()) > 4:               # 見出し4語だけの表は中身なし
                tables.append((page_at[func_marker + s], text))

        recs.append({
            "named": bool(name),
            "heading": any(ln.strip() == "【パラメータ】" for ln in block),
            "syn": squash(sections.get("入力形式", "")),
            "page": page_at[func_marker],
            "tables": tables,
            "params": [],
            "entry": {
                "command": name,
                "manual": stem,
                "category": label,
                "page": page_at[func_marker],
                "function": sections.get("機能", ""),
                "syntax": sections.get("入力形式", ""),
                "mode": first_paragraph(rest.get("動作モード", [])),
                "params": "",
                "description": section_text(rest.get("説明", [])),
                "default": section_text(rest.get("未設定時", [])),
                "ref": f"{stem}.pdf p.{page_at[func_marker]}",
            },
        })

    assign_tables(recs)
    entries = []
    for r in recs:
        if r["named"]:                                   # 凡例など非コマンドは捨てる
            r["entry"]["params"] = "\n\n".join(r["params"])
            entries.append(r["entry"])
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
