/**
 * _h3c_runtime.js — bambu-h3c.html 运行时校验（假 DOM，真执行页面脚本）
 *
 * 只断言与「H3C 页与 K3 页的差异」相关的通用不变式，不复制 K3 那套存量数据断言
 * （Makers101 / 什么值得买 条数等属 K3 专属，照搬会假红）。
 *
 * 四组：
 *   A. 15 个容器均渲染出内容（ReferenceError / 空渲染）
 *   B. 口径：总声量排除官方与媒体；负面占比分母为 0 时显示「—」而非 0.0%
 *   C. 所见即所得：面板数字 ≡ 点开后明细条数
 *   D. 结构：五页导航同源、专项卡可下钻、分页控件
 *
 * 用法：node _h3c_runtime.js [page.html]
 */
const fs = require('fs');

const FILE = process.argv[2] || 'bambu-h3c.html';
const s = fs.readFileSync(FILE, 'utf8');
const scriptStart = s.lastIndexOf('<script>');
const scriptEnd = s.lastIndexOf('</script>');
const code = s.slice(scriptStart + '<script>'.length, scriptEnd);

const store = {};
function makeEl(id) {
  return { id: id, innerHTML: '', textContent: '', className: '', _attrs: {}, value: '',
    setAttribute(k, v) { this._attrs[k] = v; }, getAttribute(k) { return this._attrs[k]; },
    scrollIntoView() {}, classList: { add() {}, remove() {}, toggle() {} } };
}
global.document = {
  getElementById(id) { if (!store[id]) store[id] = makeEl(id); return store[id]; },
  createElement() { return { click() {}, style: {}, href: '', download: '' }; },
  body: { appendChild() {}, removeChild() {} }
};
global.window = {};
global.Blob = function () {};
global.URL = { createObjectURL() { return ''; }, revokeObjectURL() {} };

const EXPORTS = ['activeFilters', 'items', 'applyFilters', 'renderAll', 'clearAllFilters',
  'toggleTopic', 'setProblem', 'setDim', 'groupOf', 'GROUP_ORDER', 'GROUP_META',
  'PROBLEM_MERGE', 'TOPIC_META', 'normProblem', 'setGroup', 'setPlatform', 'gotoPage',
  'setDatePreset', 'clearDate', 'H3C_FEEDBACK_DATA', 'H3C_BATCH_NOTE', 'H3C_UPDATE_LOG',
  'buildUpdateLog', 'DIM_TOP', 'isPromoScope'];
eval(code + "\n;globalThis.__h3c = {" + EXPORTS.join(", ") + "};");

const H = globalThis.__h3c;
const af = H.activeFilters;
let fail = 0;
const check = (n, c, x) => { console.log((c ? 'PASS ' : 'FAIL ') + n + (x !== undefined ? '  -> ' + x : '')); if (!c) fail++; };
const cnt = (str, re) => (String(str).match(re) || []).length;

console.log('--- A. 容器渲染 ---');
const must = ['kpiRow', 'sentStack', 'problemsBody', 'sourceBody', 'dimsBody', 'topicGrid',
  'channelBody', 'chanListBody', 'matrixBody', 'compareBody', 'trendBody', 'filters',
  'deepFilters', 'countLine', 'cardGrid', 'updateBar'];
const empty = must.filter(id => !store[id] || String(store[id].innerHTML).trim().length === 0);
check('16 个容器均非空', empty.length === 0, empty.length ? empty.join(',') : 'ok');

console.log('\n--- B. 口径 ---');
const all = H.items();
const isOff = x => H.groupOf(x.platform) === 'official';
const isMedia = x => !isOff(x) && (x.sourceType === '媒体' || x.sourceType === '社区综述');
// 2026-11-11 BC 批次：isPromoScope 同时收口「零互动投放」与 countInVolume:false 的动态条目，
// 断言口径必须跟页面一致，否则动态条目会把总声量 / 情感分母抬高。
const userN = all.filter(x => !isOff(x) && !isMedia(x) && !H.isPromoScope(x)).length;
const mediaN = all.filter(isMedia).length;
const offN = all.filter(isOff).length;
const kv = String(store.kpiRow.innerHTML);
check('总声量 = 用户声量（排除官方与媒体）', kv.indexOf('>' + userN + '</div>') > 0, userN + ' / 全量 ' + all.length);
check('总声量副标注明媒体与官方单列',
  kv.indexOf('另有媒体 ' + mediaN + ' 条 / 厂商官方 ' + offN + ' 条单列') > 0, '媒体 ' + mediaN + ' · 官方 ' + offN);
