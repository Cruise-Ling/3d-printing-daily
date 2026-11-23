/**
 * 专栏页运行时校验（v2，针对 _col_shell.html 生成的页面）
 *   node _col_runtime.js software-columns.html
 *   node _col_runtime.js creality-mbox.html
 * 用假 DOM 跑真实渲染函数，覆盖：KPI / 面板 / 卡片双段 / 筛选联动 / 摘要条 / 分页 / 导航
 */
const fs = require("fs");
const vm = require("vm");

const file = process.argv[2];
if (!file) { console.log("用法: node _col_runtime.js <page.html>"); process.exit(2); }
const html = fs.readFileSync(file, "utf8");

let pass = 0, fail = 0;
const bad = [];
function ok(cond, name, extra) {
  if (cond) { pass++; }
  else { fail++; bad.push(name + (extra ? " -> " + extra : "")); }
}

/* ---------------- 假 DOM ---------------- */
const els = {};
function el(id) {
  if (!els[id]) {
    els[id] = {
      id, innerHTML: "", textContent: "", offsetTop: 100,
      classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
      focus() {}, setSelectionRange() {}, value: ""
    };
  }
  return els[id];
}
const handlers = {};
const document = {
  getElementById: el,
  addEventListener: (t, fn) => { handlers[t] = fn; },
  querySelectorAll: () => [],
  activeElement: null
};
const window = { scrollTo() {} };
const ctx = {
  document, window, console, TextEncoder,
  URL: { createObjectURL: () => "blob:stub", revokeObjectURL() {} },
  Blob: function () {}, setTimeout, clearTimeout, setInterval, clearInterval
};
vm.createContext(ctx);

const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
ok(scripts.length >= 2, "页面含数据脚本 + 引擎脚本", "共 " + scripts.length + " 段");

try {
  vm.runInContext(scripts[0], ctx);
  vm.runInContext(scripts[1], ctx);
  ok(true, "引擎脚本可执行");
} catch (e) {
  ok(false, "引擎脚本可执行", e.message);
  report(); process.exit(1);
}

/* 导出抽屉是独立脚本段，单独执行后才能验证取数钩子 */
const drawerSrc = scripts.find(s => s.indexOf("function buildXlsx") > -1) || "";
let drawerErr = "";
if (!drawerSrc) drawerErr = "未找到含 xlsx 生成器的脚本段";
else {
  try { vm.runInContext(drawerSrc, ctx); } catch (e) { drawerErr = e.message; }
}
ok(!drawerErr, "导出抽屉脚本可执行", drawerErr);

function report() {
  // 批量导出（2026-11-23 改版）：默认导出当前筛选列表，纯前端出 xlsx；服务只用于补全评论
  ok(html.indexOf('id="expOpen"') > -1, "导出入口存在");
  ok(html.split('id="expDrawer"').length === 2, "导出抽屉唯一");
  ok(html.indexOf('127.0.0.1:8765') > -1, "本地服务地址已内联");
  ok(html.indexOf('EXP_VER = "2026-11-23a"') > -1, "导出组件版本 2026-11-23a");
  ok(html.indexOf('id="expChips"') > -1, "平台范围 chip 存在");
  ok(html.indexOf('id="expDeep"') > -1, "补全评论开关存在");
  ok(html.indexOf('id="expGo2"') > -1, "外部链接导出入口存在");
  ok(html.indexOf("function buildXlsx") > -1, "内联 xlsx 生成器存在");
  ok(html.indexOf("window.expApi") > -1, "导出取数钩子已暴露");
  // 旧版遗留控件必须已移除，避免两套逻辑并存
  ok(html.indexOf('id="expMax"') === -1, "旧版评论上限控件已移除");
  ok(html.indexOf('id="expTr"') === -1, "旧版选项控件已移除");

  const api = ctx.window.expApi;
  ok(!!api, "expApi 可访问");
  let rowsN = 0, colsN = 0, xlsxOk = false;
  if (api) {
    try { rowsN = api.rows().length; } catch (e) {}
    try { colsN = api.fields().length; } catch (e) {}
    try {
      const b = api.xlsx([{ name: "t", header: ["标题"], rows: [["中文测试"]] }]);
      xlsxOk = b && b.length > 300;
    } catch (e) {}
  }
  ok(rowsN > 0, "能取到当前列表行数", "rows=" + rowsN);
  ok(colsN >= 15, "字段表已定义", "cols=" + colsN);
  ok(xlsxOk, "xlsx 生成器可产出字节");

console.log("\n" + (fail ? "FAIL" : "ALL PASS") + "  " + pass + " 项通过 / " + fail + " 项失败  [" + file + "]");
  if (fail) { bad.forEach(b => console.log("  ✗ " + b)); process.exitCode = 1; }
}

