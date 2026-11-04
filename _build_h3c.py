# -*- coding: utf-8 -*-
"""
_build_h3c.py — 生成 bambu-h3c.html（拓竹 H3C 单机型专栏）

架构：与 K3 同构的「单机型引擎」，引擎体逐字继承 creality-k3.html，
所有差异集中在本文件的 CONFIG 区 + 下方的 BLOCKS / PATCHES 补丁表。

为什么 fork 而不是给 _col_shell.html 加分支：
  K3 页有九分区（总览五卡 / 情感结构 / 问题点 Top / 信源结构 / 专项八宫格 /
  关注维度 / 渠道×情感矩阵 / 竞品卡 / 趋势 / 双列筛选），壳只有四段。
  要「按 K3 格式」，就必须继承 K3 的引擎。

与 K3 引擎的差异（全部在此显式列出，便于日后抽公共引擎时一眼看清）：
  1. 数据对象 K3_FEEDBACK_DATA → H3C_FEEDBACK_DATA；id 前缀 K3- → H3C-
  2. TOPIC_META / PROBLEM_MERGE / CHANNEL_MATRIX 三块换 H3C 口径
  3. groupOf()：厂商官方识别加 Bambu / 拓竹；国内媒体加极客公园 / IT之家 / 南极熊
  4. 口径：用户声量 = 全部 − 官方 − 媒体（K3 只排官方）。首发期媒体稿占绝大多数，
     不排会把通稿读成口碑；情感结构同步收窄，保证「所见即所得」
  5. 负面占比分母为 0 时显示「—」，不显示 0.0%（空白 ≠ 无负面）
  6. 近 7 日的基准日由 REF_DATE 注入，不再写死 K3 的存量日期

用法：
  python _build_h3c.py            # 生成 bambu-h3c.html
  python _build_h3c.py --check    # 只校验，不写文件
"""
import argparse
import hashlib
import io
import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "creality-k3.html")
OUT = os.path.join(ROOT, "bambu-h3c.html")
ITEMS = os.path.join(ROOT, "_h3c_items.json")

# ============================================================================
# CONFIG — 机型级配置，改这里
# ============================================================================
REF_DATE = "2026-11-04"          # 近 7 日基准日 / 数据更新日
PAGE_TITLE = "Bambu Lab H3C 用户反馈专栏 · 用户口碑"
H1 = "Bambu Lab H3C 用户反馈专栏"
AUTHOR_LINE = ("拓竹第三代旗舰 · Swaptek 九头闪切 / 顶置 AMS 3H / 可变线径 75A TPU · "
               "视频 / 图文 / 评价 三类载体合并统计 · 国内 + 海外全渠道 · 每日增量")
ICON = "🎋"
CSV_SLUG = "bambu-h3c-feedback-"

TOPICS_ORDER = ["swaptek", "multicolor", "ams3h", "tpu", "toolhead", "accuracy",
                "ai", "price", "nozzle", "chamber", "hms", "noise", "ecosystem", "support"]

