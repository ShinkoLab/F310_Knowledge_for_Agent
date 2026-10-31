# CHANGELOG

このプロジェクトは [Semantic Versioning](https://semver.org/lang/ja/) に従います。

## [2.3.0] - 2026-10-31

検索の取りこぼしとコマンド索引の欠陥を直し、退行と公式サイトの改版を検知するしくみを入れました。
あわせて、公式サイトの 2026-10 の改版（マニュアルPDF 8冊・設定例4ページ）に追随しています。

> [!IMPORTANT]
> **知識ベースの再構築が必要です。取得ありで実行してください**（約48MBを取り直すので数分かかります）。
> ```bash
> python3 scripts/build.py
> ```
> `--skip-fetch` では手元の PDF が旧版のままなので、「手元の版が検証済みの版と違う」という注記が出続けます。
> 再構築しないと、索引に新しい欄（パラメータ表・説明・未設定時）が入らず、`cmd --full` に表示されません。

### 追加

- コマンド索引に `params`（パラメータ表）・`description`（【説明】）・`default`（【未設定時】）の欄。
  `lookup.py cmd --full` で表示し、`--desc` は【説明】も検索する
  - PDFのテキスト抽出順が崩れていて、パラメータ表の約4割は本来のコマンドより後ろに出る。
    持ち主は推定で割り当てており、約3%は構文と照合して裏が取れない。値を回答に使うときは
    `page` で出典ページを確かめるよう、スキルと MCP の案内に明記した
- 単体テスト（`tests/test_*.py`、79件）。KB もネットワークも使わない。
  `python3 -m unittest discover -s tests` で実行する
- 検索回帰テスト（`tests/retrieval_cases.json` 32件、`scripts/check_retrieval.py`）。
  既知の質問が既知の答えを返すかを、`build.py` の最後に自動で確かめる
- `scripts/diff_index.py`。2つの `command_index.json` を突き合わせ、欄ごとの変化を示す
- `build.py --check-updates`。公式サイトが検証済みの版から改版されたかを、KB に触れずに調べる
- `build.py --accept-current`。手元の KB を検証済みの版として `data/validated_versions.json` に書き出す（保守者向け）
- `scripts/setup_mcp.py`。MCP サーバ用の `.venv-mcp` の作成から `mcp` のインストール、読み込みの確認までを
  1コマンドで行い、OpenCode・Codex の設定の雛形を絶対パス入りで表示する

### 修正

- 英数字と日本語の境目で本文検索が取りこぼしていた問題を修正。PDFのテキストは `v6 プラス` のように
  境目に空白が入るため、`grep "v6プラス"` が0件だった。正規表現の記号を含まない語は境目の空白の有無を
  両方許し、入力の全角英数字も半角に当てる（`grep`・`ex`・`cmd --desc`）
- コマンド索引の `mode`（動作モード）にパラメータ表が混ざっていた問題を修正（1,914件中222件）。
  折り返しの途中に空行が挟まるモードも、途中で切れずに取れる
- MCP サーバの案内文にあった古い数値（10冊 / 3,873ページ / 54件）を削除し、コンテナ（LXC）の案内と
  回答時の注意を追加した

### 変更

- 網羅性チェックの基準を、全体の定数から `data/validated_versions.json`（パーサを検証した時点の
  公式サイトの版。冊ごとの Last-Modified・バイト数・ページ数・コマンド数、設定例ページごとの本文の指紋）に
  移した。手元の版が検証済みの版と違う冊は、数が変わっても警告ではなく注記になる。
  その冊のページ依存の回帰テストが落ちた場合も同じ扱い
- 基準値を 2026-10 版に更新: **4,021ページ / 1,964コマンド（構成定義編 1,332 / 運用管理編 632）/ 設定例56件**
- **通常のビルドで、設定例56ページを毎回取得するようになった**（1秒間隔で約1分）。公式サイトの設定例ページは
  更新日時を返さないので、本文の指紋を比べて、変わっていれば取り直す。ロジックだけを変えたときは、
  これまでどおり `--skip-fetch` で省ける
- `data/manuals_manifest.json` からページ数（`pages`）を削除した。検証済みの版の側で持つ

## [2.2.0] - 2026-08-18

コンテナ（LXC）関連の公式ドキュメントを知識ベースに取り込みました。取得元は
[コンテナFITELnet LXCアプリケーション](https://www.furukawaelectric.com/fitelnet/product/container/lxc/)
です（F70/F220系と共通の資料。F310 は V01.00 以降が対応）。

> [!IMPORTANT]
> **知識ベースの再構築が必要です。** 追加分だけを取得するので数十秒で終わります。
> ```bash
> python3 scripts/build.py
> ```
> 未実施のままだと `status` の値が旧来のまま（10冊 / 3,873ページ / 設定例54件）になり、
> 下記「修正」で復活した既存設定例の本文も反映されません。

### 追加

- マニュアルPDF 6冊。`lookup.py grep` / `page` の対象に加わる
  - 「説明書」の項
    - `lxc_app_man`（57p）コンテナ型仮想環境の使用方法 F版
    - `softflowd_man`（6p）NetFlow(softflowd) の使用方法
    - `squid_man`（8p）Proxyサーバ(squid) の使用方法
  - 「お知らせ」「Alpine Linuxイメージファイル」の項
    - `lxc_check_change`（2p）システムコンテナの確認および変更方法（旧OS→Alpine Linux）
    - `lxc_check`（1p）システムコンテナの確認方法（旧ファームウェア）
    - `alpine_oss`（2p）Alpine Linux イメージのOSS一覧（ルータ本体の `oss_list` とは別物）
- 説明書HTML 2件を `container_*.md` として生成。`lookup.py ex` で引ける
  - `container_remote-wireshark.md` 遠隔拠点からのパケットキャプチャ（Remote Wireshark）
  - `container_ztp-script.md` PythonスクリプトによるZTP（ゼロタッチプロビジョニング）
- 設定例索引（`INDEX.md`）に「コンテナ（LXC）アプリケーション」の分類

### 修正

- 設定例リニアライザが、設定例ページのテンプレート（`.title`/`.summary`/`.envname`）を使っていない
  ページで**本文を丸ごと落としていた**問題を修正。見出しだけが残り、空見出し除去でその見出しごと
  消えるため、生成物では手順が飛んでいた（Remote Wireshark なら手順2・3・5と前提条件・注意点が欠落）。
  マーカーが1つも無いページに限って `<p>`/`<li>` も拾うフォールバックを追加した
- 完成コンフィグやコンソール出力が「1セルだけの表」に入っているページで、表のまま整形した結果
  **改行が空白に潰れて1行に繋がり、コピーしても使えないconfig**になっていた問題を修正。
  この形の表は code fence として出すようにした
- 上記2件により、コンテナ説明書2件に加えて**既存の設定例14件でも本文が復活**した
  （`lbo_index` の app-profile 推奨理由、各IPoE設定例の対応バージョン注記など）。
  マーカーを持つページの出力は変わらない

### 変更

- 網羅性の基準値: **3,949ページ / 1,914コマンド / 設定例56件**（コマンド索引の中身は不変）
- スキルの `description` にコンテナ（LXC / Alpine Linux / softflowd / squid / Remote Wireshark / ZTP）の
  語を追加。コンテナの質問でもスキルが起動するようにするため
- あわせて `description` から規模の数値（冊数・ページ数・コマンド数・設定例件数）を削除。
  自動起動の判定には効かない一方、内容を足すたびに書き換えが要る。規模は README と
  `manuals_index.md` が持つ

### 既知の未収録

- 説明書の「回線速度を測定する（speedtest-cli）」は、リンク先
  `.../lxc/man/speedtest.html` が公式サイト側で 404 のため収録できていません。
  復活すれば `data/examples_manifest.json` に1行追加するだけで取り込めます

## [2.1.0] - 2026-08-18

Claude Code 以外の MCP クライアントからも、同じ知識ベースを引けるようになりました。

### 追加

- `scripts/mcp_server.py`（MCP stdio サーバ）。`lookup.py` の5サブコマンドを
  `f310_status` / `f310_cmd` / `f310_grep` / `f310_page` / `f310_ex` として公開する。
  OpenCode・Codex CLI 等から利用できる。検索ロジックは `lookup.py` と共通で、
  MCPサーバー自身は知識ベースを構築しない（`build.py` は従来どおり別途実行する）
- `mcp` パッケージ（`>=2.0.0,<3`）への**任意の**依存。MCPサーバーとして使う場合にのみ必要で、
  **この用途に限り Python 3.10 以降**を要する（`mcp` SDK 自体の要件）。
  Claude Code プラグインとしての利用には不要

### 変更

- README を再構成。「できること」を冒頭に置き、導入手順を「クイックスタート」へ集約、
  分散していた非公式表示・再配布・ライセンスの記述を末尾の「権利・再配布について」へ統合した

### 変更していないもの

- 取得元URL・変換ロジック・コマンド索引の中身（網羅性は 3,873ページ / 1,914コマンド /
  設定例54件のまま）。**知識ベースの再構築は不要**
- Claude Code から使う場合の依存（`python3` と `mutool` のみ。pip 不要）
- スキルの `description`（自動起動の判定に使われるため）

## [2.0.0] - 2026-07-31

プラグインの命名を整理し、KBデータの置き場所を Claude Code 公式のプラグインデータ置き場へ移しました。

### 破壊的変更

既存の利用者は**手動での再インストールと、知識ベースの移動が必要**です。バージョンを上げても
自動では移行されません（マーケットプレイス名が変わったため `/plugin update` では新版に上がれません）。

| | v1.0.0 | v2.0.0 |
|---|---|---|
| インストール識別子 | `fitelnet-f310@f310-kb` | `f310-kb@shinko-lab` |
| スキル呼び出し名 | `fitelnet-f310:fitelnet-f310` | `f310-kb:lookup` |
| KBデータの置き場所 | `~/.claude/f310-kb` | `~/.claude/plugins/data/f310-kb-shinko-lab` |

### 移行手順

再インストール（マーケットプレイス名が変わったため `remove` を先に行う必要があります）:

```
/plugin marketplace remove f310-kb
/plugin marketplace add ShinkoLab/F310_Knowledge_for_Agent
/plugin install f310-kb@shinko-lab
/reload-plugins
```

知識ベースの移動（マニュアルPDFの再取得は不要です）:

```bash
mkdir -p ~/.claude/plugins/data && mv ~/.claude/f310-kb ~/.claude/plugins/data/f310-kb-shinko-lab
```

移動を忘れても `lookup.py` と `build.py` が検知して同じコマンドを案内します。`build.py` は
旧パスに構築済みの知識ベースがある場合、38MBを取り直す前に停止します。

### 変更

- プラグインの命名を3層（マーケットプレイス＝配布元 / プラグイン＝製品名 / スキル＝機能）の
  役割に沿って整理。`@` の右がマーケットプレイスであり、本来は配布元を表す層のため
- KBデータを `${CLAUDE_PLUGIN_DATA}` が指す公式のプラグインデータ置き場へ移動。
  プラグイン更新をまたいで残り、`/plugin uninstall` で自動的に片付く（残す場合は `--keep-data`）
- データ置き場の id を `.claude-plugin/{plugin,marketplace}.json` から実行時に導出。
  今後の改名で追随を忘れて旧IDのディレクトリへ書き続ける事故を防ぐ
- 旧パスからの移行案内を追加

### 変更していないもの

- 取得元URL・変換ロジック・コマンド索引の中身（網羅性は 3,873ページ / 1,914コマンド /
  設定例54件のまま）
- スキルの `description`（自動起動の判定に使われるため）

## [1.0.0] - 2026-07-29

初回リリース。F310 の知識ベースを Claude Code プラグインとして提供します。

- 純正マニュアル10冊（3,873ページ・1,914コマンド）と公式設定例54件を検索する
  `fitelnet-f310:fitelnet-f310` スキル（v2.0.0 で `f310-kb:lookup` に改名）
- 公式サイトからの取得・変換・索引化を行う `scripts/build.py`
- マニュアル本文・設定例本文はリポジトリに含めず、利用者が各自で構築する方式

[2.2.0]: https://github.com/ShinkoLab/F310_Knowledge_for_Agent/releases/tag/v2.2.0
[2.1.0]: https://github.com/ShinkoLab/F310_Knowledge_for_Agent/releases/tag/v2.1.0
[2.0.0]: https://github.com/ShinkoLab/F310_Knowledge_for_Agent/releases/tag/v2.0.0
[1.0.0]: https://github.com/ShinkoLab/F310_Knowledge_for_Agent/releases/tag/v1.0.0
