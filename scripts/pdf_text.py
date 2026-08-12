#!/usr/bin/env python3
"""PDF のテキスト抽出。バックエンドは pypdfium2（PDFium）。

PDFium は BSD-3-Clause、pypdfium2 は Apache-2.0/BSD-3-Clause。prebuilt wheel だけで入り
コンパイラも外部コマンドも要らない。以前は mutool(MuPDF, AGPL) を subprocess で呼んでいたが、
利用者に AGPL のソフトを brew/apt で入れさせる必要があり、それを避けるために置き換えた。

pip 依存を持ち込むのはこのリポジトリでここだけ。影響をこのファイルに閉じるため、
導入の面倒（venv の用意）も抽出も全部ここで引き受ける。

## 和文の擬似スペースについて（このファイルの本題）

対象の純正PDFは和文をグリフ単位で位置指定しており、PDFium はその字間を単語区切りと
誤認して空白を挿入する。素の `get_text_range()` は

    コマン ド リ フ ァ レ ン ス   /   OSPF サービ ス設定モー ド への移行

を返す。これでは `lookup.py grep "サービス設定モード"` が当たらず、コマンド索引の
`【対応フ ァーム ウ ェ アバージ ョ ン】` 読み飛ばしも効かなくなって索引が壊れる。
（pypdf・pdfminer.six でも同じかそれ以上に壊れる。MuPDF だけが正しく繋いでいた。）

そこで PDFium が「生成した」空白だけを、字送りの実測値を見て落とす。実測（全10冊・
候補183,094箇所）では

    字送り / 文字幅   0.2〜0.9 : 92%   語中の字間（落とす）
                      1.0〜1.9 :  2%   ほぼ語中
                      2.0〜6.0 :  0.6% 表のセル境界（残す）
                      6.0〜    :  5%   段組み・ヘッダの列間（残す）

と分かれるので、閾値 2.0 は谷の中にある。行が違うもの（折り返しの継ぎ目）は
座標で除外する。原文にある本物の空白（IsGenerated が偽）は一切触らない。
"""
import ctypes
import os
import re
import subprocess
import sys
from pathlib import Path

import kb_paths as kb

PACKAGE = "pypdfium2"

# ひらがな・カタカナ・漢字・CJK記号・全角形。U+3000（全角空白）は空白側なので入れない。
_CJK = re.compile(r"[、-〿぀-ヿ㐀-䶿一-鿿豈-﫿！-￯]")

# これ以上離れていれば、字間ではなく本物の間隔（表のセル境界・段組み）とみなして残す。
# 文字幅に対する比。根拠は冒頭の実測分布。
_GAP_RATIO = 2.0

# PDFium が字形を Unicode に対応付けられなかった文字。対象PDFでは270箇所すべてが
# 英数字に挟まれたハイフン（port-channel / Treat-as-withdraw など）だったので復元する。
_UNMAPPED = "￾"

_mod = None      # 解決済みの pypdfium2 モジュール
_raw = None      # pypdfium2.raw（文字単位のAPIはこちらにしかない）


# ---------------------------------------------------------------- バックエンドの用意

def _venv_dir() -> Path:
    """KB配下に置く。プラグイン本体は更新のたびに入れ替わるが、KBは残るため。
    `/plugin uninstall` すればKBごと消えるので後始末も利用者の手を借りない。"""
    return kb.kb_root() / ".venv"


def _venv_python(d: Path) -> Path:
    return d / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _site_packages(d: Path) -> Path:
    """venv は実行中のインタプリタから作るので、site-packages の位置も同じ規則で決まる。
    Python を入れ替えた（mise の更新など）場合はこのパスが存在しなくなり、作り直しへ倒れる。"""
    if os.name == "nt":
        return d / "Lib" / "site-packages"
    return d / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"


def _try_import() -> bool:
    global _mod, _raw
    if _mod is not None:
        return True
    try:
        import pypdfium2
        import pypdfium2.raw
    except ImportError:
        return False
    _mod, _raw = pypdfium2, pypdfium2.raw
    return True


def _try_venv() -> bool:
    """既存の venv の site-packages を sys.path に足して import を試す。"""
    sp = _site_packages(_venv_dir())
    if not sp.is_dir() or str(sp) in sys.path:
        return False
    sys.path.append(str(sp))     # 追加は末尾。実行環境側のパッケージを隠さない
    if _try_import():
        return True
    sys.path.remove(str(sp))
    return False