TOPIC_META = """const TOPIC_META = {
  swaptek:    { name:"Swaptek 九头闪切", desc:"3.4s 换头 / 6s 全流程 / 0.038g 废料 / 长期可靠性" },
  multicolor: { name:"叠色与多色",       desc:"CMYKW 五色叠全彩 / 24 色 / 层间混色" },
  ams3h:      { name:"AMS 3H 供料烘干",  desc:"9 槽仅 2 个烘干位 / 退料需手动 / 边烘边打" },
  tpu:        { name:"软料 75A / 2.85mm", desc:"可变线径 / 底部直通 / 2.85mm 耗材供给" },
  toolhead:   { name:"工具头与加工",      desc:"刀切 / 画笔 / 压印 / 冷烫金 · 套件另购" },
  accuracy:   { name:"九头精度与校准",    desc:"微米级补偿 / 全自动校准 / 高频切换累积误差" },
  ai:         { name:"AI 监测与摄像头",   desc:"炒面 / 堵料 / 首层前整机检测 · 三路摄像头" },
  price:      { name:"价格与价值",        desc:"16,499 起 / 国补 13,999 / 比 H2C +1,500" },
  nozzle:     { name:"混径喷嘴",          desc:"0.2 / 0.4 / 0.6 / 0.8mm 同件混打", pending:true },
  chamber:    { name:"腔温与封箱",        desc:"双区主动加热至 65°C / 工程料翘曲", pending:true },
  hms:        { name:"HMS 诊断与报错",    desc:"故障排序 / MiniWiki 指引 / 错误码可读性", pending:true },
  noise:      { name:"噪音与占地",        desc:"九头挂架 / 烘干风扇 / 净重 36.28kg", pending:true },
  ecosystem:  { name:"生态与配件",        desc:"8+1 头配置 / AMS 跨代兼容 / 工作站 L" },
  support:    { name:"售后与品控",        desc:"首批品控 / 保修 / 配件供应", pending:true }
};"""

PROBLEM_MERGE = """const PROBLEM_MERGE = [
  ["换头/换料实际耗时长", ["换头","换料","切换","3.4","6 秒","6秒","等加热","回抽","手动换料"]],
  ["AMS 3H 供料与烘干局限", ["烘干位","烘干槽","一锅烘","顶盖","退料","拔料","手动拔","密封","受潮","边烘边打","气密"]],
  ["8 号头与 2.85mm 绑定", ["8 号","八号","8号","2.85","基座","喉管","干涉","留缝","1.75","8+1","九色"]],
  ["24 色扩展受限", ["24 色","24色","外接缓冲","缓冲器","1 号头","一号头","并联","AMS 组网","跨代"]],
  ["工具头与套件成本", ["刀切","画笔","压印","冷烫金","套件","升级包","平面加工","工具基座","另购"]],
  ["软料 TPU 供给与兼容", ["TPU","75A","软料","屈曲","2.85mm 耗材","弹性","鞋","线径"]],
  ["叠色效果与废料", ["叠色","CMYKW","混色","废料","0.038","冲刷","过渡色"]],
  ["九头精度与校准", ["精度","校准","微米","偏移","错位","重复定位","标定"]],
  ["噪音与占地", ["噪音","吵","分贝","占地","体积","太重","36.28","洗衣机","搬家"]],
  ["软件与切片", ["切片","Bambu Studio","Orca","参数","预设","固件","升级","app"]],
  ["价格与首发信心", ["16499","16,499","13999","13,999","国补","涨价","1500","溢价","跳水","免息","值不值"]],
  ["交付与履约", ["发货","预售","京东","定金","排队","到货","履约","物流","以旧换新"]],
  ["宣传口径与实测落差", ["宣传","名不符实","落差","PPT","发布会","实机","翻车","实测","官方口径"]],
  ["能力未经第三方验证", ["验证","未实测","第三方","演示","可靠性","观望","首批品控","长期","600 小时"]],
  ["竞品对比与定位", ["K3","U1","C5","P3C","H2C","H2D","P1S","竞品","四头","七头","多头路线","同价"]],
  ["品牌与品控信任", ["品控","信任","历史","老用户","背刺","刀法","口碑"]]
];"""

