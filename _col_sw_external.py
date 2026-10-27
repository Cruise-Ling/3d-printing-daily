# -*- coding: utf-8 -*-
"""_col_sw_external.py — 软件专栏外部信源（2026-10-27）

背景
--------------------------------------------------------------------------
用户 2026-10-27 明确本专栏定位：**全部 3D 打印行业的软件通用专栏，不是创想三维一家**。
原来的信源只有 Creality 官方论坛 + GitHub，两者都天然只覆盖自家软件，
因此「全行业」这个定位在原数据上是撑不起来的。本模块补四个外部源。

四个源的实测结论（2026-10-27，改之前先读）
--------------------------------------------------------------------------
  Reddit   可用。r/OrcaSlicer、r/BambuLab 是软件专版，命中率≈100%；
           r/3Dprinting 是主版，软件相关仅约 2%，必须过闸门。
           匿名配额极小（连发 3 次即 429），已由 _reddit_search 串行限速处理。
  B 站      可用，走 _bili_search（公共模块）。需换成软件语境关键词与闸门。
  YouTube   可用，apiKey 已在 _k3_creds.json（走 Data API v3 search）。
 什么值得买 可用但**无软件内容**：3D 打印机分类 9 条全是整机好价，
           用「切片|slicer|Orca|Cura|Studio|软件|固件」过滤命中 0 条。
           按要求仍接入，定位为「周边消费信号」：countInVolume=False，
           不进声量、不进问题结构，只在渠道覆盖清单和消费信号区出现。

设计纪律
--------------------------------------------------------------------------
1. 外部源的 productLine **不套用论坛兜底**（论坛兜底是「板块里 90% 是切片，判不出就归 Creality Print」）。
   竞品内容判不出产品线就留空 —— 硬塞成 Creality Print 会把竞品声量记到自家头上。
2. 闸门分三级：专版不过滤 / 主版强过滤 / 消费源只做软件语境过滤。
3. 哪一步失败都只记 errors，不抛 —— 一个源挂了不能拖垮整次采集。
"""

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

import _bili_search as B
import _reddit_search as RD
import _smzdm_search as SM
import _sw_rules as R

for _k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy",
           "ALL_PROXY", "all_proxy"):
    os.environ.pop(_k, None)

ROOT = os.path.dirname(os.path.abspath(__file__))
CREDS_PATH = os.path.join(ROOT, "_k3_creds.json")


# ---------------------------------------------------------------- 配置
# 专版：子版本身就是软件讨论区，不过闸门
REDDIT_PURE = ["OrcaSlicer", "BambuLab"]

# 主版：3D 打印综合版，软件相关性低，必须过软件语境闸门
REDDIT_MIXED = ["3Dprinting"]

# 不含「Orca」单词：B 站上搜 Orca 会被 AI 编程工具 Orca ADE 占满（实测）。
# 一律写成 Orca Slicer / 切片软件，把歧义挡在检索阶段而不是靠闸门兜底。
BILI_KEYWORDS = [
    "3D打印 切片软件 教程", "Orca Slicer 切片 设置", "Bambu Studio 切片 教程",
    "3D打印 拉丝 参数", "3D打印 翘边 解决", "Cura 切片 设置",
    "拓竹 切片软件", "创想三维 切片软件", "3D打印 支撑 设置",
]
# 软件语境（B站标题里必须同时命中，否则「3D打印」三个字会收进一堆整机开箱）
BILI_CTX = ("切片", "slicer", "orca", "cura", "studio", "切片软件",
            "参数", "拉丝", "翘边", "层纹", "支撑", "填充", "模型切片")

YT_QUERIES = [
    "Orca Slicer settings guide",
    "Bambu Studio slicer tutorial",
    "Cura 3d print settings",
    "3d print stringing fix slicer",
    "Creality Print slicer",
    "3d printing layer shift fix",
]

YT_ENDPOINT = "https://www.googleapis.com/youtube/v3"


def load_yt_key():
    try:
        with open(CREDS_PATH, encoding="utf-8") as f:
            return ((json.load(f) or {}).get("youtube") or {}).get("apiKey", "").strip()
    except Exception:
        return ""


