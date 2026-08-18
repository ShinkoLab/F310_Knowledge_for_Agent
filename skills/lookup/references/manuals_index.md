# FITELnet F310 マニュアル索引（ルーティング表）

古河電工 FITELnet F310 の純正マニュアル16冊（うちコンテナ(LXC)関連6冊）を、ページ番号マーカー付きテキストに変換したもの。
各ファイルは `===== PAGE N =====`（N = PDF物理ページ）で区切られている。
実体は KB（`$F310_KB_DIR`、既定 `~/.claude/plugins/data/f310-kb-shinko-lab`）の `md/` 以下。

| ファイル | ページ | 収録内容 | こんな時に見る |
|---|---:|---|---|
| `cmd_refe_config` | 1136 | **コマンドリファレンス 構成定義編**。configモードの全コマンド構文・パラメータ・デフォルト値 | 「このコマンドの書式は?」「設定の入れ方は?」 |
| `cmd_refe_ope` | 782 | **コマンドリファレンス 運用管理編**。show系・運用/保守コマンド | 「状態確認・運用コマンドの使い方」 |
| `kinou` | 114 | **機能説明書**。搭載機能の解説（ルーティング/VPN/QoS等の概念） | 「この機能は何をする?」「機能の全体像」 |
| `message` | 1604 | **メッセージ一覧**。ログ/syslog/エラーメッセージの意味と対処 | 「このログの意味は?」「エラー番号の対処」 |
| `siyou` | 78 | **仕様一覧**。ハード/ソフト仕様、MIB/Trap一覧 | 「対応本数・性能値」「MIB/Trap定義」 |
| `trouble` | 23 | **トラブルシューティング**。症状別の切り分け | 「動かない時の切り分け」 |
| `goriyouF310` | 58 | **ご利用にあたって**。導入・初期設定の概要 | 「最初のセットアップ手順」 |
| `usbband` | 21 | **USB脱落防止（取付）**。オプション品の取付説明 | 「USB脱落防止の付け方」 |
| `rackmountRMKB010211wb` | 44 | **ラックマウント取付**。RMKB010211取付説明 | 「ラックへの取り付け方」 |
| `oss_list` | 13 | **OSSライセンス一覧** | 「使用OSSとライセンス」 |
| `lxc_app_man` | 57 | **コンテナ型仮想環境の使用方法 F版**。コンテナ(LXC)の有効化・イメージ操作・ネットワーク接続・アプリ導入 | 「コンテナの使い方」「container コマンドの手順」 |
| `softflowd_man` | 6 | **NetFlow(softflowd)の使用方法**。コンテナ上のフローエクスポータ | 「NetFlow/sFlowを出したい」 |
| `squid_man` | 8 | **Proxyサーバ(squid)の使用方法**。コンテナ上のProxy | 「Proxyを立てたい」 |
| `lxc_check_change` | 2 | **システムコンテナの確認および変更方法**。旧OS→Alpine Linux の確認・入れ替え手順 | 「コンテナのOSはどっち?」「Alpineに変えたい」 |
| `lxc_check` | 1 | **システムコンテナの確認方法（旧ファームウェア）**。バージョンアップ前の確認手順 | 「古いFWのままOSを確認したい」 |
| `alpine_oss` | 2 | **Alpine Linux イメージのOSS一覧**（`oss_list` はルータ本体側。別物） | 「コンテナに入っているOSSとライセンス」 |

合計 3,949ページ。

> コンテナ関連の6冊は公式サイトの
> [コンテナFITELnet LXCアプリケーション](https://www.furukawaelectric.com/fitelnet/product/container/lxc/)
> から取得している（F310マニュアルページではない）。`lxc_app_man` / `softflowd_man` / `squid_man` は「説明書」の項、
> `lxc_check_change` / `lxc_check` / `alpine_oss` は「お知らせ」「Alpine Linuxイメージファイル」の項。
> いずれも F70/F71/F220/F221/F225/F310/F220 EX/F221 EX 共通の資料。

## コマンド索引 `md/command_index.json`

構成定義編・運用管理編の**全1,914コマンド**（構成定義編 1,299 / 運用管理編 615）を構造化したJSON。
`lookup.py cmd` はこれを引く。本文をgrepするより速く、確実に構文へ辿り着ける。1件の形:

```json
{
  "command": "ntp server",
  "manual": "cmd_refe_config",
  "category": "構成定義編",
  "page": 57,
  "function": "NTP サーバの登録",
  "syntax": "ntp [vrf <VRF 名>] server <NTP サーバ> ...",
  "mode": "基本設定モード",
  "ref": "cmd_refe_config.pdf p.57"
}
```

`set mtu`・`description` など**同名で複数エントリがあるのは正常**（動作モード違いで別ページに存在するため、それぞれ保持している）。
モードを見て、どの文脈のコマンドかを判断すること。

## 設定例 `md/setting_examples/`

公式サイト `furukawaelectric.com/fitelnet/setting/` から、**対象装置にF310を含む設定例**を抽出したもの。
索引は `setting_examples/INDEX.md`（全78項目。個別ページ56件＋大ページ内セクション14件＋外部リンク3件）。
コンテナ(LXC)の説明書HTML 2件（Remote Wireshark / ZTPスクリプト）も、設定例と同じテンプレートのため
同じ経路で `container_*.md` として生成している。
各ファイルは「完成コンフィグ＋設定条件表＋手順＋補足＋出典URL」を収録。

ファイル命名:

| 接頭辞 | 内容 |
|---|---|
| `f310_*` | F310専用ページ（DHCPサーバ / フィルタリング / NAPT / PPPoE 等） |
| `ipoe_*` | IPoE・IPv6インターネット接続（v6プラス / OCNバーチャルコネクト / クロスパス 等） |
| `ipsec_*` | 拠点間・リモートアクセスVPN |
| `cloud_*` | クラウド接続VPN |
| `redundancy_*` | 回線・装置冗長化（VRRP 等） |
| `routing_*` | ルーティング（OSPF / BGP / RIP / スタティック） |
| `interface_*` | インターフェース / QoS / USBモバイル |
| `other_*` | 運用管理（SNMP / SYSLOG / 認証 / NTP / SSH） |
| `lbo_index` | ローカルブレイクアウト集約ページ |
| `container_*` | コンテナ(LXC)の説明書（Remote Wireshark / ZTP用Pythonスクリプト） |

> 多くの設定例は F70/F220 系との共通ページ（コマンド体系が共通のため）。F310固有ページは `f310_*`。
> 対象装置欄にF310が含まれることは抽出時に確認済みだが、回答時は各ファイル冒頭の「対象装置」も併せて確認すること。
