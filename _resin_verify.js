/* 光固化专栏 · 静态校验：node _resin_verify.js */
const fs = require('fs');
const vm = require('vm');
const path = require('path');
const BASE = __dirname;
const file = path.join(BASE, 'resin-line.html');
let pass = 0, fail = 0;
function ok(cond, name, extra) { if (cond) { pass++; console.log('  PASS  ' + name); } else { fail++; console.log('  FAIL  ' + name + (extra ? ' :: ' + extra : '')); } }

if (!fs.existsSync(file)) { console.error('MISSING resin-line.html，先跑 _build_resin.py'); process.exit(1); }
const html = fs.readFileSync(file, 'utf8');
const m = html.match(/<script>([\s\S]*?)<\/script>/);
ok(!!m, '页面存在内联 script');
if (!m) process.exit(1);
const code = m[1];

let syntax = true, err = '';
try { new vm.Script(code, { filename: 'resin-inline.js' }); } catch (e) { syntax = false; err = e.message; }
ok(syntax, 'JS 语法可编译', err);

ok(!/__RESIN_(DATA|NAV)__/.test(html), '模板占位符已全部替换');
ok(!/<script[^>]+src=/.test(html), '无外部 JS 依赖');
ok(!/<link[^>]+href=["']https?:/.test(html), '无外部 CDN 样式');
ok(/var DATA = \{/.test(code), '数据对象内联');

const dm = code.match(/var DATA = (\{[\s\S]*?\});\nvar ITEMS/);
let data = null;
try { data = JSON.parse(dm ? dm[1] : 'null'); } catch (e) { data = null; }
ok(!!data, '内联 JSON 可解析');
if (data) {
  const items = data.items || [], meta = data.meta || {};
  ok(items.length > 0, '条目非空', 'count=' + items.length);
  const ids = items.map(x => x.id);
  ok(new Set(ids).size === ids.length, 'uid 无碰撞');
  ok(ids.every(x => /^RSN-\d{8}-\d{3}$/.test(x)), 'uid 前缀与格式');
  ok(items.every(x => x.sourceLink && /^https?:/.test(x.sourceLink)), '原文链接完整');
  ok(items.every(x => x.originalText && x.originalText.length > 0), '原文非空');
  ok(items.every(x => ['非常负面', '负面', '中性', '正面', '非常正面'].includes(x.sentiment)), '情感五档合法');
  ok(items.every(x => !x.model || (meta.models || []).some(mo => mo.code === x.model)), '机型均已登记');
  ok(items.every(x => new Set(x.problemPoints || []).size === (x.problemPoints || []).length), '问题点按条去重');
  ok(items.every(x => typeof x.countInVolume === 'boolean'), '有效/动态判据齐备');
  ok(items.every(x => x.translationStatus && x.labelSource), '译文状态与标注来源齐备');
  ok((meta.channelGaps || []).length > 0, '渠道缺口清单已披露');
  ok(meta.disclaimer && meta.sampleDisclosure, '口径免责与样本披露齐备');
}
console.log('\nVERIFY: ' + pass + ' PASS / ' + fail + ' FAIL');
process.exit(fail ? 1 : 0);
