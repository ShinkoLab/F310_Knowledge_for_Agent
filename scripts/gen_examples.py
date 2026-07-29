#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FITELnet 設定例HTML(UTF-8化済) -> 構造化Markdown リニアライザ
DOM順に .title/.summary/.envname/table/<pre>/.additional_* と 構成図img を拾って出力する。

入力: KB/html/*.html（fetch_examples.py が取得・UTF-8化したもの）
出力: KB/md/setting_examples/*.md
リニアライズのロジックは原型のまま。変更しているのは入出力パスの受け渡しのみ。
"""
import html as ht
import os
import re

import kb_paths as kb

SITE = 'https://www.furukawaelectric.com'

def unescape_clean(x):
    x = re.sub(r'<br\s*/?>', '\n', x, flags=re.I)
    x = re.sub(r'<[^>]+>', '', x)
    x = ht.unescape(x)
    return x

def collapse(x):
    x = unescape_clean(x)
    x = re.sub(r'[ \t　]+', ' ', x)
    x = re.sub(r' *\n *', '\n', x)
    return x.strip()

def strip_js(t):
    # title/heading cells sometimes carry JS artifacts like: '); subwindow.document.write(' ')
    t = re.sub(r"'\);.*", '', t, flags=re.S)
    t = re.sub(r'subwindow\.document.*', '', t, flags=re.S)
    return t.strip()

def abs_url(href, base):
    if not href: return ''
    if href.startswith('http'): return href
    if href.startswith('//'): return 'https:'+href
    if href.startswith('/'): return SITE+href
    # relative to page dir
    d = base.rsplit('/',1)[0]
    while href.startswith('../'):
        href = href[3:]; d = d.rsplit('/',1)[0]
    if href.startswith('./'): href = href[2:]
    return d+'/'+href

def table_to_md(tbl):
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', tbl, re.S|re.I)
    out=[]
    for r in rows:
        cells = re.findall(r'<(?:td|th)[^>]*>(.*?)</(?:td|th)>', r, re.S|re.I)
        if not cells: continue
        cells = [collapse(c).replace('\n',' ').replace('|','\\|') for c in cells]
        out.append(cells)
    if not out: return ''
    ncol = max(len(r) for r in out)
    out = [r+['']*(ncol-len(r)) for r in out]
    md = ['| '+' | '.join(out[0])+' |', '|'+'|'.join(['---']*ncol)+'|']
    for r in out[1:]:
        md.append('| '+' | '.join(r)+' |')
    return '\n'.join(md)

def is_nav_table(tbl):
    # skip tables that are basically navigation (mostly links, little text)
    txt = collapse(tbl)
    links = len(re.findall(r'<a\b', tbl, re.I))
    return links>=3 and len(txt) < links*12

# LBO一覧ページは、複数の設定例を見出し無しで <textarea id="command_..."> に詰め込んでいる。
# 生成物だけを見ると「どれが app-profile の DNS snooping 版か」が判別できなくなるため、
# id に埋まっている情報からラベルを復元する。他ページは見出し(## センタ側 等)がHTML側に
# あるので、そちらを壊さないよう対象を絞っている。
# id の付き方: command_app_dns_teams（新体系） / command_dns_teams（旧体系・接頭辞なし）
PROFILE_ID_RE = re.compile(r'^command_(?:(app|lbo)_)?(dns|http)_', re.I)
SIDE_ID_RE = re.compile(r'_(center|kyoten)(\d*)$', re.I)
PROFILE_LABEL = {'app': 'app-profile（新コマンド体系）', 'lbo': 'lbo-profile（旧コマンド体系）'}
SNOOP_LABEL = {'dns': 'DNS snooping', 'http': 'HTTP snooping'}


def pre_label(tid, heading):
    """<textarea id> から設定例の種別ラベルを作る。作れなければ None。"""
    if not tid:
        return None
    m = PROFILE_ID_RE.match(tid)
    if m:
        profile = (m.group(1) or 'lbo').lower()   # 接頭辞なしは旧コマンド体系
        return f"**{SNOOP_LABEL[m.group(2).lower()]} ／ {PROFILE_LABEL[profile]}**:"
    m = SIDE_ID_RE.search(tid)
    if m:
        # 直近の見出しが既にセンタ/拠点を示しているなら重複させない
        if heading and ('センタ' in heading or '拠点' in heading):
            return None
        side = 'センタ' if m.group(1).lower() == 'center' else '拠点'
        return f"**{side}{m.group(2)}側**:"
    return None


