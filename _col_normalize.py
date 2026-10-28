# -*- coding: utf-8 -*-
"""
专栏数据归一化（P2）

把采集器产出的原始 JSON 归一成「统一数据契约」，供 _build_column.py 生成页面：

  * 正文清洗（去论坛导航噪声 / 图片占位 / 裸链接）
  * 正文截断到 1200 字（保留 truncated 标记，卡片提示可跳原帖）
  * 版本号归一：version=主.次，versionRaw=原始串（D1）
  * 统一字段：title/titleCn/originalText/textCn/language/grade/...

用法：
  python _col_normalize.py --kind sw   --in _sw_items.json    --out _sw_items_norm.json
  python _col_normalize.py --kind mbox --in _mbox_items.json  --out _mbox_items_norm.json
"""
import argparse
import io
import json
import re
import sys
import time
from collections import Counter

BODY_LIMIT = 1200


# ---------------------------------------------------------------- 清洗
_RE_IMG_MD = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_RE_MD_LINK = re.compile(r"\[([^\]]{0,90})\]\((https?://[^)]+)\)")
_RE_URL = re.compile(r"https?://\S+")
_RE_DIM = re.compile(r"\b(?:image\s+)?\d{2,4}\s*[×x]\s*\d{2,4}\s+[\d.]+\s*[KM]B\b", re.I)
_RE_KB = re.compile(r"\b\d+(?:\.\d+)?\s*KB\b")
_RE_BARE_DOMAIN = re.compile(r"(?<![\w.])(?:www\.)?[a-z0-9-]+\.(?:com|net|org|io|de|cn|co\.uk)(?![\w.])", re.I)
_RE_WS = re.compile(r"[ \t\u00a0]+")


# Reddit RSS 每条 content 末尾都带 "submitted by /u/x [link] [comments]"。
# 纯图 / 纯链接帖没有正文，清洗后只剩这句模板尾巴 —— 采集端（_reddit_search /
# _col_collect_rd）已剥离并整条丢弃，这里再兜一层：历史数据里还有这类空壳条目，
# 重新归一时必须剔除，否则重建页面会把它们带回来。
_RE_RD_BOILER = re.compile(r"submitted\s+by\s*(?:/u/|u/)\S*|\[(?:link|comments)\]",
                           re.I)
# 同一句话在正文「末尾」出现时是 RSS 尾巴，从那里到结尾整段都要砍掉 ——
# 有真实正文的帖子也会带这句，不砍会让卡片最后挂一行「由 /u/xxx 提交 [链接] [评论]」。
_RE_RD_TAIL = re.compile(r"submitted\s+by\s*(?:/u/|u/)\S*[\s\S]*$", re.I)


def is_placeholder_body(body):
    """正文去掉 RSS 模板尾巴后为空 → 纯图 / 纯链接帖，没有可读内容。"""
    s = _RE_RD_BOILER.sub(" ", body or "")
    return not re.sub(r"[\s\W_]+", "", s)


def clean_body(s):
    """去掉论坛正文里混进来的页面导航、图片占位、链接残留。"""
    s = s or ""
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = _RE_RD_TAIL.sub(" ", s)      # Reddit RSS 尾巴（含真实正文的帖子也带）
    s = _RE_IMG_MD.sub(" ", s)
    s = _RE_MD_LINK.sub(r"\1", s)
    s = _RE_URL.sub(" ", s)
    s = _RE_DIM.sub(" ", s)
    s = _RE_KB.sub(" ", s)
    s = _RE_BARE_DOMAIN.sub(" ", s)
    # 行内空白压缩，但保留段落
    lines = [_RE_WS.sub(" ", ln).strip() for ln in s.split("\n")]
    lines = [ln for ln in lines if ln]
    # 完全重复的句子只留一次（论坛模板文案会重复整段）
    out, seen = [], set()
    for ln in lines:
        key = re.sub(r"\W+", "", ln.lower())[:60]
        if len(key) >= 12 and key in seen:
            continue
        seen.add(key)
        out.append(ln)
    s = "\n".join(out)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def truncate(s, limit=BODY_LIMIT):
    """截断到 limit 字符，尽量落在句子边界。返回 (text, truncated)。"""
    if len(s) <= limit:
        return s, False
    cut = s[:limit]
    # 在最后 180 字内找一个句子边界
    m = None
    for m2 in re.finditer(r"[.!?。！？]\s", cut[-220:]):
        m = m2
    if m:
        cut = cut[: len(cut) - 220 + m.end()] if len(cut) > 220 else cut[: m.end()]
    return cut.rstrip() + " …", True


