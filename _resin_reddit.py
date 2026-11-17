# -*- coding: utf-8 -*-
"""光固化专栏 · Reddit 公开 RSS 通道适配器（2026-11-17 H 批接入）

背景与结论订正
--------------
V1.1 口径把 Reddit 记为 `blocked`（2026-11-13 复测：www 搜 403、old.reddit 返回
「Welcome to Reddit」HTML 中间页）。2026-11-17 重测发现：

  · www.reddit.com/r/<板块>/new/.rss  → HTTP 200，Atom 正文，含当日新帖与 selftext；
  · api.reddit.com / www 的 .json 端点 → 403；
  · search.rss 与连续多板块请求 → 频繁 429，需 12 秒以上间隔；
  · PullPush 镜像可用但数据停在 2026-10-11，且全文匹配相关性松散，不作生产源。

因此本通道只走 **公开 new/.rss 新帖流**，不做搜索、不登录、不绕验证码；
低频轮询（板块间 13 秒），429 只记错误并跳过该板块，不中断主流程。

纪律
----
1. 采集器绝不判情感、绝不写问题点；本模块只产出候选池条目；
2. 强语境闸门：必须同时命中 Creality 自有品牌/光固化机型与树脂工艺词，
   FDM 专有用语只在「同时出现树脂词」的对比帖里放行；
3. 以 permalink 里的 post id 做 candKey，重跑幂等；
4. 非官方 API，可能滞后且样本稀疏，页面必须披露采集方式。
"""
import datetime as dt
import html as html_lib
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

BASE_HOST = "https://www.reddit.com"
SUBS = ("resinprinting", "Creality", "3Dprinting", "FixMyPrint", "3dprinter")
NS = {"a": "http://www.w3.org/2005/Atom"}
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

# 强语境：自有品牌 / 光固化机型
OWN_RE = re.compile(
    r"\bhalot\b|halot[- ]?(mage|one|sky|ray|lite|max)|\bld[- ]?00[2345]\b|"
    r"\blsd[- ]?00[2345]\b|creality\s+(resin|光固化|sla|msla)", re.I)
# 树脂工艺词
RESIN_RE = re.compile(
    r"\bresin\b|\bsla\b|\bmsla\b|\blcd\b|\bdlp\b|\bphotopolymer\b|\bfep\b|\bnfep\b|"
    r"\bvat\b|\bcure[ds]?\b|\bcuring\b|\buv\b|\b光固化\b|\b树脂\b", re.I)
# FDM 专属：单独出现时剔除，和树脂词共现（对比帖）则保留
FDM_RE = re.compile(
    r"\bfdm\b|\bfilament\b|\bpla\b|\bpetg\b|\babs\b|\btpu\b|\bk1\b|\bk2\b|"
    r"\bender\b|\bkobra\b|\bbambu\b|\bhotend\b|\bextruder\b|\bnozzle\b", re.I)
PROMO_RE = re.compile(r"affiliate|amzn\.to|discount\s?code|coupon|promo\s?code", re.I)
RD_TAIL = re.compile(r"submitted by\s*/u/\S+.*$", re.I | re.S)
TAG_RE = re.compile(r"<[^>]+>")

CH_WINDOW_DAILY = 7
CH_WINDOW_BACKFILL = 180
PACE_SECONDS = 13.0
MAX_SECONDS = 120


def _clean(v):
    s = html_lib.unescape(v or "")
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", s, flags=re.S | re.I)
    s = TAG_RE.sub(" ", s)
    s = RD_TAIL.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def _get(sub, limit):
    url = "%s/r/%s/new/.rss?limit=%d" % (BASE_HOST, sub, limit)
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                              "Accept": "application/atom+xml,application/xml"})
    with OPENER.open(req, timeout=15) as r:
        raw = r.read()
    root = ET.fromstring(raw)
    out = []
    for e in root.findall("a:entry", NS):
        link = ""
        for l in e.findall("a:link", NS):
            if l.get("rel") in (None, "alternate") and (l.get("href") or "").startswith("http"):
                link = l.get("href")
                break
        if not link:
            continue
        pub = (e.findtext("a:published", "", NS) or e.findtext("a:updated", "", NS) or "")[:10]
        author = ""
        au = e.find("a:author/a:name", NS)
        if au is not None:
            author = (au.text or "").strip()
        out.append({"title": (e.findtext("a:title", "", NS) or "").strip(),
                    "link": link, "pub": pub, "author": author,
                    "content": _clean(e.findtext("a:content", "", NS))})
    return out


