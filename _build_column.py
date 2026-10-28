# -*- coding: utf-8 -*-
"""
两个专栏页生成器（P1/P4）

架构 C：源码级共用 `_col_shell.html` + `_nav.html`，产物级仍是自包含单文件。
K3 页面不重写，只用 `--nav-only` 替换它的侧栏块（保证三页导航同源）。

用法：
  python _build_column.py                 # 生成两页
  python _build_column.py --only sw
  python _build_column.py --nav-only      # 只同步侧栏（K3 + 首页）
"""
import argparse
import io
import json
import os
import re
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
SHELL = os.path.join(ROOT, "_col_shell.html")
NAVT = os.path.join(ROOT, "_nav.html")
K3_PAGE = os.path.join(ROOT, "creality-k3.html")
INDEX = os.path.join(ROOT, "index.html")

SW_ITEMS = os.path.join(ROOT, "_sw_items_norm.json")
SW_TR = os.path.join(ROOT, "_col_tr_sw.json")
MBOX_ITEMS = os.path.join(ROOT, "_mbox_items_norm.json")
MBOX_TR = os.path.join(ROOT, "_col_tr_mbox.json")
FC_ITEMS = os.path.join(ROOT, "_fc_items_norm.json")
FC_TR = os.path.join(ROOT, "_col_tr_fc.json")

# 软件专栏第 2 个信源（2026-10-20 接入）：GitHub 官方仓库缺陷单。
# 口径：进明细、独立标签、不进总声量（countInVolume=false）—— 见 _col_collect_github.py 顶部说明。
GH_ITEMS = os.path.join(ROOT, "_gh_items_sw.json")
GH_TR = os.path.join(ROOT, "_col_tr_github.json")
GH_STATS = os.path.join(ROOT, "_gh_competitor_stats.json")

OUT_SW = os.path.join(ROOT, "software-columns.html")
OUT_MBOX = os.path.join(ROOT, "creality-mbox.html")
OUT_FC = os.path.join(ROOT, "fullcolor-columns.html")


def read(p):
    return io.open(p, encoding="utf-8").read()


def write_lf(p, s):
    """一律写 LF（推送脚本用文本模式读，CRLF 会被静默转成 LF）。"""
    io.open(p, "w", encoding="utf-8", newline="\n").write(s)


def load_json(p):
    return json.load(io.open(p, encoding="utf-8"))


# ============================================================================
# 双时间轴 + 更新历史（2026-10-26 用户决策）
# ----------------------------------------------------------------------------
# 口径：
#   fetchedAt   本次抓取完成时刻（含时分）——「页面是不是今天跑的」看这个
#   dataThrough 内容池最新一条的日期    ——「有没有抓到新东西」看这个
#   delta       相对上一版页面的新增条数 ——「这次多了几条」看这个
# 三者缺一，就会出现「每天时间在变但内容没动」或「内容没动就当没跑」的误读。
# ============================================================================
HIST = {"sw": os.path.join(ROOT, "_col_history_sw.json"),
        "mbox": os.path.join(ROOT, "_col_history_mbox.json"),
        "fc": os.path.join(ROOT, "_col_history_fc.json")}
SNAP = {"sw": os.path.join(ROOT, "_col_snapshot_sw.json"),
        "mbox": os.path.join(ROOT, "_col_snapshot_mbox.json"),
        "fc": os.path.join(ROOT, "_col_snapshot_fc.json")}
META_SIDE = {"sw": os.path.join(ROOT, "_sw_items_norm.json.meta.json"),
             "mbox": os.path.join(ROOT, "_mbox_items_norm.json.meta.json"),
             "fc": os.path.join(ROOT, "_fc_items_norm.json.meta.json")}

HIST_KEEP = 10


def _mtime_stamp(path):
    """采集器没写 fetchedAt 时，退回文件 mtime —— 比「昨天的时间」可信。"""
    try:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(path)))
    except OSError:
        return time.strftime("%Y-%m-%d %H:%M")


