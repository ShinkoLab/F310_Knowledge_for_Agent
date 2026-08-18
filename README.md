# FITELnet F310 Knowledge for Agent

古河電工 **FITELnet F310**（ルータ）の純正マニュアル16冊と公式設定例・コンテナ(LXC)ドキュメントを、Claude Code から
検索できる知識ベースにするプラグインです。コマンドの書式・config の組み方・ログの意味を、
**出典（マニュアル名とページ番号／設定例のURL）付き**で答えられるようになります。

> [!IMPORTANT]
> 古河電気工業株式会社による公式・公認プロジェクトではありません。
> また、**このリポジトリはマニュアル本文・設定例本文を一切含みません**（利用者自身が公式サイトから
> 取得してローカルに構築します）。詳細は [権利・再配布について](#権利再配布について) を参照してください。

## できること

インストールして知識ベースを構築すると、こう聞けるようになります。

- 「F310 で v6プラスの固定IPサービスを使う設定例を出して」 → 公式設定例から config を提示
- 「`router ospf` の入力形式は？」 → コマンドリファレンスの構文・動作モード・掲載ページ
- 「このログの `LINK UP` は何を意味する？」 → メッセージ一覧の該当ページ本文
- 「コンテナ(LXC)で squid を動かす手順は？」 → コンテナ説明書の該当ページ本文

引ける範囲は次のとおりです。

| 対象 | 規模 |
|---|---|
| 純正マニュアル | 16冊 / 3,949ページ（コンテナ(LXC)関連6冊を含む） |
| コマンド索引 | 1,914コマンド（構成定義編 1,299 + 運用管理編 615） |
| 公式設定例・コンテナ説明書 | 56件（IPoE・IPsec/VPN・VRRP・OSPF/BGP・QoS・LBO・コンテナ ほか） |

## クイックスタート

### 1. 必要なもの

| 依存 | 必要な場面 | 備考 |
|---|---|---|
| `python3`（3.9 以降） | 常に | 標準ライブラリのみ。pip 不要。macOS 標準の 3.9 でも動きます |
| `mutool`（MuPDF） | **ビルド時のみ** | PDFのテキスト抽出用。`brew install mupdf-tools` / `apt install mupdf-tools` |
| `mcp`（pip） | MCPサーバとして使う場合のみ | Claude Code から使うだけなら不要。→ [MCP サーバーとして使う](#mcp-サーバーとして使うopencode--codex-cli-向け) |

テキスト層のあるPDFなので OCR は不要です。

### 2. インストール

Claude Code で:

```
/plugin marketplace add ShinkoLab/F310_Knowledge_for_Agent
/plugin install f310-kb@shinko-lab
```

### 3. 知識ベースの構築

初回の質問時にスキルが未構築を検知して構築を提案します。手動で走らせても構いません。

```bash
python3 scripts/build.py
```

公式サイトからマニュアルPDF 16冊（約45MB）と設定例・コンテナ説明書ページ 56件を取得し、変換・索引化します。
サイトへの負荷を避けて逐次・1秒間隔で取得するため、初回は数分かかります。

## 知識ベース

### 置き場所

Claude Code 公式のプラグインデータ置き場（`${CLAUDE_PLUGIN_DATA}`）に構築します。プラグイン本体は
バージョンごとに別ディレクトリへ展開されて更新時に入れ替わりますが、この置き場は更新をまたいで残ります。

```
~/.claude/plugins/data/f310-kb-shinko-lab/
├─ .build.json            # 取得日時・Last-Modified・生成件数
├─ original/*.pdf         # 取得したPDF 16冊
├─ html/*.html            # 取得した設定例・コンテナ説明書ページ（UTF-8化済）
└─ md/
   ├─ *.md                # ページ番号マーカー付き全文
   ├─ command_index.json  # 全1,914コマンドの索引
   └─ setting_examples/   # 設定例・コンテナ説明書56件 + INDEX.md
```

別の場所に置きたいときは環境変数 `$F310_KB_DIR` で上書きできます。

`/plugin uninstall` すると既定でこの置き場も削除されます（残したいときは `--keep-data`）。
手で消しても構いません。再構築すれば元に戻ります。

### ビルドのオプション

| オプション | 内容 |
|---|---|
| `--dry-run` | 全URLの疎通確認のみ（リンク切れの検出用） |
| `--skip-fetch` | 取得を省き、手元のPDF/HTMLから再生成のみ |
| `--force` | 取得済みでも取り直す |
| `--seed DIR` | 手元にある `original/*.pdf` を流用してダウンロードを省く |
| `--prune-pdf` | 変換後にPDFを削除して容量を空ける（図の確認はできなくなる） |

ビルド末尾で網羅性（3,949ページ / 1,914コマンド / 設定例56件）を自動チェックします。
値がズレた場合は、取得漏れかサイト側の改版が疑われます。

### v1.0.0 からの移行

v1.0.0 では知識ベースを `~/.claude/f310-kb` に置いていました。そこに構築済みのものがあれば、
取得し直さずに移動できます（`lookup.py` と `build.py` も検知して同じコマンドを案内します）。

```bash
mkdir -p ~/.claude/plugins/data && mv ~/.claude/f310-kb ~/.claude/plugins/data/f310-kb-shinko-lab
```

プラグイン識別子とスキル名も変わっています。再インストール手順は [CHANGELOG.md](CHANGELOG.md) を参照してください。

## コマンドラインから直接引く

スキル経由でなく、シェルからも同じ知識ベースを引けます。

```bash
python3 scripts/lookup.py status                    # 構築状況
python3 scripts/lookup.py cmd "^router ospf" --full # コマンド構文
python3 scripts/lookup.py grep "link up" message    # 本文検索（出典ページ付き）
python3 scripts/lookup.py page cmd_refe_config 190  # ページ本文
python3 scripts/lookup.py ex "v6プラス"              # 設定例検索
```

## MCP サーバーとして使う（OpenCode / Codex CLI 向け）

Claude Code 以外の MCP クライアントからも同じ知識ベースを引けるよう、`lookup.py` の5サブコマンドを
そのまま MCP ツールとして公開する `scripts/mcp_server.py` を用意しています。検索ロジックは共通です。

| MCPツール | 対応する lookup.py サブコマンド |
|---|---|
| `f310_status()` | `lookup.py status` |
| `f310_cmd(pattern, full, desc, manual, limit)` | `lookup.py cmd <pattern> [--full] [--desc] [--manual] [--limit]` |
| `f310_grep(pattern, manuals, case, limit)` | `lookup.py grep <pattern> [manuals…] [--case] [--limit]` |
| `f310_page(manual, pages)` | `lookup.py page <manual> <pages>` |
| `f310_ex(keyword, limit)` | `lookup.py ex <keyword> [--limit]` |

### 準備

知識ベースの構築は Claude Code 経路と同じです（MCPサーバー自身はビルドしません）。

```bash
python3 scripts/build.py
```

`mcp` パッケージはこのMCPサーバー専用のオプション依存です。このリポジトリ唯一の pip 依存であり、
macOS のシステム/Homebrew Python では素の `pip install` が `externally-managed-environment`
エラーになることがあるため、venv を切って使うことを推奨します。

> [!WARNING]
> **venv は Python 3.10 以降で作ってください。** `mcp` SDK 自体が 3.10 以上を要求するため、
> macOS 標準の 3.9 では `Could not find a version that satisfies mcp>=2.0.0` で失敗します。
> `python3 -V` が 3.9 なら `brew install python@3.12` 等で用意し、`python3.12 -m venv …` の
> ようにバージョンを明示してください。

```bash
python3 -m venv .venv-mcp   # python3 は 3.10 以降であること
.venv-mcp/bin/pip install "mcp>=2.0.0,<3"
```

`.venv-mcp/bin/python3 scripts/mcp_server.py` で単体起動を確認できます（標準入力を待つため
無反応に見えますが正常です。停止は Ctrl-C）。

### クライアント側の設定

以下のパスは全て例です。**venv の Python 実行ファイルと `scripts/mcp_server.py` の絶対パス**に
置き換えてください。

OpenCode（`opencode.json`）:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "f310-kb": {
      "type": "local",
      "command": ["/path/to/.venv-mcp/bin/python3", "/path/to/F310_Knowledge_for_Agent/scripts/mcp_server.py"],
      "enabled": true
      // KBを既定以外の場所に置いている場合のみ:
      // "environment": { "F310_KB_DIR": "/path/to/kb" }
    }
  }
}
```

Codex CLI（`~/.codex/config.toml`）:

```toml
[mcp_servers.f310-kb]
command = "/path/to/.venv-mcp/bin/python3"
args = ["/path/to/F310_Knowledge_for_Agent/scripts/mcp_server.py"]