# ---------------------------------------------------------------- 版本
_RE_VER2 = re.compile(r"^(\d{1,2})\.(\d{1,2})")


def norm_version(v):
    """7.3.0.6141 -> 7.3 ；7 -> 7 ；12.3 -> 12.3"""
    v = (v or "").strip()
    if not v:
        return ""
    m = _RE_VER2.match(v)
    if m:
        return m.group(1) + "." + m.group(2)
    m = re.match(r"^(\d{1,2})$", v)
    if m:
        return m.group(1)
    return v


def major_of(v):
    v = norm_version(v)
    m = re.match(r"^(\d{1,2})", v or "")
    return m.group(1) + ".x" if m else ""


# ---------------------------------------------------------------- 实现路径归段
# 2026-10-20 用户定稿：软件专栏按「用户实现路径」组织，不再按产品线。
# 六段 = 找模型 → AI 生成 → 建模改模 → 切片 → 打印运维 → 分享变现。
# 归不到任何一段的（软件自身 UI / 安装 / 升级 / 文件管理）标「跨环节」，
# 不硬塞进路径 —— 它确实不对应路径上的某一环，塞进去会污染段占比。
STAGE_META = [
    ("S1", "找模型", "在模型库 / 社区找模型、下载 3MF / STL、看模型详情"),
    ("S2", "AI 生成", "文生 3D / 图生 3D / MakeNow·CubeMe·SignForge 生成模型"),
    ("S3", "建模改模", "Blender / Fusion / CAD / 布尔 / 修网格 / 缩放"),
    ("S4", "切片", "切片器参数：层高 / 填充 / 支撑 / 接缝 / 材料 / 多色"),
    ("S5", "打印运维", "固件 / 首层 / 堵头 / 断料 / 联网 / 远程 / 故障"),
    ("S6", "分享变现", "上传模型 / 创作中心 / 积分 / 佣金 / 比赛"),
]
STAGE_ORDER = ["S1", "S2", "S3", "S4", "S5", "S6"]
STAGE_NAME = {k: v for k, v, _ in STAGE_META}

# 顺序敏感：越靠前越先判；宽词类目往后。
# 两级匹配：先只看标题（避免正文提一句 slice 就把固件帖判成切片），标题全不中再看正文。
_STAGE_RULES = [
    ("S2", [r"make\s*now", r"maknow", r"cube\s*me", r"sign\s*forge",
            r"\bai\b.{0,12}(生成|建模|生成模型|design|model)", r"文生|图生",
            r"text[-\s]?to[-\s]?3d", r"image[-\s]?to[-\s]?3d", r"photo[-\s]?to[-\s]?3d",
            r"generative", r"生成模型"]),
    ("S5", [r"firmware", r"固件", r"klipper", r"homing", r"归零", r"bed\s*level", r"调平",
            r"\bclog", r"堵头", r"\bjam\b", r"runout", r"断料", r"翘边", r"\bwarp",
            r"power\s*loss", r"断电", r"shut\s*down", r"won'?t\s+turn", r"摄像头",
            r"\bcamera\b", r"time\s*lapse", r"start\s*printing\s+at"]),
    ("S6", [r"designer\s*award", r"commission", r"佣金", r"变现", r"creator\s*(program|center)",
            r"monetiz", r"sell\s+(model|design)", r"上传模型", r"分享模型", r"积分",
            r"\bcoins?\b", r"leaderboard", r"排行榜", r"创作者中心", r"\breward", r"баллы",
            r"\bshop\b", r"\bcontest\b", r"member\s*exclusive"]),
    ("S1", [r"3d\s*printer\s*files", r"\b3mf\s*file", r"\bstl\s*file", r"model\s*library", r"模型库",
            r"download\w*\s+model", r"模型下载", r"下载模型", r"find\s+(a\s+)?model", r"搜索模型",
            r"search\s+model", r"model\s*gallery", r"模型预览", r"sculptured_re",
            r"designer\s*award", r"\bcollection\b", r"\bcategories\b",
            r"web\s*editor", r"create-model", r"edittype"]),
    ("S3", [r"blender", r"fusion\s*360", r"freecad", r"onshape", r"tinkercad", r"shapr3d",
            r"solidworks", r"3dconnexion", r"3d\s*mouse", r"\bcad\b", r"\bboolean",
            r"remesh", r"repair\s+mesh", r"non[-\s]?manifold", r"修改模型", r"建模",
            r"挖空", r"\bhollow", r"\bsculpt", r"align\s+to\s+the", r"缩放模型",
            r"design\s*space", r"photoshop"]),
    ("S4", [r"\bslic(e|er|ers|ing)\b", r"切片", r"orca\s*slicer", r"\bcura\b", r"prusa\s*slicer",
            r"bambu\s*studio", r"super\s*slicer", r"\bprofile", r"\bpreset", r"\binfill",
            r"填充", r"layer\s*height", r"层高", r"\bsupport(s|ed|ing)?\b", r"支撑", r"g-?code",
            r"\bseam", r"接缝", r"retraction", r"回抽", r"overhang", r"悬垂", r"\bbridge",
            r"\bbrim\b", r"\braft\b", r"\bskirt\b", r"purg(e|ing)", r"\bwalls?\s+count",
            r"\bsparse\b", r"build\s*plate", r"first\s*layer", r"首层", r"start_print", r"\bkamp\b",
            r"printer\s*settings", r"print\s*settings", r"material\s*settings", r"process(es)?\b",
            r"wipe\s*tower", r"cooling\s*fan", r"fuzzy\s*skin", r"material\s*index",
            r"consumable", r"filament\s*(param|chang|sett)", r"color\s*mixing",
            r"print(ing)?\s*time", r"select\s+filament", r"\bmulti\s*colou?r", r"\d+\s*colou?r"]),
    ("S5", [r"print\w*\s+(stop|fail)", r"failed\s+print", r"error", r"\bcrash",
            r"connect", r"连接", r"\bwifi\b", r"network", r"\bremote\b", r"远程",
            r"\bpause", r"暂停", r"\bcancel", r"resume", r"续打", r"nozzle", r"热床",
            r"temperature", r"温度", r"extruder", r"风扇", r"\bfan\b", r"z-offset",
            r"\boffset\b", r"\baxis\b", r"\bapp\b", r"\blogin\b", r"登录"]),
]
_STAGE_FALLBACK = {"firmware": "S5", "park": "S6", "thirdparty": "S4"}

