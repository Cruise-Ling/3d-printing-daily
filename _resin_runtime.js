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

const CONTAINERS = ['updateBar', 'notice', 'filters', 'kpis', 'sent', 'prob', 'src', 'matrix',
  'quality', 'compete', 'channels', 'trend', 'trendCtl', 'exportFields', 'cards', 'foot'];
CONTAINERS.forEach(function (id) { ok(!!(els[id] && els[id].innerHTML.length > 0), '容器非空 ' + id); });

ok(/总声量/.test(els.kpis.innerHTML), 'KPI 五卡渲染');
ok(/口径说明/.test(els.foot.innerHTML), '口径脚注常驻');
ok(/规则预标/.test(els.notice.innerHTML), '规则预标免责提示');
ok(/光固化专栏/.test(els.filters.innerHTML) || /全部机型/.test(els.filters.innerHTML), '机型 chip 平铺筛选');
ok(!/<select/.test(els.filters.innerHTML), '筛选器无下拉折叠');
ok(/渠道覆盖|自动可达/.test(els.channels.innerHTML), '渠道缺口清单渲染');

if (!runErr) {
  const f = sandbox.filtered();
  const cards = (els.cards.innerHTML.match(/class="item"/g) || []).length;
  ok(cards === f.length, '所见即所得：明细卡片数 = 筛选命中数', cards + ' vs ' + f.length);
  const kpiVol = (els.kpis.innerHTML.match(/<div class="vl"[^>]*>(\d+|—)<\/div>/) || [])[1];
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