# ---------------------------------------------------------------- 网关
# 2026-10-27 实测踩到的三类噪声，闸门必须挡住（否则专栏一眼就假）：
#   ① 词义混叠（最致命）：
#      · B站「Orca」大量指 AI 编程工具（"我用过最好的 Agent IDE：Orca"、"Orca 多 Agent 编排"）
#      · B站「切片」大量指直播切片（"DeepSeek 批量剪辑直播切片教程"）
#      · 「3D」会撞手机膜（"IQOO16 3DAR 膜测试"）
#   ② 模型展示帖：r/BambuLab、r/OrcaSlicer 里大量 "Halloween bookmark"、"Desk Clock Mini"
#      —— 是作品分享，不是软件问题。专版也必须过闸门，不能因为是软件版就全收。
#   ③ 促销抽奖：YouTube "Giveaway Plans"、B站拼团。
# 因此：不再用「专版不过闸门」的省事做法，统一要求命中「软件行为词」。

# 软件行为词：必须在谈设置/切片/报错/参数这类动作，而不只是提到 3D 打印
SW_ACT = re.compile(
    r"slic(?:er|ing)|\borca\s*slicer\b|bambu\s*studio|\bcura\b|prusa\s*slicer|"
    r"creality\s*print|chitubox|lychee|idea\s*maker|"
    r"g[\s-]?code|3mf|\bprofile\b|\bpreset\b|settings?|parameters?|"
    r"切片|层高|支撑|填充|回抽|壁厚|参数|设置|调平|校准|"
    r"报错|崩溃|闪退|界面|菜单|安装|升级|版本|渲染|预览|"
    r"\berror\b|\bcrash|freeze|\bbug\b|not\s+working|won.?t\s+(?:slice|open|load|start)|"
    r"\bsupport(?:s)?\b|\binfill\b|retraction|bridging|overhang|"
    r"\d\.\d+\.\d+",          # 形如 2.4.2 的版本号本身就是软件信号
    re.I,
)

# 具体工具名：正文级别的判定必须命中它 —— 只提 infill/support 的多半是作品描述
# （实测 "Made a working desk fan that looks like a turbocharger" 正文含 infill，
#  被判成软件内容进了首屏。软件专栏不能出现这种东西。）
SW_TOOL = re.compile(
    r"\borca\s*slicer\b|\borcaslicer\b|bambu\s*studio|\bcura\b|prusa\s*slicer|"
    r"creality\s*print|chitubox|lychee|idea\s*maker|simplify3d|slic3r|"
    r"g[\s-]?code|\.3mf|\bstl\b|slicer",
    re.I,
)

# 歧义/噪声硬排除：命中即拒，不参与任何放宽判定
SW_NOISE = re.compile(
    r"直播切片|剪辑|剪映|短视频|带货|橱窗|小黄车|"
    r"agent\s*(?:ide|管理|编排)|\borca\s*(?:ade|agent)|"
    r"ai\s*编程|代码助手|claude\s*code|cursor\s*ide|"
    r"手机膜|钢化膜|贴膜|磁控溅射|"
    r"giveaway|抽奖|福利|送福利|拼团|团购|开团|优惠码|返现|"
    r"\bnkd\b|unboxing|开箱|晒单|到货|"
    r"for\s*sale|selling|warehouse\s*sale|deal\s*alert|discount\s*code",
    re.I,
)


def gate_software(title, body=""):
    """综合版（r/3Dprinting、r/BambuLab）与 YouTube 用：标题或正文命中软件行为词即可。
    排除词一旦命中直接拒 (标题优先看)。"""
    head = title or ""
    if SW_NOISE.search(head):
        return False
    if SW_ACT.search(head):
        return True
    body = body or ""
    if SW_NOISE.search(body[:200]):
        return False
    # 正文级别的放行要求「有具体工具名」：只靠 infill/support 这类通用词的，
    # 实测是作品展示帖，不是软件讨论。
    return bool(SW_ACT.search(body) and SW_TOOL.search(body))


def gate_strict(title, body=""):
    """专版（r/OrcaSlicer）用：仍需过闸门，只是标题范围放宽到「标题+正文前段」。
    专版里模型展示帖同样常见（"Halloween bookmark"），不能因为是软件版就全收。"""
    head = title or ""
    if SW_NOISE.search(head):
        return False
    if SW_ACT.search(head):
        return True
    body = body or ""
    if SW_NOISE.search(body[:200]):
        return False
    # 专版正文大多是软件操作细节，允许正文命中 —— 但同样必须点名工具，
    # 否则 "Halloween bookmark" 这类作品帖会因为正文里的 infill 混进来。
    seg = body[:600]
    return bool(SW_ACT.search(seg) and SW_TOOL.search(seg))


