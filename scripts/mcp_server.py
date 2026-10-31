#!/usr/bin/env python3
"""F310 知識ベースを MCP (Model Context Protocol) サーバとして公開する。

OpenCode / Codex CLI など、Claude Code 以外の MCP クライアントから
scripts/lookup.py と同じ検索を使うためのアダプタ。検索・整形ロジックは
lookup.py の cmd_* をそのまま呼び出す（ここでは再実装しない）。

起動:   python3 mcp_server.py   （引数なし。stdio transport でブロックする）
依存:   pip install "mcp>=2.0.0,<3"（README「必要なもの」参照。このファイル限定の
        オプション依存で、pip 不要という他スクリプトの方針の例外）
要件:   Python 3.10 以降（mcp SDK 自体の要件。他の scripts/*.py は 3.9 互換だが
        このファイルだけは満たせない）

必ずファイルパス直接指定で起動すること（`python3 <このファイルの絶対パス>`）。
`import lookup` は Python がスクリプト自身のディレクトリを sys.path[0] に
自動追加する挙動に依存しているため、`-m` 実行や他ディレクトリへのコピーでは
`lookup` が見つからず壊れる。
"""
import contextlib
import io
import threading
import types
from typing import List, Optional

from mcp.server import MCPServer

import lookup

INSTRUCTIONS = """古河電工 FITELnet F310 ルータの純正マニュアル（コンテナ(LXC)関連の説明書を含む）と
公式設定例・コンテナ説明書を検索する。収録の規模は f310_status が返す。
マニュアル＝コマンド書式の正典、設定例＝動く設定の実例集。用途で使い分けること。

どこを引くか:
- 「実際に動く設定を組みたい」「この機能のconfig例は?」 → f310_ex（まず実例、必要ならマニュアルで裏を取る）
- 「このコマンドの書式は?」「パラメータの意味は?」 → f310_cmd（書式の正典）
- 「このログ/エラーの意味は?」 → f310_grep(pattern, manuals=["message"])
- 「対応本数・性能値は?」「MIB/Trapは?」 → f310_grep(pattern, manuals=["siyou"])
- 「この機能は何をする?」 → f310_grep(pattern, manuals=["kinou"])
- 「動かない、切り分けたい」 → f310_grep(pattern, manuals=["trouble"])
- 「コンテナ(LXC)の使い方は?」「コンテナでNetFlow/Proxyを動かしたい」
  → f310_grep(pattern, manuals=["lxc_app_man","softflowd_man","squid_man"])、f310_ex("コンテナ")
- 「コンテナのOSは旧OS/Alpineどっち?」「入っているOSSは?」
  → f310_page("lxc_check_change", "1-2")、f310_grep(パッケージ名, manuals=["alpine_oss"])

先に f310_status を呼び、知識ベースが構築済みか確認すること。未構築ならビルド手順が返る。
回答には必ず出典（マニュアル名とページ番号、または設定例のURL）を添えること。
推測でコマンドを作らない。索引に無い構文は「マニュアルに記載が見つからない」と答えること。

注意:
- 設定例の多くは F70/F220系との共通ページ。各ファイルの「対象装置」欄にF310が含まれることを確認してから提示する。
- コンテナの説明書（lxc_app_man / softflowd_man / squid_man と container_*.md）も複数機種共通の資料。
  設定例中のホスト名やインタフェース番号が他機種のものになっていることがあるので、F310の構成に読み替えて提示する。
  container backup / restore / image 等は説明書側に記載が無く、正典はコマンドリファレンス（f310_cmd("^container")）。
- 同名コマンドは動作モード違いで複数ある。どのモードのものかを明示する。
- LBOには新（app-profile）旧（lbo-profile）2つのコマンド体系がある。どちらかを明示する。
"""

mcp = MCPServer("f310-kb", instructions=INSTRUCTIONS)


# redirect_stdout/redirect_stderr は sys.stdout/sys.stderr をプロセス全体で
# 差し替えるが、MCP SDK は同期ツール関数をワーカースレッドで並行実行する。
# 直列化しないと同時呼び出しどうしが差し替えを奪い合い、結果が入れ替わったり
# 本文が stdio transport のワイヤに漏れて JSON-RPC が壊れる。
# 各呼び出しはローカルファイル読みで短いため、素直にロックで直列化する。
_run_lock = threading.Lock()


