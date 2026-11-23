#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_h3c_collect.py — 拓竹 H3C 专栏最小采集器（第五个专栏的上游）

职责边界（与 K3 / 全彩同一纪律）
--------------------------------------------------------------------------
只做「抓取 + 去重 + 热度判定」，产出候选池 JSON。
**不写语义字段**：sentiment / topics / problemPoints 都是语义判断，
自动猜等于往页面写假结论。候选池经人工确认后才由注入器上页。

为什么这个采集器第一件事是「排除新华三」
--------------------------------------------------------------------------
H3C 是**双主体代号**：
  * 拓竹（Bambu Lab）2026-11-03 发布的九头旗舰 H3C
  * 新华三（New H3C）的路由器 / 交换机 / 无线 AP，型号同样以 H3C 命名
在 B 站直接搜「H3C」，返回的绝大多数是新华三设备评测。
不做主体闸门的采集器会把一池交换机视频灌进 3D 打印专栏 —— 这个坑必须一开始就堵。

所以 gate 是**双向**的：
  必须含 3D 打印语境（拓竹 / Bambu / 3D打印 / 喷嘴 / 耗材 / 挤出 / 打印头…）
  且命中 H3C 专属线索（H3C / Swaptek / AMS 3H / 九头闪切）
  且不含新华三特征（交换机 / 路由器 / AP / 无线 / 网络设备 / H3C 交换机型号 …）

三层信源（与全彩一致）
--------------------------------------------------------------------------
  L1 自动     B站 —— 全自动检索（关键词语义靠 gate 兜底）
  L2 手动种子 URL 列表 —— 什么值得买 / 官方 / 媒体，由人或 Agent 补 URL
  L3 不可自动 小红书 / 抖音 / 知乎 —— 只进覆盖清单，不填数

用法
--------------------------------------------------------------------------
  python _h3c_collect.py                      # B站 全跑，近 7 天
  python _h3c_collect.py --days 0             # 不限窗口（首次建池）
  python _h3c_collect.py --min-signal low     # 放宽热度门槛
  python _h3c_collect.py --seed _h3c_seed.json
  python _h3c_collect.py --out _h3c_candidates.json