CHANNEL_MATRIX = """const CHANNEL_MATRIX = [
  { site:"什么值得买",          group:"cnCommunity",   method:"auto",   state:"ok",      re:/什么值得买|smzdm/i,                                        note:"首版主源：发布夜实测汇总与购买决策帖，含 AMS 3H / 8 号头等具体边界" },
  { site:"B 站",               group:"cnCommunity",   method:"auto",   state:"ok",      re:/B\\s?站|bilibili/i,                                        note:"发布夜开箱与实机视频密集，接口有波动；需 cookie 预热后按 3s 间隔请求" },
  { site:"小红书",              group:"cnCommunity",   method:"manual", state:"blocked", re:/小红书/i,                                                  note:"SPA 空壳 + x-s 签名 + 登录墙，不可自动 · 首发实测主阵地，缺口最大" },
  { site:"抖音",               group:"cnCommunity",   method:"manual", state:"blocked", re:/抖音/i,                                                    note:"搜索接口返回空数组，需 a_bogus 签名" },
  { site:"知乎",               group:"cnCommunity",   method:"manual", state:"blocked", re:/知乎/i,                                                    note:"api 400 / 网页 403 · 首发测评人长文多在此，需登录态" },
  { site:"贴吧 / 微博",         group:"cnCommunity",   method:"manual", state:"blocked", re:/贴吧|微博/i,                                                note:"登录墙" },
  { site:"京东 / 天猫",         group:"cnEcom",        method:"manual", state:"blocked", re:/京东|淘宝|天猫|拼多多/,                                      note:"首发为京东在售；站内评价反爬，评价缺口需商家资质" },
  { site:"极客公园 / IT之家",    group:"cnMedia",       method:"auto",   state:"ok",      re:/极客公园|IT之家|腾讯新闻|新浪|搜狐|凤凰|36氪|钛媒体/i,        note:"科技媒体首发解读，第三方口径，非用户声量" },
  { site:"网易 / 南极熊",       group:"cnMedia",       method:"auto",   state:"ok",      re:/网易|南极熊|3D打印资源库/i,                                  note:"行业媒体 / 通稿，非用户声量" },
  { site:"Reddit",             group:"overseaDirect", method:"auto",   state:"ok",      re:/Reddit|r\\//i,                                             note:"r/BambuLab 为首发反馈主阵地 · 出口 IP 403 属已知封锁，需换出口或走豆包" },
  { site:"X (Twitter)",        group:"overseaDirect", method:"manual", state:"blocked", re:/Twitter|\\bX\\b|推特/i,                                       note:"syndication 仅返回空壳；api v2 需付费 Bearer" },
  { site:"Facebook / Instagram", group:"overseaDirect", method:"manual", state:"blocked", re:/Facebook|Instagram|\\bIG\\b/i,                              note:"400 / 429 登录墙" },
  { site:"YouTube",            group:"overseaVideo",  method:"auto",   state:"ok",      re:/YouTube/i,                                                 note:"Data API v3 可采评测与实机；首发期以官方投放片为主，须按评论数而非播放量定讨论度" },
  { site:"TikTok",             group:"overseaVideo",  method:"manual", state:"partial", re:/TikTok/i,                                                  note:"仅可取话题量级，拿不到明细" },
  { site:"Amazon",             group:"overseaEcom",   method:"manual", state:"unknown", re:/Amazon/i,                                                  note:"海外尚未铺货；评价页需登录，可行性待探" },
  { site:"外媒（All3DP / Fabbaloo 等）", group:"overseaMedia", method:"auto", state:"ok", re:/All3DP|Fabbaloo|3DPrint|VoxelMatters|Notebookcheck|Tom's|PCMag/i, note:"海外评测与行业分析，非用户声量" },
  { site:"拓竹官网 / FAQ",       group:"official",      method:"auto",   state:"ok",      re:/拓竹官网|bambulab|拓竹官方/i,                                note:"厂商口径（含 8+1 头配置 / 配件清单），不计入用户声量" },
  { site:"拓竹官方论坛",         group:"official",      method:"auto",   state:"todo",    re:/拓竹官方论坛|forum\\.bambulab/i,                             note:"Discourse API 通路可用，H3C 版块刚开、存量少；厂商官方单列" }
];"""

BATCH_NOTE = ('const H3C_BATCH_NOTE = {"2026-11-04": "建页 · 首发批次（媒体 5 + 官方 2 + 用户/社区 3）"};')


def read(p):
    return io.open(p, encoding="utf-8").read()