# KBを既定以外の場所に置いている場合のみ:
# [mcp_servers.f310-kb.env]
# F310_KB_DIR = "/path/to/kb"
```

<details>
<summary>うまく動かないとき</summary>

- `command`/`args` には `scripts/mcp_server.py` の**ファイルパスを直接**指定してください。
  `-m` 実行や他ディレクトリへのコピーでは `import lookup` が解決できず動きません。
- 知識ベースが未構築の場合、各ツールはビルド案内（`python3 scripts/build.py` を促す文言）を
  そのまま返します。
- `mcp` パッケージは 2026-07-28 付けの新しいステートレス仕様に対応した v2系
  （`mcp.server.MCPServer`）を前提にしています。OpenCode/Codex 側がまだ対応しておらず接続できない
  場合は、ステートフルな旧プロトコルを話す v1系へのフォールバックを検討してください
  （`pip install "mcp>=1.28,<2"` とし、`scripts/mcp_server.py` 内の
  `from mcp.server import MCPServer` を `from mcp.server.fastmcp import FastMCP` に、
  `MCPServer(...)` を `FastMCP(...)` に読み替え）。
- OpenCode/Codex の設定スキーマは変わることがあります。上記で動かない場合は各ツールの
  最新ドキュメントを確認してください。

</details>

## リポジトリ構成

```
.claude-plugin/     プラグイン定義・マーケットプレース定義
skills/lookup/
  SKILL.md          スキル本体（調べ方の手順・出典ルール）
  references/       マニュアルのルーティング表