"""
import argparse
import datetime
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

OUT_DEFAULT = os.path.join(HERE, "_h3c_candidates.json")

# ── 检索关键词（两个主体都要覆盖，gate 会把非 3D 打印的挡掉）──────────
BILI_KEYWORDS = [
    "拓竹 H3C",
    "Bambu H3C",
    "H3C 3D打印",
    "拓竹 H3C 开箱",
    "拓竹 H3C 实测",
    "拓竹 H3C 翻车",
    "Swaptek 九头",
    "拓竹 AMS 3H",
    "H3C 九头 打印",
    "拓竹 九喷嘴",
]

# ── 3D 打印语境（必须命中其一）────────────────────────────────────────
CTX_3DP = ("拓竹", "bambu", "3d打印", "3d 打印", "打印机", "打印头", "喷嘴", "喷头",
           "耗材", "挤出", "pla", "tpu", "ams", "swaptek", "层纹", "打印")

# ── H3C 专属线索（必须命中其一，防止「拓竹 A1 评测」这类蹭进来）────────
H3C_SIGNALS = ("h3c", "swaptek", "ams 3h", "ams3h", "九头", "9头", "九喷嘴")

# ── 新华三 / 网络设备噪声（命中即丢，不管别的条件）────────────────────
NOISE = re.compile(
    r"新华三|交换机|路由器|无线ap|无线 ?ap|ac控制器|防火墙|光模块|服务器|存储阵列|"
    r"网络设备|组网|vlan|poe|万兆|核心交换机|接入交换机|h3c\s?s\d|h3c\s?er|h3c\s?msr|"
    r"h3c\s?wa|h3c\s?u-?ap|交换机配置|路由配置|华为|思科|锐捷|迈普",
    re.I)


def noise(title, desc):
    return bool(NOISE.search("%s %s" % (title or "", desc or "")))


def gate(title, desc):
    """主体闸门：3D 打印语境 ∧ H3C 线索 ∧ 非新华三。"""
    s = ("%s %s" % (title or "", desc or "")).lower()
    if noise(title, desc):
        return False
    if not any(k in s for k in CTX_3DP):
        return False
    return any(k in s for k in H3C_SIGNALS)


# ── 热度（H3C 首发期样本稀薄，门槛低于 K3：首周实测视频播放几千已是有效样本）
def heat_level(views, reviews):
    if views >= 20000 or reviews >= 100:
        return "high"
    if views >= 3000 or reviews >= 15:
        return "mid"
    if views >= 300:
        return "low"
    return "thin"


LEVEL_OK = {"high": 3, "mid": 2, "low": 1, "thin": 0}
MIN_LEVEL = {"high": 3, "mid": 2, "low": 1}


def norm_link(u):
    u = (u or "").strip()
    u = re.sub(r"[?#].*$", "", u)
    return u.rstrip("/").lower()


def load_json(p, default):
    try:
        with io.open(p, encoding="utf-8") as f:
            return json.load(f)
    except (IOError, OSError, ValueError):
        return default


def write_json(p, obj):
    tmp = p + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(obj, ensure_ascii=False, indent=2))
    os.replace(tmp, p)


def collect_bili(days, sources, errors):
    try:
        import _bili_search as B
    except Exception as e:
        errors.append({"site": "B站", "query": "(import)", "err": str(e)[:160]})
        return []

    raw, src, err = B.search(BILI_KEYWORDS, gate=gate, ctx=CTX_3DP, days=days,
                             exclude=noise, label="B站")
    sources.extend(src)
    errors.extend(err)

    out = []
    for it in raw:
        title = it.get("title") or ""
        text = it.get("originalText") or ""
        # 二次闸门：_bili_search 的 ctx 只用于关键词侧过滤，落库前再判一次主体
        if not gate(title, text):
            continue
        v = int(it.get("views") or 0)
        m = re.search(r"评论\s*([\d.]+万?)", it.get("heat") or "")
        rv = 0
        if m:
            try:
                rv = int(float(m.group(1).replace("万", "")) * (10000 if "万" in m.group(1) else 1))
            except ValueError:
                rv = 0
        out.append({
            "sourceLink": it.get("sourceLink") or "",
            "platform": it.get("platform") or "B站",
            "title": title,
            "author": it.get("author") or "",
            "publishedAt": it.get("publishedAt") or "",
            "originalText": text[:600],
            "views": v,
            "reviews": rv,
            "heatLevel": heat_level(v, rv),
            "collectMethod": "search",
            "channel": "国内",
            "country": "CN",
            "language": "ZH",
        })
    return out


def collect_seed(path, sources, errors):
    """L2：人工/Agent 给的 URL 种子。本版只登记，不抓正文 ——
    smzdm 等站点的正文要单独处理反爬，不在「最小采集器」范围内。"""
    if not path or not os.path.exists(path):
        return []
    d = load_json(path, {})
    rows = d.get("urls") or d if isinstance(d, list) else d.get("urls") or []
    out = []
    for r in rows:
        if isinstance(r, str):
            r = {"sourceLink": r}
        u = (r.get("sourceLink") or "").strip()
        if not u:
            continue
        out.append({
            "sourceLink": u,
            "platform": r.get("platform") or "",
            "title": r.get("title") or "",
            "author": r.get("author") or "",
            "publishedAt": r.get("publishedAt") or "",
            "originalText": r.get("originalText") or "",
            "views": 0, "reviews": 0,
            "heatLevel": "unknown",
            "collectMethod": "seed",
            "channel": r.get("channel") or "国内",
            "country": r.get("country") or "CN",
            "language": r.get("language") or "ZH",
        })
    sources.append({"channel": "种子", "step": "seed", "code": 200, "accepted": len(out)})
    return out


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--min-signal", default="low", choices=list(MIN_LEVEL))
    ap.add_argument("--only", default="", choices=["", "bili", "seed", "reddit"])
    ap.add_argument("--seed", default=os.path.join(HERE, "_h3c_seed.json"))
    ap.add_argument("--out", default=OUT_DEFAULT)
    a = ap.parse_args(argv)

    sources, errors, rows = [], [], []
    if a.only in ("", "bili"):
        rows += collect_bili(a.days, sources, errors)
    if a.only in ("", "seed"):
        rows += collect_seed(a.seed, sources, errors)
    if a.only in ("", "reddit"):
        # 2026-11-23 用户决策：H3C 与其余五页统一接入 Reddit。
        # 先探通道再决定要不要真抓 —— 匿名 RSS 已关闭时硬抓要等 3 个子版
        # × (7s 间隔 + 20/45s 退避) ≈ 4 分钟，白等还拖累本链时限。
        try:
            import _h3c_reddit
            st, detail = _h3c_reddit.probe()
        except Exception as e:
            st, detail = "error", {"err": type(e).__name__}
        if st == "ok":
            rows += _h3c_reddit.collect(a.days, sources, errors)
        else:
            sources.append({
                "source": "Reddit", "status": st, "count": 0,
                "note": "匿名 RSS 已关闭（需 OAuth 凭据），本次跳过抓取",
                "detail": detail,
            })

    # 去重：链接 + 标题双键（同一条会被多个关键词搜到）
    seen, uniq = set(), []
    for r in rows:
        k1 = norm_link(r["sourceLink"])
        k2 = re.sub(r"\s+", "", r.get("title") or "")[:40]
        if (k1 and k1 in seen) or (k2 and k2 in seen):
            continue
        if k1:
            seen.add(k1)
        if k2:
            seen.add(k2)
        uniq.append(r)

    floor = MIN_LEVEL[a.min_signal]
    kept = [r for r in uniq if r["heatLevel"] == "unknown" or LEVEL_OK[r["heatLevel"]] >= floor]

    # 与已有候选池合并（保留人工已确认的标注字段）
    old = load_json(a.out, {})
    old_rows = old.get("items") or [] if isinstance(old, dict) else []
    by_link = {norm_link(x.get("sourceLink")): x for x in old_rows if x.get("sourceLink")}
    added = 0
    for r in kept:
        k = norm_link(r["sourceLink"])
        if k in by_link:
            base = by_link[k]
            for f in ("title", "views", "reviews", "heatLevel", "originalText"):
                if not base.get(f):
                    base[f] = r[f]
            continue
        by_link[k] = r
        added += 1
    merged = list(by_link.values())

    out = {
        "column": "h3c",
        "generatedAt": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "window_days": a.days,
        "min_signal": a.min_signal,
        "counts": {"fetched": len(rows), "after_dedupe": len(uniq),
                   "after_heat_floor": len(kept), "new": added, "pool_total": len(merged)},
        "sources": sources,
        "errors": errors,
        "items": merged,
    }
    write_json(a.out, out)

    print("抓取 %d · 去重后 %d · 过热度门槛 %d · 新增 %d · 池内共 %d"
          % (len(rows), len(uniq), len(kept), added, len(merged)))
    for e in errors[:5]:
        print("  err  %s %s: %s" % (e.get("site"), e.get("query"), e.get("err")))
    print("→ %s" % a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
