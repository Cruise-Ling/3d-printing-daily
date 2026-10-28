#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全彩专栏 · L3 通道：Reddit 社区（RSS 节流通道）

为什么是 RSS 而不是 API
-----------------------
2026-10-27 实测（本机出口）：

    *.json 端点        连不上（connect timeout，路径被丢包）
    oauth.reddit.com   403 blocked（未认证一律拦）
    api/v1/access_token 30s 超时 —— 拿不到 token，OAuth 走不通
    *.rss 端点         200 可用，但限流约「每分钟 1 次」，连打即 429

所以：**RSS 是唯一可用通道，代价是必须节流**。响应头 `x-ratelimit-reset`
给的是窗口剩余秒数，脚本按它精确等待，而不是固定 sleep —— 固定值要么慢
要么撞 429。

热度口径（RSS 不含 score / numComments，必须诚实处理）
------------------------------------------------------
Reddit 的 `sort=top` 就是「按赞数排序」，所以**请求位次本身就是热度序**：
命中 top 排序第 1 位 vs 第 20 位，含义差别巨大。因此：

    heatSource = reddit-top-rank   rank ≤5 → high，≤12 → mid，其余 low
    heatSource = reddit-comments   少数 entry 的正文模板带「N comments」，抓得到就用它

绝不用正文长度假装热度（那是外媒通道的降级手段，用在社区上会失真：
一条长自述帖可能 0 回复）。