const COL = ctx.COL;
const ITEMS = COL.items, META = COL.meta;
const KIND = META.kind;

/* ---------------- 结构 ---------------- */
ok(!!META.kind && !!META.title, "meta 完整");
ok(ITEMS.length > 0, "条目非空", String(ITEMS.length));

/* ---------------- 导航 ---------------- */
const subLinks = html.match(/class="nav-item sub[^"]*" href="([^"]+)"/g) || [];
// 2026-11-12 B3：第六个专栏（光固化 resin-line.html）上线，侧栏子项 5 -> 6
ok(subLinks.length === 6, "侧栏含六个子专栏入口（含全彩 / H3C / 光固化）", String(subLinks.length));
["creality-k3.html", "creality-mbox.html", "software-columns.html", "bambu-h3c.html", "resin-line.html"].forEach(h => {
  ok(html.indexOf('href="' + h + '"') >= 0, "侧栏可跳转 " + h);
});
if (KIND === "fc") {
  ok(html.indexOf('href="fullcolor-columns.html"') >= 0, "侧栏含全彩自身入口（四页同源）");
}
ok(/class="nav-item sub active"/.test(html), "当前页高亮");
ok(html.indexOf("用户反馈") >= 0, "父级已改名「用户反馈」");

/* ---------------- KPI ---------------- */
const kpi = els.kpiRow.innerHTML;
const kpiN = (kpi.match(/class="kpi"/g) || []).length;
ok(kpiN === 5, "KPI 五卡", String(kpiN));
// 全彩页用「热帖池」承担总声量槽位（见下方 fc 分支），不重复断言
if (KIND !== "fc") ok(kpi.indexOf("总声量") >= 0, "KPI 含总声量");
if (KIND === "sw") {
  ok(kpi.indexOf("有效问题率") >= 0, "软件 KPI 用有效问题率");
  ok(kpi.indexOf("覆盖机型") >= 0, "软件 KPI 含覆盖机型");
} else if (KIND === "fc") {
  // 全彩：情感结构需覆盖 ≥60% 才渲染，所以 KPI 不放「负面占比」，放议题口径的「成本类讨论占比」
  ["热帖池", "覆盖平台", "覆盖机型", "近 30 日新增"].forEach(n => {
    ok(kpi.indexOf(n) >= 0, "全彩 KPI 含「" + n + "」");
  });
  ok(kpi.indexOf("成本类讨论") >= 0, "全彩 KPI 含成本类讨论占比");
  ok(kpi.indexOf("负面") < 0, "全彩 KPI 不出现「负面」占比");
} else {
  ok(kpi.indexOf("独立信源") >= 0, "mBox KPI 含独立信源");
  ok(kpi.indexOf("官方动作") >= 0, "mBox KPI 含官方动作");
}

/* ---------------- 更新条 ---------------- */
ok(/数据更新(至)?/.test(els.updateBar.innerHTML), "数据更新条渲染");
ok(els.updateBar.innerHTML.indexOf("总条数") >= 0, "更新条含总条数");
ok(els.foot.innerHTML.length > 100, "页脚口径说明非空");

/* ---------------- 面板 ---------------- */
// 全彩页不沿用 panelsA/B 双区：S2 概览落在 ovA，S3 议题卡落在 topicGrid
// 2026-10-27 壳改版后三页统一为 ovA（S2 概览）/ topicGrid（S3 专项），
// 旧的 panelsA / panelsB 已不存在，断言必须跟着容器走，否则校验器自己先崩。
const P_A = els.ovA;
const P_B = els.topicGrid;
ok(P_A.innerHTML.indexOf('class="panel"') >= 0, "面板 A 渲染");
ok(P_B.innerHTML.length > 100, "面板 B 渲染");
if (KIND === "fc") {
  /* S2 概览：只讲「整体什么状况」，问题一律交给 S3 议题卡 */
  ok(P_A.innerHTML.indexOf("情感结构") >= 0, "全彩 S2 有情感结构面板");
  ok(P_A.innerHTML.indexOf("信源结构") >= 0, "全彩 S2 有信源结构面板");

  /* 护栏 A：档次不混算 —— 桌面级 / 专业级 / 工业级价差可达 10 倍，不出现跨档位均值 */
  ok(P_A.innerHTML.indexOf("不做跨档位平均") >= 0, "护栏A：机型声量标注不做跨档位平均");
  ok(P_A.innerHTML.indexOf("桌面级") >= 0 && P_A.innerHTML.indexOf("工业级") >= 0,
    "护栏A：桌面级 / 工业级分档呈现");
  ok(P_A.innerHTML.indexOf("专业级") >= 0, "护栏A：专业级（赛纳 $60k–150k 桌面形态）单独成档");
  ok(P_A.innerHTML.indexOf("全彩平均") < 0, "护栏A：S2 不出现「全彩平均」字样");

  /* 情感准入：覆盖率 <60% 时必须显式说明「准入未达」，不能留白让人误读成 0 负面 */
  const withS = ITEMS.filter(x => x.sentiment).length;
  if (ITEMS.length && withS / ITEMS.length < 0.6) {
    ok(P_A.innerHTML.indexOf("未达准入门槛") >= 0,
      "情感结构：覆盖率 " + withS + "/" + ITEMS.length + " 时显式标注准入未达");
  } else {
    ok(true, "情感结构：覆盖率已达门槛，出结构图");
  }

  /* S3 议题卡：6 机型 + 10 议题，0 条标「待样本」 */
  ok(P_B.innerHTML.indexOf('data-pick="topic"') >= 0, "议题卡可点击筛选明细");
  ok(P_B.innerHTML.indexOf("机型视角") >= 0 && P_B.innerHTML.indexOf("议题视角") >= 0,
    "议题卡分机型 / 议题两组");
  ok(P_B.innerHTML.indexOf("10 维") >= 0, "议题视角标明 10 维");
  const tcards = (P_B.innerHTML.match(/class="tcard/g) || []).length;
  ok(tcards === 16, "机型 6 + 议题 10 = 16 张卡", String(tcards));
  ok(P_B.innerHTML.indexOf("赛纳三维") >= 0, "机型卡含赛纳三维（2026-10-28 接入）");
  ok(P_B.innerHTML.indexOf("6 台") >= 0, "机型分组头标注 6 台");
  /* 品牌组匹配：卡片 key 是品牌、字段是型号，粒度不一致会让卡永久空着。
     2026-10-28 实测 Stratasys 卡显示 0 条，而池里有 J850/J55 —— 这条断言就是防它复发。 */
  const stratPool = ITEMS.filter(x => /^(stratasys|j\s*8\d\d|j\s*55|j\s*35|j\s*826|polyjet)/i.test(x.model || "")).length;
  if (stratPool > 0) {
    const seg = P_B.innerHTML.split("Stratasys PolyJet")[1] || "";
    ok(!/^[\s\S]{0,60}?待样本/.test(seg),
      "Stratasys 品牌组兜住型号别名（池内 " + stratPool + " 条，卡片不为空）");
  } else {
    ok(true, "Stratasys 池内 0 条，跳过别名兜底校验");
  }
  /* 诚实披露缺口即可：要么有 0 样本维度标「待样本」，要么全量已标情感，
     要么（自动采集场景下）情感覆盖率不足已显式标注「未达准入门槛」——
     后者是规范明文允许的诚实呈现，不应被当作缺数据惩罚。 */
  ok(P_B.innerHTML.indexOf("待样本") >= 0
     || ITEMS.every(x => x.sentiment)
     || P_A.innerHTML.indexOf("未达准入门槛") >= 0,
    "0 条维度标「待样本」而非隐藏（情感未达准入已显式标注亦视为诚实披露）");

  /* 护栏 B：多色 FDM 是替代方案讨论，单列可见但不进全彩情感分母 */
  const fdm = ITEMS.filter(x => x.techRoute === "FDM-multicolor");
  ok(fdm.length > 0, "护栏B：多色 FDM 条目已单列", String(fdm.length));
  ok(html.indexOf("多色 FDM") >= 0, "护栏B：页面标明多色 FDM 单列不计情感分母");
  ok(ITEMS.every(x => x.techRoute !== "FDM-multicolor" || x.tier === "对照"),
    "护栏B：多色 FDM 全部落「对照」档，未混进全彩对标");
  /* 技术路线不混称：赛纳是 WJP，不是 MJP。混写的后果是「喷头/耗材」类结论被套到两条不同工艺上。 */
  const sn = ITEMS.filter(x => x.model === "Sailner");
  ok(sn.every(x => x.techRoute === "WJP 体素喷墨"),
    "赛纳条目技术路线标 WJP 体素喷墨（非 MJP）", String(sn.length));

  /* S4 渠道：覆盖清单是「要不要补信源」的依据，必须渲染 */
  ok(els.chanCover.innerHTML.indexOf("渠道覆盖清单") >= 0, "渠道覆盖清单渲染");
  ok(els.chanCover.innerHTML.indexOf("赛纳官网") >= 0, "渠道清单含赛纳官网（官方源 · 降档）");
  ok(els.chanHint.textContent.indexOf("覆盖") >= 0, "渠道覆盖数已标注");
  ok(els.chanShare.innerHTML.length > 50, "渠道占比区已渲染（达标出图 / 未达标显式说明）");
} else if (KIND === "sw") {
  /* 壳改版后落点：ovA=问题类型构成+工具×环节矩阵 / topicGrid=六段路径 / topicDist=工具结构 / chanCover=渠道+段×信源 */
  ok(els.topicHint.textContent.indexOf("用户实现路径") >= 0, "软件按用户实现路径组织");
  ok(P_A.innerHTML.indexOf("问题类型构成") >= 0, "软件有「问题类型构成」");
  ok(els.topicDist.innerHTML.indexOf("工具结构") >= 0, "软件用「工具结构」替代失效的产品线");
  ok(P_A.innerHTML.indexOf("产品线结构") < 0, "旧的「产品线结构」已移除");
  // 工具结构：按「功能类型」分（用户 2026-10-20 取消自家/竞品一级分类）
  ok(els.topicDist.innerHTML.indexOf("按功能类型") >= 0, "工具结构按功能类型组织");
  ["切片软件", "建模软件", "云平台 / App", "多色与耗材", "固件与主机控制", "激光 / 扫描"].forEach(n => {
    ok(els.topicDist.innerHTML.indexOf(n) >= 0, "类型行含「" + n + "」");
  });
  ok(els.topicDist.innerHTML.indexOf('data-pick="tool"') < 0,
    "旧的「自家工具 / 竞品工具」一级分类已取消（只留二级色点）");
  ok(els.topicDist.innerHTML.indexOf('data-pick="toolType"') >= 0, "类型行可点击筛选");
  ok(els.topicDist.innerHTML.indexOf('data-pick="tool"') < 0, "不再有旧的 tool 筛选入口");
  ok((els.topicDist.innerHTML.match(/class="dot self"/g) || []).length > 0, "二级工具名带「自家」色点");
  ok((els.topicDist.innerHTML.match(/class="dot comp"/g) || []).length > 0, "二级工具名带「竞品」色点");
  ok(els.topicDist.innerHTML.indexOf("缺口") >= 0 || els.chanCover.innerHTML.indexOf("缺口") >= 0,
    "0 条的类型标出「缺口」（建模软件）");
  {
    // 每条只归一个类型 → 各类型之和必须等于总数，且二级之和 ≡ 该类型条数
    const byType = {};
    ITEMS.forEach(x => { const k = x.toolType || "__none__"; byType[k] = (byType[k] || 0) + 1; });
    const sum = Object.keys(byType).reduce((s, k) => s + byType[k], 0);
    ok(sum === ITEMS.length, "各类型条数之和 ≡ 总数", sum + " / " + ITEMS.length);

    const subs = els.topicDist.innerHTML.match(/<div class="tsub">[\s\S]*?<\/div>/g) || [];
    const typesWithName = Object.keys(byType).filter(k => k !== "__none__" && byType[k] > 0).length;
    ok(subs.length === typesWithName, "有工具名的类型各带一条明细（未提 / 0 条不展开）",
      subs.length + " 条 vs " + typesWithName + " 个类型");
    const sumOf = html => (html.match(/<b>(\d+)<\/b>/g) || [])
      .reduce((s, m) => s + parseInt(m.replace(/[^\d]/g, ""), 10), 0);
    const okSum = subs.every(html => Object.keys(byType).some(k => byType[k] === sumOf(html)));
    ok(okSum, "二级工具名之和 ≡ 对应类型条数",
      subs.map(sumOf).join(" / ") + " vs " + JSON.stringify(byType));

    // 点类型行 = 明细条数（所见即所得），含「未提具体工具」的哨兵值
    fireClick("[data-pick]", { "data-pick": "toolType", "data-val": "slice" });
    ok(els.countLine.textContent.indexOf("共 " + byType.slice + " 条") >= 0,
      "点「切片软件」→ 明细条数 = 该行数字", byType.slice + " / " + els.countLine.textContent);
    ok(els.filterSummary.innerHTML.indexOf("切片软件") >= 0, "摘要条显示「工具类型：切片软件」");
    fireClick("[data-pick]", { "data-pick": "toolType", "data-val": "__none__" });
    ok(els.countLine.textContent.indexOf("共 " + byType.__none__ + " 条") >= 0,
      "点「未提具体工具」→ 哨兵 __none__ 生效", byType.__none__ + " / " + els.countLine.textContent);
    fireClick("#clearAllBtn", { id: "clearAllBtn" });
    ok(els.countLine.textContent.indexOf("共 " + ITEMS.length + " 条") >= 0, "清空后恢复全部条目");
  }
  // 六段路径（落在 topicGrid）
  const stCards = (P_B.innerHTML.match(/class="stcard/g) || []).length;
  ok(stCards === 6, "实现路径六段各一张卡", String(stCards));
  ["找模型", "AI 生成", "建模改模", "切片", "打印运维", "分享变现"].forEach(n => {
    ok(P_B.innerHTML.indexOf(n) >= 0, "六段含「" + n + "」");
  });
  ok(P_B.innerHTML.indexOf("跨环节") >= 0, "归不到某段的单列「跨环节」");
  ok(P_B.innerHTML.indexOf("路径覆盖") >= 0, "标注路径覆盖率");
  ok(P_B.innerHTML.indexOf('data-pick="stage"') >= 0, "六段可点击筛选");
  // 矩阵替换（卷矩阵落在 chanCover）
  ok(P_A.innerHTML.indexOf("版本 × 问题类型") < 0, "旧的版本×问题矩阵已删除");
  ok(els.chanCover.innerHTML.indexOf("环节 × 信源覆盖") >= 0, "换成环节 × 信源覆盖矩阵");
  const heads = (els.chanCover.innerHTML.match(/<th>/g) || []).length;
  ok(heads >= 4, "覆盖矩阵表头 ≥ 4 列", String(heads));
  ok(/单源|缺口|双源/.test(els.chanCover.innerHTML), "覆盖矩阵标出单源 / 缺口");
  ok(els.chanCover.innerHTML.indexOf("月均") < 0, "不再出现已废弃的月均列");
} else {
  ok(els.ovA.innerHTML.indexOf("信源结构") >= 0, "mBox 有信源结构");
  ok(els.ovA.innerHTML.indexOf("载体结构") >= 0, "mBox 有载体结构");
  ok(P_A.innerHTML.indexOf("问题点 Top") >= 0, "mBox 有问题点占位面板");
}

/* ---------------- 明细卡片 ---------------- */
const grid = els.cardGrid.innerHTML;
const cards = (grid.match(/class="card[ "]/g) || []).length;
ok(cards > 0 && cards <= 20, "首页卡片数在 1..20", String(cards));
ok(grid.indexOf("原文 ·") >= 0, "卡片有原文段");

// 全彩（fc）的明细在 renderCards 里**渲染时按 heatScore 降序重排**（P7 口径：按讨论度，
// 不按日期），因此「页面上第一屏的条目」不等于 ITEMS.slice(0,N)。断言必须用与页面
// 相同的排序取第一屏，否则只看声明顺序会误报（2026-11-18 实测：期望 4 实得 14）。
const page1 = (KIND === "fc"
  ? ITEMS.slice().sort((a, b) => (b.heatScore || 0) - (a.heatScore || 0))
  : ITEMS).slice(0, cards);
// 译文段只在「可折叠」的卡里渲染（正文超过折叠阈值才出 <div class="fold">）。
// 正文极短的卡（如 Reddit RSS 只给 submitted by /u/xxx 的链接帖）不折叠，
// 整段内容已在摘要里可见，不该再期望一个译文段 —— 原断言按 textCn 全量计数会误报。
const cardHtml = grid.split(/<div class="card[ "]/).slice(1);
const folded = cardHtml.map(h => h.indexOf('class="fold"') >= 0);
ok(folded.length === cards, "卡片切分与卡片数一致", folded.length + " / " + cards);
const needCn = page1.filter((x, i) => x.textCn && x.originalText && folded[i]).length;
const gotCn = (grid.match(/class="seg-tx cn"/g) || []).length;
ok(gotCn === needCn, "折叠卡只要带 textCn 就有译文段", "期望 " + needCn + " 实得 " + gotCn);
// 反向：不折叠的卡不应出现译文段
const flatCn = page1.filter((x, i) => x.textCn && !folded[i]
  && (cardHtml[i] || "").indexOf('class="seg-tx cn"') >= 0).length;
ok(flatCn === 0, "不折叠的卡不渲染译文段", String(flatCn));
ok(/原文 · [A-Z]{2}/.test(grid) || grid.indexOf("原文 · 中文") >= 0, "原文段按语种标注");
ok(els.filterSummary.innerHTML === "", "初始无已选条件（摘要条为空）");
ok(els.countLine.textContent.indexOf("共 " + ITEMS.length + " 条") >= 0, "命中数等于总数", els.countLine.textContent);
ok(els.pager.innerHTML.indexOf("下一页") >= 0, "分页器渲染");

/* mBox 明细反馈流按 K3 版式重建（2026-11-16）：原有断言只校验折叠段，
   新版式改用 c-head / c-src / c-tags / c-foot，必须单独守护，防止同源模板回退。 */
if (KIND === "mbox") {
  ok(grid.indexOf('class="c-head"') >= 0, "mBox 卡片有 K3 式 c-head chip 行");
  ok(grid.indexOf('class="c-src"') >= 0, "mBox 卡片有 K3 式 c-src 来源行");
  ok(grid.indexOf('class="c-tags"') >= 0, "mBox 卡片有独立 c-tags 标签行");
  ok(grid.indexOf('class="c-foot"') >= 0, "mBox 卡片有 K3 式 c-foot 卡脚");
  ok(grid.indexOf('class="c-title') >= 0, "mBox 保留标题行（用户决策）");
  ok(grid.indexOf("未标注") >= 0, "mBox 无情感标注层时显式标未标注");
  ok(grid.indexOf("查看原文") >= 0, "mBox 卡脚有查看原文链接");
  ok(grid.indexOf('class="c-top"') < 0, "mBox 已移除旧 c-top 行");
  ok(grid.indexOf('class="fold"') < 0, "mBox 已移除旧折叠全文块");
  const deepSelN = (els.deepFilters.innerHTML.match(/class="deepsel/g) || []).length;
  ok(deepSelN === 4, "mBox 明细区四个下沉筛选", String(deepSelN));
  ok(els.deepFilters.innerHTML.indexOf("明细区定位") >= 0, "下沉筛选带标题");
  ok(els.flowHint.textContent.indexOf("K3 同款") >= 0, "明细区提示标注 K3 同款");
  const dm = /data-k="platform"[^>]*>[\s\S]*?<option value="([^"]+)"/.exec(els.deepFilters.innerHTML);
  if (dm) {
    const before = els.countLine.textContent;
    handlers.change({ target: { getAttribute: n => (n === "data-k" ? "platform" : null), value: dm[1] } });
    ok(els.filterSummary.innerHTML.indexOf("chip") >= 0, "下沉筛选联动摘要条");
    ok(els.countLine.textContent !== before, "下沉筛选联动明细条数", before + " -> " + els.countLine.textContent);
    fireClick("#clearAllBtn", { id: "clearAllBtn" });
    ok(els.filterSummary.innerHTML === "", "下沉筛选可清空复原");
  }
}

if (KIND === "sw") {
  // GitHub 通道：进明细、独立标签、不进总声量
  const ghAll = ITEMS.filter(x => x.sourceType === "GitHub");
  ok(ghAll.length > 0, "GitHub 缺陷单已并入明细", String(ghAll.length));
  ok(ghAll.every(x => x.countInVolume === false), "GitHub 条目不进总声量");
  ok(els.chanCover.innerHTML.indexOf("GitHub") >= 0, "覆盖清单含 GitHub 行");
  const swTotal = parseInt((els.countLine.textContent.match(/共 (\d+) 条/) || [])[1], 10);
  ok(swTotal === ITEMS.length, "明细条数含 GitHub（明细全可见）");
}

/* ---------------- 交互：面板下钻 ---------------- */
function fireClick(selector, attrs) {
  // 真实 DOM 里 e.target 既是被点元素（带 id），也能 closest 到祖先
  const node = { getAttribute: n => (attrs[n] !== undefined ? String(attrs[n]) : null), id: attrs.id || "" };
  const target = { id: attrs.id || "", getAttribute: node.getAttribute, closest: s => (s === selector ? node : null) };
  handlers.click({ target });
}
const pickRe = KIND === "fc"
  ? /data-pick="(channel|topic|model)" data-val="([^"]+)"/
  : /data-pick="(problem|major|channel|source|product|stage|tool)" data-val="([^"]+)"/;
