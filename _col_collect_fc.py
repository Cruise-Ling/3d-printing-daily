# -*- coding: utf-8 -*-
"""_col_collect_fc.py — 全彩 3D 打印专栏采集器（P7 · 2026-10-27 接入）

职责边界（与 K3 同一纪律，别越界）
--------------------------------------------------------------------------
本脚本**只做「抓取 + 归一 + 去重 + 热度判定」**，产出候选池 JSON，
**不写页面语义字段**（sentiment / problemPoints / summaryCn 需语义判断，
自动猜会把噪声当结论写进页面 —— 那比缺数据更糟）。

三层信源（2026-10-27 实测结论，见 00_台账/方案_20261027_全彩专栏.md）
--------------------------------------------------------------------------
  L1 脚本自动   B站  —— 全自动检索，含 cookie 预热（-412 就是缺 cookie）
  L2 种子抓取   什么值得买 / 3D打印资源库 / 外媒 / 官网
                URL 由 Agent 检索产出，脚本只取正文与互动数。
                为什么不能自己搜：smzdm 搜索页返回 JS 挑战壳（探测脚本 + 空 body），
                列表页 404 —— 能搜到的地方搜不到，能读到的地方读得到，故拆两层。
  L3 不可自动   小红书 / 抖音 / 知乎 —— 只进覆盖清单，绝不填数

热度门槛（本专栏独有，见规范 §讨论度）
--------------------------------------------------------------------------
用户要求「主要集中于用户讨论度比较高的帖子」，所以：
  * B站：播放/评论双指标任一达标（全彩是长测评驱动，播放 2.6 万是头部，3000 已属有效）
  * 值得买：点赞+收藏+评论
  * 其余：评论数，缺失时用「正文长度」代理（与 K3 的 Reddit 规则同源，诚实标注）

用法
--------------------------------------------------------------------------
  python _col_collect_fc.py                  # B站 + 种子 全跑，默认门槛 mid
  python _col_collect_fc.py --days 0         # 不限窗口（首次建池用）
  python _col_collect_fc.py --only bili
  python _col_collect_fc.py --only seed
  python _col_collect_fc.py --min-signal low # 月度全量
  python _col_collect_fc.py --out _fc_candidates.json
"""
import argparse
import datetime
import importlib.util
import io
import json
import os
import re
import ssl
import sys
import time
import http.cookiejar
import urllib.error
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE_PATH = os.path.join(HERE, "_k3_feishu_delta.py")
SEED_PATH = os.path.join(HERE, "_fc_sources_seed.json")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

TODAY = datetime.date.today()


