# -*- coding: utf-8 -*-
"""光固化专栏 · 机型/品牌归属判定（采集层与注入层共用同一份实现）

为什么单独抽出来
----------------
V1.1 的 model_of() 写在 _resin_collect.py 里，用子串匹配：

    for a in [m["name"]] + m["aliases"]:
        if a.lower() in text.lower():     # ← BUG

裸别名 MAGE 会命中 im**age**、RAY 会命中 g**ray** / a**rray**、ONE 会命中任意 one。
2026-11-13 复核 30 条存量样本，5 条机型归属错误或缺失（17%）：SKY→MAGE、ONE→MAGE、
LITE→None、MAGE→None、SKY→None。

修法
----
1. 词边界正则 `(?<![a-z0-9])alias(?![a-z0-9])`，杜绝子串误命中；
2. 别名按长度降序匹配（最长匹配优先），保证 "Saturn 4 Ultra 16K" 不被 "Saturn 4 Ultra" 抢走；
3. 配置层 modelAliasBlock 显式禁掉 one / max / ray / mage 等裸通用词，双保险。

层级
----
采集层：新条目入库时判定一次；
注入层：**每次注入都按当前别名表重算**，所以改别名表或改机型谱系后，历史条目的
归属会自动纠正，不需要清空 seen 重采。
"""
import json
import os
import re

BASE = os.path.dirname(os.path.abspath(__file__))
CFG_PATH = os.path.join(BASE, "resin_config.json")

_cache = {}


def load_cfg():
    """读取并缓存配置；文件 mtime 变化时重载，便于同进程内改配置后立即生效。"""
    try:
        mt = os.path.getmtime(CFG_PATH)
    except OSError:
        mt = 0
    if _cache.get("mtime") != mt:
        with open(CFG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
        _cache["cfg"] = cfg
        _cache["mtime"] = mt
        _cache["pat"] = _build(cfg)
        _cache["brands"] = {b["code"]: b for b in cfg.get("brands") or []}
    return _cache["cfg"]


def _build(cfg):
    block = set(a.lower() for a in (cfg.get("modelAliasBlock") or []))
    pairs = []
    for m in cfg.get("models") or []:
        for a in [m["name"]] + list(m.get("aliases") or []):
            a = (a or "").strip()
            if not a or a.lower() in block:
                continue
            pairs.append((a, m))
    pairs.sort(key=lambda x: -len(x[0]))          # 最长匹配优先
    out = []
    for a, m in pairs:
        rx = re.compile(r"(?<![a-z0-9])" + re.escape(a.lower()) + r"(?![a-z0-9])", re.I)
        out.append((rx, m))
    return out


def _norm(text):
    """把 hashtag 拆成词：`#CrealityHalotR6` → ` Creality Halot R6 `。

    社交平台（B站/什么值得买/YouTube 简介）常用连写 hashtag，词边界正则会把
    `#CrealityHalotR6` 当成一个词从而漏判机型。只对 # 后那段做 CamelCase 拆分，
    不动正文，避免误伤正常英文。
    """
    def sp(m):
        w = m.group(1)
        w = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", w)
        return " " + w + " "
    return re.sub(r"#(\w+)", sp, text or "")


def model_of(text):
    """返回 (modelCode, modelName, brandCode)；未命中返回 (None, None, None)。"""
    load_cfg()
    t = _norm(text).lower()
    if not t:
        return None, None, None
    for rx, m in _cache["pat"]:
        if rx.search(t):
            return m["code"], m["name"], m.get("brand")
    return None, None, None


def brand_of_model(code):
    load_cfg()
    for m in _cache["cfg"].get("models") or []:
        if m["code"] == code:
            return m.get("brand")
    return None


def competitor_hits(text):
    """返回文本里被点名的竞品机型名列表（同一机型只记一次）。"""
    cfg = load_cfg()
    own = set(b["code"] for b in (cfg.get("brands") or []) if b.get("isOwn"))
    if not own:
        own = {"creality"}                     # 旧配置兜底：未声明 brands 时只有自家算 own
    t = (text or "").lower()
    if not t:
        return []
    out = []
    for rx, m in _cache["pat"]:
        if (m.get("brand") or "creality") in own:
            continue
        if rx.search(t) and m["name"] not in out:
            out.append(m["name"])
    return out


def hits_by_side(text):
    """文本级双向点名：返回 ([我方机型...], [竞品机型...])，元素为 (name, brand, code)。

    为什么需要：机型归属是「单赢家」——一条 "Creality Halot-Mage S vs Elegoo
    Saturn 4 Ultra 16K" 只会归给别名更长的那一方（此处归竞品）。如果只看
    「我方样本里的竞品点名」，这类真正的对比语境会全部落进竞品桶，上段永远为 0。
    所以对比语境必须按文本双向命中判定，不看这条最终归给谁。
    """
    cfg = load_cfg()
    own = set(b["code"] for b in (cfg.get("brands") or []) if b.get("isOwn"))
    if not own:
        own = {"creality"}
    t = (text or "").lower()
    if not t:
        return [], []
    o, c = [], []
    for rx, m in _cache["pat"]:
        if not rx.search(t):
            continue
        item = (m["name"], m.get("brand") or "creality", m["code"])
        if item[1] in own:
            if item not in o:
                o.append(item)
        elif item not in c:
            c.append(item)
    return o, c


def brand_hits(text):
    """机型未命中时按品牌词兜底。返回 {brandCode: 命中数}，不返回空命中。

    用途：论坛里大量帖子只说「Creality / HALOT / Halot Box」而不点具体机型，
    全部落到「未归属」会让机型维度失真。兜底到品牌级后，页面显示品牌 chip
    而不是「未归属机型」，矩阵里也能看到「品牌级（未指定机型）」这一行。
    """
    cfg = load_cfg()
    hints = cfg.get("brandHints") or {}
    t = _norm(text).lower()
    if not t:
        return {}
    out = {}
    for code, words in hints.items():
        if code.startswith("_"):
            continue
        n = 0
        for w in words or []:
            w = w.lower()
            if re.fullmatch(r"[a-z0-9 ]+", w):
                if re.search(r"(?<![a-z0-9])" + re.escape(w) + r"(?![a-z0-9])", t):
                    n += 1
            elif w in t:
                n += 1
        if n:
            out[code] = n
    return out


def best_brand(text):
    """按命中数取最强品牌；同分时优先自家（论坛主源是 Creality 官方论坛）。"""
    hits = brand_hits(text)
    if not hits:
        return None
    own = set(b["code"] for b in (load_cfg().get("brands") or []) if b.get("isOwn"))
    return sorted(hits.items(), key=lambda kv: (-kv[1], 0 if kv[0] in own else 1))[0][0]


def brand_meta(code):
    load_cfg()
    return _cache["brands"].get(code) or {}


def is_own_brand(code):
    return bool(brand_meta(code).get("isOwn"))