const analytic = all.filter(x => !isOff(x) && !isMedia(x) && !H.isPromoScope(x) && x.reviewGrade === '有效');
if (!analytic.length) {
  check('负面占比分母为 0 时显示「—」', kv.indexOf('—') > 0 && kv.indexOf('0%<') < 0);
  check('分母为 0 时副标说明不计算', kv.indexOf('空白 ≠ 无负面') > 0);
} else {
  const neg = analytic.filter(x => /负面/.test(x.sentiment)).length;
  const pct = Math.round(neg / analytic.length * 1000) / 10 + '%';
  check('负面占比 = 有效档负面 / 有效档', kv.indexOf(pct) > 0, pct + '（' + neg + '/' + analytic.length + '）');
}

console.log('\n--- C. 所见即所得 ---');
H.clearAllFilters(); H.renderAll();
const stackN = analytic.length;
check('情感结构分母 = 有效档条数', String(store.sentStack.innerHTML).indexOf('全部有效档</b> ' + stackN + ' 条') > 0, '有效 ' + stackN);
check('情感结构五档齐全', ['非常负面', '负面', '中性', '正面', '非常正面'].every(x => String(store.sentStack.innerHTML).indexOf(x) > 0));

// 问题点面板：第一行的条数 ≡ 点开后明细条数
const pm = String(store.problemsBody.innerHTML).match(/data-p="([^"]+)"[\s\S]*?<span class="hnum">(\d+)/);
if (pm) {
  const cat = pm[1], shown = Number(pm[2]);
  H.setProblem(cat);
  const hit = H.applyFilters().length;
  check('问题点面板数字 = 点开后条数', shown === hit, cat.slice(0, 14) + '：面板 ' + shown + ' / 明细 ' + hit);
  H.setProblem(cat);
  check('再次点击取消问题点筛选', af.problem === 'all');
} else {
  console.log('  info  当前无问题点标签（数据为空或全为正面），跳过该组');
}

// 专项卡下钻
const firstTopic = Object.keys(H.TOPIC_META).find(k => all.some(x => (x.topics || []).includes(k)));
if (firstTopic) {
  H.toggleTopic(firstTopic);
  check('专项卡点击后筛选生效', af.topic === firstTopic, firstTopic);
  check('专项卡高亮', store.topicGrid.innerHTML.indexOf('class="topic on"') > 0);
  H.toggleTopic(firstTopic);
  check('再次点击取消', af.topic === 'all');
}

// 渠道组归并
const gcnt = {};
all.forEach(x => { const g = H.groupOf(x.platform); gcnt[g] = (gcnt[g] || 0) + 1; });
check('渠道组归并后总数 = 样本数', H.GROUP_ORDER.reduce((a, g) => a + (gcnt[g] || 0), 0) === all.length);
check('图例覆盖全部渠道组', cnt(store.channelBody.innerHTML, /legend-clk/g) === H.GROUP_ORDER.length);
check('0 值预期组标「缺口」',
  cnt(store.channelBody.innerHTML, /<span class="t-flag">缺口<\/span>/g) ===
  H.GROUP_ORDER.filter(g => !gcnt[g] && H.GROUP_META[g].expect).length);

console.log('\n--- D. 结构与交互 ---');
// 2026-11-12 B3：第六个专栏（光固化 resin-line.html）上线，侧栏子项 5 -> 6
check('六页导航同源（6 个子项）', cnt(s, /nav-item sub/g) === 6, cnt(s, /nav-item sub/g));
check('本页导航高亮', /nav-item sub active" href="bambu-h3c.html"/.test(s));
check('其余五页入口齐全',
  ['creality-k3.html', 'creality-mbox.html', 'software-columns.html', 'fullcolor-columns.html', 'resin-line.html']
    .every(h => s.indexOf('href="' + h + '"') > 0));
check('明细卡片已渲染', cnt(store.cardGrid.innerHTML, /class="card/g) === Math.min(20, all.length), cnt(store.cardGrid.innerHTML, /class="card/g) + '/' + Math.min(20, all.length));
check('数据更新条含批次与条数', String(store.updateBar.innerHTML).indexOf(String(all.length)) > 0);
check('更新历史可派生', typeof H.buildUpdateLog === 'function' && H.buildUpdateLog().length > 0, H.buildUpdateLog().length + ' 条');
check('无残留 K3 标识符（运行期）', typeof H.H3C_FEEDBACK_DATA === 'object' && H.H3C_FEEDBACK_DATA.model === 'Bambu Lab H3C');

console.log(fail ? '\n' + fail + ' 项失败' : '\n全部通过');
process.exit(fail ? 1 : 0);