产出 _fc_rd_candidates.json，由 _col_collect_fc.py 末尾合并进候选池。
"""
import datetime
import html as html_mod
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "_fc_rd_candidates.json")

# 样板正文剥离与软件专栏同源，避免两条链各写一套正则
from _reddit_search import strip_boiler  # noqa: E402

TODAY = datetime.date.today()
UA = "python:creality-fc-research:v1.0 (by /u/creality_data)"

# 最小请求间隔（秒）。Reddit 匿名 RSS 约 1 req/min，取 11s 留余量；
# 万一撞 429 再按 x-ratelimit-reset 补偿等待。
MIN_GAP = 11.0
_last = [0.0]

# (subreddit, 检索词, 排序, 用途)
# 排序 top 的项：借 Reddit 自己的赞数排序当热度序，位次即热度
# 排序 relevance 的项：机型名精确检索，避免被 "full color" 泛词灌水
TARGETS = [
    ("3Dprinting",           "full color",              "top",       "主版 · 品类热帖"),
    ("3Dprinting",           "HeyGears",                "relevance", "主版 · 机型精确（首版用 HeyGears G1X 双词 AND，返回 0 条，改用单词）"),
    ("resinprinting",        "full color",              "top",       "树脂版 · 技术同源人群"),
    ("FDMminiatures",        "full color",              "top",       "微缩模型 · 全彩与手涂之争"),
    ("FlashForge",           "CJ270",                   "relevance", "品牌版 · CJ270 首发"),
    ("3dprinter",            "full color",              "top",       "综合版"),
    ("BambuLab",             "multicolor",              "top",       "多色 FDM · 护栏 B 替代方案"),
    ("AdditiveManufacturing","full color",              "top",       "工业版 · 对标层"),
    ("3DDruck",              "Vollfarbe",               "top",       "德语版 · 欧洲价格锚"),
    ("3Dprinting",           "full color vs painting",  "relevance", "决策讨论 · 买机 vs 代打/手涂"),
    ("3Dprinting",           "material jetting",        "relevance", "主版 · 技术路线讨论"),
    ("3Dprinting",           "Sailner",                 "relevance", "赛纳 · 品牌精确（2026-10-28 接入）"),
]

MODELS = [
    ("Sailner", ["sailner", "seine 3d", "赛纳三维", "wjp"]),
    ("G1X", ["g1x", "g1 x", "heygears g1", r"\bg1\b", "黑格 g1"]),
    ("CJ270", ["cj270", "cj 270", "mj270"]),
    ("QC2A", ["qc2a", "qc-2a", "qc 2a", "inew3d", "simba3d"]),
    ("J850/J55", ["stratasys", "j850", "j55", "polyjet"]),
    ("3DUJ", ["mimaki", "3duj"]),
]
# 三档：赛纳 D450 桌面形态 + $70k 工业价位，单列「专业」（2026-10-28）
TIER = {"J850/J55": "工业", "3DUJ": "工业", "Sailner": "专业"}
INDUSTRIAL = {"J850/J55", "3DUJ"}

CTX_FC = ("full color", "full-color", "full-colour", "fullcolour", "full colored",
          "full coloured", "multicolor resin", "multi-color resin", "material jetting",
          "polyjet", "mjp", "uv print", "color 3d print", "colour 3d print",
          "multi color", "multi-color", "multicolor", "multicolour", "彩色", "全彩", "vollfarbe",
          "wjp", "voxel")

# 护栏 B：多色 FDM 是同属用户决策的「替代方案」，但不是一条技术路线。
# Reddit 上这条线声量极大（r/FDMminiatures / r/BambuLab），不打标会直接
# 把「对多色 FDM 的满意」算成全彩的满意 —— 结论会反。
FDM_HINT = re.compile(
    r"\b(filaments?|spools?|tool\s?changers?|ams\b|bambu\s*lab|bambu|snapmaker|"
    r"prusa|ender|voron|x1c|p1s|p1p|a1\s*mini|h2d|h2c|fdg|fdm|"
    r"multicolou?r\s+fdm|multi-color\s+fdm|colour\s+mixing|color\s+mixing|"
    r"snapmaker\s+u1|idex)\b", re.I)
MJP_MODEL = re.compile(
    r"g1x|cj270|mj270|qc2a|stratasys|j850|j55|j8\d\d|mimaki|3duj|polyjet|material\s+jetting"
    r"|sailner|赛纳|wjp", re.I)

# 厂商自有账号：makers101 那篇拆解里提到「七个最热帖里四个来自厂商和单一博主」。
# 不标出来，官方口径会被当成用户声量。
OFFICIAL_USER = re.compile(
    r"^(heygears|flashforge|inew3d|simba3d|stratasys|mimaki|sailner)(_|$|\d)", re.I)

# 卖货/招租/纯展示等非讨论帖：留着会污染情感结构
NOISE = re.compile(
    r"\b(for sale|selling|giveaway|promo|coupon|discount code|hiring|job|"
    r"commission|etsy|store|shop link|affiliate|self.?promo)\b", re.I)

RE_ENTRY = re.compile(r"<entry>([\s\S]*?)</entry>", re.I)
RE_TAG = re.compile(r"<[^>]+>")


def decode(s):
    """RSS 里的 content 是二次转义 HTML（&lt;p&gt;），先 unescape 再剥标签。"""
    s = html_mod.unescape(html_mod.unescape(s or ""))
    s = re.sub(r"<!--[\s\S]*?-->", " ", s)
    s = re.sub(r"<(br|/p|/div|/tr)[^>]*>", "\n", s, flags=re.I)
    s = RE_TAG.sub(" ", s)
    s = html_mod.unescape(s)
    s = re.sub(r"[ \t\u00a0]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def field(entry, name):
    m = re.search(r"<%s[^>]*>([\s\S]*?)</%s>" % (name, name), entry, re.I)
    if not m:
        m = re.search(r"<%s[^>]+href=\"([^\"]+)\"" % name, entry, re.I)
        return html_mod.unescape(m.group(1)) if m else ""
    return html_mod.unescape(m.group(1)).strip()


def fetch(url):
    """节流 + 429 自适应重试。返回 (body, err)。"""
    gap = MIN_GAP - (time.time() - _last[0])
    if gap > 0:
        time.sleep(gap)
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Accept": "application/rss+xml,application/xml;q=0.9,*/*;q=0.8",
            })
            with urllib.request.urlopen(req, timeout=25) as r:
                body = r.read().decode("utf-8", "ignore")
                _last[0] = time.time()
                return body, ""
        except urllib.error.HTTPError as e:
            _last[0] = time.time()
            rst = e.headers.get("x-ratelimit-reset") or ""
            if e.code == 429 and attempt < 2:
                wait = float(rst) if rst.replace(".", "").isdigit() else 30.0
                time.sleep(min(wait + 2, 90))
                continue
            return "", "HTTP %d" % e.code
        except Exception as e:
            _last[0] = time.time()
            if attempt < 2:
                time.sleep(12)
                continue
            return "", "%s %s" % (type(e).__name__, str(e)[:40])
    return "", "retry-exhausted"


def model_of(title, body=""):
    """机型识别，**标题优先**。

    只按表顺序扫全篇会出错：德语那条标题明明写的是 CJ270，
    正文顺带一句「HeyGears G1X」就把机型抢走，S3 机型卡数字跟着错。
    键值支持正则（以 \\b 开头的直接当正则用），中文键走子串匹配。
    """
    for src in (title, body):
        t = (src or "").lower()
        if not t:
            continue
        for name, keys in MODELS:
            for k in keys:
                if k.startswith("\\b"):
                    hit = re.search(k, t)
                elif re.search(r"[\u4e00-\u9fff]", k):
                    hit = k in t
                else:
                    hit = re.search(r"\b" + re.escape(k), t)
                if hit:
                    return name, TIER.get(name, "桌面")
    return "", ""


def has_ctx(text):
    t = (text or "").lower()
    return any(c in t for c in CTX_FC)


def collect(sources, errors):
    seen = {}
    for sub, q, sort, why in TARGETS:
        url = ("https://www.reddit.com/r/%s/search.rss?q=%s&restrict_sr=1"
               "&sort=%s&t=year&limit=25" % (sub, urllib.parse.quote_plus(q), sort))
        body, err = fetch(url)
        if err:
            sources.append({"channel": "Reddit", "query": "r/%s · %s" % (sub, q),
                            "code": 429 if "429" in err else 0, "status": "err",
                            "accepted": 0, "note": err + " · " + why})
            errors.append({"site": "Reddit", "query": "r/%s %s" % (sub, q), "err": err})
            continue

        entries = RE_ENTRY.findall(body)
        got = 0
        for rank, e in enumerate(entries, 1):
            rid = field(e, "id")
            if not rid:
                continue
            key = rid
            # 同帖在多个目标里出现：保留位次更好的那次（热度更高）
            if key in seen and seen[key]["topRank"] <= rank:
                continue
            link = ""
            m = re.search(r'<link[^>]+href="([^"]+)"', e, re.I)
            if m:
                link = html_mod.unescape(m.group(1))
            title = decode(field(e, "title"))
            content_raw = field(e, "content")
            body_txt = decode(content_raw)
            # 少数 entry 的模板带 "N comments"，抓到就用真值
            cm = re.search(r"(\d+)\s*comments?", content_raw + " " + body_txt, re.I)
            ncom = int(cm.group(1)) if cm else 0
            pub = (field(e, "published") or "")[:10]
            author = re.sub(r"^/u/", "", field(e, "name"))

            seen[key] = {
                "id": rid, "sub": sub, "q": q, "sort": sort,
                "topRank": rank if sort == "top" else 99,
                "title": title, "body": body_txt, "url": link,
                "date": pub, "author": author, "comments": ncom,
            }
            got += 1

        sources.append({"channel": "Reddit", "query": "r/%s · %s" % (sub, q),
                        "code": 200, "status": "ok", "accepted": got,
                        "note": sort + " · " + why})

    # ---- 过滤与成型 ----
    out = []
    shell = 0
    for r in seen.values():
        # 纯图帖的正文只剩模板尾巴 "submitted by /u/x [link] [comments]"，
        # 不清掉的话它会同时污染摘要展示和正文长度判定。
        # 2026-10-28：改用 _reddit_search.strip_boiler 统一剥离（与软件专栏同源），
        # 剥完为空即整条丢弃 —— 卡片只剩标题 + 外链，没有讨论内容可读。
        body = strip_boiler(r["body"])
        body = re.sub(r"\s+", " ", body).strip()
        if not body:
            shell += 1
            continue
        head = r["title"] + " " + body[:200]
        model, tier = model_of(r["title"], body)

        # 收紧上下文判定：只看「标题 + 正文前 200 字」。
        # 首版拿整篇 4000 字去匹配，结果 Blender 插件帖、树脂钥匙扣帖
        # 都因为正文顺带提了 color 被收进来 —— 精度比召回重要，这里要的是热帖不是全量。
        if not has_ctx(r["title"]) and not model and not has_ctx(body[:200]):
            continue
        if NOISE.search(r["title"]) or len(r["title"]) < 12:
            continue
        if len(body) < 40 and not model:
            continue

        # 护栏 B：多色 FDM 走独立技术路线，不进全彩情感分母
        tech = "WJP 体素喷墨" if model == "Sailner" else "MJP 喷墨"
        if not MJP_MODEL.search(head) and FDM_HINT.search(head):
            tech, tier = "FDM-multicolor", "对照"

        official = bool(OFFICIAL_USER.search(r["author"]))

        if r["comments"]:
            lvl = "high" if r["comments"] >= 40 else ("mid" if r["comments"] >= 12 else "low")
            hsrc, score = "reddit-comments", r["comments"] * 100
            heat = "评论 %d · r/%s" % (r["comments"], r["sub"])
        elif r["topRank"] < 99:
            lvl = "high" if r["topRank"] <= 5 else ("mid" if r["topRank"] <= 12 else "low")
            hsrc = "reddit-top-rank"
            score = max(0, 3000 - r["topRank"] * 100) + min(len(body), 1200) // 4
            heat = "r/%s top#%d" % (r["sub"], r["topRank"])
        else:
            lvl, hsrc = "low", "reddit-relevance"
            score = 400 + min(len(body), 1200) // 4
            heat = "r/%s 精确命中" % r["sub"]

        lang = "DE" if r["sub"] == "3DDruck" else "EN"
        if re.search(r"[\u4e00-\u9fff]", r["title"]):
            lang = "ZH"

        out.append({
            "platform": "Reddit",
            "site": "reddit",
            "channel": "海外",
            "country": "US",
            "language": lang,
            "date": r["date"], "publishedAt": r["date"], "dateGuessed": False,
            "title": r["title"], "titleCn": "",
            "originalText": body[:3000],
            "url": r["url"], "sourceLink": r["url"],
            "author": "u/" + r["author"],
            "sourceType": "官方" if official else "社区",
            "model": model, "tier": tier, "techRoute": tech,
            "heatRaw": {"topRank": r["topRank"], "comments": r["comments"],
                        "subreddit": "r/" + r["sub"]},
            "heatScore": score,
            "discussLevel": lvl,
            "heatSource": hsrc,
            "heat": heat,
            "countInVolume": True,
            "collectMethod": "reddit-rss",
            "foundBy": "reddit-rss:%s" % r["sort"],
            "subreddit": "r/" + r["sub"],
        })
    out.sort(key=lambda x: -x["heatScore"])
    return out


def main():
    sources, errors = [], []
    items = collect(sources, errors)
    ok = [s for s in sources if s.get("status") == "ok"]
    lv = {}
    for it in items:
        lv[it["discussLevel"]] = lv.get(it["discussLevel"], 0) + 1
    payload = {
        "kind": "fc", "channel": "Reddit", "generatedAt": TODAY.isoformat(),
        "items": items, "probes": sources, "errors": errors[:20],
        "stats": {
            "sourcesTotal": len(sources), "sourcesOk": len(ok),
            "sourcesError": len(sources) - len(ok),
            "items": len(items), "byLevel": lv,
            "subreddits": sorted({it["subreddit"] for it in items}),
            "models": sorted({it["model"] for it in items if it["model"]}),
        },
    }
    with io.open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print("Reddit：%d 条（high %d / mid %d / low %d）→ %s" % (
        len(items), lv.get("high", 0), lv.get("mid", 0), lv.get("low", 0),
        os.path.basename(OUT)))
    if shell:
        print("  丢弃无正文纯图/纯链接帖：%d 条（只有 RSS 模板尾巴，无讨论内容）" % shell)
    for s in sources:
        print("  %s %-28s %s %s" % ("✓" if s.get("status") == "ok" else "×",
                                    s.get("query"), s.get("accepted"), s.get("note") or ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