def side_meta(kind, src_path):
    """读归一化产出的 sidecar（fetchedAt / 信源探针 / 成败计数）。缺失则只用 mtime。"""
    p = META_SIDE.get(kind)
    if p and os.path.exists(p):
        try:
            return load_json(p)
        except Exception:
            pass
    return {"fetchedAt": _mtime_stamp(src_path), "probes": [], "stats": {}}


def track_delta(kind, items, baseline_items=None, fetched_at=None):
    """返回 (delta, 累计今日新增)。快照只存 uid 指纹，体量小、可入 git。

    baseline_items：快照首次建立时的「上一版页面条目」，用于把上线当天的真实新增算对，
    否则第一次跑会把整池都算成「新增」（会吓人一跳，也失真）。
    """
    p = SNAP[kind]
    # 抓取日而非「脚本运行日」：跨天重跑生成器时，不该把上一次抓取的新增数归零
    today = (fetched_at or time.strftime("%Y-%m-%d %H:%M"))[:10]
    prev = {"uids": [], "day": "", "addedToday": 0}
    if os.path.exists(p):
        try:
            prev.update(load_json(p))
        except Exception:
            pass
    elif baseline_items:
        prev["uids"] = [it.get("uid") for it in baseline_items if it.get("uid")]
    # 同一批数据重跑生成器（fetchedAt 未变）不产生新条目，但也不该把上次抓取的新增数改写成 0。
    # 页面上的「今日新增」描述的是 fetchedAt 那次抓取的结果，不是本次脚本运行的结果。
    if fetched_at and prev.get("fetchedAt") == fetched_at and prev.get("delta") is not None:
        return int(prev.get("delta") or 0), int(prev.get("addedToday") or 0)
    seen = set(prev.get("uids") or [])
    cur = [it.get("uid") for it in items if it.get("uid")]
    first_seed = (not prev.get("uids")) and not baseline_items
    # 首次建立快照又拿不到上一版基线时，一律记 0 —— 宁可少报「新增」，也不谎报整池
    new_n = 0 if first_seed else len([u for u in cur if u not in seen])
    if prev.get("day") != today:
        added = new_n
    else:
        added = int(prev.get("addedToday") or 0) + new_n
    state = {"uids": cur, "day": today, "addedToday": added,
             "fetchedAt": fetched_at, "delta": new_n,
             "updatedAt": time.strftime("%Y-%m-%d %H:%M")}
    write_lf(p, json.dumps(state, ensure_ascii=False))
    return new_n, added


def append_hist(kind, fetched_at, text):
    """更新历史：同一时刻只保留一条，按时间倒序留最近 HIST_KEEP 条。"""
    p = HIST[kind]
    logs = []
    if os.path.exists(p):
        try:
            logs = load_json(p)
        except Exception:
            logs = []
    if logs and logs[0].get("date") == fetched_at:
        logs[0]["text"] = text
    else:
        logs.insert(0, {"date": fetched_at, "text": text})
    logs = logs[:HIST_KEEP]
    write_lf(p, json.dumps(logs, ensure_ascii=False, indent=1))
    return logs


def status_of(delta, stats):
    """四态：ok 有新增 / zero 零新增但抓取正常 / warn 长空窗 / fail 抓取出错。"""
    fails = int((stats or {}).get("sourcesError") or 0)
    empty_days = int((stats or {}).get("emptyDays") or 0)
    if fails:
        return "fail"
    if delta and delta > 0:
        return "ok"
    if empty_days >= 3:
        return "warn"
    return "zero"


# ---------------------------------------------------------------- 侧栏
def counts():
    out = {"k3": 0, "mbox": 0, "sw": 0, "fc": 0}
    if os.path.exists(K3_PAGE):
        out["k3"] = len(re.findall(r'\{id:"K3-', read(K3_PAGE)))
    if os.path.exists(MBOX_ITEMS):
        out["mbox"] = len(load_json(MBOX_ITEMS))
    if os.path.exists(SW_ITEMS):
        out["sw"] = len(load_json(SW_ITEMS))
    if os.path.exists(FC_ITEMS):
        out["fc"] = len(load_json(FC_ITEMS))
    return out


