# -*- coding: utf-8 -*-
"""_reddit_search.py — Reddit 采集公共模块（2026-10-27）

为什么单独抽出来
--------------------------------------------------------------------------
Reddit 原本只在 K3 采集器里实现（走 search.rss），mBox 与软件专栏信源表里没有。
2026-10-27 用户在「软件专栏接入 Reddit/B站/YouTube/值得买」「mBox 接入 Reddit/值得买」
上同时提出需求 —— 三个专栏需要同一套实现，否则又是「每个专栏写一份、每份限速策略不一样」。

实测约束（重要，改速率前先读这段）
--------------------------------------------------------------------------
匿名访问 Reddit 的配额极小。实测：
  * r/3Dprinting/new.rss 首次 200，连发第 3 次即 429，响应头 x-ratelimit-remaining: 0
  * search.rss 比子版端点更早被限流
  * 因此必须**串行**、请求间隔 >= 7s；429 后至少退避 20s 才可能恢复
本模块不做并发。想快只能配 OAuth 凭据（_k3_creds.json 的 reddit.clientId/clientSecret），
但当前为空 —— 在补上之前，宁可慢，不可被封。

边界
--------------------------------------------------------------------------
本模块**只做抓取 + 归一**，不做语义判断（情感 / 问题类型 / 阶段）。
相关性闸门必须由调用方传入（gate）——
「OrcaSlicer」和「mBox」对「相关」的定义完全不同，写死在本模块里必然误收。

用法
--------------------------------------------------------------------------
    import _reddit_search as RD

    items, sources, errors = RD.search(
        subs=["OrcaSlicer", "BambuLab", "3Dprinting"],
        gate=lambda t, b: RD.gate_any(t, b, RD.SW_CTX),
        days=90,
    )

字段产出（与专栏统一数据契约对齐）
--------------------------------------------------------------------------
    uid / platform / site / channel / country / language / date / title /
    originalText / url / author / sourceType / foundBy

RSS 拿不到 score 与 comment 数（公开 .json 端点 403，OAuth 才有），
所以 replyCount / likeCount 留空 —— 页面不能拿它们排序。
"""

import html as _html
import os
import re
import time
import urllib.error
import urllib.request

# ---------------------------------------------------------------- 环境
# 沙箱默认带代理，访问 reddit 会被拒，必须清空（与 _bili_search.py 一致）
for _k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy",
           "ALL_PROXY", "all_proxy"):
    os.environ.pop(_k, None)

# Reddit 要求 UA 能标识调用方，用浏览器 UA 会拿到 403
UA = "python:col-monitor:v1.0 (by /u/colmonitor)"
BASE = "https://www.reddit.com/r/%s/new.rss?limit=%d"

RATE_SEC = 7.0          # 子版间最小间隔
BACKOFF = (20, 45)      # 429 后的两次退避
TIMEOUT = 30


# ---------------------------------------------------------------- 语义线索
# 3D 打印软件语境：切片器 / 常见工具 / 通用缺陷现象。
# 这是「判断是不是在谈 3D 打印软件」，不是「判断是不是创想」—— 专栏是全行业的。
SW_CTX = re.compile(
    r"slic(?:er|ing)|orca\s*slicer|bambu\s*studio|cura|prusa\s*slicer|"
    r"creality\s*print|chitubox|lychee|idea\s*maker|superslicer|"
    r"层高|切片|支撑|填充|拉丝|翘边|层纹|"
    r"layer\s*(?:shift|line|height|adhesion)|stringing|warping|"
    r"under[\s-]?extrusion|over[\s-]?extrusion|z[\s-]?seam|infill|"
    r"stl|3mf|g[\s-]?code|profile|preset|retraction|bridging",
    re.I,
)

# 整机/耗材/开箱类 —— 与「软件」无关，先剔掉再判
SW_EXCLUDE = re.compile(
    r"\b(?:nkd|unboxing|开箱|评测成品|到货|晒单|拼团|团购|"
    r"for\s*sale|selling|warehouse\s*sale|deal\s*alert|discount\s*code)\b",
    re.I,
)


def gate_any(title, body, pattern):
    """通用闸门：标题或正文命中 pattern 即算相关。
    标题权重更高 —— 只有正文命中而标题完全无关的，多半是顺手提了一句。"""
    head = title or ""
    if pattern.search(head):
        return True
    return bool(pattern.search(body or ""))


# ---------------------------------------------------------------- 解析
_RE_ENTRY = re.compile(r"<entry>([\s\S]*?)</entry>")
_RE_TITLE = re.compile(r"<title>(.*?)</title>", re.S)
_RE_LINK = re.compile(r'<link href="([^"]+)"')
_RE_UPD = re.compile(r"<updated>(.*?)</updated>")
_RE_PUB = re.compile(r"<published>(.*?)</published>")
_RE_AUTHOR = re.compile(r"<name>(.*?)</name>", re.S)
_RE_CONTENT = re.compile(r'<content type="html">([\s\S]*?)</content>')
_RE_CAT = re.compile(r'<category term="([^"]*)"')
_RE_RID = re.compile(r"/comments/([a-z0-9]+)/", re.I)

_TAG = re.compile(r"<[^>]+>")