const firstPick = pickRe.exec(P_A.innerHTML || P_B.innerHTML);
ok(!!firstPick, "面板条目可点击（带 data-pick）");
if (firstPick) {
  const key = firstPick[1], val = firstPick[2];
  const before = els.countLine.textContent;
  fireClick("[data-pick]", { "data-pick": key, "data-val": val });
  ok(els.filterSummary.innerHTML.indexOf("chip") >= 0, "点击后面板下钻生成已选条件");
  ok(els.filterSummary.innerHTML.indexOf("命中") >= 0, "摘要条显示命中数");
  ok(els.countLine.textContent !== before, "下钻后条数变化", before + " -> " + els.countLine.textContent);
  const chips = (els.filterSummary.innerHTML.match(/class="chip"/g) || []).length;
  ok(chips === 1, "摘要条只出现一个 chip", String(chips));
  ok(els.filters.innerHTML.indexOf('class="chip"') < 0, "筛选栏里不重复渲染已选 chip");
  fireClick("[data-pick]", { "data-pick": key, "data-val": val });
  ok(els.filterSummary.innerHTML === "", "再次点击取消该条件");
}

/* ---------------- 交互：清空 ---------------- */
const anyBar = /data-pick="([a-zA-Z]+)" data-val="([^"]+)"/.exec(P_A.innerHTML);
if (anyBar) {
  fireClick("[data-pick]", { "data-pick": anyBar[1], "data-val": anyBar[2] });
  fireClick("#clearAllBtn", { id: "clearAllBtn" });
  ok(els.filterSummary.innerHTML === "", "清空全部生效");
}