def linearize(html, source_url):
    body = re.search(r'<body[^>]*>(.*)</body>', html, re.S|re.I)
    b = body.group(1) if body else html
    b = re.sub(r'<script.*?</script>', '', b, flags=re.S|re.I)
    b = re.sub(r'<style.*?</style>', '', b, flags=re.S|re.I)
    b = re.sub(r'<!--.*?-->', '', b, flags=re.S)
    # limit to main editable content: from first content marker to footer/pagetop
    # cut off trailing site footer if present
    for marker in ['class="pagetop"', 'id="footer"', 'class="footer"', 'FITELnetサイトマップ']:
        i = b.find(marker)
        if i>0: b = b[:i]
    # Build a list of (pos, kind, payload)
    events=[]
    patterns = [
        ('h', r'<h([1-4])\b[^>]*>(.*?)</h\1>'),
        ('title', r'<[^>]*class="title"[^>]*>(.*?)</(?:div|p|h\d|td|span)>'),
        ('subtitle', r'<[^>]*class="(?:additional_title)"[^>]*>(.*?)</(?:div|p|h\d|span)>'),
        ('summary', r'<[^>]*class="summary"[^>]*>(.*?)</(?:div)>'),
        ('detail', r'<[^>]*class="additional_detail"[^>]*>(.*?)</(?:div)>'),
        ('env', r'<[^>]*class="envname"[^>]*>(.*?)</(?:div|p|span|td)>'),
        ('pre', r'<pre[^>]*>(.*?)</pre>'),
        ('table', r'<table[^>]*>(.*?)</table>'),
        ('img', r'<img[^>]+>'),
    ]
    for kind, pat in patterns:
        for m in re.finditer(pat, b, re.S|re.I):
            if kind=='h':
                events.append((m.start(), kind, (m.group(1), m.group(2))))
            else:
                events.append((m.start(), kind, m.group(1) if m.groups() else m.group(0)))
        # img has no group
    # img separately (no capture group content)
    events = [e for e in events if not (e[1]=='img')]
    for m in re.finditer(r'<img[^>]+>', b, re.I):
        src = re.search(r'(?:data-src|data-original|src)="([^"]+)"', m.group(0))
        alt = re.search(r'alt="([^"]*)"', m.group(0))
        src = src.group(1) if src else ''
        alt = alt.group(1) if alt else ''
        if any(k in src.lower() for k in ('icon','btn','arrow','logo','spacer','bullet','.svg','common/img','/parts/')):
            continue
        events.append((m.start(), 'img', (src, alt)))
    events.sort(key=lambda e: e[0])

    # <pre> がどの textarea に属するかの対応表（ラベル復元に使う）
    textareas = [(m.start(), m.end(), m.group(1))
                 for m in re.finditer(r'<textarea[^>]*\bid="([^"]+)"[^>]*>(.*?)</textarea>', b, re.S|re.I)]

    def textarea_id_at(pos):
        for s, e, tid in textareas:
            if s <= pos < e:
                return tid
        return None

    md=[]
    notes=[]           # 補足・注意点(additional_detail) は末尾にまとめる
    seen_pre=set()
    last_heading=None
    recent_heading=None   # last_heading と違い、コードブロックを挟んでも保持する
    def push(s=''):
        md.append(s)
    def heading(t):
        nonlocal last_heading, recent_heading
        t = re.sub(r'\s*（!の行はコメントです。.*?）\s*', '', t).strip()
        if not t: return
        if t == last_heading: return          # 直前と同一見出しは重複除去
        last_heading = t
        recent_heading = t
        push('\n## '+t+'\n')
    for pos, kind, payload in events:
        if kind=='h':
            heading(strip_js(collapse(payload[1])))
        elif kind=='title':
            heading(strip_js(collapse(payload)))
        elif kind=='subtitle':
            pass  # additional_title("補足・注意点")はスキップ、detailを末尾集約
        elif kind=='env':
            t = re.split(r'[!\n]', collapse(payload))[0].strip()
            if t and len(t) <= 40:
                push('\n### '+t+'\n'); last_heading=None; recent_heading=t
        elif kind=='summary':
            if '<table' in payload.lower():
                pre_txt = collapse(re.sub(r'<table.*', '', payload, flags=re.S|re.I))
                if pre_txt: push(pre_txt+'\n')
                for tb in re.findall(r'<table[^>]*>.*?</table>', payload, re.S|re.I):
                    md_t = table_to_md(tb)
                    if md_t: push('\n'+md_t+'\n'); last_heading=None
            else:
                t = collapse(payload)
                if t: push(t+'\n'); last_heading=None
        elif kind=='detail':
            t = collapse(payload)
            if t and t not in notes: notes.append(t)
        elif kind=='pre':
            code = unescape_clean(payload).replace('\r','').strip('\n')
            key = code.strip()   # 全文一致のみ重複とみなす（センタ/拠点configの誤除去を防ぐ）
            if not code.strip() or key in seen_pre: continue
            seen_pre.add(key)
            label = pre_label(textarea_id_at(pos), recent_heading)
            if label: push('\n'+label)
            push('\n```'); push(code); push('```\n'); last_heading=None
        elif kind=='table':
            if is_nav_table(payload): continue
            md_t = table_to_md(payload)
            if md_t and md_t.count('\n')>=2:
                push('\n'+md_t+'\n'); last_heading=None
        elif kind=='img':
            src, alt = payload
            u = abs_url(src, source_url)
            if not u: continue
            cap = collapse(alt) or '構成図'
            push('\n> 🖼 構成図: ['+cap+']('+u+')\n'); last_heading=None
    if notes:
        push('\n## 補足・注意点\n')
        for n in notes: push(n+'\n')
    text='\n'.join(md)
    # 空見出し除去: 見出し行の直後に本文が無い(次も見出し/EOF)なら削除
    lines=text.split('\n')
    out=[]
    for i,ln in enumerate(lines):
        if ln.startswith('## ') or ln.startswith('### '):
            # 次に非空・非見出しが来るか先読み
            has_body=False
            for nx in lines[i+1:]:
                if nx.strip()=='' : continue
                has_body = not (nx.startswith('## ') or nx.startswith('### '))
                break
            if not has_body: continue
        out.append(ln)
    text='\n'.join(out)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

