# -*- coding: utf-8 -*-
"""光固化专栏 · 什么值得买通道适配器（2026-11-13 E 批接入）

背景与结论订正
--------------
V1.0 口径把什么值得买记为 `manual`（「WP REST 401，按 K3 现有 search 补录路径」），
2026-11-13 复测出的真实可达性是：

  · search.smzdm.com  → HTTP 202 + 209 字节空壳（JS 挑战），不可用；
  · 分类页 www.smzdm.com/fenlei/3ddayinji/  → HTTP 200 / 77 万字节真实 SSR HTML，
    内含 28+ 条 post.smzdm.com/p/{id}/ 文章链接，分页 /p2/ 同样可用；
  · 文章页 post.smzdm.com/{栏}/p/{id}/ → HTTP 200 / 92 万字节，
    <title>、发布时间（正文首行的 yyyy-mm-dd HH:mm:ss）、正文段落均可抽取。

所以本通道走「分类页列表 → 标题/摘要预筛 → 只对命中条取正文」，
不是 seed-only，也不是人工补录。列表页里每条卡片自带 `contentsingle` 摘要属性，
可以不进正文就做光固化相关性预筛，避免 30×90 万字节的无效下载。

纪律
----
1. 只读公开页面，不登录、不绕验证码；
2. 列表页抓 p1~pN（默认 2 页），正文只取通过预筛的前 N 条（默认 8），硬上限 90 秒；
3. 不判情感、不写问题点；
4. 什么值得买内容属「消费评测 / 晒物」，信源记「媒体」或「KOL」，不冒充用户原声。
"""
import datetime as dt
import re
import time
import urllib.parse
import urllib.request

# 稀疏渠道窗口：什么值得买光固化内容偶发，日更按 3 天窗口会长期 0 命中。
CH_WINDOW_DAILY = 180

BASE_HOST = "https://www.smzdm.com"
LIST_URL = BASE_HOST + "/fenlei/3ddayinji/%s"
ART_RE = re.compile(r"https://post\.smzdm\.com/[a-z]*/?p/([a-z0-9]{6,})/")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

STRICT = ["光固化", "光敏树脂", "树脂", "离型膜", "料槽", "sla", "msla", "dlp",
          "halot", "photon", "saturn", "mighty 8k", "fep", "nfep", "清洗固化",
          "uv固化", "lcd 打印"]
FDM_ONLY = ["fdm", "熔融", "耗材", "pla", "petg", "喷头", "热床", "进料", "k1 ", "k2 ",
            "ender", "kobra", "bambu"]

MAX_SECONDS = 90


def _get(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                              "Accept": "text/html,application/xhtml+xml"})
    with OPENER.open(req, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8", "replace")


def _text(s):
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", s or "", flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = (s.replace("&nbsp;", " ").replace("&amp;", "&").replace("&quot;", '"')
         .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">"))
    return re.sub(r"\s+", " ", s).strip()


def _list_page(page):
    """返回 ([(url, title, snippet)], url)。卡片按 shaiwu-card-container 切块解析。

    2026-11-13 实测：列表页是 Nuxt SSR，每张卡是
      <div class="shaiwu-card-container" ... subtitleurl="<文章URL>" contentsingle="<摘要>">
        ... <a class="title-normal-b">标题</a>
    只按 <a href> 取标题会抓到图片锚点（inner 为空），故改为按卡片块解析。
    """
    url = LIST_URL % ("" if page == 1 else "p%d/" % page)
    st, html = _get(url)
    if st != 200:
        raise RuntimeError("list HTTP %s" % st)
    out, seen = [], set()
    for blk in html.split('class="shaiwu-card-container"')[1:]:
        blk = blk[:9000]
        m = (re.search(r'subtitleurl="(https://post\.smzdm\.com/[^"]+)"', blk)
             or re.search(r'href="(https://post\.smzdm\.com/[a-z]*/?p/[a-z0-9]{6,}/)"', blk))
        if not m:
            continue
        u = m.group(1)
        aid = ART_RE.search(u)
        aid = aid.group(1) if aid else u
        if aid in seen:
            continue
        seen.add(aid)
        t = re.search(r'class="title-normal[^"]*"[^>]*>(.*?)</a>', blk, re.S)
        title = _text(t.group(1)) if t else ""
        s = re.search(r'contentsingle="([^"]{4,400})"', blk)
        snip = _text(s.group(1)) if s else ""
        out.append((u, title[:160], snip[:300]))
    return out, url


