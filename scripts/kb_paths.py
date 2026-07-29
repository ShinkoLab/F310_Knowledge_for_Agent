#!/usr/bin/env python3
"""知識ベース(KB)とリポジトリのパス解決を一元化する。

リポジトリ側はスクリプトとマニフェストだけを持ち、実データ(PDF/変換済みmd)は
リポジトリ外の KB ディレクトリに置く。プラグインは
`~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/` へバージョン別に展開され、
更新のたびに中身が入れ替わるため、生成物をプラグイン内に置くと消えてしまう。

解決順は `$F310_KB_DIR` → `~/.claude/f310-kb` の2段のみ。
"""
import json
import os
from pathlib import Path
from typing import Union   # `list | dict` は Python 3.10 以降。3.9 でも import できるようにする

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"
MANUALS_MANIFEST = DATA / "manuals_manifest.json"
EXAMPLES_MANIFEST = DATA / "examples_manifest.json"

DEFAULT_KB = Path.home() / ".claude" / "f310-kb"


def kb_root() -> Path:
    env = os.environ.get("F310_KB_DIR")
    return Path(env).expanduser().resolve() if env else DEFAULT_KB


def original_dir() -> Path:
    return kb_root() / "original"


def html_dir() -> Path:
    return kb_root() / "html"


def md_dir() -> Path:
    return kb_root() / "md"


def examples_dir() -> Path:
    return md_dir() / "setting_examples"


def state_path() -> Path:
    return kb_root() / ".build.json"


def load_state() -> dict:
    p = state_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state: dict) -> None:
    kb_root().mkdir(parents=True, exist_ok=True)
    state_path().write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def is_built() -> bool:
    """マニュアル検索が可能な状態か。本文とコマンド索引が揃っていることを条件とする。

    設定例はここに含めない。含めると、マニュアルが完全に揃っていても設定例の生成に
    失敗しただけでコマンド検索まで止まってしまう。設定例の欠落は
    example_count()（status表示）と lookup.py ex 側で個別に扱う。
    """
    return (md_dir() / "command_index.json").exists() and any(md_dir().glob("*.md"))


def example_count() -> int:
    """生成済みの設定例md（INDEX.md を除く）の数。"""
    d = examples_dir()
    if not d.is_dir():
        return 0
    return len([p for p in d.glob("*.md") if p.name != "INDEX.md"])


def load_manifest(path: Path) -> Union[list, dict]:
    return json.loads(path.read_text(encoding="utf-8"))


SITE = "https://www.furukawaelectric.com"


def page_key(url: str) -> str:
    """設定例ページURL → KB/html 内のファイル名（拡張子なし）。

    取得側(fetch_examples)と生成側(gen_examples)が同じ規則を使う必要があるため、
    ここに一本化している。規則自体は元の gen.py のものを維持。
    """
    u = url.split("#")[0]
    return (
        u.replace(SITE + "/fitelnet/", "")
        .replace("/", "__")
        .replace(".html", "")
        .replace("+", "plus")
    )