def write_lf(p, s):
    io.open(p, "w", encoding="utf-8", newline="\n").write(s)


# ---------------------------------------------------------------- uid
TRACK = re.compile(r"[?&](utm_[a-z]+|ref|fbclid|gclid|si|spm|share_[a-z]+|from|src|xsec_token)=[^&#]*", re.I)


def norm_url(u):
    u = (u or "").strip()
    u = re.sub(r"#.*$", "", u)
    u = TRACK.sub("", u)
    u = u.replace("http://", "https://")
    u = re.sub(r"/+$", "", u)
    return u


def norm_text(t):
    return re.sub(r"\s+", " ", (t or "")).strip()[:200]


def uid_of(it):
    raw = norm_url(it.get("sourceLink")) + "|" + norm_text(it.get("originalText"))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------- 数据块
def build_data(seed):
    items = seed["items"]
    for it in items:
        it["uid"] = uid_of(it)
    uids = [it["uid"] for it in items]
    if len(set(uids)) != len(uids):
        raise SystemExit("！uid 碰撞：%d 条 / %d 个唯一 uid" % (len(uids), len(set(uids))))

    head = (
        'const H3C_FEEDBACK_DATA = {\n'
        '  model: "Bambu Lab H3C",\n'
        '  updated: "%s",\n'
        '  updatedAt: "%s",\n'
        '  fetchedAt: "%s",\n'
        '  note: %s,\n'
        '  audit: %s,\n'
        '  items: [\n'
        % (REF_DATE, REF_DATE + " 10:00", REF_DATE + " 10:30",
           json.dumps(seed["note"], ensure_ascii=False),
           json.dumps(seed["audit"], ensure_ascii=False))
    )
    rows = []
    for it in items:
        body = json.dumps(it, ensure_ascii=False, separators=(",", ":"))
        # JS 对象字面量：顶层键不加引号也不是必须，但引号更安全；这里统一保持 JSON 形态（合法 JS）
        rows.append("    " + body + ",")
    tail = "  ]\n};\n\nconst SENT_ORDER = [\"非常负面\",\"负面\",\"中性\",\"正面\",\"非常正面\"];\nwindow.DATA = H3C_FEEDBACK_DATA;\n"
    return head + "\n".join(rows) + "\n" + tail, items


def replace_block(src, start_marker, end_line_marker, new_text, label):
    i = src.find(start_marker)
    if i < 0:
        raise SystemExit("！未找到块起点：%s（%s）" % (start_marker, label))
    j = src.find(end_line_marker, i)
    if j < 0:
        raise SystemExit("！未找到块终点：%s（%s）" % (end_line_marker, label))
    return src[:i] + new_text + src[j + len(end_line_marker):]