/* ---------------- 交互：分页 ---------------- */
if (ITEMS.length > 20) {
  const pg2 = /data-pg="2"/.exec(els.pager.innerHTML);
  ok(!!pg2, "分页器提供下一页");
  if (pg2) {
    fireClick("[data-pg]", { "data-pg": "2" });
    ok(els.countLine.textContent.indexOf("第 2 /") >= 0, "翻页到第 2 页", els.countLine.textContent);
    fireClick("[data-pg]", { "data-pg": "1" });
    ok(els.countLine.textContent.indexOf("第 1 /") >= 0, "翻回第 1 页");
  }
}

/* ---------------- 数据口径 ---------------- */
const missCn = ITEMS.filter(x => x.countInVolume !== false && x.originalText
  && !/[\u4e00-\u9fff]/.test(x.originalText) && !x.textCn).length;
ok(missCn === 0, "论坛条目非中文全部有译文", "缺 " + missCn);
// 中文原帖本来就不需要译文段，只需保证「非中文的 GitHub 条目都有译文」
const ghMiss = ITEMS.filter(x => x.countInVolume === false && !x.textCn
  && !/[\u4e00-\u9fff]/.test((x.title || "") + (x.originalText || ""))).length;
ok(ghMiss === 0, "非中文 GitHub 条目全部有译文", "缺 " + ghMiss);
if (KIND === "sw") {
  const ghCn = ITEMS.filter(x => x.countInVolume === false && /[\u4e00-\u9fff]/.test(x.title || "")).length;
  ok(ghCn > 0, "GitHub 里有中文用户直接提交的 issue", String(ghCn));
}
const tooLong = ITEMS.filter(x => (x.originalText || "").length > 1300).length;
ok(tooLong === 0, "正文均已按 1,200 字截断", "超长 " + tooLong);
if (KIND === "sw") {
  const badVer = ITEMS.filter(x => x.version && !/^\d{1,2}(\.\d{1,2})?$/.test(x.version)).length;
  ok(badVer === 0, "版本已归一为 主.次", "异常 " + badVer);
  const hasRaw = ITEMS.filter(x => x.version && !x.versionRaw).length;
  ok(hasRaw === 0, "保留 versionRaw 原始串", "缺 " + hasRaw);
  const badStage = ITEMS.filter(x => x.stage && !/^S[1-6]$/.test(x.stage)).length;
  ok(badStage === 0, "环节取值只能是 S1..S6 或空", "异常 " + badStage);
  const noStage = ITEMS.filter(x => !x.stage).length;
  ok(noStage / ITEMS.length < 0.25, "跨环节占比 < 25%", (noStage / ITEMS.length * 100).toFixed(1) + "%");
}

/* ---------------- mBox 去预热 ---------------- */
if (KIND === "mbox") {
  // 只查页面自身文案（模板 + meta），不能查用户原帖 —— 用户原话里出现「一键预热」属正常，
  // 早期整页 indexOf 会把它当违规误报。
  const staticPart = html.slice(0, html.indexOf("var COL="));
  const metaTxt = JSON.stringify(META);
  ["预热", "未上市", "未发布", "待验证", "预计", "尚未正式发布"].forEach(w => {
    ok(staticPart.indexOf(w) < 0 && metaTxt.indexOf(w) < 0, "页面文案不含「" + w + "」", w);
  });
  ok(html.indexOf("原文 + 译文") >= 0, "mBox 标注原文 + 译文");
}

report();