# ---------------------------------------------------------------- 引擎口径复用
def load_engine():
    """复用推送引擎的 norm_url / norm_text / uid_of —— 禁止复制实现，避免三处口径漂移。"""
    spec = importlib.util.spec_from_file_location("_k3_engine", ENGINE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ENG = load_engine()
ENG.clear_proxy()


# ---------------------------------------------------------------- 机型与技术档次
# 2026-10-27 用户决策：桌面三台 + 工业两台各建一张卡（S3 共 5 张机型卡）
# 机型识别优先级：越具体的放前面，避免 G1 抢走 G1X
MODELS = [
    ("G1X", "桌面", r"(?<![a-z0-9])g\s*1\s*-?\s*x(?![a-z0-9])|黑格\s*g\s*1|heygears?\s*g\s*1"),
    ("CJ270", "桌面", r"(?<![a-z0-9])c\s*j\s*-?\s*270(?![a-z0-9])|闪铸\s*c\s*j"),
    ("QC2A", "桌面", r"(?<![a-z0-9])q\s*c\s*-?\s*2\s*a(?![a-z0-9])|inew\s*3?\s*d|simbа?\s*3d|拓远"),
    ("Stratasys", "工业", r"stratasys|(?<![a-z0-9])j\s*55(?![a-z0-9])|(?<![a-z0-9])j\s*35(?![a-z0-9])"
                          r"|(?<![a-z0-9])j\s*826(?![a-z0-9])|polyjet"),
    ("Mimaki", "工业", r"mimaki|3\s*duj"),
]
# 型号归一（用户口述的 MJ270 归到 CJ270：在售桌面全彩为 CJ270，MJ270 无对应在售机型）
MODEL_ALIAS = {"MJ270": "CJ270", "G1": "G1X", "QC-2A": "QC2A"}

# 相关性闸门：必须命中机型，且命中全彩语境词 —— 挡住「G1X 是指别的东西」这类误收
CTX_FC = ("全彩", "彩色", "多色", "color", "colour", "喷墨", "jetting", "mjp", "polyjet",
          "uv", "手办", "上色", "涂装", "3d打印", "3d 打印", "打印机", "printer", "printing",
          "光固化", "树脂")
# 噪音：只挡归并帖陷阱（拼团/加微信），**不挡导购** —— 值得买的长帖正是本专栏最优质样本
NOISE_RE = re.compile(r"开团|拼团|优惠码|领券|返现|加微信|招代理|加盟|二手|转让|闲置", re.I)

BILI_KEYWORDS = [
    "黑格 G1X",
    "黑格G1X 全彩",
    "全彩3D打印机",
    "全彩 3D 打印 手办",
    "闪铸 CJ270",
    "CJ270 全彩",
    "inew3d QC2A",
    "全彩喷墨 3D打印",
    "UV打印机 浮雕",
    "全彩光固化",
]


def model_of(text):
    """返回 (机型, 档次)。识别不到返回 ("", "")—— 未标注也必须如实留空，不得猜。"""
    s = (text or "").lower()
    for name, tier, pat in MODELS:
        if re.search(pat, s, re.I):
            return name, tier
    return "", ""


# ---------------------------------------------------------------- 网络
_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE
_OP = urllib.request.build_opener(
    urllib.request.ProxyHandler({}),
    urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
    urllib.request.HTTPSHandler(context=_CTX),
)


def probe_status(code):
    """探针三态。403/429 是「受限」不是「出错」——混在一起会让页面天天报 fail。

    这条分档与 K3 的 errors[] 口径一致：受限源如实标注，不当故障处理。
    """
    if code == 200:
        return "ok"
    if code in (401, 403, 429):
        return "blocked"
    if code == 404:
        return "absent"
    return "error"


def get(url, referer="", timeout=25, retries=2, backoff=4.0):
    """返回 (code, text)。异常一律降级成 ('ERR', 原因)，任何一路挂掉都不中断整体。"""
    last = ("ERR", "unknown")
    for i in range(retries + 1):
        try:
            h = {"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"}
            if referer:
                h["Referer"] = referer
            r = _OP.open(urllib.request.Request(url, headers=h), timeout=timeout)
            raw = r.read()
            enc = "utf-8"
            ct = (r.headers.get("Content-Type") or "").lower()
            if "gbk" in ct or "gb2312" in ct:
                enc = "gbk"
            return r.status, raw.decode(enc, "ignore")
        except urllib.error.HTTPError as e:
            last = (e.code, "HTTP %s" % e.code)
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(backoff * (i + 1))
                continue
            return last
        except Exception as e:
            last = ("ERR", "%s: %s" % (type(e).__name__, str(e)[:80]))
            time.sleep(backoff * (i + 1))
    return last


# ---------------------------------------------------------------- 正文抽取
_RE_SCRIPT = re.compile(r"<(script|style|noscript|svg|iframe)[\s\S]*?</\1>", re.I)
_RE_TAG = re.compile(r"<[^>]+>")
_RE_WS = re.compile(r"[ \t\u00a0]+")
_RE_P = re.compile(r"<p[^>]*>([\s\S]*?)</p>", re.I)


def strip_tags(s):
    s = _RE_SCRIPT.sub(" ", s or "")
    s = _RE_TAG.sub(" ", s)
    s = (s.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<")
          .replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'"))
    return _RE_WS.sub(" ", s).strip()


_RE_BOILER = re.compile(
    r"shopping link|cookie|subscribe|newsletter|advertisement|sign up|all rights reserved|"
    r"点击查看|关注我们|扫码|下载客户端|责任编辑", re.I)


def clean_title(t):
    """标题清洗：解 HTML 实体 + 去站点后缀。

    实测不清理会直接在卡片标题上出现 `...这波&quot;全彩打印机&quot;热潮_3D打印机_什么值得买`。
    """
    import html as _html
    t = _html.unescape(t or "").strip()
    t = re.sub(r"\s*[_|\-–—]\s*(什么值得买|腾讯新闻|南方\+?|南方plus|3D打印机|"
               r"3dzyk.*|All3DP|Fabbaloo|VoxelMatters|3DPrinting\.com)\s*$", "", t, flags=re.I)
    t = re.sub(r"\s*[«»]\s*\S+\s*$", "", t)
    t = re.sub(r"\s*[_|]\s*[^_|]{0,12}$", "", t) if re.search(r"[_|]", t) else t
    return t.strip()


def extract_main_text(html):
    """通用正文抽取：优先拼 <p> 块（多数 CMS 的正文都在 p 里），不足 200 字退回全文。

    宁可短也不要抓一屏导航 —— 正文长度在下面还要当热度代理，混进导航会让代理失真。
    <p> 里混着的 cookie / 订阅 / 导购模板文案要剔掉：实测 All3DP 首段就是
    「This is a shopping link.」，不剔会让整条卡片的标题和摘要都变成这句。
    """
    ps = []
    for m in _RE_P.finditer(html or ""):
        t = strip_tags(m.group(1))
        if len(t) >= 20 and not _RE_BOILER.search(t):
            ps.append(t)
    body = "\n".join(ps)
    if len(body) < 200:
        body = strip_tags(html or "")
    # 去掉成串重复（模板文案）
    out, seen = [], set()
    for ln in body.split("\n"):
        k = re.sub(r"\W+", "", ln.lower())[:60]
        if len(k) >= 12 and k in seen:
            continue
        seen.add(k)
        out.append(ln)
    return "\n".join(out).strip()


def meta_of(html, prop):
    m = re.search(r'<meta[^>]+(?:property|name)="%s"[^>]+content="([^"]+)"' % re.escape(prop),
                  html or "", re.I)
    return m.group(1).strip() if m else ""


def title_of(html):
    """标题优先级：og:title > h1 > title。

    实测 All3DP 页面首个 <h1> 是页面内的导购小标题（"This is a shopping link."），
    先取 h1 会把整条卡片的标题写错 —— og:title 才是文章标题。
    """
    og = meta_of(html, "og:title")
    if og and len(og) >= 6:
        return og
    m = re.search(r'<h1[^>]*>([\s\S]{4,200}?)</h1>', html or "", re.I)
    if m:
        t = strip_tags(m.group(1))
        if len(t) >= 6:
            return t
    m = re.search(r"<title>([\s\S]{4,300}?)</title>", html or "", re.I)
    return strip_tags(m.group(1)) if m else ""


_RE_DATE = re.compile(r"(20\d{2})[-/年.](\d{1,2})[-/月.](\d{1,2})")


def date_of(html, url):
    raw = (meta_of(html, "article:published_time") or meta_of(html, "og:updated_time")
           or meta_of(html, "publishdate") or "")
    m = _RE_DATE.search(raw)
    if not m:
        m = _RE_DATE.search(url or "")
    if m:
        return "%04d-%02d-%02d" % (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return ""


def counts_of(html, text):
    """互动数解析。取不到就返回 None，由 heat_of 退到正文长度代理 —— 不填 0，
    因为 0 的意思是「确认没人讨论」，与「没解析到」是两件事。"""
    c = {"views": None, "review": None, "like": None, "fav": None}
    for key, pats in (
        ("like", [r'(\d+)\s*(?:人)?点赞', r'点赞\s*[（(]?\s*(\d+)']),
        ("fav", [r'(\d+)\s*(?:人)?收藏', r'收藏\s*[（(]?\s*(\d+)']),
        ("review", [r'(\d+)\s*条?评论', r'评论\s*[（(]?\s*(\d+)']),
    ):
        for p in pats:
            m = re.search(p, text or "")
            if m:
                try:
                    c[key] = int(m.group(1))
                    break
                except ValueError:
                    pass
    return c


# ---------------------------------------------------------------- 热度门槛
def heat_of(platform, views, review, like, fav, body_len):
    """返回 (discussLevel, heatScore, heatSource)。

    heatScore 只用于页面上做「讨论度排序」，不是跨平台可比指标 ——
    各平台量纲不同，所以卡片脚注永远显示原始数字，不显示 score。
    """
    views, review = int(views or 0), int(review or 0)
    like, fav = int(like or 0), int(fav or 0)
    if platform == "B站":
        if views >= 3000 or review >= 20:
            return "high", views + review * 150, "play+review"
        if views >= 500 or review >= 5:
            return "mid", views + review * 150, "play+review"
        return "low", views + review * 150, "play+review"
    if platform == "什么值得买":
        eng = like + fav
        if eng >= 50 or review >= 20:
            return "high", eng * 20 + review * 60, "like+fav+review"
        if eng >= 10 or review >= 5:
            return "mid", eng * 20 + review * 60, "like+fav+review"
        return "low", eng * 20 + review * 60, "like+fav+review"
    # 外媒 / 官网：没有稳定互动数，用评论数；再没有就用正文长度代理（诚实标注）
    if review:
        lvl = "high" if review >= 30 else ("mid" if review >= 10 else "low")
        return lvl, review * 100, "review"
    n = body_len or 0
    lvl = "high" if n >= 800 else ("mid" if n >= 300 else "low")
    return lvl, n, "body-length"


# ---------------------------------------------------------------- L1：B 站
def collect_bili(days, sources, errors):
    """复用公共模块 _bili_search（mBox 也用它，同一套 cookie 预热与重试）。"""
    try:
        import _bili_search as B
    except Exception as e:
        errors.append({"site": "B站", "query": "(import)", "err": str(e)[:120]})
        return []

    def gate(title, desc):
        s = ("%s %s" % (title or "", desc or "")).lower()
        if not model_of(s)[0]:
            return False
        return any(k in s for k in CTX_FC)

    raw, src, err = B.search(BILI_KEYWORDS, gate=gate, ctx=CTX_FC, days=days,
                             exclude=lambda t, d: bool(NOISE_RE.search(t or "")),
                             label="B站")
    for s in src:
        s.setdefault("status", probe_status(s.get("code")))
    sources.extend(src)
    errors.extend(err)

    out = []
    for it in raw:
        text = "%s %s" % (it.get("title") or "", it.get("originalText") or "")
        model, tier = model_of(text)
        # 本专栏的热度门槛与 K3 不同（3000/20 而非 1000/30），必须重算，不能沿用 signal
        v = int(it.get("views") or 0)
        m = re.search(r"评论\s*([\d.]+万?)", it.get("heat") or "")
        review = 0
        if m:
            try:
                review = int(float(m.group(1).replace("万", "")) * (10000 if "万" in m.group(1) else 1))
            except ValueError:
                review = 0
        lvl, score, hsrc = heat_of("B站", v, review, 0, 0, 0)
        it.update({
            "model": model, "tier": tier, "techRoute": "MJP 喷墨",
            "heatRaw": {"views": v, "review": review},
            "heatScore": score, "discussLevel": lvl, "heatSource": hsrc,
            "sourceType": it.get("sourceType") or "用户",
            "countInVolume": True,
        })
        out.append(it)
    return out


# ---------------------------------------------------------------- L2：种子抓取
def collect_seed(sources, errors):
    """读 _fc_sources_seed.json，逐条抓正文与互动数。

    种子文件由 Agent 检索产出（WebSearch 能找到，脚本搜不到 —— 见模块头注释）。
    拿不到就跳过并记 probe，不阻断。
    """
    if not os.path.exists(SEED_PATH):
        errors.append({"site": "seed", "query": "(file)", "err": "_fc_sources_seed.json 不存在"})
        return []
    try:
        seed = json.load(io.open(SEED_PATH, encoding="utf-8"))
    except Exception as e:
        errors.append({"site": "seed", "query": "(parse)", "err": str(e)[:120]})
        return []

    out = []
    for row in seed:
        url = row.get("url") or ""
        plat = row.get("platform") or "其他"
        if not url:
            continue
        code, html = get(url, referer=row.get("referer") or "")
        ok = (code == 200)
        st = probe_status(code)
        sources.append({"channel": plat, "query": url[:70], "code": code,
                        "status": st, "accepted": 1 if ok else 0})
        if not ok:
            errors.append({"site": plat, "query": url[:70], "err": str(html)[:80]})
            continue

        title = clean_title(row.get("title") or title_of(html))
        body = extract_main_text(html)
        text = "%s %s" % (title, body)
        model, tier = model_of(text)
        if not model and not row.get("force"):
            # 不含任何机型 → 可能是行业综述，保留但标未标注，由页面「机型」筛选兜住
            model, tier = "", ""
        pub = row.get("date") or date_of(html, url)
        # 解析不到发布日时退回「采集日」并打标，**不丢条目** —— 静默丢数比日期不准更严重
        date_guessed = False
        if not pub:
            pub = TODAY.isoformat()
            date_guessed = True
        c = counts_of(html, body)
        lvl, score, hsrc = heat_of(plat, c["views"], c["review"], c["like"], c["fav"], len(body))

        it = {
            "platform": plat,
            "site": row.get("site") or plat,
            "channel": row.get("channel") or ("国内" if row.get("country") == "CN" else "海外"),
            "country": row.get("country") or "CN",
            "language": row.get("language") or ("ZH" if re.search(r"[\u4e00-\u9fff]", title) else "EN"),
            "date": pub, "publishedAt": pub, "dateGuessed": date_guessed,
            "title": title, "titleCn": title,
            "originalText": body[:3000],
            "url": url, "sourceLink": url,
            "author": row.get("author") or "",
            "sourceType": row.get("sourceType") or "媒体",
            "model": model, "tier": tier, "techRoute": "MJP 喷墨",
            "heatRaw": {k: v for k, v in c.items() if v is not None},
            "heatScore": score, "discussLevel": lvl, "heatSource": hsrc,
            "heat": " · ".join("%s %s" % ({"views": "浏览", "review": "评论", "like": "点赞",
                                            "fav": "收藏"}[k], v)
                               for k, v in c.items() if v is not None) or "未取到互动数",
            "countInVolume": row.get("countInVolume", True),
            "collectMethod": "seed",
            "foundBy": row.get("foundBy") or "agent-search",
        }
        out.append(it)
        time.sleep(0.8)
    return out


# ---------------------------------------------------------------- 窗口与差集
# ---------------------------------------------------------------- L3：外部社区通道
# YouTube 与 Reddit 各有自己的约束（API 配额 / RSS 1req·min 节流），拆成独立脚本
# 单独跑，任一路失败都不拖垮主链；这里只负责「把结果并回同一个池」。
EXT_CHANNELS = [("YouTube", "_fc_yt_candidates.json"),
                ("Reddit", "_fc_rd_candidates.json")]


def load_external(sources, errors):
    """读 L3 通道产出。字段契约与本地采集完全一致（见各自脚本头注释）。"""
    out = []
    for name, fn in EXT_CHANNELS:
        p = os.path.join(HERE, fn)
        if not os.path.exists(p):
            sources.append({"channel": name, "query": "(file)", "code": 0,
                            "status": "absent", "accepted": 0,
                            "note": "%s 未生成（该通道本次未跑）" % fn})
            continue
        try:
            d = json.load(io.open(p, encoding="utf-8"))
        except Exception as e:
            errors.append({"site": name, "query": "(parse)", "err": str(e)[:100]})
            continue
        got = d.get("items") or []
        st = d.get("stats") or {}
        sources.append({
            "channel": name,
            "query": "L3 通道汇总",
            "code": 200 if got else 0,
            "status": "ok" if got else "absent",
            "accepted": len(got),
            "note": "生成 %s · 探针 %d/%d · %s" % (
                (d.get("generatedAt") or "")[:10],
                st.get("sourcesOk", 0), st.get("sourcesTotal", 0),
                json.dumps(st.get("byLevel") or {}, ensure_ascii=False)),
        })
        out.extend(got)
    return out


def in_window(pub, days):
    if not pub:
        return days in (0, None)
    if not days or days <= 0:
        return True
    try:
        d = datetime.datetime.strptime(pub[:10], "%Y-%m-%d").date()
    except ValueError:
        return True
    return (TODAY - d).days <= days


LEVEL_RANK = {"low": 0, "mid": 1, "high": 2}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=0, help="发布窗口天数，0=不限（2026 建池用 0）")
    ap.add_argument("--only", choices=["bili", "seed", "ext", "all"], default="all")
    ap.add_argument("--min-signal", choices=["low", "mid", "high"], default="mid")
    ap.add_argument("--out", default="")
    a = ap.parse_args()

    # 用户决策：首次建池回溯「2026 年至今」——起点固定 2026-01-01，
    # 三台桌面机正好都在 2026 年发布/众筹，窗口与产品生命周期天然对齐。
    since = datetime.date(2026, 1, 1)
    days = (TODAY - since).days if a.days == 0 else a.days

    items, sources, errors = [], [], []
    if a.only in ("bili", "all"):
        items += collect_bili(days, sources, errors)
    if a.only in ("seed", "all"):
        items += collect_seed(sources, errors)
    if a.only in ("ext", "all"):
        items += load_external(sources, errors)

    # 窗口 + 噪音 + 去重（uid 带原文片段，双线兜底：uid + 归一化 URL）
    kept, dropped = [], {"window": 0, "noise": 0, "dup": 0, "low-signal": 0}
    seen_uid, seen_url = set(), set()
    for it in items:
        if not in_window(it.get("date"), days):
            dropped["window"] += 1
            continue
        if NOISE_RE.search((it.get("title") or "") + (it.get("originalText") or "")[:200]):
            dropped["noise"] += 1
            continue
        uid = ENG.uid_of(it)
        it["uid"] = uid
        nurl = ENG.norm_url(it.get("sourceLink") or it.get("url") or "")
        it["dedupKey"] = nurl
        if uid in seen_uid or (nurl and nurl in seen_url):
            dropped["dup"] += 1
            continue
        if LEVEL_RANK.get(it.get("discussLevel") or "low", 0) < LEVEL_RANK[a.min_signal]:
            dropped["low-signal"] += 1
            continue
        seen_uid.add(uid)
        if nurl:
            seen_url.add(nurl)
        kept.append(it)

    # 讨论度优先：与 K3 按日期排不同 —— 用户要的是「讨论度高的帖子」先看到
    kept.sort(key=lambda x: (-(x.get("heatScore") or 0), x.get("date") or ""), reverse=False)

    payload = {
        "fetchedAt": time.strftime("%Y-%m-%d %H:%M"),
        "window": {"since": since.isoformat(), "days": days},
        "count": len(kept),
        "items": kept,
        "probes": sources,
        "stats": {
            "sourcesTotal": len(sources),
            # 只把 status=error 计入故障；blocked / absent 是「受限」与「没有这一页」，
            # 计进去会让页面天天挂 fail 徽标（K3 早期踩过同一个坑）
            "sourcesError": sum(1 for s in sources if s.get("status") == "error"),
            "sourcesBlocked": sum(1 for s in sources if s.get("status") == "blocked"),
            "dropped": dropped,
            "byLevel": {k: sum(1 for x in kept if x.get("discussLevel") == k)
                        for k in ("high", "mid", "low")},
            "byPlatform": {},
            "byModel": {},
        },
        "errors": errors,
    }
    for it in kept:
        payload["stats"]["byPlatform"][it["platform"]] = \
            payload["stats"]["byPlatform"].get(it["platform"], 0) + 1
        k = it.get("model") or "未标注"
        payload["stats"]["byModel"][k] = payload["stats"]["byModel"].get(k, 0) + 1

    out = a.out or os.path.join(HERE, "_fc_candidates_%s.json" % TODAY.strftime("%Y%m%d"))
    io.open(out, "w", encoding="utf-8").write(
        json.dumps(payload, ensure_ascii=False, indent=1))

    print("=== 全彩专栏采集 ===")
    print("窗口      : %s 起（%d 天）" % (since.isoformat(), days))
    print("门槛      : %s" % a.min_signal)
    print("保留      : %d 条" % len(kept))
    print("丢弃      : %s" % dropped)
    print("讨论度    : %s" % payload["stats"]["byLevel"])
    print("平台      : %s" % payload["stats"]["byPlatform"])
    print("机型      : %s" % payload["stats"]["byModel"])
    print("探针      : %d 个 / 异常 %d" % (len(sources), len(errors)))
    print("产出      : %s" % out)
    if errors:
        print("\n异常明细（不阻断，仅记录）:")
        for e in errors[:12]:
            print("  - %s | %s | %s" % (e.get("site"), e.get("query"), e.get("err")))


if __name__ == "__main__":
    main()
