#!/usr/bin/env python3
"""知識ベース(KB)とリポジトリのパス解決を一元化する。

リポジトリ側はスクリプトとマニフェストだけを持ち、実データ(PDF/変換済みmd)は
リポジトリ外の KB ディレクトリに置く。プラグインは
`~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/` へバージョン別に展開され、
更新のたびに中身が入れ替わるため、生成物をプラグイン内に置くと消えてしまう。

置き先は Claude Code 公式のプラグインデータ置き場
`~/.claude/plugins/data/<plugin>-<marketplace>/`（プラグイン更新をまたいで残る）。
スキル経由の実行では SKILL.md 内で `${CLAUDE_PLUGIN_DATA}` が実際の値に展開され、
`$F310_KB_DIR` として渡ってくる。`CLAUDE_PLUGIN_DATA` を環境変数として直読みしては
いけない。この変数がプロセスに渡るのは hook / MCP / LSP サブプロセスだけで、素の
Bash 実行で見える値は他プラグインが書き出したもののことがある。

解決順は `$F310_KB_DIR` → `DEFAULT_KB` の2段のみ。`LEGACY_KB` は解決順に入れない
（`$F310_KB_DIR` が常に指定される経路では到達せず、あっても効かないため）。旧パスに
構築済みKBが残っている場合は legacy_hint() が移行コマンドを案内する。
"""
import json
import os
import re
from pathlib import Path
from typing import Union   # `list | dict` は Python 3.10 以降。3.9 でも import できるようにする

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"
MANUALS_MANIFEST = DATA / "manuals_manifest.json"
EXAMPLES_MANIFEST = DATA / "examples_manifest.json"

FALLBACK_ID = "f310-kb-shinko-lab"


def plugin_data_id() -> str:
    """データ置き場の id。プラグイン識別子 `<plugin>@<marketplace>` の
    `a-zA-Z0-9_-` 以外を `-` に置換したもの、という Claude Code の規則で決まる。

    定義ファイルは配布物にそのまま同梱されるので実行時に読める。ハードコードすると
    プラグイン名やマーケットプレイス名を変えたときに追随を忘れ、旧IDのディレクトリへ
    黙って書き続ける事故になるため、名前の実体から毎回導出する。
    """
    d = REPO / ".claude-plugin"
    try:
        plugin = json.loads((d / "plugin.json").read_text(encoding="utf-8"))["name"]
        market = json.loads((d / "marketplace.json").read_text(encoding="utf-8"))["name"]
    except (OSError, KeyError, json.JSONDecodeError):
        return FALLBACK_ID
    return re.sub(r"[^a-zA-Z0-9_-]", "-", f"{plugin}@{market}")


DEFAULT_KB = Path.home() / ".claude" / "plugins" / "data" / plugin_data_id()
LEGACY_KB = Path.home() / ".claude" / "f310-kb"  # 移行案内にのみ使う（解決順には入れない）


def kb_root() -> Path:
    env = os.environ.get("F310_KB_DIR")
    return Path(env).expanduser().resolve() if env else DEFAULT_KB


def original_dir() -> Path:
    return kb_root() / "original"


def html_dir() -> Path:
    return kb_root() / "html"


def md_dir(root: Path = None) -> Path:
    """root 省略時は解決済みのKB。旧パスの構築状況を調べるときだけ明示的に渡す。"""
    return (root or kb_root()) / "md"


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


def is_built(root: Path = None) -> bool:
    """マニュアル検索が可能な状態か。本文とコマンド索引が揃っていることを条件とする。

    設定例はここに含めない。含めると、マニュアルが完全に揃っていても設定例の生成に
    失敗しただけでコマンド検索まで止まってしまう。設定例の欠落は
    example_count()（status表示）と lookup.py ex 側で個別に扱う。
    """
    d = md_dir(root)
    return (d / "command_index.json").exists() and any(d.glob("*.md"))


def legacy_hint() -> str:
    """旧パス(~/.claude/f310-kb)に構築済みKBが残っているときだけ移行コマンドを返す。

    自動で移動はしない。ユーザーのデータの移動であり、案内すれば1コマンドで済む。
    """
    root = kb_root()
    # 案内するのは「本来の置き場に未構築」のときだけ。$F310_KB_DIR で任意の場所を
    # 指定している場合（テスト用ディレクトリなど）に実KBの移動を促すのは誤り。
    # プラグイン経由の値は必ず plugins/data 配下なので、そこも対象に含める。
    plugin_data = Path.home() / ".claude" / "plugins" / "data"
    if root != DEFAULT_KB and plugin_data not in root.parents:
        return ""
    if is_built(root) or not is_built(LEGACY_KB):
        return ""
    # パスは必ず引用符で囲む。この案内はそのまま実行される導線があり、ホーム
    # ディレクトリ名に空白が含まれる環境で別のパスを指してしまうため。
    return (
        "旧パスに構築済みの知識ベースがあります。取得し直さずに移行できます:\n"
        f'    mkdir -p "{root.parent}" && mv "{LEGACY_KB}" "{root}"'
    )


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