def render_nav(active):
    c = counts()
    nav = read(NAVT)
    nav = nav.replace("__C_K3__", str(c["k3"]))
    nav = nav.replace("__C_MBOX__", str(c["mbox"]))
    nav = nav.replace("__C_SW__", str(c["sw"]))
    nav = nav.replace("__C_FC__", str(c["fc"]))
    nav = nav.replace("__ON_K3__", "active" if active == "k3" else "")
    nav = nav.replace("__ON_MBOX__", "active" if active == "mbox" else "")
    nav = nav.replace("__ON_SW__", "active" if active == "sw" else "")
    nav = nav.replace("__ON_FC__", "active" if active == "fc" else "")
    return nav


def _patch_sidebar(path, kind):
    """只替换侧栏块，其余零改动 —— 用于不重渲染内容的页面（K3 / mBox / 软件）。

    2026-10-27：加第 4 个专栏后，mBox 与软件两页的侧栏还停在 3 项。重渲染它们会
    牵动 delta / 更新历史，代价大于收益，所以只同步侧栏这一块。
    """
    if not os.path.exists(path):
        return
    s = read(path)
    i = s.find('<div class="sidebar" id="sidebar">')
    j = s.find('<div class="main">', i)
    if i < 0 or j < 0:
        print("！%s 侧栏定位失败，跳过" % os.path.basename(path))
        return
    s2 = s[:i] + render_nav(kind) + "\n" + s[j:]
    if s2 != s:
        write_lf(path, s2)
        print("%s 侧栏已同步（%d 条）" % (os.path.basename(path), counts()[kind]))
    else:
        print("%s 侧栏无变化" % os.path.basename(path))


def sync_nav():
    """把三个专栏页与首页的导航同步（只替换侧栏块，其余零改动）。"""
    _patch_sidebar(K3_PAGE, "k3")
    _patch_sidebar(OUT_MBOX, "mbox")
    _patch_sidebar(OUT_SW, "sw")

    if os.path.exists(INDEX):
        h = read(INDEX)
        n0 = h
        h = h.replace(
            '<span class="nav-icon">💬</span><span>用户点评</span><span class="nav-badge">海外用户</span>',
            '<span class="nav-icon">💬</span><span>用户反馈</span><span class="nav-badge">海外用户</span>')
        h = h.replace(
            '<a class="nav-item" href="software-columns.html"><span class="nav-icon">🧩</span>',
            '<a class="nav-item" href="software-columns.html" style="padding-left:44px;font-size:12.5px"><span class="nav-icon">🧩</span>')
        h = h.replace('<span class="nav-badge" style="background:rgba(210,153,34,.16);color:#d29922">预热</span>',
                      '<span class="nav-badge">%d 条</span>' % counts()["mbox"])
        # 2026-10-26：首页 mBox 徽标此前只在「预热」→「N 条」那一次改过，之后再没同步，
        # 页面加了 7 条 B站内容、首页还挂着旧数字。改成按位置替换，永久对齐。
        h = re.sub(r'(mBox 专栏</span><span class="nav-badge"[^>]*>)[^<]*(</span>)',
                   lambda m: "%s%d 条%s" % (m.group(1), counts()["mbox"], m.group(2)),
                   h, count=1)
        # 2026-10-27：全彩专栏同 mBox 一样按位置替换，避免徽标写死后越跑越偏
        h = re.sub(r'(全彩专栏</span><span class="nav-badge"[^>]*>)[^<]*(</span>)',
                   lambda m: "%s%d 条%s" % (m.group(1), counts()["fc"], m.group(2)),
                   h, count=1)
        if h != n0:
            write_lf(INDEX, h)
            print("首页导航已同步")
        else:
            print("首页导航无变化")
    return True


# ---------------------------------------------------------------- 数据装配
def merge_tr(items, tr):
    miss = 0
    for it in items:
        t = tr.get(it["uid"])
        if t:
            it["titleCn"] = t.get("t", "")
            it["textCn"] = t.get("b", "")
        elif it["originalText"] and not re.search(r"[\u4e00-\u9fff]", it["originalText"]):
            miss += 1
    return miss


