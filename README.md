# FITELnet F310 Knowledge for Agent

古河電工 **FITELnet F310**（ルータ）の純正マニュアルと公式設定例を、Claude Code から検索できる
知識ベースにするプラグインです。F310 のコマンド構文・config 作成・ログの意味・設定例の調べ物を、
出典（マニュアル名とページ番号／設定例のURL）付きで答えられるようになります。

## 非公式プロジェクトについて

本プロジェクトは、古河電気工業株式会社およびその関連会社による公式・公認プロジェクトではありません。
FITELnet および関連する製品名・会社名は、各権利者の商標または登録商標です。
本プロジェクトでは、製品を識別し、公開されている公式資料を利用者のローカル環境で参照しやすくする目的で名称を使用しています。

## 再配布について

**このリポジトリは古河電気工業株式会社のマニュアル本文・設定例本文を一切含みません。**
含まれているのは取得先URL・変換スクリプト・調べ方の手順だけです。

マニュアルPDFと設定例ページは、**利用者自身が**ビルド時に公式サイトから取得します。
取得したデータの著作権は古河電気工業株式会社または各権利者に帰属します。
利用にあたっては、古河電工サイトの利用条件および各資料の利用条件に従ってください。

生成された知識ベース以下のPDF、HTML、Markdown、索引データには、
古河電気工業株式会社または各権利者の著作物に由来する内容が含まれます。
これらの生成物の利用・共有・再配布についても、古河電工サイトの利用条件および各資料の利用条件に従ってください。

本ツールの回答では、必要最小限の引用・要約にとどめ、出典URLまたはマニュアル名・ページ番号を明示してください。

- マニュアル: <https://www.furukawaelectric.com/fitelnet/product/f310/manual/>
- 設定例: <https://www.furukawaelectric.com/fitelnet/setting/>

## 必要なもの

| 依存 | 用途 |
|---|---|
| `python3`（3.9 以降） | スクリプト全般（標準ライブラリのみ。pip 不要）。macOS 標準の 3.9 でも動きます |
| `mutool`（MuPDF） | PDFのテキスト抽出。**ビルド時のみ**必要。`brew install mupdf-tools` / `apt install mupdf-tools` |
| `mcp`（pip, `>=2.0.0,<3`） | **MCPサーバとして使う場合のみ**（OpenCode/Codex向け）。`pip install "mcp>=2.0.0,<3"`。**この用途に限り Python 3.10 以降が必要**（mcp SDK 自体の要件。macOS標準の3.9では入りません）。Claude Codeプラグインとしての利用には不要 |

テキスト層のあるPDFなのでOCRは不要です。

## インストール

Claude Code で:

```
/plugin marketplace add ShinkoLab/F310_Knowledge_for_Agent
/plugin install f310-kb@shinko-lab
```

## 知識ベースの構築

初回の質問時にスキルが未構築を検知して構築を提案しますが、手動でも実行できます。

```bash
python3 scripts/build.py
```

公式サイトからマニュアルPDF 10冊（約38MB）と設定例ページ 54件を取得し、変換・索引化します。
サイトへの負荷を避けるため逐次・1秒間隔で取得するため、初回は数分かかります。

主なオプション:

| オプション | 内容 |
|---|---|
| `--dry-run` | 全URLの疎通確認のみ（リンク切れの検出用） |
| `--skip-fetch` | 取得を省き、手元のPDF/HTMLから再生成のみ |
| `--force` | 取得済みでも取り直す |
| `--seed DIR` | 手元にある `original/*.pdf` を流用してダウンロードを省く |
| `--prune-pdf` | 変換後にPDFを削除して容量を空ける（図の確認はできなくなる） |

ビルド末尾で網羅性（3,873ページ / 1,914コマンド / 設定例54件）を自動チェックします。
値がズレた場合は、取得漏れかサイト側の改版が疑われます。

## 知識ベースの置き場所

Claude Code 公式のプラグインデータ置き場（`${CLAUDE_PLUGIN_DATA}`）です。プラグイン本体は
バージョンごとに別ディレクトリへ展開され更新時に入れ替わりますが、この置き場は更新をまたいで残ります。

```
~/.claude/plugins/data/f310-kb-shinko-lab/
├─ .build.json          # 取得日時・Last-Modified・生成件数
├─ original/*.pdf       # 取得したPDF 10冊
├─ html/*.html          # 取得した設定例ページ（UTF-8化済）
└─ md/
   ├─ *.md              # ページ番号マーカー付き全文
   ├─ command_index.json  # 全1,914コマンドの索引
   └─ setting_examples/   # 設定例54件 + INDEX.md
```

別の場所に置きたいときは `$F310_KB_DIR` で上書きできます。

`/plugin uninstall` すると既定でこの置き場も削除されます（残したいときは `--keep-data`）。
手で消しても構いません。再構築すれば元に戻ります。

### 旧バージョンからの移行

v1.0.0 では `~/.claude/f310-kb` に置いていました。そちらに構築済みの知識ベースがある場合は、
取得し直さずに移動できます。`lookup.py` と `build.py` が検知して同じコマンドを案内します。

```bash
mkdir -p ~/.claude/plugins/data && mv ~/.claude/f310-kb ~/.claude/plugins/data/f310-kb-shinko-lab
```

## 直接使う

スキル経由でなくコマンドラインからも引けます。