scripts/            取得・変換・索引化・検索
data/               取得先URLと設定例マニフェスト（本文は含まない）
```

## 権利・再配布について

### 非公式プロジェクトです

本プロジェクトは、古河電気工業株式会社およびその関連会社による公式・公認プロジェクトではありません。
FITELnet および関連する製品名・会社名は、各権利者の商標または登録商標です。
本プロジェクトでは、製品を識別し、公開されている公式資料を利用者のローカル環境で参照しやすくする
目的で名称を使用しています。

### マニュアル本文は同梱していません

**このリポジトリは古河電気工業株式会社のマニュアル本文・設定例本文を一切含みません。**
含まれているのは取得先URL・変換スクリプト・調べ方の手順だけです。マニュアルPDFと設定例ページは、
**利用者自身が**ビルド時に公式サイトから取得します。

- マニュアル: <https://www.furukawaelectric.com/fitelnet/product/f310/manual/>
- 設定例: <https://www.furukawaelectric.com/fitelnet/setting/>
- コンテナ(LXC)ドキュメント: <https://www.furukawaelectric.com/fitelnet/product/container/lxc/>

取得したデータの著作権は古河電気工業株式会社または各権利者に帰属します。生成された知識ベース以下の
PDF・HTML・Markdown・索引データにも、同社または各権利者の著作物に由来する内容が含まれます。
これらの利用・共有・再配布にあたっては、古河電工サイトの利用条件および各資料の利用条件に従ってください。

本ツールの回答では、必要最小限の引用・要約にとどめ、出典URLまたはマニュアル名・ページ番号を
明示してください。

### License

このリポジトリ内のスクリプト、Skill 定義、プラグイン定義、および付随するドキュメントは
[ISC License](LICENSE.md) で提供します。

ただし、本ツールが利用者の環境で取得・変換する古河電気工業株式会社のマニュアル、設定例、PDF、HTML、
Markdown 化テキスト、およびそれらに由来する索引データ・知識ベースは、本ライセンスの対象外です。
これらの著作権および利用条件は、古河電工サイトの利用条件および各資料の利用条件に従います。

PDF からのテキスト抽出には、利用者環境にインストールされた MuPDF / `mutool` を外部コマンドとして
使用します。MuPDF / `mutool` 自体は本リポジトリには含まれず、本ライセンスの対象外です。
MuPDF / `mutool` の利用条件は、その配布元のライセンスに従います。