# 工具识别（替代失效的「产品线」维度）：竞品被提及 = 用户在拿别家对标
_TOOL_COMPETITOR = [r"orca\s*slicer", r"\borca\b", r"\bcura\b", r"prusa\s*slicer",
                    r"super\s*slicer", r"bambu\s*studio", r"\bbambu\b", r"slic3r",
                    r"octoprint", r"fluidd", r"mainsail", r"\bkamp\b",
                    r"idea\s*maker", r"simplify3d"]
_TOOL_SELF = [r"creality\s*print", r"creality\s*slicer", r"creality\s*cloud",
              r"crealitycloud", r"creality\s*app", r"\bfalcon\b", r"creality\s*park",
              r"\bcfs\b", r"creality\s*scan"]
TOOL_NAME = {"self": "自家工具", "competitor": "竞品工具", "": "未提具体工具"}


def stage_of(it):
    t = (it.get("title") or "").lower()
    b = t + " " + (it.get("originalText") or "").lower()
    for code, pats in _STAGE_RULES:
        for p in pats:
            if re.search(p, t):
                return code
    for code, pats in _STAGE_RULES:
        for p in pats:
            if re.search(p, b):
                return code
    return _STAGE_FALLBACK.get(it.get("productLine") or "", "")


def tool_of(it):
    b = ((it.get("title") or "") + " " + (it.get("originalText") or "")).lower()
    for p in _TOOL_COMPETITOR:
        if re.search(p, b):
            return "competitor"
    for p in _TOOL_SELF:
        if re.search(p, b):
            return "self"
    return ""


# ---------------------------------------------------------------- 主流程
def norm_sw(items):
    out = []
    dropped = 0
    for it in items:
        body = clean_body(it.get("originalText") or "")
        if is_placeholder_body(body):
            dropped += 1
            continue
        body, cut = truncate(body)
        raw = it.get("version") or ""
        out.append({
            "uid": it["uid"],
            "date": (it.get("date") or "")[:10],
            "platform": it.get("platform") or "",
            "site": it.get("site") or it.get("platform") or "",
            "channel": it.get("channel") or "官方论坛",
            "country": it.get("country") or "",
            "language": it.get("language") or "",
            "title": (it.get("title") or "").strip(),
            "titleCn": it.get("titleCn") or "",
            "originalText": body,
            "textCn": it.get("textCn") or "",
            "truncated": cut,
            "url": it.get("url") or "",
            "productLine": it.get("productLine") or "",
            "version": norm_version(raw),
            "versionRaw": raw,
            "problemType": it.get("problemType") or "",
            "model": it.get("model") or "",
            "grade": it.get("grade") or "",
            "stage": it.get("stage") or stage_of(it),
            "tool": it.get("tool") or tool_of(it),
            "replyCount": it.get("replyCount") or 0,
            "views": it.get("views") or 0,
            "likeCount": it.get("likeCount") or 0,
            # 2026-10-27：本专栏扩到全行业多信源，sourceType 必须透传。
            # 原实现硬编 "论坛"，会把 Reddit/B站/YouTube/什么值得买全标成论坛。
            "sourceType": it.get("sourceType") or "论坛",
            # 导购类（什么值得买）不是用户反馈，不计入声量 —— 与 GitHub 缺陷单「单列」同理。
            "countInVolume": it.get("countInVolume", True),
            "price": it.get("price") or "",
            "author": it.get("author") or "",
            "flair": it.get("flair") or "",
        })
    out.sort(key=lambda x: (x["date"], x["uid"]), reverse=True)
    if dropped:
        print("  剔除无正文条目（RSS 模板尾巴）: %d" % dropped)
    return out


