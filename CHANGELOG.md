# CHANGELOG

このプロジェクトは [Semantic Versioning](https://semver.org/lang/ja/) に従います。

## [2.2.0] - 2026-08-18

コンテナ（LXC）関連の公式ドキュメントを知識ベースに取り込みました。取得元は
[コンテナFITELnet LXCアプリケーション](https://www.furukawaelectric.com/fitelnet/product/container/lxc/)
です（F70/F220系と共通の資料。F310 は V01.00 以降が対応）。

> [!IMPORTANT]
> **知識ベースの再構築が必要です。** 追加分だけを取得するので数十秒で終わります。
> ```bash
> python3 scripts/build.py
> ```
> 未実施のままだと `status` の値が旧来のまま（10冊 / 3,873ページ / 設定例54件）になります。

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

### 変更

- 網羅性の基準値: **3,949ページ / 1,914コマンド / 設定例56件**（コマンド索引の中身は不変）
- スキルの `description` にコンテナ（LXC / Alpine Linux / softflowd / squid / Remote Wireshark / ZTP）の
  語を追加。コンテナの質問でもスキルが起動するようにするため

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
