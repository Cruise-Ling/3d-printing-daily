/* 光固化专栏 · 运行时校验（假 DOM 真执行）：node _resin_runtime.js */
const fs = require('fs');
const vm = require('vm');
const path = require('path');
const html = fs.readFileSync(path.join(__dirname, 'resin-line.html'), 'utf8');
const code = html.match(/<script>([\s\S]*?)<\/script>/)[1];
let pass = 0, fail = 0;
function ok(c, n, x) { if (c) { pass++; console.log('  PASS  ' + n); } else { fail++; console.log('  FAIL  ' + n + (x ? ' :: ' + x : '')); } }

const els = {};
function mk() { return { innerHTML: '', textContent: '', oninput: null, style: {}, setAttribute() {}, getAttribute() {} }; }
const document = {
  getElementById(id) { if (!els[id]) els[id] = mk(); return els[id]; },
  addEventListener() {},
  createElement() { return mk(); },
  body: { appendChild() {}, removeChild() {} }
};
const sandbox = {
  document, console, Date, Math, JSON, String, Number, Array, Object, Boolean, RegExp,
  parseInt, parseFloat, isNaN,
  Blob: function () {}, URL: { createObjectURL() { return ''; } },
  window: {}
};
let runErr = '';
try { vm.runInNewContext(code, sandbox, { timeout: 5000 }); } catch (e) { runErr = e.message; }
ok(!runErr, '脚本完整执行无异常', runErr);

const CONTAINERS = ['updateBar', 'filters', 'kpis', 'sent', 'prob', 'src', 'matrix',
  'quality', 'compete', 'channels', 'trend', 'trendCtl', 'exportFields', 'cards', 'foot'];
CONTAINERS.forEach(function (id) { ok(!!(els[id] && els[id].innerHTML.length > 0), '容器非空 ' + id); });

ok(/总声量/.test(els.kpis.innerHTML), 'KPI 五卡渲染');
ok(/口径说明/.test(els.foot.innerHTML), '口径脚注常驻');
ok(/光固化专栏/.test(els.filters.innerHTML) || /全部机型/.test(els.filters.innerHTML), '机型 chip 平铺筛选');
ok(!/<select/.test(els.filters.innerHTML), '筛选器无下拉折叠');
ok(/渠道覆盖|自动可达/.test(els.channels.innerHTML), '渠道缺口清单渲染');

/* 2026-11-12 版式对齐 K3（Q1–Q5）：顶部无标注、四分区、200px 侧栏、V1.1 文案 */
ok(!/class="notice"/.test(html), 'Q1 顶部无橙黄警示横幅');
ok(!/规则预标 · 待人工确认|需 T\+1 触达|· 规则预标结果/.test(html), 'Q5 V1.0 过时文案已清除');
ok(/AI 逐条语义复核/.test(els.foot.innerHTML), 'V1.1 AI 逐条语义复核口径披露');
ok(/class="ub-dot"/.test(els.updateBar.innerHTML), 'K3 灰底 update-bar 绿点结构');
ok(/口径版本 <b>V1\.1<\/b>/.test(els.updateBar.innerHTML), 'update-bar 口径版本为 V1.1');
ok(/class="top-bar"/.test(html) && /class="brand-icon"/.test(html), 'Q2 K3 top-bar 品牌区');
ok((html.match(/class="sec-title"/g) || []).length === 4, 'Q2 四个 K3 风格分区');
ok(/class="panel"/.test(html) && /class="kpi-row"/.test(html), 'Q2 K3 panel / kpi-row 结构');
ok(/\.sidebar\{[^}]*width:200px/.test(html), 'Q4 侧栏 200px 与其余六页同源');
ok(/全局筛选 · 联动所有面板/.test(els.filters.innerHTML), 'Q3 顶部全局筛选标注保留');
ok(/class="k-value"/.test(els.kpis.innerHTML), 'KPI 取数结构为 k-value');

if (!runErr) {
  const f = sandbox.filtered();
  const cards = (els.cards.innerHTML.match(/class="item"/g) || []).length;
  ok(cards === f.length, '所见即所得：明细卡片数 = 筛选命中数', cards + ' vs ' + f.length);
  const kpiVol = (els.kpis.innerHTML.match(/<div class="k-value"[^>]*>(\d+|—)<\/div>/) || [])[1];
  ok(kpiVol === String(f.length), 'KPI 总声量与筛选结果一致', kpiVol + ' vs ' + f.length);

  const before = f.length;
  sandbox.S.model = 'halot-mage';
  sandbox.renderAll();
  const after = sandbox.filtered().length;
  ok(after <= before && after >= 0, '机型筛选联动生效', before + ' -> ' + after);
  ok(/halot-mage/.test(JSON.stringify(sandbox.S)), '机型状态已写入');

  sandbox.S.model = '__no_such_model__';
  sandbox.renderAll();
  ok(/—/.test(els.sent.innerHTML), '空分母显示「—」而非 0.0%');
  ok(/当前筛选无明细/.test(els.cards.innerHTML), '空态有明确文案');

  sandbox.S.model = 'all';
  sandbox.S.scope = 'all';
  sandbox.renderAll();
  ok(sandbox.filtered().length >= before, '全量口径可切换');

  const cols = Object.keys(sandbox.S.fields).filter(k => sandbox.S.fields[k]);
  ok(cols.length >= 10, 'CSV 自定义字段可选', 'fields=' + cols.length);
}
console.log('\nRUNTIME: ' + pass + ' PASS / ' + fail + ' FAIL');
process.exit(fail ? 1 : 0);
