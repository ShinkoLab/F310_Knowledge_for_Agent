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
                      validated.py（検証済みの版の照合・改版検知）, check_retrieval.py（検索回帰テスト）,
                      diff_index.py（索引の差分）,
                      mcp_server.py（MCP stdio サーバ。lookup.py の cmd_* を薄くラップ。任意・pip依存）,
                      setup_mcp.py（mcp_server 用の .venv-mcp 作成と設定例の表示）
data/                 manuals_manifest.json（PDF16冊のURL）, examples_manifest.json（設定例・コンテナ説明書78件）,
                      validated_versions.json（パーサを検証した時点の版）
tests/                単体テスト（test_*.py）, retrieval_cases.json（検索回帰テストのケース）
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
python3 scripts/build.py --dry-run    # 全URLの疎通確認（リンク切れの一次診断）
python3 scripts/build.py --check-updates  # 公式サイトが検証済みの版から改版されたか（KBに触れない）
python3 scripts/build.py --accept-current # 手元のKBを検証済みの版として記録する
```

## 網羅性の基準値（退行検知）

`build.py` が末尾で自動チェックする。基準値は `data/validated_versions.json` に持つ。中身はパーサを検証した
時点の公式サイトの版で、冊ごとの Last-Modified・バイト数・ページ数・コマンド数、設定例ページごとの本文の指紋、
設定例md件数（本文は含まない）。2026-10 版で 4,021ページ / 1,964コマンド（構成定義編 1,332 / 運用管理編 632）/ 設定例md 56件。

- 手元の版が検証済みの版と同じなのに数が違えば、抽出ロジックの退行か取得漏れとして警告する。
- 手元の版が検証済みの版と違う冊は、サイト側の改訂で数が変わるのは想定どおりなので、警告ではなく注記になる。
  抽出結果を確認し、`python3 scripts/build.py --accept-current` で検証済みの版を更新してコミットする。
- 抽出ロジックを触ったら、手元の版が検証済みの版と一致している状態でチェックが通ることを確認する。
- 公式サイトの改版は `python3 scripts/build.py --check-updates` でKBに触れず調べられる。変化があれば終了コード1。
- 設定例ページは Last-Modified も ETag も返さないため、本文（`<main>` または `<div id="contents">` の範囲）の
  sha256 で判定する。正規化規則（`fetch_examples.fingerprint()`）を変えると記録済みの指紋が全部無効になる。

抽出漏れは凡例（マニュアル冒頭のマーカー説明）2件のみで、これは意図的に除外している。

### 検索の回帰テスト

`build.py` は末尾で `scripts/check_retrieval.py` を呼び、`tests/retrieval_cases.json` のケース
（既知の質問が既知の答えを返すか）を評価する。件数が合っていても「語を変えると0件」「modeに表が混ざる」
といった退行はここで拾う。失敗は網羅性の警告と同じ扱い。単独でも実行できる。

    python3 scripts/check_retrieval.py            # 全ケース（--list で一覧、--id で個別）

- ケースにマニュアル本文は入れない（マニュアル名・ページ番号・コマンド名・設定例のファイル名・件数の下限だけ）。
- ページ番号の完全一致は `page_dependent: true` のケースに限る。版が検証済みの版と違う冊のページ依存ケースが落ちても、
  `build.py` は警告にせず注記に回す。`--accept-current` で版を更新するときに、ここのページ番号も合わせて直す。
  版が同じなのに落ちたら退行。
- 検索・抽出ロジック（lookup.py / build_command_index.py）を変えたときは、変更前後の
  command_index.json を `python3 scripts/diff_index.py old.json new.json` で比べ、意図した欄だけが変わったか確認する。

### 単体テスト

KB もネットワークも不要の単体テストが `tests/` にある（標準ライブラリ unittest のみ、CI なし）。

    python3 -m unittest discover -s tests

入力はすべて合成データ（マニュアル本文をコピーしないこと）。パーサ（`build_command_index`）・リニアライザ
（`gen_examples`）・`fuzzy_pattern`・`kb_paths` の挙動を固定している。抽出ロジックを触ったら、網羅性チェックに
加えてこれも通すこと。

この表の数値を `skills/lookup/SKILL.md` の `description` に書かないこと。自動起動の判定に効くのは
固有名（`v6プラス`・`softflowd`・`squid` 等）であって数値ではなく、書くと内容を足すたびに
description の更新が必要になる。規模を示すのは README と `manuals_index.md` の役割。

## command_index.json のスキーマ / パーサの前提

1件 = `{command, manual, category, page, function（【機能】）, syntax（【入力形式】, no形式含む）, mode（【動作モード】）, params（パラメータ表）, description（【説明】）, default（【未設定時】）, ref}`。

`scripts/build_command_index.py` は本文の `【機能】` ブロックを起点に、直前行をコマンド名として抽出する。
純正PDFのレイアウト揺れに個別対応済み:

- 版数見出し `【対応/対象ファームウェアバージョン】` の読み飛ばし
- 節番号 `10.10.1 ` とモード括弧 `（基本設定モード）` の除去
- `access-list（IPv4 標準設定）` 等の日本語括弧修飾は名前の一部として保持
- ページ跨ぎで名前が前ページに残る場合、`【入力形式】` の先頭語から補完

`set mtu`・`description` 等の**同名複数エントリは正常**（動作モード違いで別ページに存在するため各々保持）。

`mode` / `params` / `description` / `default` はPDFのテキスト抽出順が崩れている前提で読む（`function`・`syntax` は従来どおり）:

- **mode は最初の段落だけ**。【動作モード】の直後に表の見出し（パラメータ/設定内容…）や次ページのヘッダが
  続けて出るため、空行かページ区切りで打ち切る。複数モードの折り返し（空行なしの複数行）は正常。
  ただし折り返しの途中に空行が挟まることがある（「…インタフェー」⏎⏎「ス設定モード」）ので、空行の手前が
  モード名の終わり（`モード`・`）`）に見えないときは、表の見出しが来ない限り次の段落へ続ける。
- **パラメータ表は元の位置にいない**。「パラメータ／設定内容」で始まる表を本文から切り出し、
  約4割は後ろのコマンドのブロックやページ末尾に回っている。持ち主は【パラメータ】見出しの待ち行列と、
  表の先頭セルが構文に含まれるかで決める（`assign_tables()`）。割当は推定で、約3%は構文で裏が取れない。
- `description` / `default` はページヘッダと次コマンドの節番号・名前を落としたもの。

## 設定例パイプラインの前提

- 元ページは **Shift_JIS**。`fetch_examples.py` が cp932 で解釈してUTF-8で保存する。
- `KB/html` のファイル名は `kb_paths.page_key()` が決める。取得側と生成側で規則がずれると
  `MISSING` になるので、変えるなら両方が同じ関数を使い続けること。
- `gen_examples.py` のリニアライザには、テンプレート違いのページ向けに2つの分岐がある。
  どちらも**マーカー（`.title`/`.summary`/`.envname`/`.additional_*`）を持つページの出力は変えない**ので、
  触るときは既存の生成物が変化しないことを diff で確認すること。
  - **prose フォールバック**: マーカーが1つも無いページでは `<p>`/`<li>` も拾う。この分岐に入るページは
    先に `<main>` の中身へ絞る（ヘッダ・グローバルナビの `<p>`/`<li>` を巻き込まないため）。
    絞り込みはフッタ切り落としより**先**に行う。後にすると、切り落とし位置が `</main>` より前に来た
    ページで閉じタグごと消え、絞り込みが効かずナビが本文に混ざる。
  - **`table_as_code()`**: データセル1つだけ・中身が `<br>` 区切り複数行、という表を code fence にする。
    完成コンフィグやコンソール出力がこの形で置かれているページがあり、表のままだと `table_to_md()` が
    改行を空白に潰して1行に繋がった使えないconfigになる。
- `gen_examples.py` のリニアライザ（DOM順に title/summary/envname/table/pre/img を拾う）と
  `gen_examples_index.py` の SECT・NOPAGE マップは、サイトを見ながら人手で確定させたもの。
  自動判定できないため手で保守する。
- **LBO一覧ページだけ例外**: 複数の設定例が見出し無しで `<textarea id="command_...">` に詰め込まれている。
  id からラベル（`DNS snooping ／ app-profile（新コマンド体系）` 等）を復元している。
  id の付き方は `command_app_dns_teams`（新体系）/ `command_dns_teams`（旧体系・接頭辞なし）。
  センタ/拠点の別（`_center` / `_kyoten`）も同様に復元するが、HTML側に既に見出しがある場合は重複させない。

## コンテナ(LXC)ドキュメントの扱い

取得元は F310 マニュアルページではなく
<https://www.furukawaelectric.com/fitelnet/product/container/lxc/>。F70/F220系と共通の資料で、
F310 は V01.00 以降が対応。パイプラインは既存のものをそのまま使い、新しい経路は作っていない。

- PDF 6冊は `manuals_manifest.json` に追加。「説明書」の項が `lxc_app_man` 57p / `softflowd_man` 6p /
  `squid_man` 8p、「お知らせ」「Alpine Linuxイメージファイル」の項が `lxc_check_change` 2p / `lxc_check` 1p /
  `alpine_oss` 2p。F310マニュアルページ以外から取るエントリには `source` キーで掲載ページを持たせている
  （取得処理は使わない。出所の記録用）。`alpine_oss` はコンテナイメージのOSS一覧で、ルータ本体の `oss_list` とは別物。
- HTML 2件（`remote-wireshark` / `ztp-script`）は `examples_manifest.json` に `kind: detail` で追加し、
  既存のリニアライザで `container_*.md` として生成する。`no` は `C1`/`C2`（SECT/NOPAGE の数字キーと
  衝突させないため）。分類は `gen_examples.py` の CATMAP と `gen_examples_index.py` の BUCKETS の
  `/container/lxc/` 判定で決まる。
  **ただし設定例ページのテンプレート（`.title`/`.summary`/`.envname`）は使っていない。**
  本文が素の `<p>`/`<li>` に入っているため、下記のフォールバックが無いと手順の説明文が丸ごと落ちる。
- 説明書の `speedtest.html`（回線速度測定）は**サイト側が404**でリンク切れのため未収録。復活したら
  examples_manifest に1行足すだけで入る。

## マニュアルPDFを差し替え・追加するとき

`data/manuals_manifest.json` にURLを足し（ページ数はもう書かない）、`python3 scripts/build.py --force` で取り直す。
続けて `python3 scripts/build.py --accept-current` で検証済みの版を更新し、
`skills/lookup/references/manuals_index.md` の表と README の規模の数値も合わせて更新すること。
