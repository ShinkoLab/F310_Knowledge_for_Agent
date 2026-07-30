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

生成された `~/.claude/f310-kb` 以下のPDF、HTML、Markdown、索引データには、
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

`$F310_KB_DIR`、未設定なら `~/.claude/f310-kb`。プラグインはバージョンごとに別ディレクトリへ
展開され更新時に入れ替わるため、生成データは意図的にプラグイン外へ置いています。

```
~/.claude/f310-kb/
├─ .build.json          # 取得日時・Last-Modified・生成件数
├─ original/*.pdf       # 取得したPDF 10冊
├─ html/*.html          # 取得した設定例ページ（UTF-8化済）
└─ md/
   ├─ *.md              # ページ番号マーカー付き全文
   ├─ command_index.json  # 全1,914コマンドの索引
   └─ setting_examples/   # 設定例54件 + INDEX.md
```

削除するときはこのディレクトリごと消してください（`rm -rf ~/.claude/f310-kb`）。再構築すれば元に戻ります。
なお `~/.claude/f310-kb` はデータ置き場であり、プラグイン本体
（`~/.claude/plugins/cache/shinko-lab/f310-kb/<version>/`）とは別物です。名前は同じですが消しても
プラグインはアンインストールされません。

## 直接使う

スキル経由でなくコマンドラインからも引けます。

```bash
python3 scripts/lookup.py status                    # 構築状況
python3 scripts/lookup.py cmd "^router ospf" --full # コマンド構文
python3 scripts/lookup.py grep "link up" message    # 本文検索（出典ページ付き）
python3 scripts/lookup.py page cmd_refe_config 190  # ページ本文
python3 scripts/lookup.py ex "v6プラス"              # 設定例検索
```

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