CATMAP = [('product/f310','F310基本設定'),('ipoe','IPoE / IPv6インターネット'),
    ('cloud-connect','クラウド接続(VPN)'),('ipsec','IPsec / 拠点間VPN'),
    ('redundancy','冗長化'),('routing','ルーティング'),('lbo','ローカルブレイクアウト'),
    ('interface','インターフェース / QoS / USB'),('other','運用・管理')]

def category(u):
    for k,v in CATMAP:
        if '/'+k+'/' in u or '/'+k.split('/')[-1]+'/' in u: return v
    return 'その他'

def outname(u):
    seg = re.search(r'/(ipoe|ipsec|cloud-connect|redundancy|routing|lbo|interface|other)/([^/]+)\.html', u)
    if seg:
        pre = {'cloud-connect':'cloud'}.get(seg.group(1), seg.group(1).split('-')[0])
        base = seg.group(2).replace('+','plus')
        return f"{pre}_{base}.md"
    if 'product/f310' in u:
        base = os.path.basename(u).replace('.html','').replace('+','plus')
        return f"f310_{base}.md"
    return re.sub(r'\W+','_',u)+'.md'

def run(quiet: bool = False) -> int:
    items = kb.load_manifest(kb.EXAMPLES_MANIFEST)
    # url(without frag) -> list of (title, device, no)
    meta={}
    for it in items:
        if it['kind']!='detail': continue
        u = it['url'].split('#')[0]
        meta.setdefault(u, {'titles':[], 'device':it['device']})
        meta[u]['titles'].append(it['title'])

    src_dir = kb.html_dir()
    out_dir = kb.examples_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    report=[]
    for u, mt in sorted(meta.items()):
        f = src_dir / (kb.page_key(u) + '.html')
        if not f.exists():
            report.append((u,'MISSING',0)); continue
        html = f.read_text(encoding='utf-8', errors='replace')
        titles=list(dict.fromkeys(mt['titles']))
        primary=min(titles, key=len)
        body_md = linearize(html, u)
        header=[f"# {primary}", ""]
        if len(titles)>1:
            header.append("**掲載名（別項目）**: "+' / '.join(t for t in titles if t!=primary))
            header.append("")
        header.append(f"- **対象装置**: {mt['device']}")
        header.append(f"- **カテゴリ**: {category(u)}")
        header.append(f"- **出典**: {u}")
        header.append("")
        header.append("---")
        header.append("")
        out='\n'.join(header)+body_md+'\n'
        name=outname(u)
        (out_dir / name).write_text(out, encoding='utf-8')
        report.append((name, 'OK', out.count('\n')))
    report.sort()
    ok = len([r for r in report if r[1]=='OK'])
    if not quiet:
        for n,st,ln in report:
            print(f"{st:<8} {ln:>4}  {n}")
    print("設定例md:", ok, "件 →", out_dir)
    missing = [n for n,st,_ in report if st=='MISSING']
    if missing:
        print(f"  ⚠ HTML未取得のため未生成: {len(missing)} 件")
    return ok

if __name__=='__main__':
    run()