```bash
python3 scripts/lookup.py status                    # 構築状況
python3 scripts/lookup.py cmd "^router ospf" --full # コマンド構文
python3 scripts/lookup.py grep "link up" message    # 本文検索（出典ページ付き）
python3 scripts/lookup.py page cmd_refe_config 190  # ページ本文
python3 scripts/lookup.py ex "v6プラス"              # 設定例検索
```

## MCP サーバーとして使う（OpenCode / Codex CLI 向け）

Claude Code 以外の MCP クライアント（OpenCode、Codex CLI など）からも同じ知識ベースを
引けるよう、`lookup.py` の5サブコマンドをそのまま MCP ツールとして公開する
`scripts/mcp_server.py` を用意しています。検索ロジックは `lookup.py` と共通です。

### 準備

まず知識ベースを構築します（Claude Code経路と同じ。MCPサーバー自体はビルドしません）。

```bash
python3 scripts/build.py
```

`mcp` パッケージはこのMCPサーバー専用のオプション依存です。このリポジトリ初のpip依存であり、
macOSのシステム/Homebrew Python では素の `pip install` が `externally-managed-environment`
エラーになることがあるため、venvを切って使うことを推奨します。

**venvは Python 3.10 以降で作ってください。** `mcp` SDK が 3.10 以上を要求するため、
macOS標準の 3.9 で venv を作ると `Could not find a version that satisfies mcp>=2.0.0`
で失敗します（`python3 -V` で確認。3.9 なら `brew install python@3.12` 等で用意し、
`python3.12 -m venv …` のようにバージョンを明示してください）。

```bash
python3 -m venv .venv-mcp   # python3 は 3.10 以降であること
.venv-mcp/bin/pip install "mcp>=2.0.0,<3"
```

`.venv-mcp/bin/python3 scripts/mcp_server.py` で単体起動できます（標準入力を待つため
無反応に見えますが正常です。停止は Ctrl-C）。

### 提供するツール

| MCPツール | 対応する lookup.py サブコマンド |
|---|---|
| `f310_status()` | `lookup.py status` |
| `f310_cmd(pattern, full, desc, manual, limit)` | `lookup.py cmd <pattern> [--full] [--desc] [--manual] [--limit]` |
| `f310_grep(pattern, manuals, case, limit)` | `lookup.py grep <pattern> [manuals…] [--case] [--limit]` |
| `f310_page(manual, pages)` | `lookup.py page <manual> <pages>` |
| `f310_ex(keyword, limit)` | `lookup.py ex <keyword> [--limit]` |

### OpenCode の設定例（`opencode.json`）

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

### Codex CLI の設定例（`~/.codex/config.toml`）

```toml
[mcp_servers.f310-kb]
command = "/path/to/.venv-mcp/bin/python3"
args = ["/path/to/F310_Knowledge_for_Agent/scripts/mcp_server.py"]

# KBを既定以外の場所に置いている場合のみ:
# [mcp_servers.f310-kb.env]
# F310_KB_DIR = "/path/to/kb"
```

### 注意

- パスは全て例です。venvのPython実行ファイルと `scripts/mcp_server.py` の**絶対パス**に置き換えてください。
- `command`/`args` は必ず `scripts/mcp_server.py` の**ファイルパスを直接**指定してください
  （`-m` 実行や他ディレクトリへのコピーでは `import lookup` が解決できず動きません）。
- 知識ベースが未構築の場合、各ツールがビルド案内（`python3 scripts/build.py` を実行するよう促す文言）を
  そのまま返します。MCPサーバー自身は知識ベースを構築しません。
- `mcp` パッケージは2026-07-28付けの新しいステートレス仕様に対応した v2系
  （`mcp.server.MCPServer`）を前提にしています。OpenCode/Codex側がまだこの仕様に対応しておらず
  接続できない場合は、ステートフルな旧プロトコルを話す v1系（`pip install "mcp>=1.28,<2"`、
  `scripts/mcp_server.py` 内の `from mcp.server import MCPServer` を
  `from mcp.server.fastmcp import FastMCP` に、`MCPServer(...)` を `FastMCP(...)` に読み替え）
  へのフォールバックを検討してください。
- OpenCode/Codexの設定スキーマは変わることがあります。上記で動かない場合は各ツールの
  最新ドキュメントを確認してください。

## リポジトリ構成

```
.claude-plugin/     プラグイン定義・マーケットプレース定義
skills/lookup/
  SKILL.md          スキル本体（調べ方の手順・出典ルール）
  references/       マニュアルのルーティング表
scripts/            取得・変換・索引化・検索
data/               取得先URLと設定例マニフェスト（本文は含まない）
```

## License

このリポジトリ内のスクリプト、Skill 定義、プラグイン定義、および付随するドキュメントは ISC License で提供します。

ただし、本ツールが利用者の環境で取得・変換する古河電気工業株式会社のマニュアル、設定例、PDF、HTML、Markdown 化テキスト、およびそれらに由来する索引データ・知識ベースは、本ライセンスの対象外です。これらの著作権および利用条件は、古河電工サイトの利用条件および各資料の利用条件に従います。

PDF からのテキスト抽出には、利用者環境にインストールされた MuPDF / `mutool` を外部コマンドとして使用します。MuPDF / `mutool` 自体は本リポジトリには含まれず、本ライセンスの対象外です。MuPDF / `mutool` の利用条件は、その配布元のライセンスに従います。
