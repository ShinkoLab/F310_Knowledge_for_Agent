# CLAUDE.md

このファイルは、**このリポジトリ自体を保守するとき**の手引きです。
F310 について調べる手順は `skills/lookup/SKILL.md` に一本化してあります（このファイルには書かない）。

## このリポジトリの性質

ソフトウェアのプロジェクトではなく、**古河電工 FITELnet F310（ルータ）の知識ベースを構築する
Claude Code プラグイン**。リポジトリが持つのは「取得先URL・変換スクリプト・調べ方の手順」だけで、
**マニュアル本文・設定例本文は一切含まない**（再配布しないため）。実データは利用者が
`scripts/build.py` で公式サイトから取得し、KB（既定 `~/.claude/plugins/data/f310-kb-shinko-lab`）に構築する。

この方針は意図的なもの。生成物や取得物をリポジトリにコミットしないこと。

## 構成

```
.claude-plugin/       plugin.json / marketplace.json
skills/lookup/        SKILL.md（スキル本体）、references/manuals_index.md（ルーティング表）
scripts/              kb_paths, httpget, fetch_*, convert_to_md, build_command_index,
                      gen_examples*, build.py（統合）, lookup.py（検索）,
                      mcp_server.py（MCP stdio サーバ。lookup.py の cmd_* を薄くラップ。任意・pip依存）
data/                 manuals_manifest.json（PDF10冊のURL）, examples_manifest.json（設定例76件）
```

パス解決はすべて `scripts/kb_paths.py` 経由。KBの位置は `$F310_KB_DIR` → `DEFAULT_KB` の2段で決まる。

| | パス | 性質 |
|---|---|---|
| プラグイン本体 | `~/.claude/plugins/cache/shinko-lab/f310-kb/<version>/` | バージョン別展開。更新で入れ替わる |
| KBデータ | `~/.claude/plugins/data/f310-kb-shinko-lab/` | Claude Code 公式のプラグインデータ置き場。更新をまたいで残る |

プラグイン側は更新時に丸ごと入れ替わるため、生成物をプラグイン内に置いてはいけない。

### `${CLAUDE_PLUGIN_DATA}` の扱い（重要）

データ置き場のパスは `${CLAUDE_PLUGIN_DATA}` として Claude Code から供給される。id は
プラグイン識別子 `<plugin>@<marketplace>` の `a-zA-Z0-9_-` 以外を `-` に置換した規則で決まる。
`kb_paths.plugin_data_id()` が `.claude-plugin/{plugin,marketplace}.json` から毎回導出するので、
**改名しても追随は不要**（定義ファイルは配布物に同梱されるため実行時に読める）。読めない場合だけ
`FALLBACK_ID` に落ちる。

スキル経由では SKILL.md 内の `${CLAUDE_PLUGIN_DATA}` が展開され、`F310_KB_DIR=…` として
渡ってくる。プラグイン外で実行した場合は空文字になり `DEFAULT_KB` に落ちるので、どちらの
経路でも同じ場所を指す。

**`CLAUDE_PLUGIN_DATA` を環境変数として直読みしてはいけない。** この変数がプロセスに渡るのは
hook / MCP / LSP サブプロセスだけで、素の Bash 実行で見える値は他プラグインが自分の値を
セッション環境変数へ書き出したものであることがある（codex プラグインが実際にそうしている）。
読むと他プラグインのデータ置き場にKBを書き込む事故になる。

旧パス `~/.claude/f310-kb` に構築済みKBが残っている場合は `kb_paths.legacy_hint()` が
移行コマンドを案内する。解決順には入れていない（`$F310_KB_DIR` が常に指定される経路では
到達しないため）。

## 再構築

```bash
python3 scripts/build.py              # 取得 → 変換 → 索引 → 網羅性チェック
python3 scripts/build.py --skip-fetch # 手元のPDF/HTMLから再生成のみ（ロジック変更時はこれ）
python3 scripts/build.py --dry-run    # 全URLの疎通確認（サイト改版の一次診断）
```

## 網羅性の基準値（退行検知）

`build.py` が末尾で自動チェックする。抽出ロジックを触ったら、この値が崩れていないか必ず確認すること。

| 項目 | 値 |
|---|---|
| 総ページ数 | 3,873 |
| コマンド数 | 構成定義編 1,299 / 運用管理編 615（計1,914） |
| 設定例md | 54件 |

抽出漏れは凡例（マニュアル冒頭のマーカー説明）2件のみで、これは意図的に除外している。

## command_index.json のスキーマ / パーサの前提

1件 = `{command, manual, category, page, function（【機能】）, syntax（【入力形式】, no形式含む）, mode（【動作モード】）, ref}`。

`scripts/build_command_index.py` は本文の `【機能】` ブロックを起点に、直前行をコマンド名として抽出する。
純正PDFのレイアウト揺れに個別対応済み:

- 版数見出し `【対応/対象ファームウェアバージョン】` の読み飛ばし
- 節番号 `10.10.1 ` とモード括弧 `（基本設定モード）` の除去
- `access-list（IPv4 標準設定）` 等の日本語括弧修飾は名前の一部として保持
- ページ跨ぎで名前が前ページに残る場合、`【入力形式】` の先頭語から補完

`set mtu`・`description` 等の**同名複数エントリは正常**（動作モード違いで別ページに存在するため各々保持）。

## 設定例パイプラインの前提

- 元ページは **Shift_JIS**。`fetch_examples.py` が cp932 で解釈してUTF-8で保存する。
- `KB/html` のファイル名は `kb_paths.page_key()` が決める。取得側と生成側で規則がずれると
  `MISSING` になるので、変えるなら両方が同じ関数を使い続けること。
- `gen_examples.py` のリニアライザ（DOM順に title/summary/envname/table/pre/img を拾う）と
  `gen_examples_index.py` の SECT・NOPAGE マップは、サイトを見ながら人手で確定させたもの。
  自動判定できないため手で保守する。
- **LBO一覧ページだけ例外**: 複数の設定例が見出し無しで `<textarea id="command_...">` に詰め込まれている。
  id からラベル（`DNS snooping ／ app-profile（新コマンド体系）` 等）を復元している。
  id の付き方は `command_app_dns_teams`（新体系）/ `command_dns_teams`（旧体系・接頭辞なし）。
  センタ/拠点の別（`_center` / `_kyoten`）も同様に復元するが、HTML側に既に見出しがある場合は重複させない。

## マニュアルPDFを差し替え・追加するとき

`data/manuals_manifest.json` にURLとページ数を足し、`python3 scripts/build.py --force` で取り直す。
ページ数が変わったら `scripts/build.py` の `EXPECT_PAGES` と、
`skills/lookup/references/manuals_index.md` の表も更新すること。
