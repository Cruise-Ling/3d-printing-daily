# -*- coding: utf-8 -*-
"""_col_channels.py — 七个专栏的信源口径单一来源（2026-11-23）

为什么要有这个文件
--------------------------------------------------------------------------
页面上的「渠道」筛选器（platform）一直是**纯数据驱动**的：ITEMS 里出现过的
platform 才出 chip。这造成一个致命的表达缺陷 ——

    「这个渠道今天 0 条」和「这个渠道根本不在采集范围」在页面上长得一模一样。

2026-11-23 用户提出「Reddit 有些专栏没接入」，排查后发现：Reddit 匿名通道
在 11-07 前后被 Reddit 关闭，K3 留下 38 条历史存量、光固化 2 条，其余四页
0 条。但页面只显示「没有 Reddit 这个 chip」，读起来像「人家没讨论」，
而不是「我们采不到」。这个文件就是为了让页面能说清这件事。

口径纪律
--------------------------------------------------------------------------
1. `platforms` 声明的是**采集器实际接入的源**，不是当前有数据的源。
   数据为 0 也要声明，否则页面又退回「没数据 = 没接入」的糊涂账。
2. 声明集合由采集器代码决定，改采集器必须同步改这里（四套校验器有断言）。
3. Reddit 的 lastOk 来自采集日志，不来自猜测：
   - K3       2026-11-07（页面 38 条 Reddit 的最大 publishedAt）
   - 软件     2026-11-10（_log_sw.log：Reddit 71 条）
   - 全彩     2026-11-10（_log_fc.log：Reddit 23 条）
   - mBox     无（_log_mbox.log 仅 Creality ok 1，未入池）
   - H3C      无（从未接入，2026-11-23 本次补）
   - 光固化   无（2 条为历史遗留，无日期）
"""

import datetime

# ---------------------------------------------------------------- 通道状态

# Reddit 匿名通道已于 2026-11-07 前后关闭。证据（2026-11-23 实测）：
#   www.reddit.com/r/x/new.rss   → 404 / 429，x-ratelimit-remaining: 0.0
#   old.reddit.com/r/x/new.rss   → 200 但 341KB HTML，302 跳 login?reason=lor2
#   www.reddit.com/.../new.json  → 403
#   RSSHub 四公共实例             → 403 / 503 / 404 / URLError
#   api.pullpush.io              → 429
#   www.reddit.com/api/v1/access_token → 401（唯一可达，缺 OAuth 凭据）
# 结论：OAuth 是唯一活路；凭据未提供前，本模块把 Reddit 标为 blocked。
REDDIT = {
    "key": "Reddit",
    "status": "blocked",          # ok / blocked
    "blockedSince": "2026-11-07",
    "reason": "匿名 RSS 已关闭，需 OAuth 凭据（clientId/clientSecret 未配置）",
    "evidence": ("实测 www 429/404 · old 302 跳登录 · .json 403 · "
                 "RSSHub 4 实例全挂 · PullPush 429 · access_token 401"),
    # 各专栏最近一次真实取到 Reddit 数据的日期（None = 从未成功）
    "lastOk": {
        "k3": "2026-11-07",
        "h3c": None,
        "sw": "2026-11-10",
        "mbox": None,
        "fc": "2026-11-10",
        "resin": None,
    },
    # 2026-11-23 用户决策：H3C 也要接，与其余五页统一
    "declared": {
        "k3": True, "h3c": True, "sw": True,
        "mbox": True, "fc": True, "resin": True,
    },
}

# ---------------------------------------------------------------- 各专栏声明

# 顺序即页面 chip 的展示顺序（GitHub 风格：先主流后长尾）。
# 「B站」统一写归一后的形态，页面 platOf() 会把 "B 站" 折叠过来。
CHANNELS = {
    "k3": {
        "label": "K3",
        "platforms": [
            "YouTube", "Reddit", "B站", "什么值得买",
            "Makers101", "Slice Lab", "Fast3DPrinters",
            "Creality 官方论坛",
        ],
        "collector": "_k3_collect_channels.py --only bili|reddit|youtube|forum|all",
    },
    "h3c": {
        "label": "H3C",
        "platforms": [
            "拓竹官方论坛", "B站", "Reddit",
            "腾讯新闻", "网易", "什么值得买", "拓竹官网",
            "极客公园", "微信公众号",
        ],
        "collector": "_h3c_collect.py（B站 + 种子）+ _h3c_forum_collect.py（论坛）+ _h3c_reddit.py",
    },
    "sw": {
        "label": "软件",
        "platforms": [
            "Creality 官方论坛", "YouTube", "Reddit", "B站",
            "什么值得买", "GitHub",
        ],
        "collector": "_col_collect_sw.py + _col_sw_external.py + _col_collect_github.py",
    },
    "mbox": {
        "label": "mBox",
        "platforms": [
            "YouTube", "B站", "Reddit", "什么值得买",
            "Creality 官网", "3druck", "知乎",
        ],
        "collector": "_col_collect_mbox.py（forum/official/bili/youtube/play/zhihu/reddit/smzdm）",
    },
    "fc": {
        "label": "全彩",
        "platforms": [
            "YouTube", "B站", "Reddit", "什么值得买",
            "腾讯新闻", "网易新闻", "Fabbaloo", "3D打印资源库",
            "南方+", "All3DP",
        ],
        "collector": "_col_collect_fc.py --only bili|seed|ext + _col_collect_rd.py",
    },
    "resin": {
        "label": "光固化",
        "platforms": [
            "YouTube", "YouTube 评论", "B站", "Reddit",
            "Creality 官方论坛", "什么值得买",
        ],
        "collector": "_resin_collect.py（forum/youtube/bili/smzdm/reddit）",
    },
}