BADGE = {"blue": "b-blue", "grn": "b-grn", "yel": "b-yel", "gray": "b-gray"}


def badges_html(lst):
    return "".join('<span class="badge %s">%s</span>' % (BADGE[c], t) for t, c in lst)


def _mbox_foot(sm, src_n):
    """mBox 页脚「信源覆盖」：按本轮探针真实结果生成，不写死结论。

    写死过一次的教训：老文案还写着「论坛 0 帖、YouTube 1 条」，B站接入后就不对了。
    """
    pr = sm.get("probes") or []
    ok = [p for p in pr if p.get("status") == "ok"]
    empty = [p for p in pr if p.get("status") == "empty"]
    bad = [p for p in pr if p.get("status") in ("error", "need-cookie", "need-signature",
                                                "blocked", "absent")]
    bad_txt = "、".join("%s（%s）" % (p.get("source"), p.get("status")) for p in bad[:8]) or "无"
    return (
        "<b>信源覆盖</b>（本轮实测）<br>"
        "① 探针 %d 个：命中 %d · 正常空返回 %d · 异常/受限 %d。<br>"
        "② 受限源：%s —— 受限不等于无声量，页面不做任何填充。<br>"
        "③ 国内主源为 <b>B站</b>（2026-10-26 接入）；知乎需登录态 Cookie，抖音 / 小红书需签名，本期只探不采。<br>"
        "④ 时点口径：<b>数据更新</b> = 抓取完成时刻，<b>内容截至</b> = 池内最新一条的日期。"
        "两者差距大不代表没跑，代表源里真的没新内容（见「更新历史」）。<br>"
        "⑤ 独立信源 %d 家；3druck 的 EN / DE 为同一篇稿，按 2 条计入、独立信源只算 1 家。"
        % (len(pr), len(ok), len(empty), len(bad), bad_txt, src_n)
    )