def norm_mbox(items):
    out = []
    for it in items:
        body = clean_body(it.get("originalText") or "")
        body, cut = truncate(body)
        # 2026-10-26：中文原文不产生「译文」段（B站 titleCn == title，会重复两行）
        title = (it.get("title") or "").strip()
        title_cn = it.get("titleCn") or ""
        text_cn = it.get("textCn") or ""
        if (it.get("language") or "").upper() == "ZH" or title_cn.strip() == title:
            title_cn, text_cn = "", ""
        out.append({
            "uid": it["uid"],
            "date": (it.get("date") or "")[:10],
            "platform": it.get("platform") or "",
            "site": it.get("site") or it.get("platform") or "",
            "channel": it.get("channel") or "",
            "country": it.get("country") or "",
            "language": it.get("language") or "",
            "title": title,
            "titleCn": title_cn,
            "originalText": body,
            "textCn": text_cn,
            "truncated": cut,
            "url": it.get("url") or "",
            "productLine": "",
            "version": "",
            "versionRaw": "",
            "problemType": "",
            "model": "mBox",
            "grade": "",
            "replyCount": 0,
            "views": it.get("views") or 0,
            "likeCount": 0,
            "sourceType": it.get("sourceType") or "媒体",
            # 2026-10-27：mBox 接入 什么值得买（导购/竞品价格带），必须透传「不计声量」与价格，
            # 否则 9 条整机好价会被当作用户声量计入 KPI。
            "countInVolume": it.get("countInVolume", True),
            "price": it.get("price") or "",
            # 仅展示用的辅助字段
            "author": it.get("author") or "",
            "signal": it.get("signal") or "",
            "mirrorOf": it.get("mirrorOf") or "",
            "foundBy": it.get("foundBy") or "",
        })
    out.sort(key=lambda x: x["date"], reverse=True)
    return out