def _article(url):
    st, html = _get(url)
    if st != 200:
        raise RuntimeError("article HTTP %s" % st)
    t = re.search(r"<title>(.*?)</title>", html, re.S)
    title = _text(t.group(1)).replace("_什么值得买", "").strip() if t else ""
    # 发布时间：正文首行形如 2021-03-20 16:01:42
    pub = ""
    dp = re.search(r"(20\d{2})-(\d{2})-(\d{2})\s+\d{2}:\d{2}", html)
    if dp:
        pub = "%s-%s-%s" % (dp.group(1), dp.group(2), dp.group(3))
    body = ""
    m = re.search(r'(?:id="articleId"|class="article-details")[^>]*>(.*?)(?:<div class="tips|'
                  r'<div class="article-tags|id="comment)', html, re.S)
    if m:
        body = _text(m.group(1))
    if len(body) < 80:                       # 回退：取 og:description + 首屏段落
        d = re.search(r'name="description"\s+content="([^"]{40,})"', html)
        body = _text(d.group(1)) if d else body
    return title, pub, body[:2400]


def collect(cfg, ctx):
    daily = ctx["daily"]
    win_start = ctx["win_start"]
    today = ctx["today"]
    stats = ctx["stats"]
    seen = ctx["seen"]
    topics = ctx["topics"]
    model_of = ctx["model_of"]
    competitor_hits = ctx["competitor_hits"]

    recall, errors = [], []
    started = time.time()
    own_start = today - dt.timedelta(days=CH_WINDOW_DAILY) if daily else win_start
    pages = 1 if daily else 3
    max_articles = 5 if daily else 10

    links, page_meta = [], []
    for p in range(1, pages + 1):
        if time.time() - started > MAX_SECONDS * 0.5:
            break
        try:
            got, u = _list_page(p)
        except Exception as e:
            errors.append({"channel": "smzdm", "page": p,
                           "error": "%s: %s" % (type(e).__name__, str(e)[:60])})
            continue
        recall.append({"layer": "smzdm/list", "term": "3d打印机 p%d" % p,
                       "posts": len(got), "topics": len(got)})
        page_meta.extend(got)
        time.sleep(1.0)

    # 预筛：标题或卡片摘要命中光固化语义词；同 id 去重
    cands, ids = [], set()
    for u, title, snip in page_meta:
        aid = ART_RE.search(u)
        aid = aid.group(1) if aid else u
        if aid in ids:
            continue
        ids.add(aid)
        blob = ((title or "") + " " + (snip or "")).lower()
        if not any(k in blob for k in STRICT):
            continue                              # 标题与摘要都不含光固化词，跳过（省带宽）
        if any(k in blob for k in FDM_ONLY) and not any(
                k in blob for k in ("光固化", "树脂", "halot", "sla", "msla")):
            continue
        cands.append((aid, u, title))
    recall.append({"layer": "smzdm/prescreen", "term": "标题含光固化/树脂",
                   "posts": len(cands), "topics": len(page_meta)})

    fetched = 0
    for aid, u, lt in cands:
        if fetched >= max_articles or time.time() - started > MAX_SECONDS:
            break
        cand = "szdm:%s" % aid
        if cand in seen or cand in topics:
            stats["duplicate"] += 1
            continue
        try:
            title, pub, body = _article(u)
        except Exception as e:
            errors.append({"channel": "smzdm", "url": u,
                           "error": "%s: %s" % (type(e).__name__, str(e)[:60])})
            continue
        fetched += 1
        time.sleep(1.0)
        pub = pub or ""
        if not pub or pub < own_start.isoformat():
            stats["out_of_window"] += 1
            continue
        title = title or lt
        text = (title + " " + body).strip()
        low = text.lower()
        if not any(k in low for k in STRICT):
            stats["no_context"] += 1
            continue
        if any(k in low for k in FDM_ONLY) and not any(
                k in low for k in ("光固化", "树脂", "halot", "sla", "msla")):
            stats["offtopic"] += 1
            continue
        mcode, mname = model_of(text)
        comps = competitor_hits(text)
        is_own = bool(mcode) or "creality" in low or "创想" in low or "halot" in low
        if not is_own and not comps:
            stats["no_subject"] += 1
            continue
        if len(text) < cfg["noiseRules"]["minContentChars"]:
            stats["too_short"] += 1
            continue
        topics[cand] = {
            "candKey": cand, "queryLayer": "smzdm/list", "queryTerm": "3d打印机分类页",
            "topicId": aid, "postId": aid,
            "title": title[:200], "blurb": body[:200], "originalText": text[:2400],
            "sourceLink": u,
            "pubDate": pub, "crawlDate": today.isoformat(),
            "author": "", "platform": "什么值得买",
            "channel": "smzdm", "channelGroup": "国内评测社区", "region": "国内",
            "language": "zh",
            "model": mcode, "modelName": mname,
            "competitorMentioned": comps,
            "sourceType": "KOL",          # 社区晒物/评测，不冒充用户原声
            "heat": 0, "replyCount": 0,
            "collectMethod": "auto",
            "batchKind": "daily" if daily else "backfill",
            "contentKind": "图文", "needsReview": True, "detailFetched": True,
            "gate": {"context": True, "subject": bool(is_own or comps), "offtopic": []},
        }

    return recall, errors