def build(kind):
    if kind == "fc":
        items = load_json(FC_ITEMS)
        tr = load_json(FC_TR) if os.path.exists(FC_TR) else {}
        miss = merge_tr(items, tr)
        sites = {x.get("site") for x in items if x.get("site")}
        plats = {x.get("platform") for x in items if x.get("platform")}
        models = {x.get("model") for x in items if x.get("model")}
        levels = {}
        for x in items:
            k = x.get("discussLevel") or "low"
            levels[k] = levels.get(k, 0) + 1
        ref = max((x.get("date") or "") for x in items) if items else ""
        through = ref
        sm = side_meta("fc", FC_ITEMS)
        fetched = sm.get("fetchedAt") or _mtime_stamp(FC_ITEMS)
        delta, today_added = track_delta("fc", items, fetched_at=fetched)
        st = status_of(delta, sm.get("stats"))
        n_guess = sum(1 for x in items if x.get("dateGuessed"))
        span = 0
        ds = sorted([x["date"] for x in items if x.get("date")])
        if len(ds) > 1:
            import datetime
            span = (datetime.date(*map(int, ds[-1].split("-")))
                    - datetime.date(*map(int, ds[0].split("-")))).days
        hist = append_hist(
            "fc", fetched,
            "抓取 %d 个信源 · 本次新增 %d 条 · 池 %d 条（%d 平台 / %d 机型）"
            % (len(set(p.get("channel") for p in (sm.get("probes") or [])) or plats),
               delta, len(items), len(plats), len(models)))

        blocked = sm.get("stats", {}).get("sourcesBlocked") or 0
        meta = {
            "kind": "fc",
            "updatedDate": through,
            "dataThrough": through,
            "fetchedAt": fetched,
            "delta": delta,
            "deltaToday": today_added,
            "status": st,
            "refDate": through,
            "batch": "工作日 03:30",
            "updateLog": hist,
            "sources": ("信源：① B站（国内用户口碑主源）· ② YouTube（Data API 采评测与实机）· "
                        "③ Reddit（RSS 采公开讨论）· ④ 什么值得买（深度长帖）· "
                        "⑤ 3D打印资源库 / 南方+ / 腾讯新闻（国内媒体）· "
                        "⑥ 外媒（All3DP / Fabbaloo / VoxelMatters）· 每日增量采集 · 原文 + 机翻"),
            "foot": (
                "<b>口径说明</b><br>"
                "① <b>讨论度优先</b>：明细默认按讨论度降序，不按日期 —— 本专栏只收"
                "<b>讨论度达标的帖子</b>（B站 播放≥3000 或 评论≥20 为高；≥500 或 ≥5 为中；"
                "值得买按点赞+收藏+评论；无互动数的外媒用正文长度代理，卡片上如实标注）。低讨论度不进池。<br>"
                "② <b>三层信源</b>：脚本自动（B站 / YouTube / Reddit）· 种子抓取（值得买 / 资源库 / 外媒，URL 由检索产出）· "
                "不可自动（小红书 / 抖音 / 知乎）。<b>受限不等于无声量</b>，页面不做任何填充。"
                "YouTube 走 Data API 按关键词搜实机与评测视频，<b>讨论度以评论为主、播放量只作辅助</b> —— "
                "官方投放片动辄百万播放却无讨论，按播放算会把广告读成口碑；Reddit 走 RSS 采公开讨论，"
                "<b>RSS 不带 score</b>，以 <code>sort=top</code> 的申请位次作热度代理，卡片上如实标注。"
                "两家厂商自有账号（inew3d / FLASHFORGE / HeyGears 等）发布的内容标记官方并降档，"
                "<b>不把官方声量算成用户声量</b>。<br>"
                "③ <b>档次不混算</b>：桌面级（$3.6k–10k）与工业级（数万美元起）价差 5–10 倍，"
                "本页所有计数与占比都在档次内呈现，不出现跨档位的「全彩平均」。<br>"
                "④ <b>多色 FDM 卡单列</b>：CMYK 套装 / 手涂 / 浮雕玩法是替代方案讨论，"
                "进明细与议题卡，但<b>不进全彩的情感分母</b> —— 否则「对多色的满意」会被读成全彩的满意。<br>"
                "⑤ <b>议题为规则预标注</b>：关键词命中，未经人工复核，只说明「哪类话题被提得多」，"
                "不作为情感或结论；0 条维度标「待样本」，空白 ≠ 无问题。<br>"
                "⑥ <b>时点</b>：数据更新 = 抓取完成时刻，内容截至 = 池内最新条目的发布日；"
                "跨度 %d 天。%s<br>"
                "⑦ <b>情感结构暂不渲染</b>：需覆盖率 ≥60%% 才出，当前标注未达门槛 —— 这是准入规则生效，不是缺数据。"
                % (span, ("其中 %d 条原页未给发布日，按采集日计入并已在卡片标注。" % n_guess)
                         if n_guess else "全部条目均有原页发布日。")
            ),
        }
        meta["badges"] = badges_html([
            ("%d 条热帖" % len(items), "blue"),
            ("%d 平台" % len(plats), "grn"),
            ("高讨论 %d" % levels.get("high", 0), "yel"),
            ("桌面 %d / 工业 %d" % (
                sum(1 for x in items if x.get("tier") == "桌面"),
                sum(1 for x in items if x.get("tier") == "工业")), "gray"),
            ("原文 + 机翻", "blue"),
        ])
        meta["title"] = "桌面全彩 3D 打印用户声音专栏"
        meta["icon"] = "🎨"
        meta["subtitle"] = (
            "MJP 喷墨路线（≠ 多色 FDM）· 桌面三台 + 工业两台对标 · "
            "国内 + 海外 · 讨论度优先 · 每日增量 · 原文 + 机翻双段")
        out = OUT_FC
        if miss:
            print("  ⚠ 未译条目 %d 条（原文照常展示，不显示译文段）" % miss)
    elif kind == "sw":
        items = load_json(SW_ITEMS)
        tr = load_json(SW_TR) if os.path.exists(SW_TR) else {}
        miss = merge_tr(items, tr)
        gh, gh_miss, gh_stats = [], 0, {}
        if os.path.exists(GH_ITEMS):
            gh = load_json(GH_ITEMS)
            gtr = load_json(GH_TR) if os.path.exists(GH_TR) else {}
            gh_miss = merge_tr(gh, gtr)
            if os.path.exists(GH_STATS):
                gh_stats = load_json(GH_STATS)
        forum_n = len(items)
        items = items + gh
        items.sort(key=lambda x: (x.get("date") or "", x.get("uid") or ""), reverse=True)

        valid = sum(1 for x in items if x.get("grade") == "有效" and x.get("countInVolume") is not False)
        vers = {x["version"] for x in items if x.get("version")}
        models = {x["model"] for x in items if x.get("model") and x["model"] != "未标注"}
        stages = {x.get("stage") for x in items if x.get("stage")}
        gap = sum(1 for x in items if not x.get("stage"))
        cov = (len(items) - gap) / len(items) * 100 if items else 0
        ref = max(x["date"] for x in items)
        through = ref
        sm = side_meta("sw", SW_ITEMS)
        fetched = sm.get("fetchedAt") or _mtime_stamp(SW_ITEMS)
        delta, today_added = track_delta("sw", items, fetched_at=fetched)
        st = status_of(delta, sm.get("stats"))
        hist = append_hist("sw", fetched,
                           "抓取 %d 个信源 · 本次新增 %d 条 · 池 %d 条（论坛 %d + GitHub %d）"
                           % (len(sm.get("probes") or []) or len({x.get("site") for x in items}),
                              delta, len(items), forum_n, len(gh)))

        gh_note = ""
        for repo, s in gh_stats.items():
            gh_note += ("%s：%s 个 open issue、★%s、最近 push %s。" % (
                repo, s.get("openIssues"), s.get("stars"), s.get("pushedAt")))
        meta = {
            "kind": "sw",
            "updatedDate": through,
            "dataThrough": through,
            "fetchedAt": fetched,
            "delta": delta,
            "deltaToday": today_added,
            "status": st,
            "refDate": through,
            "batch": "工作日 03:30",
            "updateLog": hist,
            "sources": ("信源：① Creality 官方论坛 Software 板块（%d 条）· ② GitHub CrealityOfficial 仓库 open issue"
                        "（%d 条，CrealityPrint / K1·K2 Klipper）· 每日增量采集" % (forum_n, len(gh))),
            "foot": (
                "<b>口径说明</b><br>"
                "① <b>按用户实现路径组织</b>：找模型 → AI 生成 → 建模改模 → 切片 → 打印运维 → 分享变现。"
                "归不到某一段的（软件自身 UI / 安装 / 升级 / 文件管理）单列为「跨环节」，不硬塞 —— "
                "当前路径覆盖 %.1f%%，跨环节 %d 条。<br>"
                "② <b>两个信源分工不同，不合并计数</b>：官方论坛 %d 条是用户声量（求助 / 吐槽 / 需求），"
                "GitHub %d 条是可复现的缺陷单（带标签、版本号、复现步骤）。"
                "<b>GitHub 条目不进总声量</b>，只进明细与结构面板 —— 混进去会把论坛可比基线打乱。<br>"
                "③ <b>泛讨论不计入结构</b>：提问 / 教程 / 公告类只计声量，不进问题类型榜，但在明细里可见（灰底、标「泛讨论」）。<br>"
                "④ <b>版本</b>：已归一到「主.次」，原始串保留在明细卡片。<br>"
                "⑤ <b>译文</b>：非中文内容全量机器翻译，原文零改动；正文超过 1,200 字保留前 1,200 字并标注可跳原帖。<br>"
                "⑥ <b>竞品背景</b>：%s 该仓库 issue 与 Creality 机型相关度低（实测近 45 条仅 3 条弱相关），"
                "因此只取仓库级指标作背景，不进明细。"
                % (cov, gap, forum_n, len(gh), gh_note or "OrcaSlicer")
            ),
        }
        meta["badges"] = badges_html([
            ("论坛 %d" % forum_n, "blue"),
            ("GitHub %d" % len(gh), "grn"),
            ("有效 %d" % valid, "grn"),
            ("%d 段覆盖" % len(stages), "yel"),
            ("原文 + 译文", "blue"),
        ])
        meta["title"] = "3D 打印软件用户使用专栏"
        meta["icon"] = "🧩"
        meta["subtitle"] = ("按用户实现路径组织：找模型 → AI 生成 → 建模改模 → 切片 → 打印运维 → 分享变现 · "
                            "官方论坛 %d 条 + GitHub 缺陷单 %d 条 · 覆盖 %d 个版本 / %d 个机型 · "
                            "每日增量 · 原文 + 机翻双段"
                            % (forum_n, len(gh), len(vers), len(models)))
        out = OUT_SW
        if miss:
            print("  ⚠ 未译条目 %d 条（原文照常展示，不显示译文段）" % miss)
        if gh_miss:
            print("  ⚠ GitHub 未译 %d 条（原文照常展示）" % gh_miss)
    else:
        items = load_json(MBOX_ITEMS)
        tr = load_json(MBOX_TR) if os.path.exists(MBOX_TR) else {}
        merge_tr(items, tr)
        sites = {x["site"] for x in items}
        ref = max(x["date"] for x in items)
        through = ref
        sm = side_meta("mbox", MBOX_ITEMS)
        fetched = sm.get("fetchedAt") or _mtime_stamp(MBOX_ITEMS)
        delta, today_added = track_delta("mbox", items, fetched_at=fetched)
        st = status_of(delta, sm.get("stats"))
        src_n = len({x.get("site") for x in items})
        hist = append_hist("mbox", fetched,
                           "抓取 %d 个信源 · 本次新增 %d 条 · 池 %d 条（%d 家独立信源）"
                           % (len(sm.get("probes") or []) or 1, delta, len(items), src_n))
        meta = {
            "kind": "mbox",
            "updatedDate": through,
            "dataThrough": through,
            "fetchedAt": fetched,
            "delta": delta,
            "deltaToday": today_added,
            "status": st,
            "refDate": through,
            "batch": "工作日 03:30",
            "updateLog": hist,
            "sources": ("信源：B站（国内主源 · 2026-10-26 接入）· Creality 官方论坛 · creality.com 官网 · "
                        "YouTube · Google Play · 3druck · 知乎（待登录态）· 每日增量采集"),
            "foot": _mbox_foot(sm, src_n),
        }
        meta["badges"] = badges_html([
            ("%d 条" % len(items), "blue"),
            ("独立信源 %d 家" % len(sites), "grn"),
            ("官方动作 %d 条" % sum(1 for x in items if x["sourceType"] == "官方"), "yel"),
            ("原文 + 译文", "blue"),
        ])
        meta["title"] = "Creality mBox 用户反馈专栏"
        meta["icon"] = "📦"
        meta["subtitle"] = ("面向家庭的紧凑机型 · 成型体积 153 × 153 × 153 mm · 配套应用 Creality Park · "
                            "每日增量 · 原文 + 机翻双段")
        out = OUT_MBOX

    data = {"meta": meta, "items": items}
    shell = read(SHELL)
    # 注意顺序：__DATA__ 必须最后替换，否则数据里的文本可能被二次替换
    page = (shell
            .replace("__ICON__", meta["icon"])
            .replace("__TITLE__", meta["title"])
            .replace("__SUBTITLE__", meta["subtitle"])
            .replace("__BADGES__", meta["badges"])
            .replace("__NAV__", render_nav(kind))
            .replace("__DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":"))))
    left = re.findall(r"__[A-Z]+__", page)
    if left:
        print("  ⚠ 未替换占位符：", set(left))
    write_lf(out, page)
    print("生成 %-24s %8d 字节  %d 条" % (os.path.basename(out), len(page.encode("utf-8")), len(items)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["sw", "mbox", "fc", "all"], default="all")
    ap.add_argument("--nav-only", action="store_true")
    a = ap.parse_args()

    if a.nav_only:
        sync_nav()
        return
    sync_nav()
    if a.only in ("sw", "all"):
        build("sw")
    if a.only in ("mbox", "all"):
        build("mbox")
    if a.only in ("fc", "all"):
        build("fc")


if __name__ == "__main__":
    main()