def clean_html(s):
    """Reddit RSS 的 content 是一段被转义的 HTML 表格（图片预览 + 正文）。
    这里只保留可读文本：去掉 table/tr/td/img/a 的壳，保留文字。"""
    s = _html.unescape(s or "")
    # 图片预览往往是 <a href=...><img ...></a>，整段没文本，去掉
    s = re.sub(r"<a[^>]*>\s*<img[^>]*>\s*</a>", " ", s, flags=re.I)
    s = re.sub(r"<img[^>]*>", " ", s, flags=re.I)
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"</(?:p|div|td|tr|table|li)>", "\n", s, flags=re.I)
    s = _TAG.sub(" ", s)
    s = _html.unescape(s)
    s = re.sub(r"[ \t\u00a0]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def parse_feed(xml, sub):
    """把一次 new.rss 响应解析成条目列表（不含窗口/闸门判断）。"""
    out = []
    for raw in _RE_ENTRY.findall(xml or ""):
        t = _RE_TITLE.search(raw)
        title = _html.unescape(t.group(1)).strip() if t else ""
        title = re.sub(r"^r/\w+\s*-\s*", "", title)   # 部分 feed 会带 "r/xxx - " 前缀
        if not title:
            continue
        lk = _RE_LINK.search(raw)
        url = lk.group(1) if lk else ""
        au = _RE_AUTHOR.search(raw)
        author = (au.group(1).strip() if au else "")
        upd = _RE_UPD.search(raw) or _RE_PUB.search(raw)
        date = (upd.group(1) or "")[:10] if upd else ""
        c = _RE_CONTENT.search(raw)
        body = clean_html(c.group(1)) if c else ""
        cats = _RE_CAT.findall(raw)
        rid = _RE_RID.search(url)
        out.append({
            "id": rid.group(1) if rid else "",
            "sub": sub,
            "title": title,
            "url": url,
            "author": author,
            "date": date,
            "body": body,
            "flair": (cats[0] if cats else ""),
        })
    return out


# ---------------------------------------------------------------- 抓取
def _get(url):
    """单次 GET。返回 (xml, status)；失败抛 (status, retry_after) 给上层决定退避。"""
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/rss+xml,application/xml",
    })
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.read().decode("utf-8", "replace"), r.status
    except urllib.error.HTTPError as e:
        return "", e.code
    except Exception as e:
        return "", type(e).__name__


def fetch_sub(sub, limit=100, errors=None):
    """抓一个子版，返回原始 XML。429 时按 BACKOFF 退避后重试，最终失败只记录不抛。"""
    url = BASE % (sub, limit)
    for attempt in range(len(BACKOFF) + 1):
        xml, st = _get(url)
        if st == 200 and xml:
            return xml
        if st == 429 and attempt < len(BACKOFF):
            wait = BACKOFF[attempt]
            if errors is not None:
                errors.append({"sub": sub, "status": 429,
                               "note": "%ds 后重试" % wait})
            time.sleep(wait)
            continue
        if errors is not None:
            errors.append({"sub": sub, "status": st, "url": url})
        return ""
    return ""


def search(subs, gate=None, days=90, label="Reddit", limit=100,
           rate=RATE_SEC, sources=None, errors=None, keep_body=True):
    """按子版顺序抓取（串行），返回统一契约条目。

    subs    : ["OrcaSlicer", ...] 或 [("/r/x 展示名", "OrcaSlicer"), ...]
    gate    : gate(title, body) -> bool；None 表示不过滤（子版本身就是软件专版时可省）
    days    : 发布日期窗口，0 表示不限
    sources : 传入 list 则追加每个子版的抓取状态（供采集器盘点）
    errors  : 传入 list 则追加错误

    返回 (items, sources, errors)
    """
    if sources is None:
        sources = []
    if errors is None:
        errors = []

    from datetime import date, timedelta
    cutoff = ""
    if days:
        cutoff = (date.today() - timedelta(days=days)).isoformat()

    items = []
    for i, spec in enumerate(subs):
        if isinstance(spec, (tuple, list)):
            disp, sub = spec[0], spec[1]
        else:
            disp, sub = spec, spec
        if i:
            time.sleep(rate)      # 串行限速：Reddit 匿名配额极小，见模块头注释
        xml = fetch_sub(sub, limit=limit, errors=errors)
        if not xml:
            sources.append({"source": "Reddit %s" % disp, "status": "error", "count": 0})
            continue
        rows = parse_feed(xml, sub)
        kept = 0
        for r in rows:
            if cutoff and r["date"] and r["date"] < cutoff:
                continue
            if gate and not gate(r["title"], r["body"]):
                continue
            items.append({
                "uid": "rd_%s" % (r["id"] or re.sub(r"\W+", "", r["title"])[:16]),
                "platform": "Reddit",
                "site": "r/%s" % sub,
                "channel": "海外社区",
                "country": "US",
                "language": "EN",
                "date": r["date"],
                "title": r["title"],
                "originalText": (r["body"] or "") if keep_body else "",
                "url": r["url"],
                "author": r["author"],
                "flair": r["flair"],
                "sourceType": "社区",
                "foundBy": "reddit r/%s/new.rss" % sub,
            })
            kept += 1
        sources.append({"source": "Reddit %s" % disp, "status": "ok" if kept else "empty",
                        "count": kept})
    return items, sources, errors


if __name__ == "__main__":
    its, src, err = search(["OrcaSlicer", "BambuLab"], days=120)
    print("items=%d" % len(its))
    for s in src:
        print("  %-24s %-6s %s" % (s["source"], s["status"], s["count"]))
    for e in err[:5]:
        print("  ERR", e)
    for it in its[:5]:
        print("   -", it["date"], it["site"], it["title"][:60])
