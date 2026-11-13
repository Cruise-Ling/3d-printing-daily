# -*- coding: utf-8 -*-
"""光固化产品线口碑专栏 · 采集器（六步归一化）

用法：
  python _resin_collect.py --probe                 # 只做渠道可达性探测
  python _resin_collect.py --backfill --months 12  # L3 全量回填（默认 12 个月）
  python _resin_collect.py --daily                 # L1 日更窗口

设计纪律（沿用 K3 规范）：
  1. 采集器绝不判情感、绝不写问题点标签 —— 那是标注层的职责
  2. 只采公开内容，不登录、不用小号、不越权
  3. uid 与 seen 双线差集保证幂等，重跑不产生重复条目
  4. 沙箱默认 HTTPS_PROXY 会 502，这里强制走无代理 opener（实测直连可用）
"""
import argparse
import datetime as dt
import hashlib
import html
import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(BASE, "resin_config.json"), encoding="utf-8"))
SEEN_FILE = os.path.join(BASE, "_resin_seen.json")
PROBE_FILE = os.path.join(BASE, "_resin_probe_report.json")
FORUM = "https://forum.creality.com"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
socket.setdefaulttimeout(8)

# 机型/品牌归属统一走 _resin_models（词边界 + 最长匹配 + hashtag 拆分），
# 采集层与注入层共用一份实现，改别名表即可全站生效。
import _resin_models as RM

# 光固化「强语境」白名单：YouTube 通用搜索里 FDM 视频会因 "3d print" / "lcd"
# 命中宽泛 contextTerms 而灌入噪声（2026-11-12 首跑 13 条里 12 条是 K2/Ender/Kobra）。
RESIN_STRICT = ["resin", "光固化", "光敏树脂", "树脂", "sla", "msla", "dlp",
                "halot", "photon", "saturn 4", "mighty 8k", "fep", "nfep",
                "离型膜", "料槽", "曝光", "uv cure", "wash and cure", "vat"]
FDM_MARKERS = ["fdm", "ender 3", "k2 plus", "k2 combo", "k2 se", "k2 pro",
               "kobra", "filament", "pla ", "petg", "nozzle", "extruder",
               "cfs", "multicolor 3d printer", "bambu lab a1"]

# 强制绕过沙箱代理：实测 HTTPS_PROXY=http://127.0.0.1:52097 会 502 / timeout
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def fetch(url, as_json=True, timeout=8):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
    })
    with OPENER.open(req, timeout=timeout) as r:
        raw = r.read()
    return (json.loads(raw) if as_json else raw), r.status


def clean_html(s):
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", s or "", flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def norm_text(s):
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", clean_html(s).lower())


def hit(text, terms):
    low = (text or "").lower()
    return [t for t in terms if t.lower() in low]


def model_of(text):
    """返回 (modelCode, modelName)。判定逻辑在 _resin_models（词边界 + 最长匹配）。"""
    c, n, _b = RM.model_of(text)
    return c, n


def model_brand(text, mcode=None):
    """机型命中返回机型品牌；未命中再按品牌词兜底（返回品牌 code 或 None）。"""
    if mcode:
        return RM.brand_of_model(mcode)
    return RM.best_brand(text)


def competitor_hits(text):
    """被点名的竞品机型名列表（只认竞品品牌的机型）。"""
    return RM.competitor_hits(text)


# 强光固化信号：用于 FDM 误召回的否决权。论坛是混合版块，FDM 帖只要出现 "resin"
# 就会通过 contextTerms，实测 30 条里混进 K2 Series / Ender 3V3 两条。
RESIN_VETO_PASS = ["halot", "光固化", "光敏树脂", "sla", "msla", "离型膜", "料槽",
                   "resin printer", "resin printing", "ld-003", "lcd 打印"]


def load_seen():
    return json.load(open(SEEN_FILE, encoding="utf-8")) if os.path.exists(SEEN_FILE) else {}


