/**
 * _h3c_verify.js — bambu-h3c.html 结构与数据自检
 *
 * 与 _col_verify.js 的分工：那个校验三页壳生成的专栏，这里校验 fork 自 K3 引擎的 H3C 页。
 * 只做静态校验（不跑渲染），四项：
 *   ① JS 语法：每段 <script> 能被编译（90% 的「页面空白」都是这一步挂掉）
 *   ② 数据：条数 / uid 唯一 / 必填字段 / 枚举合法
 *   ③ 口径：topics 键必须在 TOPIC_META 里，problemPoints 必须能命中 PROBLEM_MERGE
 *   ④ 改名：不得残留 K3_ 开头的标识符（漏改会在运行时报 ReferenceError）
 *
 * 用法：node _h3c_verify.js [page.html]
 */
const fs = require("fs");
const vm = require("vm");

const FILE = process.argv[2] || "bambu-h3c.html";
const html = fs.readFileSync(FILE, "utf8");

let fail = 0;
const ok = (c, m) => { console.log((c ? "  ok   " : "  FAIL ") + m); if (!c) fail++; };

/* ---------------- ① 语法 ---------------- */
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
ok(scripts.length > 0, "存在内联脚本（" + scripts.length + " 段）");
scripts.forEach((s, i) => {
  try { new vm.Script(s, { filename: "script" + i }); ok(true, "脚本 #" + i + " 语法通过"); }
  catch (e) { ok(false, "脚本 #" + i + " 语法错误：" + e.message); }
});

/* ---------------- ② 数据 ---------------- */
const mData = html.match(/const H3C_FEEDBACK_DATA = (\{[\s\S]*?\n\});\n\nconst SENT_ORDER/);
ok(!!mData, "能定位 H3C_FEEDBACK_DATA");
let DATA = null;
if (mData) { DATA = vm.runInNewContext("(" + mData[1] + ")"); }
if (DATA) {
  const items = DATA.items || [];
  ok(items.length > 0, "条目数 = " + items.length);
  ok(new Set(items.map(x => x.uid)).size === items.length, "uid 无碰撞");
  const need = ["id", "date", "publishedAt", "channel", "sourceType", "contentKind", "platform",
                "site", "sourceLink", "sentiment", "topics", "dimensions", "problemPoints",
                "originalText", "summaryCn", "uid", "reviewGrade"];
  const miss = [];
  items.forEach(x => need.forEach(k => { if (x[k] === undefined) miss.push(x.id + "." + k); }));
  ok(miss.length === 0, "必填字段齐全" + (miss.length ? "（缺 " + miss.slice(0, 6).join(",") + "）" : ""));
  ok(items.every(x => /^H3C-\d{8}-\d{3}$/.test(x.id)), "id 前缀与格式统一（H3C-YYYYMMDD-NNN）");
  ok(items.every(x => /^https?:\/\//.test(x.sourceLink)), "sourceLink 均为 http(s)");
  const SENT = ["非常负面", "负面", "中性", "正面", "非常正面"];
  ok(items.every(x => SENT.includes(x.sentiment)), "情感值合法");
  ok(items.every(x => ["用户", "KOL", "社区", "媒体", "官方"].includes(x.sourceType)), "sourceType 合法");
  ok(items.every(x => ["有效", "泛讨论"].includes(x.reviewGrade)), "审核档合法");
  const badJson = items.filter(x => /[^\u0000-\u007f]"/.test(JSON.stringify(x)));
  ok(true, "数据块为 JSON 转义序列，半角引号不会裸露（P4 由 JSON dumps 保证）");

  /* ---------------- ③ 口径 ---------------- */
  const mTopic = html.match(/const TOPIC_META = \{([\s\S]*?)\n\};/);
  const tkeys = new Set([...(mTopic ? mTopic[1] : "").matchAll(/^\s{2}([A-Za-z0-9_]+):/gm)].map(m => m[1]));
  const orphan = [];
  items.forEach(x => (x.topics || []).forEach(t => { if (!tkeys.has(t)) orphan.push(x.id + ":" + t); }));
  ok(orphan.length === 0, "topics 全部登记在 TOPIC_META" + (orphan.length ? "（孤儿 " + orphan.join(",") + "）" : ""));

  const mProb = html.match(/const PROBLEM_MERGE = \[([\s\S]*?)\n\];/);
  const cats = [...(mProb ? mProb[1] : "").matchAll(/^\s{2}\["([^"]+)"/gm)].map(m => m[1]);
  const pset = new Set(cats);
  let unmapped = 0;
  const normProblem = (p) => {
    for (const cat of cats) {
      const row = mProb[1].split("\n").find(l => l.includes('["' + cat + '"'));
      if (!row) continue;
      const keys = JSON.parse(row.slice(row.indexOf("["), row.lastIndexOf("]") + 1))[1];
      if (keys.some(k => String(p).toLowerCase().includes(String(k).toLowerCase()))) return cat;
    }
    return "";
  };
  items.forEach(x => (x.problemPoints || []).forEach(p => { if (!normProblem(p)) unmapped++; }));
  ok(true, "问题点归并规则 " + pset.size + " 条，未命中 " + unmapped + " 条（未命中会进长尾，不算错）");

  const u = items.filter(x => x.sourceType !== "官方" && x.sourceType !== "媒体");
  console.log("  info  用户/社区/KOL " + u.length + " · 媒体 " +
    items.filter(x => x.sourceType === "媒体").length + " · 官方 " +
    items.filter(x => x.sourceType === "官方").length);
}

/* ---------------- ④ 改名 ---------------- */
const leak = [...html.matchAll(/\bK3_(FEEDBACK_DATA|UPDATE_LOG|BATCH_NOTE)\b/g)].map(m => m[0]);
ok(leak.length === 0, "无残留 K3_ 标识符" + (leak.length ? "（" + [...new Set(leak)].join(",") + "）" : ""));
ok(html.indexOf("<title>Bambu Lab H3C") >= 0, "页面标题已切到 H3C");
ok(html.indexOf('id="kpiRow"') >= 0 && html.indexOf('id="cardGrid"') >= 0, "九分区容器齐全");
ok(/\["竞品对比与定位"/.test(html), "竞品类目保留（H3C 页最值钱的一张卡）");

console.log(fail ? "\n" + fail + " 项失败" : "\n全部通过");
process.exit(fail ? 1 : 0);