def gate_bili(title, desc=""):
    s = ((title or "") + " " + (desc or "")).lower()
    if B.NOISE_BOOST.search(s) or SW_NOISE.search(s):
        return False
    if not any(k.lower() in s for k in BILI_CTX):
        return False
    # 「切片」在 B 站歧义最重：必须同时出现 3D/打印机/模型 语境，否则是直播切片
    if "切片" in s and not re.search(r"3d|打印|模型|slicer|orca|cura|studio", s, re.I):
        return False
    return bool(SW_ACT.search(s))


def gate_yt(title, desc=""):
    return gate_software(title, desc)


# ---------------------------------------------------------------- 归类
def judge(title, body):
    """外部条目的语义字段。产品线**不做论坛兜底**（见模块头设计纪律 1）。"""
    text = (title or "") + " " + (body or "")
    product = R.classify_product(text) or ""
    problem = R.classify_problem(title or "", body or "")
    # 判得出问题类型的算「有效」，判不出的算「泛讨论」—— 与论坛侧口径一致
    grade = "有效" if problem else "泛讨论"
    model = R.extract_model(text) or "未标注"
    lang = "EN"
    if re.search(r"[\u4e00-\u9fff]", title or ""):
        lang = "ZH"
    return {
        "productLine": product,
        "problemType": problem,
        "grade": grade,
        "model": model,
        "language": lang,
    }


def _finish(items, src_label):
    """统一补齐 uid / 语义字段 / 信源标记。"""
    out = []
    for it in items:
        t = it.get("title") or ""
        b = it.get("originalText") or ""
        j = judge(t, b)
        it.setdefault("uid", "")
        if not it["uid"]:
            it["uid"] = "%s_%s" % (src_label, re.sub(r"\W+", "", t)[:20])
        it.update(j)
        if not it.get("language"):
            it["language"] = j["language"]
        it.setdefault("countInVolume", True)
        out.append(it)
    return out


# ---------------------------------------------------------------- Reddit
def collect_reddit(days=180, sources=None, errors=None):
    sources = [] if sources is None else sources
    errors = [] if errors is None else errors
    items = []

    # 专版：也要过闸门（软件版里同样有大量模型展示帖），但允许正文命中
    pure, _s, _e = RD.search(REDDIT_PURE, gate=gate_strict, days=days,
                             sources=sources, errors=errors)
    items += pure

    # 主版：软件语境闸门
    mixed, _s2, _e2 = RD.search(REDDIT_MIXED, gate=gate_software, days=days,
                                sources=sources, errors=errors)
    items += mixed

    return _finish(items, "rd")


# ---------------------------------------------------------------- B 站
def collect_bili(days=180, sources=None, errors=None):
    sources = [] if sources is None else sources
    errors = [] if errors is None else errors
    raw, src, err = B.search(BILI_KEYWORDS, gate=gate_bili, ctx=BILI_CTX, days=days,
                             exclude=lambda t, d: bool(B.NOISE_BOOST.search(t or "")),
                             label="B站")
    items = []
    for it in raw:
        items.append({
            "uid": "bili_%s" % (it.get("_bvid") or re.sub(r"\W+", "", it.get("title") or "")[:16]),
            "platform": "B站",
            "site": "B站",
            "channel": "国内",
            "country": "CN",
            "language": "ZH",
            "date": it.get("date") or "",
            "title": it.get("title") or "",
            "titleCn": it.get("titleCn") or "",
            "originalText": it.get("originalText") or "",
            "url": it.get("url") or "",
            "author": it.get("author") or "",
            "sourceType": it.get("sourceType") or "用户",
            "signal": it.get("signal") or "",
            "views": it.get("views") or 0,
            "foundBy": it.get("foundBy") or "",
        })
    # B 站信源记录格式与 Reddit 不同，做一次合并整理。
    # 注意：src[].accepted 是「该关键词收了几条」，求和才是条目数（原写法错误地当成了关键词命中数）。
    ok = sum(int(s.get("accepted") or 0) for s in src)
    sources.append({"source": "B站 搜索", "status": "ok" if ok else "empty",
                    "count": ok, "scanned": len(BILI_KEYWORDS)})
    for e in err:
        errors.append(e)
    return _finish(items, "bili")