def norm_fc(items):
    """全彩专栏（P7）。契约在规范 §四 之上多四个字段：

    model / tier / techRoute  机型与技术档次 —— 桌面三台 + 专业一台 + 工业两台各建卡
                              （2026-10-27 定桌面/工业两档；2026-10-28 加赛纳，其 D450 是
                              桌面形态但 $70k 工业价位，故单列「专业」档），
                              所以「档次」必须落成字段，否则护栏 A（分档呈现、不出全彩平均）没有依据
    discussLevel / heatScore  讨论度分档与排序权重 —— 用户要求「主要集中于讨论度比较高的帖子」，
                              默认排序按它降序，不按日期
    """
    out = []
    dropped = 0
    for it in items:
        body = clean_body(it.get("originalText") or "")
        if is_placeholder_body(body):
            dropped += 1
            continue
        body, cut = truncate(body)
        title = (it.get("title") or "").strip()
        lang = (it.get("language") or "").upper()
        # 中文原文不产生译文段：B站采集器会把 titleCn 直接设成 title，
        # 不清掉卡片上会出现两行一模一样的标题（与 norm_mbox 同一处理）
        title_cn = it.get("titleCn") or ""
        text_cn = it.get("textCn") or ""
        if lang == "ZH" or title_cn.strip() == title:
            title_cn, text_cn = "", ""
        out.append({
            "uid": it["uid"],
            "date": (it.get("date") or "")[:10],
            "publishedAt": (it.get("publishedAt") or it.get("date") or "")[:10],
            "dateGuessed": bool(it.get("dateGuessed")),
            "platform": it.get("platform") or "",
            "site": it.get("site") or it.get("platform") or "",
            "channel": it.get("channel") or "",
            "country": it.get("country") or "",
            "language": lang,
            "title": title,
            "titleCn": title_cn,
            "originalText": body,
            "textCn": text_cn,
            "truncated": cut,
            "url": it.get("url") or "",
            "sourceType": it.get("sourceType") or "用户",
            "countInVolume": it.get("countInVolume", True),
            "model": it.get("model") or "",
            "tier": it.get("tier") or "",
            # 技术路线按机型兜底，不搞一刀切 MJP —— 赛纳走的是 WJP 体素喷墨（2026-10-28 接入）
            "techRoute": it.get("techRoute") or ("WJP 体素喷墨" if (it.get("model") == "Sailner") else
                                                ("" if not it.get("model") else "MJP 喷墨")),
            "heat": it.get("heat") or "",
            "heatRaw": it.get("heatRaw") or {},
            "heatScore": int(it.get("heatScore") or 0),
            "discussLevel": it.get("discussLevel") or "low",
            "heatSource": it.get("heatSource") or "",
            "author": it.get("author") or "",
            "grade": "",
        })
    out.sort(key=lambda x: (-(x.get("heatScore") or 0), x.get("date") or ""))
    if dropped:
        print("  剔除无正文条目（RSS 模板尾巴）: %d" % dropped)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", required=True, choices=["sw", "mbox", "fc"])
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    a = ap.parse_args()

    d = json.load(io.open(a.inp, encoding="utf-8"))
    items = d.get("items") if isinstance(d, dict) else d
    fn = {"sw": norm_sw, "mbox": norm_mbox, "fc": norm_fc}[a.kind]
    out = fn(items)

    io.open(a.out, "w", encoding="utf-8").write(
        json.dumps(out, ensure_ascii=False, indent=1))

    # 2026-10-26：sidecar —— 把「抓取时刻 / 信源探针 / 成败计数」带给页面生成器。
    # norm 产物本身是纯列表（页面直接吃），元信息若混进去会污染卡片渲染，所以分文件。
    if isinstance(d, dict):
        probes = d.get("probes") or d.get("sources") or []
        err_n = sum(1 for p in (probes or [])
                    if isinstance(p, dict) and p.get("status") in ("error", "fail"))
        side = {
            "fetchedAt": d.get("fetchedAt") or d.get("updatedAt")
                         or time.strftime("%Y-%m-%d %H:%M"),
            "probes": probes,
            "stats": dict(d.get("stats") or {}, sourcesError=err_n,
                          sourcesTotal=len(probes or [])),
        }
        io.open(a.out + ".meta.json", "w", encoding="utf-8").write(
            json.dumps(side, ensure_ascii=False, indent=1))
        print("  sidecar -> %s.meta.json（探针 %d 个 / 异常 %d 个）"
              % (a.out, len(probes or []), err_n))

    cut = sum(1 for x in out if x["truncated"])
    print("归一化 %d 条 -> %s" % (len(out), a.out))
    print("  正文被截断: %d" % cut)
    if a.kind == "fc":
        print("  讨论度: %s" % dict(Counter(x["discussLevel"] for x in out).most_common()))
        print("  平台  : %s" % dict(Counter(x["platform"] for x in out).most_common()))
        print("  机型  : %s" % dict(Counter(x["model"] or "未标注" for x in out).most_common()))
        print("  档次  : %s" % dict(Counter(x["tier"] or "未标注" for x in out).most_common()))
        print("  热度来源: %s" % dict(Counter(x["heatSource"] for x in out).most_common()))
        print("  日期靠采集日兜底: %d 条" % sum(1 for x in out if x["dateGuessed"]))
        return
    print("  版本(归一): %d 个 -> %s" % (
        len(set(x["version"] for x in out if x["version"])),
        dict(Counter(x["version"] for x in out if x["version"]).most_common(8))))
    print("  主版本: %s" % dict(Counter(major_of(x["version"]) for x in out if x["version"]).most_common()))
    print("  问题类型: %s" % dict(Counter(x["problemType"] or "(无)" for x in out).most_common()))
    if a.kind == "sw":
        sc = Counter(x["stage"] or "跨环节" for x in out)
        cov = len(out) - sc["跨环节"]
        print("  实现路径归段: %d/%d (%.1f%%)  %s" % (
            cov, len(out), cov / len(out) * 100 if out else 0,
            {STAGE_NAME.get(k, k): v for k, v in sorted(sc.items())}))
        print("  工具结构: %s" % dict(Counter(TOOL_NAME.get(x["tool"], x["tool"]) for x in out).most_common()))
    print("  待翻译(titleCn/textCn 均为空): %d" % sum(
        1 for x in out if not x["titleCn"] and re.search(r"[\u4e00-\u9fff]", x["title"] + x["originalText"]) is None))


if __name__ == "__main__":
    main()
