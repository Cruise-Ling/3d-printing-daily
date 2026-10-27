# -*- coding: utf-8 -*-
"""
Creality mBox 专栏 · 采集器
=============================================================================
口径与 K3 专栏一致（用户 10-19 决策：mbox 直接参考 K3 做，产品即将上线）。

数据源与实测状态（2026-10-26 复查，国内源为本轮新增）：
  Creality 官方论坛 search=mbox   -> 200，0 帖（真实零声量）
  Creality 官方论坛 search=m box  -> 200，0 帖（双探，防单关键词漏检）
  creality.com 官网               -> 无产品页（搜索页命中是 Next.js 参数假阳性）
  B站 search/all/v2               -> 可采（本轮接入，实测 8 条，含 10-25 首发评测）
  知乎                             -> 403（需登录态 + x-zse-96 签名，缺 Cookie 记 need-cookie）
  YouTube                         -> 可采；官方频道 `creality park` 的 mBox 视频
  Google Play com.creality.f038App.global -> 就是 Creality Park，可采元数据
  3druck 媒体                      -> 直连 403（反爬），需人工/WebFetch 兜底
  Reddit                          -> 403（已知出口封锁，不当失败告警）
  抖音 / 小红书                     -> 仅探针（SPA + 签名，本期不产出条目）

⚠️ 2026-10-26 用户反馈「B 站已有 mBox 测评但没抓到」——
   根因是本文件信源表里原本没有 B站。B站采集已下沉到公共模块 `_bili_search.py`，
   与 K3 共用一套实现，后续机型专栏不再各写一份。

用法：
    python _col_collect_mbox.py
    python _col_collect_mbox.py --no-yt     # 跳过 YouTube
    python _col_collect_mbox.py --no-bili   # 跳过 B 站（调试用）
"""

import argparse
import gzip
import hashlib
import html as H
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120 Safari/537.36")

# 2026-10-26：清空环境代理。沙箱内 HTTPS_PROXY 指向本地隧道，走它会 502，
# 表现成「YouTube / Google Play 全挂」的假故障（当天实测踩过）。
for _k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
    os.environ.pop(_k, None)
FORUM = "https://forum.creality.com"
PARK_PKG = "com.creality.f038App.global"      # 实测 = Creality Park
CLOUD_PKG = "com.cxsw.sdprinter"              # Creality Cloud（36446 评分）
OUT = "_mbox_items.json"

KEYWORDS = ["creality mbox", "creality park app", "mbox 3d printer"]

# ⚠️ 词边界必须严格：`m\s*box` 会把 "Fro**m Box** to Benchy" 当成 mBox（实测误收过）
MBOX_RX = re.compile(r"(?<![a-z])m\s*-?\s*box(?![a-z])|creality\s*park", re.I)


def get(url, timeout=25, accept_lang="en-US,en;q=0.9"):
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                              "Accept-Language": accept_lang})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
        return r.status, raw.decode("utf-8", "replace")