# 逐条精确替换（old 必须命中一次，否则报错——宁可失败也不要静默漏改）
PATCHES = [
    ("<title>Creality K3 用户反馈专栏 · 用户口碑</title>", "<title>%s</title>" % PAGE_TITLE, "页面标题"),
    ("<text y='.9em' font-size='90'>🖨️</text>", "<text y='.9em' font-size='90'>%s</text>" % ICON, "favicon"),
    ('<span class="brand-icon">🖨️</span>', '<span class="brand-icon">%s</span>' % ICON, "标题栏图标"),
    ("<h1>Creality K3 用户反馈专栏</h1>", "<h1>%s</h1>" % H1, "H1"),
    ('<div class="author-line">首款 KliTek 四喷嘴换嘴机型 · 视频 / 图文 / 评价 三类载体合并统计 · 国内 + 海外全渠道 · 每日增量</div>',
     '<div class="author-line">%s</div>' % AUTHOR_LINE, "副标题"),
    ('<h2 class="sec-title">K3 专项分析（按机型特性）', '<h2 class="sec-title">H3C 专项分析（按技术模块）', "专项区标题"),
    # 渠道组识别：官方加拓竹，国内媒体补首发媒体；顺序敏感（与 K3 同序）
    ('  if (/什么值得买|smzdm|B\\s?站|bilibili|知乎|贴吧|小红书|抖音|微博|Chiphell/i.test(p)) return "cnCommunity";',
     '  if (/什么值得买|smzdm|B\\s?站|bilibili|知乎|贴吧|小红书|抖音|微博|Chiphell|微信公众号|公众号|微信/i.test(p)) return "cnCommunity";',
     "groupOf.cnCommunity"),
    ('  if (/网易|3D打印资源库|腾讯新闻|新浪|搜狐|凤凰|百家号|东方财富|caifuhao|36氪|钛媒体/.test(p)) return "cnMedia";',
     '  if (/网易|3D打印资源库|腾讯新闻|新浪|搜狐|凤凰|百家号|东方财富|caifuhao|36氪|钛媒体|极客公园|IT之家|南极熊/.test(p)) return "cnMedia";',
     "groupOf.cnMedia"),
    ('  if (/Creality|创想/i.test(p)) return "official";',
     '  if (/Creality|创想|Bambu|拓竹|bambulab/i.test(p)) return "official";',
     "groupOf.official"),
    # 口径：用户声量 = 全部 − 官方 − 媒体
    ('  const userAll = all.filter(function(x){ return groupOf(x.platform) !== "official"; });\n'
     '  const officialN = all.length - userAll.length;',
     '  // H3C 口径：厂商官方与媒体稿均单列，不计入用户声量与情感分母（首发期媒体稿占绝大多数，\n'
     '  // 不排会把通稿读成口碑）。K3 只排官方，此处是两页唯一的口径差异，已写入页脚说明。\n'
     '  const isOff = function(x){ return groupOf(x.platform) === "official"; };\n'
     '  const isMedia = function(x){ return !isOff(x) && (x.sourceType === "媒体" || x.sourceType === "社区综述"); };\n'
     '  const userAll = all.filter(function(x){ return !isOff(x) && !isMedia(x); });\n'
     '  const officialN = all.filter(isOff).length;\n'
     '  const mediaN = all.filter(isMedia).length;',
     "KPI.用户声量口径"),
    # 情感结构 / 矩阵同步收窄，保证「面板数字 = 点开后条数」
    ('  const isUserValid = function(x){ return x.reviewGrade === "有效" && groupOf(x.platform) !== "official"; };',
     '  const isUserValid = function(x){ return x.reviewGrade === "有效" && groupOf(x.platform) !== "official"'
     ' && x.sourceType !== "媒体" && x.sourceType !== "社区综述"; };',
     "isUserValid"),
    ('  const cutoff = new Date("2026-10-13"); cutoff.setDate(cutoff.getDate() - 7);',
     '  const cutoff = new Date("%s"); cutoff.setDate(cutoff.getDate() - 7);' % REF_DATE,
     "近7日基准"),
    # 总声量副标：把媒体 / 官方单列讲清楚
    ('    { l:"总声量", v:userAll.length, s:kindSub + (genN ? " · 含泛讨论 " + genN + " 条" : "") + (officialN ? " · 另有厂商官方 " + officialN + " 条单列" : ""), c:"#e6edf3" },',
     '    { l:"总声量", v:userAll.length, s:(userAll.length ? kindSub : "首发期 · 用户声量待累积")'
     ' + (genN ? " · 含泛讨论 " + genN + " 条" : "")'
     ' + " · 另有媒体 " + mediaN + " 条 / 厂商官方 " + officialN + " 条单列", c:"#e6edf3" },',
     "KPI.总声量"),
    # 负面占比：分母为 0 时显示「—」
    ('    { l:"负面占比", v:rate(neg, analytic.length) + "%",',
     '    { l:"负面占比", v:(analytic.length ? rate(neg, analytic.length) + "%" : "—"),', "KPI.负面v"),
    ('      s:"分析口径 · 有效 " + analytic.length + " / " + userAll.length + " 条" +',
     '      s:(analytic.length ? "分析口径 · 有效 " + analytic.length + " / " + userAll.length + " 条"'
     ' : "分析口径 · 有效用户样本 0 条，首发期不计算（空白 ≠ 无负面）") +', "KPI.负面s"),
    # 专项八宫格取数顺序
    ('  const order = ["kliTek","multicolor","nozzle","tpu","ai","sensor","wifi","noise","slicer","material","build","price","ecosystem","support"];',
     '  const order = %s;' % json.dumps(TOPICS_ORDER), "renderTopics.order"),
    # 竞品卡图例
    ('<div class="legend"><span>被 K3 反馈主动点名的对标机型与竞品；Snapmaker U1 是最常被引用的价格与体验标尺</span></div>',
     '<div class="legend"><span>被 H3C 反馈主动点名的对标机型；Creality K3 与 Snapmaker U1 是最常被引用的多头架构标尺，H2C 是价格参照</span></div>',
     "竞品图例"),
    # 按条去重：与 K3 规范「维度与问题点必须去重后按条」一致。
    # 不去重时，一条反馈里两个原始标签归到同一类目会被计两次，面板数字 > 点开后的明细条数，
    # 直接破坏「所见即所得」（实测：8 号头类目 面板 3 / 明细 2）。
    ('  base.forEach(function(it){ (it.problemPoints || []).forEach(function(p){ const k = normProblem(p); cnt[k] = (cnt[k] || 0) + 1; }); });',
     '  base.forEach(function(it){ const seen = {}; (it.problemPoints || []).forEach(function(p){'
     ' const k = normProblem(p); if (!k || seen[k]) return; seen[k] = 1; cnt[k] = (cnt[k] || 0) + 1; }); });',
     "问题点按条去重"),
    ('  return (it.dimensions || []).map(function(d){ return d.split(" - ")[0]; });',
     '  // 同一条内的一级维度去重：一条反馈可命中多个二级维度，但一级只算一次（按条计数）\n'
     '  const seen = {}; const out = [];\n'
     '  (it.dimensions || []).forEach(function(d){ const k = d.split(" - ")[0]; if (!seen[k]) { seen[k] = 1; out.push(k); } });\n'
     '  return out;',
     "维度按条去重"),
    # 长尾折叠门槛：K3 按样本 400+ 设固定值，首版 10 条会把面板全折成一行提示
    ('  const main = allArr.filter(function(r){ return r.n >= 4; });\n'
     '  const tail = allArr.filter(function(r){ return r.n < 4; });',
     '  // H3C 差异：门槛随样本量自适应。K3 固定 4 是基于 400+ 样本；首版 10 条时会把全部类目\n'
     '  // 折进「仅提及 1 次」一行，等于把唯一有信息量的面板藏起来。样本长起来后自动回到 K3 口径。\n'
     '  const PROBLEM_MAIN_MIN = total >= 200 ? 4 : (total >= 50 ? 2 : 1);\n'
     '  const main = allArr.filter(function(r){ return r.n >= PROBLEM_MAIN_MIN; });\n'
     '  const tail = allArr.filter(function(r){ return r.n < PROBLEM_MAIN_MIN; });',
     "问题点门槛"),
    ('  const top = plats.filter(function(r){ return r.n >= 2; });\n'
     '  const tail = plats.filter(function(r){ return r.n < 2; });',
     '  // 同上：首版每个站点仅 1 条，固定门槛 2 会把全部站点折进「各仅 1 条」\n'
     '  const PLAT_MAIN_MIN = total >= 200 ? 2 : 1;\n'
     '  const top = plats.filter(function(r){ return r.n >= PLAT_MAIN_MIN; });\n'
     '  const tail = plats.filter(function(r){ return r.n < PLAT_MAIN_MIN; });',
     "站点行门槛"),
    # CSV 文件名 / console 标识
    ('a.download = "creality-k3-feedback-" + K3_FEEDBACK_DATA.updated + ".csv";',
     'a.download = "%s" + H3C_FEEDBACK_DATA.updated + ".csv";' % CSV_SLUG, "CSV 名"),
    ('console.log("boot start: K3 专栏 records =",', 'console.log("boot start: H3C 专栏 records =",', "console.log"),
    ('  // 105 条泛讨论里 81 条是中性（「K3 上市了吗」这类），一直混在分母里把负面占比机械性压低。',
     '  // 泛讨论（「H3C 什么时候发货」这类）混在分母里会把负面占比机械性压低，故只计声量不进情感。',
     "注释.泛讨论"),
    ('（K3 有 14 个平台，', '（H3C 首发期平台数少于 K3，', "注释.平台数"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只校验不写文件")
    a = ap.parse_args()

    src = read(SRC)
    seed = json.load(io.open(ITEMS, encoding="utf-8"))
    data_block, items = build_data(seed)

    # 1) 换数据块：从 const K3_FEEDBACK_DATA = { 到 window.DATA = K3_FEEDBACK_DATA;
    i = src.find("const K3_FEEDBACK_DATA = {")
    j = src.find("window.DATA = K3_FEEDBACK_DATA;")
    if i < 0 or j < 0:
        raise SystemExit("！数据块定位失败")
    page = src[:i] + data_block + src[j + len("window.DATA = K3_FEEDBACK_DATA;"):]

    # 2) 三块口径表整块替换
    page = replace_block(page, "const TOPIC_META = {", "\n};", TOPIC_META, "TOPIC_META")
    page = replace_block(page, "const PROBLEM_MERGE = [", "\n];", PROBLEM_MERGE, "PROBLEM_MERGE")
    page = replace_block(page, "const CHANNEL_MATRIX = [", "\n];", CHANNEL_MATRIX, "CHANNEL_MATRIX")

    # 3) 批次备注：整段（含上一行注释尾部不影响）
    page = re.sub(r"const K3_BATCH_NOTE = \{[^\n]*\};", BATCH_NOTE, page, count=1)

    # 4) 逐条补丁必须在标识符改名之前（CSV 那条的原文里含 K3_FEEDBACK_DATA）
    miss = []
    for old, new, label in PATCHES:
        if page.count(old) != 1:
            miss.append("%s（命中 %d 次）" % (label, page.count(old)))
            continue
        page = page.replace(old, new)

    # 5) 剩余标识符改名
    page = page.replace("K3_UPDATE_LOG", "H3C_UPDATE_LOG")
    page = page.replace("K3_BATCH_NOTE", "H3C_BATCH_NOTE")
    page = page.replace("K3_FEEDBACK_DATA", "H3C_FEEDBACK_DATA")

    # 5) 侧栏：留给 _build_column.py --nav-only 统一注入（此处仅提示）
    if miss:
        print("！补丁未命中：")
        for m in miss:
            print("   -", m)
        raise SystemExit(1)

    left = re.findall(r"__[A-Z_]+__", page)
    if left:
        print("！残留占位符：", set(left))
        raise SystemExit(1)

    if a.check:
        print("校验通过：items=%d · 补丁 %d 条 · 字节 %d" % (len(items), len(PATCHES), len(page.encode("utf-8"))))
        return
    write_lf(OUT, page)
    print("生成 %s  %d 字节  %d 条  (补丁 %d 条全部命中)"
          % (os.path.basename(OUT), len(page.encode("utf-8")), len(items), len(PATCHES)))

    # 6) 侧栏必须最后注入：页面是从 K3 源码 fork 的，内联侧栏带的是「K3 高亮」，
    #    不重跑 nav-only 就会把 K3 的 active 一起继承过来（h3c 页看起来像 K3 页）。
    import subprocess
    subprocess.call([sys.executable, os.path.join(ROOT, "_build_column.py"), "--nav-only"])


if __name__ == "__main__":
    main()