# 兼容采集器里 "Bilibili" / "B 站" 的写法，页面与注册表统一按这个映射
ALIAS = {
    "B 站": "B站",
    "Bilibili": "B站",
    "bilibili": "B站",
    "reddit": "Reddit",
    "youtube": "YouTube",
}


def norm_platform(p):
    """把采集器的各种写法收敛成注册表里的标准名。"""
    s = (p or "").strip() or "未标注"
    return ALIAS.get(s, s)


# ---------------------------------------------------------------- 状态计算

def _has_recent(platform, items, days=14):
    """该渠道在最近 N 天内是否还有新增（用于区分「有历史」与「仍在产出」）。"""
    cutoff = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    for x in items or []:
        if norm_platform(x.get("platform")) != platform:
            continue
        d = x.get("publishedAt") or x.get("date") or ""
        if d >= cutoff:
            return True
    return False


def chip_states(kind, items):
    """返回 [(platform, count, state, note)]。

    设计取舍（重要，别擅自改回去）
    ------------------------------------------------------------------
    只给 Reddit 出「0 条 chip」，其余源仍然「有数据才出 chip」。原因：
      · 全彩/软件的多家长尾媒体本身就是低频源，给它们出 0 条 chip
        会让页面一半 chip 是灰的，噪声大过信息量；
      · Reddit 不同 —— 它是有明确定位、有历史存量、有确定阻断原因的通道，
        「0 条」本身就是要传达的信息，不能像长尾源那样直接隐藏。

    state 四态，blocked / stale 在页面上置灰：
      ok       有数据、通道正常
      stale    有历史数据但通道已断（K3 的 38 条 Reddit 就是这种）
      blocked  声明了但从未取到数（mBox / 软件 / 全彩 / H3C / 光固化）
      zero     声明了、通道正常、当前 0 条 —— 正常现象，不置灰
    """
    reg = CHANNELS.get(kind) or {}
    declared = list(reg.get("platforms") or [])

    counts = {}
    for x in items or []:
        p = norm_platform(x.get("platform"))
        counts[p] = counts.get(p, 0) + 1

    # 数据里出现过但没声明的源也要显示（采集器临时加源时不能丢 chip）
    extra = [p for p in counts if p not in declared and p != "未标注"]

    rd = REDDIT
    rd_on = (rd.get("declared") or {}).get(kind, False)
    rd_blocked = rd.get("status") == "blocked"
    rd_last = (rd.get("lastOk") or {}).get(kind)

    out = []
    # 1) 声明顺序里**有数据**的源，按声明顺序输出，保证 chip 排列稳定
    for p in declared:
        n = counts.get(p, 0)
        if p == "Reddit":
            continue                       # Reddit 单列在最后，见下
        if n:
            out.append((p, n, "ok", ""))
    # 2) 未声明的源（按条数降序）
    for p in sorted(extra, key=lambda x: -counts[x]):
        if p == "Reddit":
            continue
        out.append((p, counts[p], "ok", ""))

    # 3) Reddit 恒定出现在末尾，无论有没有数据
    if rd_on or counts.get("Reddit"):
        n = counts.get("Reddit", 0)
        if not rd_on:
            out.append(("Reddit", n, "blocked", "本页未接入"))
        elif rd_blocked:
            note = "通道不可用 · 最近成功 " + rd_last if rd_last else "通道不可用 · 从未成功"
            out.append(("Reddit", n, "stale" if n else "blocked", note))
        elif n:
            out.append(("Reddit", n, "ok", ""))
        else:
            out.append(("Reddit", 0, "zero", ""))
    return out


def payload(kind):
    """构建器注入页面用的静态配置 —— **只放声明与通道状态，不放条数**。

    为什么不放条数：K3 / 光固化走增量注入（`_k3_inject_candidates.py`、
    `_resin_inject.py`），数据每天变但页面不重建，注入的条数第二天就是错的。
    条数一律由前端从当前筛选结果实时算，这里只回答「声明了哪些源」和
    「Reddit 这条通道现在通不通」——这两件事不随数据变。
    """
    rd = REDDIT
    return {
        "declared": list((CHANNELS.get(kind) or {}).get("platforms") or []),
        # 前端只对 Reddit 做特殊呈现，其余源沿用「有数据才出 chip」的老规则
        "reddit": {
            "on": (rd.get("declared") or {}).get(kind, False),
            "status": rd.get("status"),
            "since": rd.get("blockedSince"),
            "lastOk": (rd.get("lastOk") or {}).get(kind),
            "reason": rd.get("reason"),
        },
    }


def text_summary(kind):
    """给「导出说明」sheet 与日志用的一句话口径。"""
    rd = REDDIT
    if not (rd.get("declared") or {}).get(kind):
        return "本页未接入 Reddit 源"
    lo = (rd.get("lastOk") or {}).get(kind) or "从未成功"
    return "Reddit 通道不可用（%s 起），最近成功：%s" % (rd.get("blockedSince"), lo)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    print("Reddit 通道状态：%s（%s 起）" % (REDDIT["status"], REDDIT["blockedSince"]))
    print("原因：%s" % REDDIT["reason"])
    print()
    for k in CHANNELS:
        print("%-6s 声明 %2d 源 | %s" % (k, len(CHANNELS[k]["platforms"]), text_summary(k)))