def _post_id(link):
    m = re.search(r"/comments/([a-z0-9]+)/", link, re.I)
    return m.group(1).lower() if m else re.sub(r"[^a-z0-9]", "", link.lower())[-14:]


def collect(cfg, ctx):
    """返回 (items, recall, errors)；条目直接落 _resin_collect 的候选池 schema。"""
    daily = bool(ctx["daily"])
    today = ctx["today"]
    start = today - dt.timedelta(days=CH_WINDOW_DAILY if daily else CH_WINDOW_BACKFILL)
    if ctx.get("win_start") and ctx["win_start"] > start:
        start = ctx["win_start"]
    stats, seen, topics = ctx["stats"], ctx["seen"], ctx["topics"]
    model_of, competitor_hits = ctx["model_of"], ctx["competitor_hits"]
    min_chars = int((cfg.get("noiseRules") or {}).get("minContentChars", 40))

    items, recall, errors = [], [], []
    t0 = time.time()
    for i, sub in enumerate(SUBS):
        if time.time() - t0 > MAX_SECONDS:
            errors.append({"channel": "reddit", "sub": sub, "error": "time budget exceeded"})
            break
        if i:
            time.sleep(PACE_SECONDS)
        try:
            rows = _get(sub, 100 if not daily else 50)
            recall.append({"layer": "reddit/rss", "term": "r/" + sub,
                           "posts": len(rows), "topics": 200})
        except urllib.error.HTTPError as e:
            errors.append({"channel": "reddit", "sub": sub, "error": "HTTP %s" % e.code})
            recall.append({"layer": "reddit/rss", "term": "r/" + sub,
                           "posts": 0, "topics": e.code})
            continue
        except Exception as e:
            errors.append({"channel": "reddit", "sub": sub,
                           "error": "%s: %s" % (type(e).__name__, str(e)[:80])})
            continue

        for r in rows:
            title, text, pub = r["title"], r["content"], r["pub"]
            blob = (title + " " + text).strip()
            low = blob.lower()
            head = low[:500]   # 只看标题+正文开头：品牌出现在长文末尾多为转述，不是本题主体
            cand = "reddit:" + _post_id(r["link"])
            if not pub or pub < start.isoformat():
                stats["out_of_window"] += 1
                continue
            if not RESIN_RE.search(head):
                stats["no_context"] += 1
                continue
            if not OWN_RE.search(head):
                stats["no_subject"] += 1
                continue
            if FDM_RE.search(head) and not OWN_RE.search(head):
                stats["no_context"] += 1
                continue
            if PROMO_RE.search(low) or len(blob) < min_chars:
                stats["too_short"] += 1
                continue
            if cand in seen or cand in topics:
                stats["duplicate"] += 1
                continue

            mcode, mname = model_of(blob)
            comps = competitor_hits(blob)
            zh = bool(re.search(r"[\u4e00-\u9fff]", blob))
            items.append({
                "candKey": cand,
                "queryLayer": "reddit/rss",
                "queryTerm": "r/" + sub,
                "topicId": _post_id(r["link"]),
                "postId": _post_id(r["link"]),
                "title": title[:200],
                "blurb": text[:200],
                "originalText": blob[:1200],
                "pubDate": pub,
                "crawlDate": today.isoformat(),
                "sourceLink": r["link"],
                "author": r["author"],
                "platform": "Reddit",
                "channel": "reddit",
                "channelGroup": "海外社区",
                "region": "海外",
                "language": "zh" if zh else "en",
                "sourceType": "用户",
                "heat": 0,
                "replyCount": 0,
                "collectMethod": "auto",
                "batchKind": "daily" if daily else "backfill",
                "contentKind": "图文",
                "needsReview": True,
                "gate": {"context": True, "subject": True, "offtopic": False,
                         "own": bool(OWN_RE.search(head)), "competitors": comps,
                         "model": mcode},
            })
            topics[cand] = items[-1]
    return items, recall, errors
