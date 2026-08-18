#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""設定例マニフェストから KB/md/setting_examples/INDEX.md を生成する。

分類バケット・LBO/冗長のセクション対応(SECT)・個別ページ無しの注記(NOPAGE)は
サイトを見ながら人手で確定させたもの。自動判定できないのでここに保持する。
"""
import os
import re

import kb_paths as kb

SITE='https://www.furukawaelectric.com'

def outname(u):
    u=u.split('#')[0]
    seg = re.search(r'/(ipoe|ipsec|cloud-connect|redundancy|routing|lbo|interface|other)/([^/]+)\.html', u)
    if seg:
        pre = {'cloud-connect':'cloud'}.get(seg.group(1), seg.group(1).split('-')[0])
        return f"{pre}_{seg.group(2).replace('+','plus')}.md"
    if 'product/f310' in u:
        return "f310_"+os.path.basename(u).replace('.html','').replace('+','plus')+".md"
    if '/container/lxc/' in u:
        return "container_"+os.path.basename(u).replace('.html','').replace('+','plus')+".md"
    return ''

# section(no) -> covering file or note
SECT = {
 '26':'lbo_index.md','27':'lbo_index.md','28':'lbo_index.md','29':'lbo_index.md',
 '30':'lbo_index.md','31':'lbo_index.md','34':'lbo_index.md',
}
NOPAGE = {
 '61':'本サイトにF310向け個別ページ無し（F60/F220向け・旧サイト furukawa.co.jp 参照）',
 '62':'本サイトにF310向け個別ページ無し（F60/F220向け・旧サイト furukawa.co.jp 参照）',
 '70':'本サイトにF310向け個別ページ無し（EtherIP版。F2500版のみ存在）',
 '71_1':'本サイトにF310向け個別ページ無し（L2TPv3版。F2500版 f2500_ipsec-l2tpv3 のみ存在）',
 # redundancy-01は「センタ側で回線および装置冗長」の単一シナリオ。以下は別ページ(未リンク)で本サイトから未抽出。
 '76':'本サイトで未リンク（redundancy-01は別シナリオ。redundancy_redundancy-01.md は「センタ側 回線+装置冗長」のみ収録）',
 '78':'本サイトで未リンク（同上。VRRPプライオリティ減算は別ページ）',
 '79':'本サイトで未リンク（同上。ポリシールーティング負荷分散は別ページ）',
}

# バケット定義（表示順）
BUCKETS = [
 ('F310 基本設定（F310専用ページ）', lambda u:'product/f310' in u),
 ('IPoE / IPv6インターネット接続', lambda u:'/ipoe/' in u),
 ('ローカルブレイクアウト（LBO）', lambda u:'/lbo/' in u),
 ('IPsec / 拠点間・リモートVPN', lambda u:'/ipsec/' in u),
 ('クラウド接続（VPN）', lambda u:'/cloud-connect/' in u),
 ('回線・装置冗長化', lambda u:'/redundancy/' in u),
 ('ルーティング', lambda u:'/routing/' in u),
 ('インターフェース / QoS / USBモバイル', lambda u:'/interface/' in u),
 ('運用・管理（SNMP/SYSLOG/認証/NTP/SSH等）', lambda u:'/other/' in u),
 ('コンテナ（LXC）アプリケーション', lambda u:'/container/lxc/' in u),
]


def run() -> int:
    items = kb.load_manifest(kb.EXAMPLES_MANIFEST)

    # detail をバケットへ割当（URL重複は最初のtitleを代表に）
    by_url={}
    for it in items:
        if it['kind']!='detail': continue
        u=it['url'].split('#')[0]
        by_url.setdefault(u,{'titles':[],'device':it['device']})
        by_url[u]['titles'].append(it['title'])

    lines=[]
    lines.append("# FITELnet F310 公式設定例ナレッジ（索引）")
    lines.append("")
    lines.append("古河電工 FITELnet の公式サイト「設定例」ページから、**対象装置に F310 を含む設定例**を抽出し、")
    lines.append("各ページの完成コンフィグ・設定条件表・手順・補足を Markdown 化したもの。")
    lines.append("出典は `https://www.furukawaelectric.com/fitelnet/setting/` 配下、")
    lines.append("およびコンテナ(LXC)説明書の `.../product/container/lxc/man/` 配下（各ファイル冒頭に出典URL記載）。")
    lines.append("")
    lines.append("- 個別ページを持つ設定例: **{}件**（下表のファイルリンク）".format(len(by_url)))
    lines.append("- 大ページ内のセクション扱い（LBO/冗長の派生）: 索引のみ、本文は集約ファイルを参照")
    lines.append("- 外部サイト（Cloudflare等）: リンクのみ（本文抽出対象外）")
    lines.append("")
    lines.append("> ⚠ 多くの設定例は F70/F220 系と共通ページ（コマンド体系が共通のため）。F310固有ページは `f310_*.md`。")
    lines.append("")

    # 各バケット
    assigned=set()
    for name, pred in BUCKETS:
        urls=[u for u in by_url if pred(u)]
        if not urls: continue
        lines.append(f"## {name}")
        lines.append("")
        lines.append("| 設定例 | 対象装置 | ファイル | 出典 |")
        lines.append("|---|---|---|---|")
        for u in sorted(urls):
            m=by_url[u]; titles=list(dict.fromkeys(m['titles']))
            primary=min(titles,key=len)
            fn=outname(u)
            assigned.add(u)
            extra = ('　※別掲載名: '+' / '.join(t for t in titles if t!=primary)) if len(titles)>1 else ''
            lines.append(f"| {primary}{extra} | {m['device']} | [`{fn}`]({fn}) | [link]({u}) |")
        lines.append("")

    # セクション扱い（LBO / 冗長 / 個別ページ無し）
    sec_items=[it for it in items if it['kind']=='section']
    if sec_items:
        lines.append("## 大ページ内セクション扱い・個別ページ無しの設定例")
        lines.append("")
        lines.append("以下は独立した詳細ページを持たず、大ページ内のセクション、または本サイトにF310向け個別ページが無いもの。")
        lines.append("")
        lines.append("| 設定例 | 対象装置 | 参照先 |")
        lines.append("|---|---|---|")
        seen=set()
        for it in sec_items:
            no=it['no']
            if (it['title']) in seen: continue
            seen.add(it['title'])
            if no in SECT:
                ref=f"[`{SECT[no]}`]({SECT[no]}) 内のセクション"
            elif no in NOPAGE:
                ref=NOPAGE[no]
            else:
                ref="lbo_index.md 内のセクション"
            lines.append(f"| {it['title']} | {it['device']} | {ref} |")
        lines.append("")

    # 外部リンク
    ext=[it for it in items if it['kind']=='external']
    if ext:
        lines.append("## 外部サイト掲載（リンクのみ）")
        lines.append("")
        lines.append("| 設定例 | 対象装置 | URL |")
        lines.append("|---|---|---|")
        for it in ext:
            lines.append(f"| {it['title']} | {it['device']} | <{it['url']}> |")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 再生成メモ")
    lines.append("")
    lines.append("この索引と各 `*.md` は、設定例ページの検索テーブル（`setting_index.html` 内 `<table class=\"list\">`）から")
    lines.append("F310対象行を抽出し、各詳細ページHTML(Shift-JIS)を UTF-8 化 → DOM順リニアライザで生成した。")
    lines.append("コンテナ(LXC)の説明書ページ（`container_*.md`）も同じテンプレートのため同じ経路で生成している。")
    lines.append(f"抽出元の全{len(items)}項目（title / url / device / 分類）はリポジトリの `data/examples_manifest.json` に保持。")
    lines.append("")

    out = kb.examples_dir() / "INDEX.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    text = '\n'.join(lines)
    out.write_text(text, encoding='utf-8')
    print("INDEX generated:", len(text.split('\n')), "lines →", out)
    print("assigned detail urls:", len(assigned), "/", len(by_url))
    return len(by_url)


if __name__=='__main__':
    run()
