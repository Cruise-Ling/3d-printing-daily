#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全彩专栏 · L3 通道：YouTube 社区（YouTube Data API v3）

为什么单独一个脚本
------------------
B站/值得买/官网走 HTML 抓取（_col_collect_fc.py），YouTube 必须走官方 API ——
网页端被 Google 的反爬拦，且网页端拿不到 commentCount。API 三个端点分工：

    search.list         发现 videoId（100 units/次，配额大头）
    videos.list         拿 viewCount / likeCount / commentCount（1 unit/次）
    commentThreads.list 拿高赞评论正文（1 unit/次）—— 评论才是「用户讨论」

配额账（免费额度 10000 units/天，按下面的跑法约 1300，安全）
    12 关键词 × search.list 100        = 1200
    1  次批量 videos.list（50 id/次）   ≈   2
    ≤40 个视频 × commentThreads 1      ≤  40

热度口径 —— **以评论为主、播放只做次级权重**（这一条踩过坑，见下）
    首版按播放定级，结果 Flashforge 官方投放片以 409 万播放占了 high，
    实际只有 352 赞、30 条评论、0 讨论。用户要的是「讨论度高的帖子」，
    播放量是曝光不是讨论。改为：
        high : 评论 ≥ 100，或 评论 ≥ 30 且 赞 ≥ 300
        mid  : 评论 ≥ 20， 或 评论 ≥ 8  且 赞 ≥ 100
        low  : 其余
    heatScore = 评论×150 + 赞×3 + 播放÷300
        播放权重压到极小，但仍保留 —— 头部视频的曝光本身是信号，
        只是不能让它盖过「有多少人真的在讨论」。

产出 _fc_yt_candidates.json，由 _col_collect_fc.py 在末尾合并进候选池，
不单独进归一化 —— 保证「一个数据契约、一个入口」。
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
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CREDS = os.path.join(HERE, "_k3_creds.json")
OUT = os.path.join(HERE, "_fc_yt_candidates.json")
API = "https://www.googleapis.com/youtube/v3/"

TODAY = datetime.date.today()
# 用户决策：首次建池回溯到 2026-01-01（三台机正好都在这一年发布/众筹）
WINDOW_START = "2026-01-01T00:00:00Z"

# 机型识别与 B 站/种子通道共用同一张表（口径漂移会让 S3 卡数字打架）
MODELS = [
    ("Sailner", ["sailner", "seine 3d", "赛纳", "赛纳三维", "wjp"]),
    ("G1X", ["g1x", "g1 x", "heygears g1", r"\bg1\b", "黑格 g1"]),
    ("CJ270", ["cj270", "cj 270", "mj270"]),
    ("QC2A", ["qc2a", "qc-2a", "qc 2a", "inew3d", "simba3d"]),
    ("J850/J55", ["stratasys", "j850", "j55", "polyjet"]),
    ("3DUJ", ["mimaki", "3duj", "3d uj"]),
]
# 三档，不是两档：赛纳 D450 是桌面形态但 $70k 工业价位（2026-10-28 用户决策）
TIER = {"J850/J55": "工业", "3DUJ": "工业", "Sailner": "专业"}
INDUSTRIAL = {"J850/J55", "3DUJ"}

# 全彩上下文：标题/描述必须命中其一，否则是普通 3D 打印视频（会灌偏情感结构）
CTX_FC = ("full color", "full-colour", "full colour", "fullcolor", "multicolor resin",
          "multi-color resin", "material jetting", "polyjet", "mjp", "uv print",
          "color 3d print", "colour 3d print", "彩色", "全彩", "wjp", "voxel", "体素")

NOISE = re.compile(r"\b(shorts?|asmr|unboxing only|giveaway|promo code|coupon)\b", re.I)

# 官方账号：实测里 inew3d 5 条、PR Mimaki 4 条、FLASHFORGE 2 条、HeyGears 2 条都在池里。
# 不标出来的后果很直接 —— 官方宣传片的播放量会把「用户讨论」的排序顶掉，
# 情感结构也会被厂商口径污染。标 sourceType=官方 后由生成的护栏排除在情感分母外。
OFFICIAL_CH = re.compile(
    r"heygears|flashforge|inew3d|iNEW3D|stratasys|mimaki|pr\s*mimaki|sailner|赛纳三维|"
    r"黑格|闪铸|官方|official", re.I)