def probe():
    """渠道可达性实测：只发探测请求，不写候选池"""
    report = {"probeDate": dt.date.today().isoformat(), "channels": [], "queries": []}
    checks = [
        ("creality_forum", FORUM + "/latest.json"),
        ("youtube", "https://www.googleapis.com/youtube/v3/search?part=snippet&q=halot&key=INVALID"),
        ("bilibili", "https://api.bilibili.com/x/web-interface/search/type?search_type=video&keyword=Halot"),
        ("smzdm_list", "https://www.smzdm.com/fenlei/3ddayinji/"),
        ("reddit", "https://old.reddit.com/r/resinprinting/new/.rss"),
        ("github_pages", "https://cruise-ling.github.io/3d-printing-daily/creality-k3.html"),
    ]
    for key, url in checks:
        try:
            _, code = fetch(url, as_json=False)
            report["channels"].append({"key": key, "http": code, "reachable": code in (200, 400, 401, 403, 412)})
        except urllib.error.HTTPError as e:
            report["channels"].append({"key": key, "http": e.code, "reachable": True, "blocked": e.code >= 400})
        except Exception as e:
            report["channels"].append({"key": key, "http": None, "reachable": False, "error": type(e).__name__})

    q = CFG["queries"]["model"][:3]
    for term in q:
        try:
            d, code = fetch(FORUM + "/search.json?q=" + urllib.parse.quote(term))
            report["queries"].append({"term": term, "http": code,
                                     "posts": len(d.get("posts", [])), "topics": len(d.get("topics", []))})
        except Exception as e:
            report["queries"].append({"term": term, "http": None, "error": type(e).__name__})
        time.sleep(0.3)

    for ch in CFG["channels"]:
        found = next((x for x in report["channels"] if x["key"] == ch["key"]), None)
        if found:
            ch["probe"] = found
    report["channelConfig"] = CFG["channels"]
    with open(PROBE_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("[PROBE] %s" % PROBE_FILE)
    for c in report["channels"]:
        print("  %-20s http=%s" % (c["key"], c["http"]))
    for q in report["queries"]:
        print("  %-20s posts=%s topics=%s" % (q["term"], q.get("posts"), q.get("topics")))
    return report


def gate_stats():
    return {"no_context": 0, "no_subject": 0, "offtopic": 0, "too_short": 0,
            "duplicate": 0, "out_of_window": 0, "kept": 0}


YT_MAX_SECONDS = 180


def yt_api(path, params, api_key):
    p = dict(params)
    p["key"] = api_key
    url = "https://www.googleapis.com/youtube/v3/%s?%s" % (path, urllib.parse.urlencode(p))
    return fetch(url, timeout=10)[0]


def yt_pubdate(s):
    try:
        return dt.datetime.fromisoformat((s or "").replace("Z", "+00:00")).date()
    except Exception:
        return dt.date.today()


def collect_youtube(topics, seen, win_start, today, daily, stats, errors, recall, quota, delay):
    """YouTube Data API v3：视频（标题+简介）与公开评论，走与论坛相同的五道闸门。

    quota 纪律：search.list 每次 100 units，videos.list / commentThreads.list 每次 1 unit，
    免费额度 1 万/天。按「机型×时间窗」固定查询词，禁止无脑翻页；整段硬上限 180 秒。
    采集器仍不判情感：视频与评论只进候选池，标注由 _resin_prelabel.py / AI 复核负责。
    """
    cred_path = os.path.join(BASE, "_k3_creds.json")
    api_key = None
    if os.path.exists(cred_path):
        try:
            api_key = (json.load(open(cred_path, encoding="utf-8")).get("youtube") or {}).get("apiKey")
        except Exception:
            pass
    if not api_key:
        errors.append({"channel": "youtube", "error": "缺少 _k3_creds.json 的 youtube.apiKey"})
        return

    terms = []
    for t in CFG["queries"]["model"][:3]:
        terms.append(("model", t))
    for t in CFG["queries"]["category"][:2]:
        terms.append(("category", t))
    for t in CFG.get("competitorQueries", []):
        terms.append(("competitor", t))

    published_after = win_start.isoformat() + "T00:00:00Z"
    started = time.time()
    vids, own_vids, comment_hashes = {}, [], set()

    # 原文存档：YouTube 公开 API 响应落盘，满足附录 B「原文截图或存档文件」
    ev_dir = os.path.join(BASE, "_resin_evidence")
    os.makedirs(ev_dir, exist_ok=True)
    ev_path = os.path.join(ev_dir, "index.json")
    ev_index = {}
    if os.path.exists(ev_path):
        try:
            ev_index = json.load(open(ev_path, encoding="utf-8"))
        except Exception:
            pass

    for layer, term in terms:
        if time.time() - started > YT_MAX_SECONDS:
            errors.append({"channel": "youtube", "error": "YouTube 采集超过 180 秒上限，提前收尾"})
            break
        try:
            d = yt_api("search", {"part": "snippet", "q": term, "type": "video",
                                  "order": "date", "maxResults": 25,
                                  "publishedAfter": published_after}, api_key)
            quota["units"] += 100
            quota["searches"] += 1
        except Exception as e:
            errors.append({"channel": "youtube", "term": term,
                           "error": "%s: %s" % (type(e).__name__, str(e)[:80])})
            continue
        rows = d.get("items", [])
        recall.append({"layer": "youtube/" + layer, "term": term,
                       "posts": len(rows), "topics": len(rows)})
        for v in rows:
            vid = (v.get("id") or {}).get("videoId")
            if not vid:
                continue
            sn = v.get("snippet") or {}
            title = clean_html(sn.get("title") or "")
            desc = clean_html(sn.get("description") or "")[:900]
            text = (title + " " + desc).strip()
            cand = "yt:%s" % vid
            if cand in seen or cand in topics:
                stats["duplicate"] += 1
                continue
            pub = yt_pubdate(sn.get("publishedAt"))
            if pub < win_start:
                stats["out_of_window"] += 1
                continue
            low = text.lower()
            strong = [t for t in RESIN_STRICT if t in low]
            fdm = [t for t in FDM_MARKERS if t in low]
            if not strong:
                stats["no_context"] += 1
                continue
            # 命中 FDM 机型词时，必须同时有明确光固化主体，否则判同名异物
            if fdm and not any(k in low for k in
                               ("halot", "光固化", "resin printer", "光敏树脂", "resin 3d printer")):
                stats["offtopic"] += 1
                continue
            mcode, mname = model_of(text)
            brand = model_brand(text, mcode)
            comps = competitor_hits(text)
            is_own = brand == "creality" or "creality" in low or "halot" in low
            if not brand and not comps and not is_own:
                stats["no_subject"] += 1
                continue
            off = hit(text, CFG["offtopicTerms"])
            if off and not any(k in low for k in ("resin", "光固化", "3d print", "3d打印", "sla", "msla")):
                stats["offtopic"] += 1
                continue
            if len(text) < CFG["noiseRules"]["minContentChars"]:
                stats["too_short"] += 1
                continue
            vids[vid] = {"cand": cand, "title": title, "model": mcode,
                         "modelName": mname, "brand": brand, "comps": comps, "own": is_own}
            if is_own:
                own_vids.append(vid)
            topics[cand] = {
                "candKey": cand, "queryLayer": "youtube/" + layer, "queryTerm": term,
                "topicId": vid, "postId": vid, "title": title, "blurb": desc[:200],
                "originalText": text[:1200],
                "sourceLink": "https://www.youtube.com/watch?v=%s" % vid,
                "pubDate": pub.isoformat(), "crawlDate": today.isoformat(),
                "author": sn.get("channelTitle") or "", "platform": "YouTube",
                "channel": "youtube", "channelGroup": "海外视频", "region": "海外",
                "language": "zh" if re.search(r"[\u4e00-\u9fff]", text) else "en",
                "model": mcode, "modelName": mname, "brand": brand, "brandCode": brand,
                "isCompetitor": bool(brand) and not RM.is_own_brand(brand),
                "subjectKind": "own" if RM.is_own_brand(brand) else ("competitor" if brand else "none"),
                "competitorMentioned": comps,
                "sourceType": "KOL", "heat": 0, "replyCount": 0,
                "collectMethod": "api", "batchKind": "daily" if daily else "backfill",
                "contentKind": "视频", "needsReview": True, "detailFetched": True,
                "gate": {"context": True, "subject": bool(mcode or comps or is_own), "offtopic": off},
            }
            ev_rel = "_resin_evidence/yt_%s.json" % vid
            try:
                with open(os.path.join(ev_dir, "yt_%s.json" % vid), "w", encoding="utf-8") as f:
                    json.dump({"apiResponse": v, "sourceLink": topics[cand]["sourceLink"],
                               "archivedAt": today.isoformat()}, f, ensure_ascii=False, indent=2)
                ev_index[cand] = ev_rel
            except Exception:
                pass
        time.sleep(delay)

    # 批量取播放/点赞/评论数（一次最多 50 个 id，1 unit）
    if vids:
        try:
            d = yt_api("videos", {"part": "statistics", "id": ",".join(list(vids)[:50])}, api_key)
            quota["units"] += 1
            quota["stat_calls"] += 1
            for st in d.get("items", []):
                row = topics.get("yt:%s" % st.get("id"))
                if not row:
                    continue
                s = st.get("statistics") or {}
                row["heat"] = int(s.get("viewCount") or s.get("likeCount") or 0)
                row["replyCount"] = int(s.get("commentCount") or 0)
        except Exception as e:
            errors.append({"channel": "youtube:stats", "error": type(e).__name__})

    # 只对我方机型相关视频取评论；竞品视频只进「被点名」统计，不引入竞品评论区噪声
    for vid in own_vids[:8]:
        if time.time() - started > YT_MAX_SECONDS:
            break
        try:
            d = yt_api("commentThreads", {"part": "snippet", "videoId": vid,
                                          "maxResults": 10, "order": "relevance",
                                          "textFormat": "plainText"}, api_key)
            quota["units"] += 1
            quota["comment_calls"] += 1
        except Exception as e:
            errors.append({"channel": "youtube:comments", "video": vid, "error": type(e).__name__})
            continue
        meta = vids[vid]
        for th in d.get("items", []):
            cs = ((th.get("snippet") or {}).get("topLevelComment") or {}).get("snippet") or {}
            txt = clean_html(cs.get("textDisplay") or "")
            # 评论质量闸门（对齐 K3）：过短、纯链接、纯 @ 提及、批量同文案一律不入池
            if len(txt) < 40 or re.match(r"^(https?://|@)", txt.strip()):
                stats["too_short"] += 1
                continue
            h = hashlib.md5(norm_text(txt)[:200].encode("utf-8")).hexdigest()
            if h in comment_hashes:
                stats["duplicate"] += 1
                continue
            comment_hashes.add(h)
            cid = th.get("id") or hashlib.md5(txt.encode("utf-8")).hexdigest()[:12]
            cand = "ytc:%s" % cid
            if cand in seen or cand in topics:
                stats["duplicate"] += 1
                continue
            pub = yt_pubdate(cs.get("publishedAt"))
            if pub < win_start:
                stats["out_of_window"] += 1
                continue
            low = txt.lower()
            topics[cand] = {
                "candKey": cand, "queryLayer": "youtube/comment", "queryTerm": meta["title"][:60],
                "topicId": vid, "postId": cid,
                "title": "%s（评论）" % meta["title"],
                "blurb": txt[:200], "originalText": txt[:1200],
                "sourceLink": "https://www.youtube.com/watch?v=%s&lc=%s" % (vid, cid),
                "pubDate": pub.isoformat(), "crawlDate": today.isoformat(),
                "author": cs.get("authorDisplayName") or "", "platform": "YouTube 评论",
                "channel": "youtube", "channelGroup": "海外视频", "region": "海外",
                "language": "zh" if re.search(r"[\u4e00-\u9fff]", txt) else "en",
                "model": meta["model"], "modelName": meta["modelName"],
                "brand": meta.get("brand"), "brandCode": meta.get("brand"),
                "isCompetitor": bool(meta.get("brand")) and not RM.is_own_brand(meta.get("brand")),
                "subjectKind": "own" if RM.is_own_brand(meta.get("brand")) else "competitor",
                "competitorMentioned": meta["comps"] + [c for c in competitor_hits(txt)
                                                        if c not in meta["comps"]],
                "sourceType": "用户", "heat": int(cs.get("likeCount") or 0), "replyCount": 0,
                "collectMethod": "api", "batchKind": "daily" if daily else "backfill",
                "contentKind": "评论", "needsReview": True, "detailFetched": True,
                "gate": {"context": True, "subject": bool(meta["own"]), "offtopic": []},
            }
            safe_cid = hashlib.md5(cid.encode("utf-8")).hexdigest()[:12]
            ev_rel = "_resin_evidence/ytc_%s.json" % safe_cid
            try:
                with open(os.path.join(ev_dir, "ytc_%s.json" % safe_cid), "w", encoding="utf-8") as f:
                    json.dump({"apiResponse": th, "sourceLink": topics[cand]["sourceLink"],
                               "archivedAt": today.isoformat()}, f, ensure_ascii=False, indent=2)
                ev_index[cand] = ev_rel
            except Exception:
                pass
        time.sleep(delay)

    with open(ev_path, "w", encoding="utf-8") as f:
        json.dump(ev_index, f, ensure_ascii=False, indent=2)


def collect(months, daily, max_detail, delay):
    today = dt.date.today()
    win_start = today - dt.timedelta(days=3 if daily else 30 if months <= 1 else 365)
    mode = "daily" if daily else "backfill"
    stats = gate_stats()
    seen = load_seen()
    topics = {}
    errors = []
    recall = []

    all_terms = []
    for layer, terms in CFG["queries"].items():
        # 日更裁剪：8 个场景词在论坛侧几乎必然 429（11-12 实测 8/8），
        # 留给 L2/L3 全量批次，避免每天制造 8 条限流错误并拖长日更链。
        use = terms
        if daily:
            use = terms[:8] if layer == "model" else (terms[:2] if layer == "category" else [])
        for t in use:
            all_terms.append((layer, t))

    for layer, term in all_terms:
        url = FORUM + "/search.json?q=" + urllib.parse.quote(term)
        try:
            d, _ = fetch(url)
        except Exception as e:
            errors.append({"term": term, "error": "%s: %s" % (type(e).__name__, str(e)[:80])})
            continue
        posts = d.get("posts", [])
        tmap = {t["id"]: t for t in d.get("topics", [])}
        recall.append({"layer": layer, "term": term, "posts": len(posts), "topics": len(tmap)})
        for p in posts:
            tid = str(p.get("topic_id"))
            t = tmap.get(p.get("topic_id"), {})
            title = clean_html(t.get("title") or t.get("fancy_title") or "")
            blurb = clean_html(p.get("blurb") or "")
            text = (title + " " + blurb).strip()
            key = "post:%s" % p.get("id")
            if key in seen or key in topics:
                stats["duplicate"] += 1
                continue
            try:
                pub = dt.datetime.fromisoformat(p.get("created_at", "").replace("Z", "+00:00")).date()
            except Exception:
                pub = today
            if pub < win_start:
                stats["out_of_window"] += 1
                continue
            if not hit(text, CFG["contextTerms"]):
                stats["no_context"] += 1
                continue
            # FDM 否决：命中 FDM 机型词且没有任何强光固化信号 → 判同名异物
            fdm = hit(text, CFG.get("fdmMarkers") or FDM_MARKERS)
            if fdm and not any(k in text.lower() for k in RESIN_VETO_PASS):
                stats["offtopic"] += 1
                continue
            mcode, mname = model_of(text)
            brand = model_brand(text, mcode)
            comps = competitor_hits(text)
            is_own = brand == "creality" or "creality" in text.lower() or "创想" in text
            if not brand and not comps and not is_own:
                stats["no_subject"] += 1
                continue
            off = hit(text, CFG["offtopicTerms"])
            if off and not any(k in text.lower() for k in ("halot", "resin", "3d print", "3d打印", "光固化")):
                stats["offtopic"] += 1
                continue
            if len(text) < CFG["noiseRules"]["minContentChars"]:
                stats["too_short"] += 1
                continue
            author = p.get("username") or ""
            topics[key] = {
                "candKey": key,
                "queryLayer": layer,
                "queryTerm": term,
                "topicId": tid,
                "postId": str(p.get("id")),
                "title": title,
                "blurb": blurb,
                "originalText": text,
                "sourceLink": "%s/t/%s/%s" % (FORUM, t.get("slug", "topic"), tid),
                "pubDate": pub.isoformat(),
                "crawlDate": today.isoformat(),
                "author": author,
                "platform": "Creality 官方论坛",
                "channel": "creality_forum",
                "channelGroup": "海外社区",
                "region": "海外",
                "language": "zh" if re.search(r"[\u4e00-\u9fff]", text) else "en",
                "model": mcode,
                "modelName": mname,
                "brand": brand,
                "brandCode": brand,
                "isCompetitor": bool(brand) and not RM.is_own_brand(brand),
                "subjectKind": "own" if RM.is_own_brand(brand) else ("competitor" if brand else "none"),
                "competitorMentioned": comps,
                "sourceType": "官方" if author.upper() in ("CREALITY", "ADMIN", "STAFF", "MODERATOR") else "用户",
                "heat": int(p.get("like_count") or 0),
                "replyCount": int(t.get("posts_count") or 1) - 1,
                "collectMethod": "auto",
                "batchKind": "backfill" if not daily else "daily",
                "contentKind": "图文",
                "needsReview": True,
                "gate": {"context": True, "subject": bool(mcode or comps), "offtopic": off},
            }
        time.sleep(delay)

    # YouTube 通道（2026-11-12 B2 接入）：与论坛共用五道闸门，quota 单独记账
    quota = {"units": 0, "searches": 0, "stat_calls": 0, "comment_calls": 0}
    collect_youtube(topics, seen, win_start, today, daily, stats, errors, recall, quota, delay)

    # 国内通道（2026-11-13 E 批接入）：B站 + 什么值得买。
    # 两个适配器都只往 topics 里写候选条目，不判情感；任何异常只记 errors 不中断主流程。
    adapter_ctx = {"daily": daily, "win_start": win_start, "today": today,
                   "stats": stats, "seen": seen, "topics": topics, "delay": delay,
                   "model_of": model_of, "competitor_hits": competitor_hits}
    for mod_name in ("_resin_bili", "_resin_smzdm"):
        try:
            mod = __import__(mod_name)
            rc, er = mod.collect(CFG, adapter_ctx)
            recall.extend(rc or [])
            errors.extend(er or [])
        except Exception as e:
            errors.append({"channel": mod_name,
                           "error": "%s: %s" % (type(e).__name__, str(e)[:100])})

    # 二次取首帖完整正文（只取通过闸门的论坛帖、限量），失败回退 blurb
    detail_n = 0
    for key, it in topics.items():
        if it.get("channel") != "creality_forum":
            continue
        if detail_n >= max_detail:
            break
        try:
            d, _ = fetch("%s/t/%s.json" % (FORUM, it["topicId"]))
            plist = d.get("post_stream", {}).get("posts", [])
            if plist:
                full = clean_html(plist[0].get("cooked") or "")
                if len(full) > len(it["originalText"]):
                    it["originalText"] = (it["title"] + " " + full).strip()
                    it["detailFetched"] = True
        except Exception:
            pass  # 论坛限流时保留 blurb，不丢条目
        detail_n += 1
        time.sleep(delay * 0.6)

    # 统一补齐品牌字段：论坛 / YouTube / B站 / 值得买四条通道都走同一套判定，
    # 新增通道不必各自实现品牌归属。
    for it in topics.values():
        if not it.get("brand"):
            it["brand"] = model_brand(it.get("originalText") or "", it.get("model"))
        b = it.get("brand")
        it["brandCode"] = b
        it["isCompetitor"] = bool(b) and not RM.is_own_brand(b)
        it["subjectKind"] = "own" if RM.is_own_brand(b) else ("competitor" if b else "none")

    items = list(topics.values())

    # 去噪标记：批量同文案 / 零互动 / 短期集中发布
    cluster = {}
    burst = {}
    noise = CFG["noiseRules"]
    for it in items:
        h = hashlib.md5(norm_text(it["originalText"])[:200].encode("utf-8")).hexdigest()
        it["textHash"] = h
        cluster.setdefault(h, []).append(it["candKey"])
        burst.setdefault(it["pubDate"], []).append(it["candKey"])
    for it in items:
        it["noiseFlags"] = []
        if it["sourceType"] == "官方" and it["heat"] <= noise["zeroInteractionLikeMax"] and it["replyCount"] <= noise["zeroInteractionReplyMax"]:
            it["noiseFlags"].append("zero_interaction_official")
        if len(cluster.get(it["textHash"], [])) >= noise["clusterMinSameText"]:
            it["noiseFlags"].append("same_text_cluster")
        if len(burst.get(it["pubDate"], [])) >= noise["burstMinPosts"]:
            it["noiseFlags"].append("short_window_burst")
        # 联盟带货 / 导流文案：YouTube 免费 API 只给标题+简介，实测首批召回 5/5 为联盟带货；
        # 该判据对全部通道生效（B站简介、值得买正文同样会出现），按 K3「官方纯营销帖」同纪律剔除。
        ytext = (it.get("originalText") or "").lower()
        if any(k in ytext for k in ("amzn.to", "check current price", "garimpodeofertas",
                                    "affiliate", "supports channel", "affiliate link",
                                    "commission", "返利链接")):
            it["noiseFlags"].append("low_signal_affiliate")
        it["isPromo"] = any(k in it["noiseFlags"] for k in
                            ("zero_interaction_official", "same_text_cluster", "low_signal_affiliate"))

    stats["kept"] = len(items)
    out = {
        "meta": {
            "column": CFG["columnKey"],
            "mode": mode,
            "windowStart": win_start.isoformat(),
            "windowEnd": today.isoformat(),
            "months": months,
            "generatedAt": dt.datetime.now().isoformat(timespec="seconds"),
            "forumDetailFetched": detail_n,
            "gateStats": stats,
            "recall": recall,
            "youtubeQuota": quota,
            "errors": errors,
            "disclaimer": "采集器不判情感；情感与问题点由标注层规则预标并需人工确认。",
        },
        "items": items,
    }
    # 同日可能既有回填又有日更，按 mode 分文件，避免 daily 覆盖 backfill 候选池
    fn = os.path.join(BASE, "_resin_candidates_%s_%s.json" % (mode, today.strftime("%Y%m%d")))
    with open(fn, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    # 增量 seen：只在成功写出候选池后更新
    for it in items:
        seen[it["candKey"]] = {"firstSeen": today.isoformat(), "pubDate": it["pubDate"]}
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(seen, f, ensure_ascii=False, indent=2)

    print("[COLLECT] %s | mode=%s | kept=%d | detail=%d | errors=%d" % (fn, mode, len(items), detail_n, len(errors)))
    print("[GATE] %s" % json.dumps(stats, ensure_ascii=False))
    for r in recall:
        print("  %-8s %-28s posts=%-3s topics=%s" % (r["layer"], r["term"], r["posts"], r["topics"]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--backfill", action="store_true")
    ap.add_argument("--daily", action="store_true")
    ap.add_argument("--months", type=int, default=12)
    ap.add_argument("--max-detail", type=int, default=45)
    ap.add_argument("--delay", type=float, default=0.25)
    a = ap.parse_args()
    if a.probe:
        probe()
    elif a.backfill or a.daily:
        collect(a.months, a.daily, a.max_detail, a.delay)
    else:
        ap.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
