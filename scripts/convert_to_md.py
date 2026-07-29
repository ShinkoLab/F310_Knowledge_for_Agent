#!/usr/bin/env python3
"""FITELnet F310 の PDF マニュアルを、ページ番号マーカー付きの Markdown/テキストへ変換する。
- テキスト層をそのまま抽出（OCR不要）
- 各ページの先頭に `===== PAGE N =====` を挿入 → grep で該当ページを特定・引用できる
- 入力は KB/original/*.pdf（無変更）、出力は KB/md/*.md
"""
import re
import subprocess
import sys
from pathlib import Path

import kb_paths as kb

# 3行以上の空行を1行に、行末空白を除去
_blank = re.compile(r"\n[ \t]*\n[ \t]*\n+")
_trail = re.compile(r"[ \t]+\n")


def clean(text: str) -> str:
    text = _trail.sub("\n", text)
    text = _blank.sub("\n\n", text)
    return text.strip("\n")


def convert(pdf: Path, out_dir: Path) -> tuple[int, int]:
    # mutool は txt 出力でページ間を \f (form feed) で区切る
    raw = subprocess.run(
        ["mutool", "draw", "-F", "txt", "-o", "-", str(pdf)],
        capture_output=True, check=True,
    ).stdout.decode("utf-8", errors="replace")

    pages = raw.split("\f")
    # source 行は KB ルートからの相対パス（旧レイアウトでは manuals/original/… だった）
    out_lines = [f"# {pdf.name}", "", f"source: original/{pdf.name}", ""]
    n = 0
    for page in pages:
        body = clean(page)
        if not body and n > 0:
            # 末尾の空ページはスキップ（先頭以外）
            continue
        n += 1
        out_lines.append(f"\n===== PAGE {n} =====\n")
        out_lines.append(body)

    md = out_dir / (pdf.stem + ".md")
    md.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    return n, md.stat().st_size


def run() -> int:
    src, out = kb.original_dir(), kb.md_dir()
    out.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(src.glob("*.pdf"))
    if not pdfs:
        print(f"PDF がありません: {src}", file=sys.stderr)
        return 0
    print(f"{len(pdfs)} PDF を変換 → {out}\n")
    total_pages = 0
    for pdf in pdfs:
        n, size = convert(pdf, out)
        total_pages += n
        print(f"  {pdf.name:30s} {n:5d} p  {size/1024:8.1f} KB")
    print(f"\n合計 {total_pages} ページを Markdown 化しました。")
    return total_pages


if __name__ == "__main__":
    run()