# 护栏 B：多色 FDM 是「替代方案」，同属用户真实决策，但不是同一条技术路线。
# 必须单独打标，否则「对多色+手涂的满意」会被算成全彩的满意，结论直接反。
# 注意复数：首版写 \bfilament\b 漏掉了 "4 Filaments, ALL The Colors" 这条，
# 它带着 706 条评论混进全彩 high 档 —— 词边界写窄了就是这种后果。
FDM_HINT = re.compile(
    r"\b(filaments?|spools?|tool\s?changers?|ams\b|bambu\s*lab|bambu|snapmaker|"
    r"prusa|ender|voron|x1c|p1s|p1p|a1\s*mini|h2d|h2c|fdg|fdm|fdm3d|fdm\s*3d|"
    r"multicolou?r\s+fdm|multi-color\s+fdm|colour\s+mixing|"
    r"color\s+mixing|snapmaker\s+u1|idex|phrozen|arco)\b", re.I)
MJP_MODEL = re.compile(r"g1x|cj270|mj270|qc2a|stratasys|j850|j55|mimaki|3duj|polyjet|"
                       r"material\s+jetting|sailner|赛纳|wjp", re.I)

# 只做 2D 平面的 UV 平板机：相邻品类，不是本专栏的机型
UV_FLAT = re.compile(r"eufymake|x\s?tool\s*o1|uv\s+printer|uv\s+flatbed|flatbed\s+uv", re.I)

LANG_MAP = {"en": "EN", "zh": "ZH", "ja": "JA", "ko": "KO", "de": "DE",
            "es": "ES", "fr": "FR", "pt": "PT", "ru": "RU", "tr": "TR",
            "it": "IT", "pl": "PL"}


def lang_of(title, desc, api_lang):
    """语种：API 的 defaultAudioLanguage 最准，但它经常缺（实测西/土/俄三条都缺）。

    缺时按字符集 + 高频功能词兜底 —— 标错语种会直接导致「未翻译」的条目
    混进中文界面，比多花一点判定成本更难看。
    """
    l = (api_lang or "").split("-")[0].lower()
    if l and l != "en" and l in LANG_MAP:
        return LANG_MAP[l]
    t = (title or "") + " " + (desc or "")[:400]
    if re.search(r"[\u0400-\u04FF]", t):
        return "RU"
    if re.search(r"[\u3040-\u30FF]", t):
        return "JA"
    if re.search(r"[\uAC00-\uD7AF]", t):
        return "KO"
    if re.search(r"[\u4e00-\u9fff]", t):
        return "ZH"
    if re.search(r"[ığşİĞŞ]", t):
        return "TR"
    if re.search(r"[äöüß]", t):
        return "DE"
    if re.search(r"[ñ¿¡]", t):
        return "ES"
    if re.search(r"\b(conoce|impresi[oó]n|todo color|nuevo|para|con la|de la|m[aá]s)\b", t, re.I):
        return "ES"
    if re.search(r"\b(renk|yaz[ıi]c[ıi]|yeni|için|nas[ıi]l)\b", t, re.I):
        return "TR"
    if re.search(r"\b(für|und|mit|ist|neue|nicht|ohne)\b", t, re.I):
        return "DE"
    return "EN"

# (检索词, 排序方式, 该词的主要目的)
KEYWORDS = [
    ("HeyGears G1X review",              "relevance", "机型主战场（英文长测评）"),
    ("HeyGears G1X full color printing", "viewCount", "机型头部热帖"),
    ("Flashforge CJ270 review",          "relevance", "机型 · 刚开箱"),
    ("Flashforge CJ270 full color",      "viewCount", "机型头部热帖"),
    ("iNEW3D QC2A",                      "relevance", "机型 · 众筹期"),
    ("full color 3D printer review",     "viewCount", "品类头部样本"),
    ("full color 3D printing material jetting", "relevance", "技术路线讨论"),
    ("Stratasys J850 full color",        "relevance", "工业对标"),
    ("Mimaki 3DUJ full color",           "relevance", "工业对标"),
    ("Sailner full color 3D printer",    "relevance", "赛纳 · WJP 路线（2026-10-28 接入）"),
    ("Sailner D450 full color",          "relevance", "赛纳 · 桌面机型实测"),
    ("full color 3D print vs painting",  "relevance", "替代方案（护栏 B 议题）"),
    ("multicolor FDM vs full color resin", "relevance", "替代方案（护栏 B 议题）"),
    ("HeyGears G1X problems ink printhead", "relevance", "负面/故障（喷头与耗材）"),
]