# ---------------------------------------------------------------- YouTube
def collect_youtube(days=180, sources=None, errors=None):
    sources = [] if sources is None else sources
    errors = [] if errors is None else errors
    key = load_yt_key()
    if not key:
        sources.append({"source": "YouTube", "status": "error", "count": 0,
                        "note": "缺 apiKey（_k3_creds.json）"})
        return []

    from datetime import date, timedelta
    cutoff = (date.today() - timedelta(days=days)).isoformat() if days else ""
    items, seen = [], set()

    for i, q in enumerate(YT_QUERIES):
        if i:
            time.sleep(1.2)
        url = "%s/search?%s" % (YT_ENDPOINT, urllib.parse.urlencode({
            "part": "snippet", "type": "video", "maxResults": 25,
            "order": "date", "q": q, "key": key}))
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=25) as r:
                data = json.loads(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            errors.append({"site": "YouTube", "query": q, "err": "HTTP %s" % e.code})
            sources.append({"source": "YouTube %s" % q, "status": "error", "count": 0})
            continue
        except Exception as e:
            errors.append({"site": "YouTube", "query": q, "err": type(e).__name__})
            sources.append({"source": "YouTube %s" % q, "status": "error", "count": 0})
            continue

        kept = 0
        for row in (data.get("items") or []):
            vid = ((row.get("id") or {}).get("videoId") or "")
            sn = row.get("snippet") or {}
            if not vid or vid in seen:
                continue
            title = (sn.get("title") or "").strip()
            desc = (sn.get("description") or "").strip()
            pub = (sn.get("publishedAt") or "")[:10]
            if cutoff and pub and pub < cutoff:
                continue
            if not gate_yt(title, desc):
                continue
            seen.add(vid)
            kept += 1
            author = sn.get("channelTitle") or ""
            items.append({
                "uid": "yt_%s" % vid,
                "platform": "YouTube",
                "site": "YouTube",
                "channel": "海外视频",
                "country": "US",
                "date": pub,
                "title": title,
                "originalText": desc,
                "url": "https://www.youtube.com/watch?v=%s" % vid,
                "author": author,
                "sourceType": "官方" if re.match(r"^creality|^bambu|^orca", author, re.I) else "媒体",
                "foundBy": "youtube search: %s" % q,
            })
        sources.append({"source": "YouTube %s" % q,
                        "status": "ok" if kept else "empty", "count": kept})

    return _finish(items, "yt")


# ---------------------------------------------------------------- 什么值得买
def collect_smzdm(sources=None, errors=None):
    sources = [] if sources is None else sources
    errors = [] if errors is None else errors
    # 用户 2026-10-27：软件专栏也接什么值得买，定位「周边消费信号」。
    # 因此**不做软件相关性过滤** —— 收进来的整机好价不是软件内容，靠 sourceType=导购
    # 和 countInVolume=False 与舆情区分，而不是靠闸门把它们挡掉。
    # （试过用软件语境闸门过滤：9 条整机好价里有 2 条因为摘要含 profile/infill 被误判为软件内容，
    #  说明这类商品摘要做语义过滤只会产生假阳性。）
    raw, src, err = SM.search(gate=None,
                              sources=sources, errors=errors)
    items = []
    for it in raw:
        it = dict(it)
        it["channel"] = "国内导购"
        items.append(it)
    return _finish(items, "sm")


# ---------------------------------------------------------------- 汇总
def collect_all(days=180):
    """返回 (items, sources, errors)。任一源失败都不抛。"""
    items, sources, errors = [], [], []
    for name, fn in (("Reddit", collect_reddit), ("B站", collect_bili),
                     ("YouTube", collect_youtube), ("什么值得买", collect_smzdm)):
        try:
            got = fn(days=days, sources=sources, errors=errors) \
                if fn is not collect_smzdm else fn(sources=sources, errors=errors)
            print("  %-10s %d 条" % (name, len(got)))
            items += got
        except Exception as e:
            print("  %-10s 失败: %s" % (name, type(e).__name__))
            errors.append({"site": name, "err": "%s: %s" % (type(e).__name__, str(e)[:120])})
    return items, sources, errors


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    its, src, err = collect_all()
    print("\n合计 %d 条" % len(its))
    from collections import Counter
    print("平台:", dict(Counter(x["platform"] for x in its)))
    print("产品线:", dict(Counter(x.get("productLine") or "(空)" for x in its)))
    print("审核:", dict(Counter(x.get("grade") for x in its)))
    print("\n信源:")
    for s in src:
        print("  %-30s %-6s %s" % (s.get("source"), s.get("status"), s.get("count")))
    if err:
        print("\n错误 %d 条，前 5:" % len(err))
        for e in err[:5]:
            print("  ", e)
