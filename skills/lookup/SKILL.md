---
name: lookup
description: 古河電工 FITELnet F310 ルータの純正マニュアル（全10冊3,873ページ・全1,914コマンド）と公式設定例76件を引くための知識ベース。F310 / FITELnet のコマンド構文や書式、config・コンフィグの作成、show系の運用コマンド、ログ・syslog・エラーメッセージの意味、ハード/ソフト仕様やMIB、IPoE（v6プラス・OCNバーチャルコネクト）・IPsec/VPN・冗長化(VRRP)・OSPF/BGP・QoS・ローカルブレイクアウト(LBO)の設定例を調べるときに使う。
---

# FITELnet F310 知識ベース

古河電工 FITELnet F310（ルータ）の純正マニュアルと公式設定例をローカル検索するためのスキル。
検索は必ず `lookup.py` を経由する。ページ番号の解決や出典整形が組み込まれている。
実行時は必ず `F310_KB_DIR="${CLAUDE_PLUGIN_DATA}" python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lookup.py" <サブコマンド> …` の形で呼ぶこと
（本文中で `lookup.py …` と書いている箇所も、実行時はこのフルパスに読み替える）。

## 0. 最初に構築状況を確認する

```bash
F310_KB_DIR="${CLAUDE_PLUGIN_DATA}" python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lookup.py" status
```

**未構築だった場合**は、ユーザーに「公式サイトから約38MB（マニュアルPDF10冊＋設定例54ページ）を取得して
知識ベースを構築する」と伝えたうえで実行する。数分かかる。

```bash
F310_KB_DIR="${CLAUDE_PLUGIN_DATA}" python3 "${CLAUDE_PLUGIN_ROOT}/scripts/build.py"
```

`mutool` が無いと止まる（`brew install mupdf-tools`）。構築済みなら以降このステップは黙って飛ばす。

## 1. どこを引くか

| 聞かれたこと | 引く先 |
|---|---|
| 「実際に動く設定を組みたい」「この機能のconfig例は?」 | **設定例**（`lookup.py ex`）。まず実例、必要ならマニュアルで裏を取る |
| 「このコマンドの書式は?」「パラメータの意味は?」 | **コマンド索引**（`lookup.py cmd`）。書式の正典 |
| 「このログ/エラーの意味は?」 | `lookup.py grep "<文言>" message` |
| 「対応本数・性能値は?」「MIB/Trapは?」 | `lookup.py grep "<語>" siyou` |
| 「この機能は何をする?」 | `lookup.py grep "<語>" kinou` |
| 「動かない、切り分けたい」 | `lookup.py grep "<症状>" trouble` |

マニュアル＝**コマンド書式の正典**、設定例＝**動く設定の実例集**。用途で使い分ける。
どのマニュアルに何が載るかの詳細は `references/manuals_index.md` を読む。

## 2. lookup.py の使い方

**1行がそのまま1回のBash呼び出しになる。** シェル変数は呼び出しをまたいで残らないので、
`LOOKUP=…` のような短縮は使わず、毎回このままフルパスで実行すること。

```bash
# コマンド索引
F310_KB_DIR="${CLAUDE_PLUGIN_DATA}" python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lookup.py" cmd "ospf"
F310_KB_DIR="${CLAUDE_PLUGIN_DATA}" python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lookup.py" cmd "^router ospf" --full
F310_KB_DIR="${CLAUDE_PLUGIN_DATA}" python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lookup.py" cmd "MTU" --desc
F310_KB_DIR="${CLAUDE_PLUGIN_DATA}" python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lookup.py" cmd "vrf" --manual cmd_refe_ope

# 本文検索（"message.pdf p.414: …" の形で出典付きで返る。対象は省略時 全10冊）
F310_KB_DIR="${CLAUDE_PLUGIN_DATA}" python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lookup.py" grep "link up" message
F310_KB_DIR="${CLAUDE_PLUGIN_DATA}" python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lookup.py" grep "MAP-E" kinou siyou

# ページ本文（N または N-M）
F310_KB_DIR="${CLAUDE_PLUGIN_DATA}" python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lookup.py" page cmd_refe_config 190
F310_KB_DIR="${CLAUDE_PLUGIN_DATA}" python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lookup.py" page message 414-415

# 設定例（索引＋本文。完成コンフィグ内のコマンド名でも引ける）
F310_KB_DIR="${CLAUDE_PLUGIN_DATA}" python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lookup.py" ex "v6プラス"
F310_KB_DIR="${CLAUDE_PLUGIN_DATA}" python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lookup.py" ex "dns-snooping"
```

| サブコマンド | 主なオプション |
|---|---|
| `cmd <regex>` | `--full`（【機能】と入力形式を全文）/ `--desc`（機能本文も検索）/ `--manual <名>` |
| `grep <pat> [manual…]` | `--case`（大小区別）/ `--limit` |
| `page <manual> <N[-M]>` | — |
| `ex <keyword>` | `--limit` |

設定例の本文を読むときは、`ex` が出したファイルパスを Read する。

## 3. 原本の確認は md で完結する

`md/*.md` は PDF のテキスト層をそのまま抽出したもので、**同じPDFを再抽出しても同一のテキストしか返らない**。
前後の文脈が必要なときは `lookup.py page <manual> <N-M>` を使い、**PDFは開かない**。

PDFを開く必要があるのは、構成図・写真などテキストに無いものを**人が目で見る**ときだけ。
その場合のみ `open "<KB>/original/<file>.pdf"` を案内する（KBの場所は `status` が表示する）。

## 4. 回答には必ず出典を添える（必須）

| 情報源 | 出典の書き方 |
|---|---|
| マニュアル | `cmd_refe_config.pdf p.190` — `lookup.py` の出力にそのまま入っている |
| 設定例 | 各mdファイル冒頭の `**出典**:` のURL |

ページ番号は**PDF物理ページ**であり、紙面に印字されたページ番号とは一致しないことがある。
`lookup.py` が返した値をそのまま使うこと。

## 5. 回答するときの注意

- **F310以外の設定例が混ざる**: 設定例の多くは F70/F220系との共通ページ。各ファイルの「対象装置」欄に
  F310が含まれることを確認してから提示する。
- **同名コマンドは動作モード違い**: `set mtu`・`description` 等は複数エントリある。どのモードのものかを明示する。
- **LBOには新旧2つのコマンド体系がある**: 設定例では `app-profile（新コマンド体系）` と
  `lbo-profile（旧コマンド体系）` が併記されている。どちらの体系かを明示して提示する。
- 推測でコマンドを作らない。索引に無い構文は「マニュアルに記載が見つからない」と答える。