def _run(fn, ns) -> str:
    """cmd_* を呼び、標準出力/標準エラーへの print をすべて捕まえて文字列で返す。

    require_kb() が投げる SystemExit(2) もここで飲み込み、直前に stderr へ
    出したビルド案内メッセージをそのまま返す（プロセスを落とさない）。
    """
    buf = io.StringIO()
    try:
        with _run_lock:
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                fn(ns)
    except SystemExit:
        pass
    except Exception as e:  # 想定外の例外でサーバプロセスを落とさない
        buf.write(f"\n[内部エラー] {type(e).__name__}: {e}")
    return buf.getvalue().rstrip("\n") or "(出力なし)"


@mcp.tool()
def f310_status() -> str:
    """F310知識ベースの構築状況（マニュアル冊数・ページ数・コマンド数・設定例件数・索引生成日）を返す。
    他のツールを呼ぶ前にまずこれを呼ぶこと。未構築ならビルド手順の案内が返る。"""
    return _run(lookup.cmd_status, None)


@mcp.tool()
def f310_cmd(
    pattern: str,
    full: bool = False,
    desc: bool = False,
    manual: Optional[str] = None,
    limit: int = 20,
) -> str:
    """F310のコマンド索引を正規表現で引く（部分一致・大小無視）。書式・入力形式・出典ページの正典。
    「このコマンドの書式は?」「パラメータの意味は?」に使う。
    full=True で【機能】・全入力形式・【説明】・【未設定時】・パラメータ表を表示。desc=True で【機能】【説明】本文も検索対象にする。
    パラメータ表の持ち主は推定で割り当てているので、値そのものを回答に使うときは f310_page で出典ページを確かめること。
    manual は cmd_refe_config（構成定義編）/ cmd_refe_ope（運用管理編）のどちらかに絞れる。
    同名コマンドが複数出ることがある（動作モード違いで別ページに存在するため、いずれも正常）。"""
    ns = types.SimpleNamespace(
        pattern=pattern, full=full, desc=desc, manual=manual, limit=limit
    )
    return _run(lookup.cmd_cmd, ns)


@mcp.tool()
def f310_grep(
    pattern: str,
    manuals: Optional[List[str]] = None,
    case: bool = False,
    limit: int = 40,
) -> str:
    """マニュアル本文を正規表現で全文検索し、出典ページ付きで返す（例: "message.pdf p.420: …"）。
    manuals 省略時は全マニュアル（コンテナ関連を含む）が対象。用途別の絞り込み:
    ログ/エラーの意味 → manuals=["message"]。対応本数・性能値・MIB/Trap → ["siyou"]。
    機能説明 → ["kinou"]。障害切り分け → ["trouble"]。
    コンテナ(LXC) → ["lxc_app_man","softflowd_man","squid_man"]、OS/OSS → ["lxc_check_change","alpine_oss"]。
    正規表現の記号を含まない語は、英数字と日本語の境目の空白ゆれ（v6プラス / v6 プラス）と全角英数字を吸収する。
    前後の文脈が必要なときは f310_page で該当ページを読む。"""
    ns = types.SimpleNamespace(
        pattern=pattern, manuals=manuals or [], case=case, limit=limit
    )
    return _run(lookup.cmd_grep, ns)


@mcp.tool()
def f310_page(manual: str, pages: str) -> str:
    """指定マニュアルの指定ページ（N または N-M、PDF物理ページ）の本文をそのまま返す。
    f310_grep/f310_cmd の結果の前後文脈を読みたいとき、または原本確認に使う（PDFを開く必要はない）。"""
    ns = types.SimpleNamespace(manual=manual, pages=pages)
    return _run(lookup.cmd_page, ns)


@mcp.tool()
def f310_ex(keyword: str, limit: int = 15) -> str:
    """公式設定例をキーワードで検索する（索引の行・本文の両方が対象）。
    「実際に動く設定を組みたい」「この機能のconfig例は?」にまず使う（マニュアルより先に引く）。
    設定例の多くは F70/F220系との共通ページなので、対象装置にF310が含まれることを確認してから提示すること。
    コンテナ説明書（container_*.md）も対象で、複数機種共通の資料なのでF310向けに読み替えること。
    LBOには新（app-profile）/旧（lbo-profile）2つのコマンド体系があるので、どちらかを明示すること。"""
    ns = types.SimpleNamespace(keyword=keyword, limit=limit)
    return _run(lookup.cmd_ex, ns)


if __name__ == "__main__":
    mcp.run()
