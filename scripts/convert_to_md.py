#!/usr/bin/env python3
"""FITELnet F310 の PDF マニュアルを、ページ番号マーカー付きの Markdown/テキストへ変換する。
- テキスト層をそのまま抽出（OCR不要）
- 各ページの先頭に `===== PAGE N =====` を挿入 → grep で該当ページを特定・引用できる
- 入力は KB/original/*.pdf（無変更）、出力は KB/md/*.md
"""
import re
import sys
from pathlib import Path
from typing import Optional   # `int | None` は Python 3.10 以降。3.9 でも import できるようにする

import kb_paths as kb
import pdf_text

# 3行以上の空行を1行に、行末空白を除去
_blank = re.compile(r"\n[ \t]*\n[ \t]*\n+")
_trail = re.compile(r"[ \t]+\n")


def clean(text: str) -> str:
    text = _trail.sub("\n", text)
    text = _blank.sub("\n\n", text)
    return text.strip("\n")


def convert(pdf: Path, out_dir: Path) -> tuple[int, int]:
    # 物理ページと1対1。空要素を落としてはいけない。図版だけのページや空ページを詰めると
    # 以降の PAGE 番号が全てずれ、出典のページ番号が黙って狂う。
    bodies = [clean(t) for t in pdf_text.page_texts(pdf)]

    # source 行は KB ルートからの相対パス（旧レイアウトでは manuals/original/… だった）
    out_lines = [f"# {pdf.name}", "", f"source: original/{pdf.name}", ""]
    n = 0
    for body in bodies:
        n += 1
        out_lines.append(f"\n===== PAGE {n} =====\n")
        out_lines.append(body)

    md = out_dir / (pdf.stem + ".md")
    md.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    return n, md.stat().st_size


def run() -> Optional[int]:
    """変換したページ数。PDFが1冊も無く変換段が動けなかった場合は None。

    「0ページ生成した」と「動けなかった」を呼び出し側が区別できるようにしている
    （--prune-pdf 後の再生成では後者が正常な状態）。
    """
    src, out = kb.original_dir(), kb.md_dir()
    out.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(src.glob("*.pdf"))
    if not pdfs:
        print(f"PDF がありません: {src}（既存のmdをそのまま使います）", file=sys.stderr)
        return None
    # 単体実行の入口。build.py は取得の前に同じ確認を済ませている（済んでいれば即座に返る）。
    err = pdf_text.ensure_available()
    if err:
        print(err, file=sys.stderr)
        return None
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