def _provision() -> str:
    """venv を作って pypdfium2 を入れる。失敗したら理由を文字列で返す。"""
    d = _venv_dir()
    print(f"PDF抽出ライブラリ（{PACKAGE}）を {d} に導入します…", file=sys.stderr)
    d.parent.mkdir(parents=True, exist_ok=True)
    steps = (
        ([sys.executable, "-m", "venv", str(d)], "venv の作成"),
        ([str(_venv_python(d)), "-m", "pip", "install", "--quiet",
          "--disable-pip-version-check", PACKAGE], f"{PACKAGE} の取得"),
    )
    for cmd, what in steps:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True)
        except OSError as e:
            return f"{what}に失敗しました: {e}"
        if r.returncode != 0:
            tail = (r.stderr or r.stdout or "").strip().splitlines()
            return f"{what}に失敗しました:\n    " + "\n    ".join(tail[-5:])
    return ""


def ensure_available() -> str:
    """抽出できる状態にする。できていれば空文字、できなければ利用者向けの説明を返す。

    解決順は「実行中のインタプリタ → KB配下の venv → venv を作る」。自分で入れている人の
    環境には触らず、そうでない人には黙って用意する。利用者の Python へ pip install はしない。
    """
    if _try_import() or _try_venv():
        return ""
    err = _provision()
    if not err:
        # 作った直後は site-packages が sys.path に無いので、ここで初めて入る
        if _try_venv() or _try_import():
            return ""
        err = f"導入は成功しましたが {PACKAGE} を読み込めませんでした"
    return (
        f"PDFのテキスト抽出に必要な {PACKAGE} を用意できませんでした。\n"
        f"  {err}\n"
        f"ネットワークに繋がるか確認してください。venv を作れない環境では\n"
        f"  Debian/Ubuntu: sudo apt install python3-venv\n"
        f"手動で入れる場合は次のいずれかでも構いません:\n"
        f"  pip install {PACKAGE}\n"
        f'  python3 -m venv "{_venv_dir()}" && "{_venv_python(_venv_dir())}" -m pip install {PACKAGE}'
    )


# ---------------------------------------------------------------- 抽出

def _page_text(tp) -> str:
    """1ページ分のテキスト。PDFium が挿入した和文の擬似スペースだけを取り除く。"""
    n = tp.count_chars()
    if n < 3:
        return tp.get_text_range() if n else ""
    text = tp.get_text_range()
    # get_text_range() の戻りは文字配列と1対1で並ぶ前提。崩れたら添字が意味を失うので、
    # 何も削らずそのまま返す（誤った位置を削るくらいなら擬似スペースを残す方がまし）。
    if len(text) != n:
        return text

    handle = tp.raw
    left, right, bottom, top = (ctypes.c_double() for _ in range(4))

    def box(i):
        _raw.FPDFText_GetCharBox(handle, i, left, right, bottom, top)
        return left.value, right.value, bottom.value, top.value

    drop = set()
    for i in range(1, n - 1):
        if text[i] != " " or not _raw.FPDFText_IsGenerated(handle, i):
            continue
        prev, nxt = text[i - 1], text[i + 1]
        # 和文どうしの字間か、和文と閉じ括弧の間（`< ユーザ名 >` → `< ユーザ名>`）だけを見る。
        # 和文と英数字の間（`OSPF サービス` など）は原文でも空いているので触らない。
        if not (_CJK.match(prev) and (_CJK.match(nxt) or nxt in ")]}>")):
            continue
        pl, pr, pb, pt = box(i - 1)
        nl, nr, nb, nt = box(i + 1)
        width = max(pr - pl, nr - nl)
        if width <= 0:
            continue
        if abs((pb + pt) / 2 - (nb + nt) / 2) > (pt - pb) * 0.5:
            continue                              # 行が違う＝折り返しの継ぎ目
        if (nl - pr) / width < _GAP_RATIO:
            drop.add(i)

    if drop:
        text = "".join(c for i, c in enumerate(text) if i not in drop)
    return text.replace(_UNMAPPED, "-")


def page_texts(pdf: Path) -> list:
    """PDFの物理ページごとのテキスト。長さは必ず物理ページ数と一致する。

    図版だけのページ・空のページも空文字で残すこと。詰めると以降のページ番号が全部ずれ、
    md に振る `===== PAGE N =====` と出典のページ番号が黙って狂う。
    """
    doc = _mod.PdfDocument(str(pdf))
    out = []
    for i in range(len(doc)):
        tp = doc[i].get_textpage()
        out.append(_page_text(tp))
        tp.close()
    doc.close()
    return out