MAX_PER_KW = 10
DUR_MIN = 45          # 秒；低于此基本是 Shorts，信息量与评论结构都不适合做样本
COMMENTS_PER_VIDEO = 8


def load_key():
    if not os.path.exists(CREDS):
        return ""
    try:
        d = json.load(io.open(CREDS, encoding="utf-8"))
        return ((d.get("youtube") or {}).get("apiKey") or "").strip()
    except Exception:
        return ""


KEY = load_key()


def api(path, params, timeout=25, retries=2):
    """调 API，返回 (data, err)。err 是短字符串，便于写进 probes。

    配额超限是 403 + reason=quotaExceeded，要和普通 403（key 失效）分开报，
    否则排查时会误以为是凭据问题。
    """
    q = dict(params)
    q["key"] = KEY
    url = API + path + "?" + urllib.parse.urlencode(q)
    last = ""
    for i in range(retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", "ignore")), ""
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", "ignore")
            except Exception:
                pass
            reason = ""
            m = re.search(r'"reason"\s*:\s*"([^"]+)"', body or "")
            if m:
                reason = m.group(1)
            if e.code == 403 and reason == "quotaExceeded":
                return None, "quotaExceeded"
            # 429 rateLimitExceeded 是「短时速率限制」，和 403 quotaExceeded（日配额耗尽）
            # 完全是两回事：前者退避几秒就好，后者当天无解。首次没区分，
            # 连续跑批时 4 个关键词被直接判失败，白丢样本。
            if e.code == 429 and i < retries:
                time.sleep(9 * (i + 1))
                last = "HTTP 429 rateLimit"
                continue
            if e.code in (500, 503) and i < retries:
                time.sleep(3 * (i + 1))
                last = "HTTP %d" % e.code
                continue
            return None, "HTTP %d %s" % (e.code, reason or body[:60])
        except Exception as e:
            last = "%s %s" % (type(e).__name__, str(e)[:50])
            if i < retries:
                time.sleep(3 * (i + 1))
                continue
    return None, last


def iso_seconds(s):
    """PT46M41S -> 2801"""
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", s or "")
    if not m:
        return 0
    h, mi, se = (int(x) if x else 0 for x in m.groups())
    return h * 3600 + mi * 60 + se


def model_of(title, body=""):
    """机型识别，标题优先（与 Reddit 通道同一口径）。

    键值支持正则（\\b 开头的直接当正则），中文键走子串匹配。
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


def level_of(views, comments, likes):
    """讨论度以评论为主。播放只作次级信号 —— 官方投放片的教训。"""
    if comments >= 100 or (comments >= 30 and likes >= 300):
        return "high"
    if comments >= 20 or (comments >= 8 and likes >= 100):
        return "mid"
    return "low"


def score_of(views, comments, likes):
    return comments * 150 + likes * 3 + views // 300


def collect(sources, errors):
    """三端点串起来，返回候选条目列表。任何一步失败都记 probe 后继续。"""
    seen = {}          # vid -> search snippet
    for kw, order, why in KEYWORDS:
        if not KEY:
            break
        d, err = api("search", {
            "part": "snippet", "q": kw, "type": "video",
            "maxResults": MAX_PER_KW, "order": order,
            "publishedAfter": WINDOW_START, "relevanceLanguage": "en",
        })
        if err:
            sources.append({"channel": "YouTube", "query": kw, "code": 0,
                            "status": "err", "accepted": 0, "note": err + " · " + why})
            errors.append({"site": "YouTube", "query": kw, "err": err})
            if err == "quotaExceeded":
                break
            continue
        got = 0
        for it in (d.get("items") or []):
            vid = ((it.get("id") or {}).get("videoId") or "")
            if not vid or vid in seen:
                continue
            seen[vid] = it.get("snippet") or {}
            got += 1
        sources.append({"channel": "YouTube", "query": kw, "code": 200,
                        "status": "ok", "accepted": got, "note": order + " · " + why})
        # 关键词之间留够间隔：search.list 是重接口，0.4s 连发会触发 429 rateLimitExceeded
        time.sleep(2.0)

    if not seen:
        return []

    # 批量取统计（videos.list 一次最多 50 个 id）
    ids = list(seen.keys())
    stats, details = {}, {}
    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        d, err = api("videos", {"part": "statistics,contentDetails,snippet",
                                "id": ",".join(chunk)})
        if err:
            errors.append({"site": "YouTube", "query": "videos.list", "err": err})
            break
        for it in (d.get("items") or []):
            stats[it["id"]] = it.get("statistics") or {}
            details[it["id"]] = it.get("contentDetails") or {}

    out = []
    for vid in ids:
        s = seen.get(vid) or {}
        st = stats.get(vid) or {}
        if not st:
            continue                       # 已下架/私享，videos.list 不返回
        title = html_mod.unescape(s.get("title") or "").strip()
        desc = html_mod.unescape(s.get("description") or "").strip()
        channel = html_mod.unescape(s.get("channelTitle") or "").strip()
        pub = (s.get("publishedAt") or "")[:10]
        dur = iso_seconds((details.get(vid) or {}).get("duration"))
        views = int(st.get("viewCount") or 0)
        likes = int(st.get("likeCount") or 0)
        comments = int(st.get("commentCount") or 0)

        blob = title + " " + desc
        model, tier = model_of(title, desc + " " + channel)
        # 机型没命中时，全彩上下文也能收；两者都不中就是无关视频，直接丢
        if not model and not has_ctx(blob):
            continue
        if not has_ctx(blob) and model in ("G1X", "CJ270", "QC2A", "Sailner"):
            pass                           # 机型明确命中，即使没写 full color 也收
        elif not has_ctx(blob):
            continue
        if dur and dur < DUR_MIN:
            continue
        if NOISE.search(title):
            continue
        # 边界：纯 UV 平板机（eufyMake E1 / xTool O1 这类）只做 2D 平面，
        # 不做逐层成型，不属于「全彩 3D 打印机」。但 G1X 本身带 UV 模式，
        # 所以「四方对比」这种同时点到 G1X 的视频要留 —— 那正是用户的真实对比。
        if UV_FLAT.search(blob) and not MJP_MODEL.search(blob):
            continue

        # 护栏 B：多色 FDM 打独立 techRoute，生成器据此把它排除在全彩情感分母外
        # 赛纳走 WJP（自研体素级多材料喷墨），不能一律写 MJP —— 那是另一条路线
        tech = "WJP 体素喷墨" if model == "Sailner" else "MJP 喷墨"
        if not MJP_MODEL.search(blob) and FDM_HINT.search(blob):
            tech, tier = "FDM-multicolor", "对照"
        elif FDM_HINT.search(title) and not MJP_MODEL.search(title):
            tech, tier = "FDM-multicolor", "对照"

        # 官方账号 vs 用户/KOL：官方口径不能进情感分母
        official = bool(OFFICIAL_CH.search(channel))
        if official:
            stype = "官方"
        elif views >= 5000:
            stype = "KOL"
        else:
            stype = "用户"

        lang = lang_of(title, desc, s.get("defaultAudioLanguage") or s.get("defaultLanguage"))

        # 高赞评论：这是本条样本里「用户讨论」的主体，比视频描述有价值得多
        ctexts, cerr = comments_of(vid, COMMENTS_PER_VIDEO)
        if cerr:
            errors.append({"site": "YouTube", "query": "comments " + vid, "err": cerr})

        body = desc
        if ctexts:
            body = (desc + "\n\n【高赞评论】\n" + "\n".join("- " + c for c in ctexts)).strip()
        if len(body) < 80:
            body = (title + " " + desc).strip()

        lvl = level_of(views, comments, likes)
        heat_bits = ["评论 %s" % fmt(comments), "播放 %s" % fmt(views), "赞 %s" % fmt(likes)]
        if dur:
            heat_bits.append("%d:%02d" % (dur // 60, dur % 60))
        heat_raw = {"views": views, "like": likes, "review": comments}
        if dur:
            heat_raw["durationSec"] = dur

        out.append({
            "platform": "YouTube",
            "site": "youtube",
            "channel": "海外",
            "country": "US",
            "language": lang,
            "date": pub, "publishedAt": pub, "dateGuessed": False,
            "title": title, "titleCn": "",
            "originalText": body[:3000],
            "url": "https://www.youtube.com/watch?v=" + vid,
            "sourceLink": "https://www.youtube.com/watch?v=" + vid,
            "author": channel,
            "sourceType": stype,
            "model": model, "tier": tier, "techRoute": tech,
            "heatRaw": heat_raw,
            "heatScore": score_of(views, comments, likes),
            "discussLevel": lvl,
            "heatSource": "comment-first+view+like",
            "heat": " · ".join(heat_bits),
            "countInVolume": True,
            "collectMethod": "youtube-api",
            "foundBy": "youtube-api:search",
            "videoId": vid,
        })
    out.sort(key=lambda x: -x["heatScore"])
    return out


def comments_of(vid, n):
    """高赞评论正文。评论关闭/受限时返回 ([], err)，不阻断条目。"""
    d, err = api("commentThreads", {
        "part": "snippet", "videoId": vid, "maxResults": n,
        "order": "relevance", "textFormat": "plainText",
    })
    if err:
        return [], err
    out = []
    for it in (d.get("items") or []):
        sn = (((it.get("snippet") or {}).get("topLevelComment") or {}).get("snippet") or {})
        t = re.sub(r"\s+", " ", (sn.get("textDisplay") or sn.get("textOriginal") or "")).strip()
        if len(t) >= 15:
            out.append("(%s赞) %s" % (sn.get("likeCount", 0), t[:220]))
    return out[:n], ""


def fmt(n):
    n = int(n or 0)
    if n >= 10000:
        return "%.1f万" % (n / 10000.0)
    return "%d" % n


def main():
    if not KEY:
        print("× 未找到 youtube.apiKey（%s），跳过" % CREDS)
        return 1
    sources, errors = [], []
    items = collect(sources, errors)
    ok = [s for s in sources if s.get("status") == "ok"]
    lv = {}
    for it in items:
        lv[it["discussLevel"]] = lv.get(it["discussLevel"], 0) + 1
    st_type, tech = {}, {}
    for it in items:
        st_type[it["sourceType"]] = st_type.get(it["sourceType"], 0) + 1
        tech[it["techRoute"]] = tech.get(it["techRoute"], 0) + 1
    payload = {
        "kind": "fc", "channel": "YouTube", "generatedAt": TODAY.isoformat(),
        "windowStart": WINDOW_START[:10],
        "items": items,
        "probes": sources,
        "errors": errors[:30],
        "stats": {
            "sourcesTotal": len(sources), "sourcesOk": len(ok),
            "sourcesError": len(sources) - len(ok),
            "items": len(items),
            "byLevel": lv,
            "bySourceType": st_type,
            "byTechRoute": tech,
            "langs": sorted({it["language"] for it in items}),
            "models": sorted({it["model"] for it in items if it["model"]}),
            "quotaEstimate": len(KEYWORDS) * 100 + 2 + len(items),
        },
    }
    with io.open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print("YouTube：%d 条（high %d / mid %d / low %d）→ %s" % (
        len(items), lv.get("high", 0), lv.get("mid", 0), lv.get("low", 0),
        os.path.basename(OUT)))
    print("  信源类型 %s · 技术路线 %s · 语种 %s" % (
        st_type, tech, sorted({it["language"] for it in items})))
    for s in sources:
        if s.get("status") != "ok":
            print("  ! %s %s" % (s.get("query"), s.get("note") or ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
