# -*- coding: utf-8 -*-
"""光固化专栏 · B 站通道适配器（2026-11-13 E 批接入）

背景与结论订正
--------------
V1.0 口径把 B 站记为 `blocked`（「直连返回 412，需登录态或签名」）。2026-11-13 复测：
直连确实 412，但**先 GET 首页拿 cookie（warmup）+ 带 Referer 打 search/type 即 code=0**，
实测「光固化 打印机」返回 200 / 30KB / 12 组结果、单条最高 21.6 万播放。
故本模块复用 _bili_search.py 的成熟实现，不重复造轮子。

纪律
----
1. 只采公开搜索结果，不登录、不用小号；
2. 不判情感、不写问题点 —— 那是标注层的职责；
3. 站内搜索页不翻页（page=1 已足够，翻页命中衰减且易触发风控）；
4. 返回条目直接落 _resin_collect.py 的候选池 schema，由主采集器统一过闸门。
"""
import datetime as dt
import re
import time

import _bili_search as B

# 稀疏渠道窗口：光固化在 B 站属低频内容，按 3 天窗口日更会长期 0 命中。
# 改为长窗口滚动召回，靠主采集器的 seen 差集保证不重复入库。
CH_WINDOW_DAILY = 120
CH_WINDOW_BACKFILL = 0        # 0 = 不限，交给主流程按回填窗口过滤

# B 站中文语料专用强语境词：比 RESIN_STRICT 更严，避免「曝光」等泛词误召回
BILI_STRICT = ["光固化", "光敏树脂", "树脂打印", "离型膜", "料槽", "sla", "msla",
               "dlp", "halot", "photon", "saturn 4", "mighty 8k", "nfep", "fep",
               "uv固化", "清洗固化", "光固化3d", "lcd光固化"]
BILI_FDM = ["fdm", "熔融沉积", "耗材烘干", "k2 plus", "k1 max", "ender", "kobra",
            "喷头", "热床", "进料", "支撑材料 pla"]

# 中文检索词：机型别名 + 品类词。英文机型名在 B 站命中率低，配中文品类词兜底。
KW_MODEL = ["HALOT-MAGE PRO", "HALOT-MAGE", "HALOT-ONE", "创想三维 光固化", "HALOT 光固化"]
KW_CATEGORY = ["光固化 3D打印 评测", "光固化打印机 选购", "光固化 树脂 新手"]
KW_COMPETITOR = ["Elegoo 土星4", "Anycubic 光固化", "Phrozen 8K"]


def _gate(title, desc):
    s = (title or "") + " " + (desc or "")
    low = s.lower()
    if not any(k in low for k in BILI_STRICT):
        return False
    # 纯 FDM 内容剔除（同时命中光固化词时保留，因为对比类视频常两者都提）
    if any(k in low for k in BILI_FDM) and not any(
            k in low for k in ("光固化", "树脂", "halot", "sla", "msla")):
        return False
    return True


def collect(cfg, ctx):
    """返回 (items, recall, errors)；items 已是候选池 schema。

    ctx 由 _resin_collect.collect() 传入，含 model_of / competitor_hits /
    win_start / today / daily / delay / stats / seen / topics。
    """
    daily = ctx["daily"]
    win_start = ctx["win_start"]
    today = ctx["today"]
    stats = ctx["stats"]
    seen = ctx["seen"]
    topics = ctx["topics"]
    model_of = ctx["model_of"]
    competitor_hits = ctx["competitor_hits"]

    model_kw = KW_MODEL[:3] if daily else KW_MODEL
    cat_kw = KW_CATEGORY[:1] if daily else KW_CATEGORY
    comp_kw = [] if daily else KW_COMPETITOR
    keywords = model_kw + cat_kw + comp_kw
    days = CH_WINDOW_DAILY if daily else CH_WINDOW_BACKFILL
    own_start = today - dt.timedelta(days=CH_WINDOW_DAILY) if daily else win_start

    recall, errors = [], []
    rows, sources, errs = B.search(
        keywords, gate=_gate, days=days,
        exclude=lambda t, d: bool(re.search(r"搬运|合集|直播回放|开箱合集", t or "")),
        per_kw_limit=12 if daily else 25, label="Bilibili", sleep=1.6)
    errors.extend(errs)

    for r in sources:
        recall.append({"layer": "bili/" + str(r.get("step") or "search"),
                       "term": r.get("query") or "(warmup)",
                       "posts": r.get("accepted", 0), "topics": r.get("code")})

    for v in rows:
        bv = v.get("_bvid") or ""
        cand = "bili:%s" % bv
        if not bv or cand in seen or cand in topics:
            stats["duplicate"] += 1
            continue
        title = B.clean_title(v.get("title"))
        desc = B.strip_tags(v.get("originalText") or "")
        text = (title + " " + desc).strip()
        pub = str(v.get("date") or "")
        if not pub or pub < own_start.isoformat():
            stats["out_of_window"] += 1
            continue
        low = text.lower()
        if not any(k in low for k in BILI_STRICT):
            stats["no_context"] += 1
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
        author = v.get("author") or ""
        topics[cand] = {
            "candKey": cand,
            "queryLayer": "bili/" + ("model" if any(k in v.get("foundBy", "") for k in KW_MODEL) else "category"),
            "queryTerm": (v.get("foundBy") or "").split(":")[-1].strip()[:40],
            "topicId": bv, "postId": bv,
            "title": title, "blurb": desc[:200], "originalText": text[:1200],
            "sourceLink": v.get("sourceLink"),
            "pubDate": pub, "crawlDate": today.isoformat(),
            "author": author,
            "platform": "Bilibili",
            "channel": "bilibili", "channelGroup": "国内视频", "region": "国内",
            "language": "zh",
            "model": mcode, "modelName": mname,
            "competitorMentioned": comps,
            "sourceType": "官方" if v.get("sourceType") == "官方" else "KOL",
            "heat": int(v.get("views") or 0), "replyCount": 0,
            "collectMethod": "auto",
            "batchKind": "daily" if daily else "backfill",
            "contentKind": "视频", "needsReview": True, "detailFetched": True,
            "gate": {"context": True, "subject": bool(is_own or comps), "offtopic": []},
            "biliSignal": v.get("signal"),
        }
        time.sleep(0.05)

    return recall, errors