def uid_of(url, title):
    k = (url or "") + "|" + (title or "")[:200]
    return hashlib.sha1(k.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# 1. 官方论坛（双探 + 话题白名单）
# ---------------------------------------------------------------------------
# 2026-10-26：单探 search=mbox 恒为 0，无法区分「真无声量」与「关键词没覆盖」；
# 同时 `search=creality park` 会返回 50 条全是「extruder parking」的假阳性。
# 解法：多关键词探 + 话题标题白名单，命中才收。
FORUM_QUERIES = ["mbox", "m box", "creality park studio"]
FORUM_KEEP = re.compile(r"(?<![a-z])m\s*-?\s*box(?![a-z])|park\s*studio|creality\s*park\s*app",
                        re.I)


def probe_forum(probes):
    out = []
    for q in FORUM_QUERIES:
        url = "%s/search.json?q=%s" % (FORUM, urllib.parse.quote(q))
        try:
            st, h = get(url)
            j = json.loads(h)
        except Exception as e:
            probes.append({"source": "Creality 官方论坛 search=%s" % q, "url": url,
                           "status": "error", "err": str(e)[:120], "count": 0})
            continue
        topics = j.get("topics") or []
        posts = j.get("posts") or []
        kept = [t for t in topics if FORUM_KEEP.search(t.get("title") or "")]
        probes.append({"source": "Creality 官方论坛 search=%s" % q, "url": url,
                       "status": "empty" if not kept else "ok",
                       "count": len(kept),
                       "raw": len(topics) + len(posts)})
        for t in kept:
            tid, slug = t.get("id"), t.get("slug") or ""
            turl = "%s/t/%s/%s" % (FORUM, slug, tid)
            title = H.unescape(t.get("title") or "")
            out.append({
                "platform": "Creality 官方论坛", "site": "Creality 官方论坛",
                "channel": "官方论坛", "country": "US", "language": "EN",
                "date": (t.get("created_at") or "")[:10],
                "title": title,
                "originalText": title,
                "url": turl, "uid": uid_of(turl, title),
                "sourceType": "用户", "signal": "mid",
                "foundBy": "forum search=%s" % q,
            })
        time.sleep(0.6)
    return out


# ---------------------------------------------------------------------------
# 2. 官网探针
# ---------------------------------------------------------------------------
def probe_official(probes):
    """只做存在性探针：官网搜索页命中 mbox 是 Next.js 查询参数，不算产品页。"""
    hits = []
    for path, label in [("/products/creality-mbox", "产品页"),
                        ("/pages/creality-park", "Park 页"),
                        ("/products/mbox", "产品页 alt")]:
        url = "https://www.creality.com" + path
        try:
            st, h = get(url, timeout=20)
            ok = (st == 200 and len(h) > 5000)
            probes.append({"source": "官网" + label, "url": url,
                           "status": "ok" if ok else "absent", "count": 1 if ok else 0})
            if ok:
                title = re.search(r"<title>([^<]*)</title>", h)
                hits.append({
                    "platform": "Creality 官网", "site": "creality.com",
                    "channel": "厂商官方", "country": "US", "language": "EN",
                    "date": time.strftime("%Y-%m-%d"),
                    "title": H.unescape(title.group(1)) if title else "Creality mBox",
                    "originalText": "官网已上线 mBox 产品页。",
                    "url": url, "uid": uid_of(url, "mbox-official"),
                    "sourceType": "官方", "signal": "high",
                })
        except urllib.error.HTTPError as e:
            probes.append({"source": "官网" + label, "url": url,
                           "status": "absent" if e.code == 404 else "error",
                           "err": "HTTP %s" % e.code, "count": 0})
        except Exception as e:
            probes.append({"source": "官网" + label, "url": url,
                           "status": "error", "err": str(e)[:80], "count": 0})
    return hits


# ---------------------------------------------------------------------------
# 2b. B 站（2026-10-26 接入 — 用户反馈 B 站已有 mBox 测评却漏采）
# ---------------------------------------------------------------------------
BILI_KEYWORDS = ["创想三维 mBox", "Creality mBox", "mBox 3D打印机", "Creality Park"]
# 闸门：必须命中 mBox / Creality Park（带词边界），且命中 3D 打印语境。
# 「m box」词边界是硬要求 —— "From Box to Benchy" 曾被误收。
MBOX_MODEL_RX = r"m\s*-?\s*box|creality\s*park"


def collect_bili(probes):
    import _bili_search as B
    items, src, err = B.search(
        BILI_KEYWORDS,
        gate=lambda t, d: B.gate_model(t, d, MBOX_MODEL_RX, B.CTX_MBOX),
        days=180,
        exclude=lambda t, d: bool(B.NOISE_BOOST.search((t or "") + " " + (d or ""))),
        label="B站",
    )
    for s in src:
        probes.append({"source": "B站 %s" % (s.get("query") or s.get("step") or ""),
                       "url": "", "status": ("ok" if s.get("accepted") else "empty"),
                       "count": s.get("accepted", 0)})
    for e in err:
        probes.append({"source": "B站 %s" % e.get("query", ""), "url": "",
                       "status": "error", "err": e.get("err", "")[:90], "count": 0})
    for it in items:
        it["uid"] = uid_of(it["url"], it["title"])
    return items


# ---------------------------------------------------------------------------
# 2c. 知乎（P1：需登录态 Cookie；缺凭据时如实记 need-cookie，不伪造条目）
# ---------------------------------------------------------------------------
ZHIHU_COOKIE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_zhihu_cookie.txt")
ZHIHU_QUERIES = ["mBox 创想三维", "创想三维 mBox 评测", "Creality Park mBox"]


def _zhihu_cookie():
    try:
        with open(ZHIHU_COOKIE_FILE, encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def collect_zhihu(probes):
    """知乎搜索 API 需要 x-zse-96 签名，只带 Cookie 通常仍 403。

    因此本函数的口径是「有凭据就试、没凭据就明确报缺」——
    绝不返回编造条目，也不让缺失静默混进「零新增」。
    """
    cookie = _zhihu_cookie()
    if not cookie:
        probes.append({"source": "知乎", "url": "https://www.zhihu.com/search",
                       "status": "need-cookie", "count": 0,
                       "err": "缺 _zhihu_cookie.txt（需登录态 z_c0），已跳过"})
        return []
    out = []
    for q in ZHIHU_QUERIES:
        url = ("https://www.zhihu.com/api/v4/search_v3?t=general&q=%s"
               "&correction=1&offset=0&limit=20" % urllib.parse.quote(q))
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA, "Referer": "https://www.zhihu.com/search",
                "Cookie": cookie, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=25) as r:
                j = json.loads(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            probes.append({"source": "知乎 %s" % q, "url": url,
                           "status": "need-signature" if e.code == 403 else "error",
                           "err": "HTTP %s" % e.code, "count": 0})
            continue
        except Exception as e:
            probes.append({"source": "知乎 %s" % q, "url": url, "status": "error",
                           "err": str(e)[:90], "count": 0})
            continue
        got = 0
        for row in (j.get("data") or []):
            obj = row.get("object") or {}
            title = re.sub(r"<[^>]+>", "", obj.get("title") or "")
            if not title or not re.search(MBOX_MODEL_RX, title, re.I):
                continue
            zid = obj.get("id")
            if obj.get("type") == "article":
                zurl = "https://zhuanlan.zhihu.com/p/%s" % zid
            else:
                zurl = "https://www.zhihu.com/question/%s" % (
                    (obj.get("question") or {}).get("id") or zid)
            got += 1
            out.append({
                "platform": "知乎", "site": "知乎", "channel": "国内社区",
                "country": "CN", "language": "ZH",
                "date": time.strftime("%Y-%m-%d"),
                "title": title,
                "originalText": re.sub(r"<[^>]+>", "", obj.get("content") or title)[:600],
                "url": zurl, "uid": uid_of(zurl, title),
                "sourceType": "用户", "signal": "mid",
                "foundBy": "zhihu search_v3: %s" % q,
            })
        probes.append({"source": "知乎 %s" % q, "url": url,
                       "status": "ok" if got else "empty", "count": got})
        time.sleep(1.0)
    return out


# ---------------------------------------------------------------------------
# 2d. 抖音 / 小红书 探针（P2：SPA + 签名，本期只探不采）
# ---------------------------------------------------------------------------
def probe_domestic_spa(probes):
    probes.append({"source": "抖音",
                   "url": "https://www.douyin.com/search/mBox%203D%E6%89%93%E5%8D%B0%E6%9C%BA",
                   "status": "blocked", "count": 0,
                   "err": "返回 SPA 空壳，搜索列表需 a_bogus 签名，本期不接入"})
    probes.append({"source": "小红书",
                   "url": "https://www.xiaohongshu.com/search_result?keyword=mBox",
                   "status": "blocked", "count": 0,
                   "err": "SSR 页面需登录态 + x-s 签名，本期不接入"})
    return []


# ---------------------------------------------------------------------------
# 3. YouTube
# ---------------------------------------------------------------------------
def collect_youtube(probes):
    out, seen = [], set()
    for q in KEYWORDS:
        url = "https://www.youtube.com/results?search_query=%s" % urllib.parse.quote(q)
        try:
            st, h = get(url)
        except Exception as e:
            probes.append({"source": "YouTube 搜索 " + q, "url": url,
                           "status": "error", "err": str(e)[:80], "count": 0})
            continue
        # videoRenderer 里需要同时抓 id / title / 发布时间
        rx = re.compile(
            r'"videoRenderer":\{"videoId":"([\w-]{11})".*?'
            r'"title":\{"runs":\[\{"text":"(.*?)"\}\].*?'
            r'"publishedTimeText":\{"simpleText":"([^"]*)"', re.S)
        got = 0
        for vid, title, pub in rx.findall(h):
            if vid in seen:
                continue
            title = H.unescape(title).encode("utf-8").decode("unicode_escape", "ignore") \
                if "\\u" in title else H.unescape(title)
            if not MBOX_RX.search(title):
                continue
            seen.add(vid)
            got += 1
            vurl = "https://www.youtube.com/watch?v=" + vid
            meta = {}
            try:
                _, vh = get(vurl, timeout=25)
                for key, pat in [("upload", r'"uploadDate":"([^"]+)"'),
                                 ("channel", r'"ownerChannelName":"([^"]+)"'),
                                 ("views", r'"viewCount":"(\d+)"')]:
                    m = re.search(pat, vh)
                    meta[key] = m.group(1) if m else ""
            except Exception:
                pass
            date = (meta.get("upload") or "")[:10]
            if not date:
                m = re.search(r"(\d+)\s*(day|week|month|year)s?\s+ago", pub or "")
                date = "" if not m else "近%s%s" % (m.group(1), m.group(2))
            ch = meta.get("channel") or ""
            official = bool(re.search(r"creality", ch, re.I))
            out.append({
                "platform": "YouTube", "site": "YouTube",
                "channel": "厂商官方" if official else "海外视频",
                "country": "US", "language": "EN",
                "date": date,
                "title": title,
                "originalText": title,
                "url": vurl, "uid": uid_of(vurl, title),
                "sourceType": "官方" if official else "用户",
                "author": ch,
                "views": int(meta.get("views") or 0),
                "signal": "high" if official else "mid",
            })
        probes.append({"source": "YouTube 搜索 " + q, "url": url,
                       "status": "ok", "count": got})
        time.sleep(0.8)
    return out


# ---------------------------------------------------------------------------
# 4. Google Play 应用元数据
# ---------------------------------------------------------------------------
def collect_play(probes):
    meta_out = {}
    for pkg, label in [(PARK_PKG, "Creality Park"), (CLOUD_PKG, "Creality Cloud")]:
        url = "https://play.google.com/store/apps/details?id=%s&hl=en&gl=US" % pkg
        try:
            st, h = get(url)
        except Exception as e:
            probes.append({"source": "Google Play " + label, "url": url,
                           "status": "error", "err": str(e)[:80], "count": 0})
            continue
        og = re.search(r'<meta property="og:title" content="([^"]+)"', h)
        rating = re.search(r'"ratingValue":"?([\d.]+)"?', h)
        count = re.search(r'"ratingCount":"?(\d+)"?', h)
        ver = re.search(r'"versionName":"([^"]+)"', h)
        upd = re.search(r'"datePublished":"([^"]+)"', h)
        dl = re.search(r'>([\d.,]+[KMB]?\+)<', h)
        meta_out[pkg] = {
            "label": og.group(1).replace(" - Apps on Google Play", "") if og else label,
            "package": pkg,
            "rating": round(float(rating.group(1)), 2) if rating else None,
            "ratingCount": int(count.group(1)) if count else 0,
            "version": ver.group(1) if ver else "",
            "published": (upd.group(1) if upd else "")[:10],
            "downloads": dl.group(1) if dl else "",
            "url": url,
        }
        probes.append({"source": "Google Play " + label, "url": url,
                       "status": "ok", "count": 1})
        time.sleep(0.6)
    return meta_out


# ---------------------------------------------------------------------------
# 5. 已知媒体（3druck 反爬，记录为手工补录口）
# ---------------------------------------------------------------------------
KNOWN_MEDIA = [
    {
        "platform": "3druck", "site": "3druck.com", "channel": "海外媒体",
        "country": "DE", "language": "EN", "date": "2026-10-01",
        "title": "Creality mBox: Slicer Update Reveals Compact 3D Printer for Families",
        "originalText": ("Creality appears to be working on a small 3D printer for families. "
                         "Version 7.3.0.6141 of Creality Print shows a previously unknown device "
                         "called Creality mBox in the printer selection. The image shows a white, "
                         "cube-shaped enclosure with a solid front panel, a viewing window and a "
                         "handle; a small display sits in the upper right. Build volume 153 x 153 x 153. "
                         "No specs, price or release date are provided. The companion app Creality Park "
                         "was released on August 14, 2026 as v1.0.0 on Google Play (Android 7.0+, PEGI 3, 100+ downloads)."),
        "url": ("https://3druck.com/en/printers-and-products/"
                "creality-mbox-slicer-update-verraet-kompakten-3d-drucker-fuer-familien-42163402"),
        "sourceType": "媒体", "signal": "high",
    },
    {
        "platform": "3druck", "site": "3druck.com", "channel": "海外媒体",
        "country": "DE", "language": "DE", "date": "2026-10-01",
        "title": "Creality mBox: Slicer-Update verrät kompakten 3D-Drucker für Familien",
        "originalText": ("Hinweise darauf stecken in Version 7.3.0.6141 des hauseigenen Slicers Creality Print. "
                         "Dort erscheint in der Druckerauswahl ein bisher unbekanntes Gerät namens Creality mBox."),
        "url": "https://3druck.com/drucker-und-produkte/creality-mbox-slicer-update-verraet-kompakten-3d-drucker-fuer-familien-42163402",
        "sourceType": "媒体", "signal": "high", "mirrorOf": "3druck-EN",
    },
]


# ---------------------------------------------------------------- 外部信源（2026-10-27）
# 用户 2026-10-27：mBox 要接 Reddit 与 什么值得买。
#   Reddit —— 海外社区声量，mBox 是海外首发机型，主战场在英文社区；
#   什么值得买 —— 国内导购，提供的是**竞品价格带**（Bambu A1/P1S/X2D、纵维 Kobra X 的到手价），
#                 mBox 的定价锚点靠它，不是用户反馈，所以 countInVolume=False。
MBOX_REDDIT_SUBS = ["Creality", "3Dprinting"]
MBOX_REDDIT_CTX = re.compile(
    r"m\s*-?\s*box|creality\s*park|儿童\s*3d|kids?\s*3d\s*print|"
    r"家庭\s*3d\s*打印|亲子|入门\s*3d\s*打印|compact\s*3d\s*print",
    re.I)


def collect_reddit(probes):
    import _reddit_search as RD
    try:
        its, src, err = RD.search(
            MBOX_REDDIT_SUBS,
            gate=lambda t, b: RD.gate_any(t, b, MBOX_REDDIT_CTX),
            days=180, label="Reddit",
        )
    except Exception as e:
        probes.append({"source": "Reddit", "status": "error", "count": 0,
                       "note": type(e).__name__})
        return []
    got = 0
    for it in its:
        it["productLine"] = "mbox"
        it["model"] = "mBox"
        it["grade"] = it.get("grade") or ""
        got += 1
    for s in src:
        probes.append({"source": s["source"], "status": s["status"],
                       "count": s.get("count", 0)})
    return its


def collect_smzdm(probes):
    import _smzdm_search as SM
    try:
        its, src, err = SM.search(gate=None)
    except Exception as e:
        probes.append({"source": "什么值得买", "status": "error", "count": 0,
                       "note": type(e).__name__})
        return []
    for it in its:
        # 好价条目不是用户反馈：与 GitHub 缺陷单同理，单列不计声量
        it["countInVolume"] = False
        it["productLine"] = ""
        it["model"] = "未标注"
        it["grade"] = ""
    for s in src:
        probes.append({"source": s["source"], "status": s["status"],
                       "count": s.get("count", 0)})
    return its


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-yt", action="store_true")
    ap.add_argument("--no-bili", action="store_true")
    ap.add_argument("--no-reddit", action="store_true", help="跳过 Reddit（调试用）")
    ap.add_argument("--no-smzdm", action="store_true", help="跳过 什么值得买（调试用）")
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args()

    probes, items = [], []

    print("[1/10] 官方论坛（双探 + 白名单）...")
    items += probe_forum(probes)

    print("[2/10] 官网探针 ...")
    items += probe_official(probes)

    print("[3/10] B站 ...")
    if not args.no_bili:
        items += collect_bili(probes)

    print("[4/10] YouTube ...")
    if not args.no_yt:
        items += collect_youtube(probes)

    print("[5/10] Google Play 元数据 ...")
    apps = collect_play(probes)

    print("[6/10] 知乎 ...")
    items += collect_zhihu(probes)

    print("[7/10] 抖音 / 小红书探针 ...")
    items += probe_domestic_spa(probes)

    print("[8/10] Reddit ...")
    if not args.no_reddit:
        items += collect_reddit(probes)

    print("[9/10] 什么值得买（竞品价格带）...")
    if not args.no_smzdm:
        items += collect_smzdm(probes)

    print("[10/10] 已知媒体（反爬源补录）...")
    for m in KNOWN_MEDIA:
        m = dict(m)
        m["uid"] = uid_of(m["url"], m["title"])
        items.append(m)

    # uid 唯一
    seen = {}
    for it in items:
        u = it["uid"]
        if u in seen:
            seen[u] += 1
            it["uid"] = u[:12] + "%04x" % seen[u]
        else:
            seen[u] = 1
    items.sort(key=lambda x: (x.get("date") or ""), reverse=True)

    payload = {
        "updatedAt": time.strftime("%Y-%m-%d %H:%M"),
        "fetchedAt": time.strftime("%Y-%m-%d %H:%M"),
        "launchMode": "pre",
        "items": items,
        "apps": apps,
        "probes": probes,
        "stats": {
            "total": len(items),
            "sourcesOk": sum(1 for p in probes if p.get("status") == "ok"),
            "sourcesEmpty": sum(1 for p in probes if p.get("status") == "empty"),
            "sourcesFail": sum(1 for p in probes
                               if p.get("status") in ("error", "blocked", "need-cookie",
                                                      "need-signature", "absent")),
        },
    }
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)

    print("\n=== 结果 ===")
    print("条目 %d" % len(items))
    for it in items:
        print("  [%s] %-9s %s" % (it.get("date") or "-", it.get("channel"), it["title"][:64]))
    print("\n探针状态:")
    for p in probes:
        print("  %-34s %-8s %s" % (p["source"][:34], p["status"], p.get("count", "")))
    print("\nApp 元数据:")
    for k, v in apps.items():
        print("  %-30s rating=%s count=%s dl=%s" % (v["label"][:30], v["rating"],
                                                    v["ratingCount"], v["downloads"]))
    print("-> %s" % args.out)


if __name__ == "__main__":
    main()
