const fs = require('fs');
const s = fs.readFileSync('creality-k3.html', 'utf8');

const scriptStart = s.lastIndexOf('<script>');
const scriptEnd = s.lastIndexOf('</script>');
const code = s.slice(scriptStart + '<script>'.length, scriptEnd);

const store = {};
function makeEl(id) {
  return { id: id, innerHTML: '', textContent: '', className: '', _attrs: {},
    setAttribute(k, v) { this._attrs[k] = v; }, scrollIntoView() {},
    classList: { add() {}, remove() {}, toggle() {} } };
}
global.document = {
  getElementById(id) { if (!store[id]) store[id] = makeEl(id); return store[id]; },
  createElement() { return { click() {}, style: {}, href: '', download: '' }; },
  body: { appendChild() {}, removeChild() {} }
};
global.window = {};
global.Blob = function () {};
global.URL = { createObjectURL() { return ''; }, revokeObjectURL() {} };

const EXPORTS = ['activeFilters','items','applyFilters','setDatePreset','setDateMode','setDateBound',
  'clearDate','pickDay','toggleTopic','dateRangeOf','nearestPublished','todayStr','K3_FEEDBACK_DATA',
  'groupOf','setGroup','setPlatform','GROUP_ORDER','GROUP_META',
  'setProblem','setDim','toggleTail','tailOpen','clearPanelFilters','clearAllFilters','normProblem','topDims','PROBLEM_MERGE',
  'setF','renderDeepFilters','renderCards','DIM_TOP','DIM_OTHER',
  'CHANNEL_MATRIX','renderChanList','removeFilter','buildUpdateLog','toggleUpdHist','K3_BATCH_NOTE','K3_UPDATE_LOG'];
const harness = code + "\n;globalThis.__k3 = {" + EXPORTS.join(", ") + "};";
eval(harness);

const K = globalThis.__k3;
const activeFilters = K.activeFilters;

const cnt = (str, re) => (String(str).match(re) || []).length;
let fail = 0;
function check(name, cond, extra) {
  console.log((cond ? 'PASS ' : 'FAIL ') + name + (extra !== undefined ? '  -> ' + extra : ''));
  if (!cond) fail++;
}

const must = ['kpiRow','sentStack','problemsBody','sourceBody','dimsBody','dimsNote','topicGrid','channelBody','matrixBody','compareBody','trendBody','filters','countLine','cardGrid','updateBar'];
let empty = must.filter(id => !store[id] || String(store[id].innerHTML).length === 0);
check('15 个容器均非空', empty.length === 0, empty.length ? empty.join(',') : 'ok');

console.log('\n--- 时间筛选 ---');
check('筛选栏含「时间」', store.filters.innerHTML.indexOf('>时间<') >= 0);
check('筛选栏含「口径」', store.filters.innerHTML.indexOf('>口径<') >= 0);
check('含快捷段 今天/昨天/近7天/近30天',
  ['今天','昨天','近 7 天','近 30 天'].every(x => store.filters.innerHTML.indexOf(x) >= 0));
check('含自定义日期输入', cnt(store.filters.innerHTML, /type="date"/g) === 2);
check('含口径切换双按钮', store.filters.innerHTML.indexOf('按发布日') >= 0 && store.filters.innerHTML.indexOf('按采集日') >= 0);
console.log('   今天字符串 =', todayStr());

console.log('\n--- 日期口径判定（按发布日 / 按采集日） ---');
const total = items().length;
activeFilters.dateKey = 'all';
console.log('   全部 =', applyFilters().length, '/', total);
setDatePreset('d30');
console.log('   近30天 =', applyFilters().length);
setDatePreset('d7');
console.log('   近7天 =', applyFilters().length);
setDatePreset('today');
const todayPublished = applyFilters().length;
console.log('   今天(按发布日) =', todayPublished, '| 空态命中 =', store.cardGrid.innerHTML.indexOf('暂无反馈') >= 0);
if (todayPublished === 0) {
  check('空态给出最近日期提示', store.cardGrid.innerHTML.indexOf('最近一条发布于') >= 0);
  check('空态给出跳转按钮', store.cardGrid.innerHTML.indexOf('跳到最近有数据的日期') >= 0);
}
setDateMode('collection');
console.log('   今天(按采集日) =', applyFilters().length, '（数据 date 字段全为 2026-10-13）');
setDateMode('published');

console.log('\n--- 趋势图下钻 ---');
const near = nearestPublished();
pickDay(near);
check('pickDay 后区间锁定该日', activeFilters.dateFrom === near && activeFilters.dateTo === near, near);
check('pickDay 后模式回到按发布日', activeFilters.dateMode === 'published');
check('pickDay 命中条目 > 0', applyFilters().length > 0, applyFilters().length);
check('趋势柱标记 on', cnt(store.trendBody.innerHTML, /class="tcol on"/g) === 1);
check('趋势柱可点击', cnt(store.trendBody.innerHTML, /onclick="pickDay/g) >= 5);
check('趋势柱堆叠为三档段', cnt(store.trendBody.innerHTML, /class="tseg"/g) > 0, cnt(store.trendBody.innerHTML, /class="tseg"/g) + ' 段');
check('趋势柱含负面/中性/正面三色', store.trendBody.innerHTML.indexOf('#f85149') > 0 && store.trendBody.innerHTML.indexOf('#8b949e') > 0 && store.trendBody.innerHTML.indexOf('#3fb950') > 0);
check('趋势柱 title 含三档明细', store.trendBody.innerHTML.indexOf('负面') > 0 && store.trendBody.innerHTML.indexOf('中性') > 0 && store.trendBody.innerHTML.indexOf('正面') > 0);
check('趋势图例（三档合计）', store.trendBody.innerHTML.indexOf('stack-legend') > 0 && store.trendBody.innerHTML.indexOf('柱高 = 当日声量') > 0);
check('趋势数字降噪（低量日隐藏数字）', cnt(store.trendBody.innerHTML, /t-num t-hide/g) > 0, cnt(store.trendBody.innerHTML, /t-num t-hide/g) + ' 天');

console.log('\n--- 卡片特性标签 ---');
clearDate();
const cards = cnt(store.cardGrid.innerHTML, /class="card/g);
check('卡片数 = 首页条数（每页 20）', cards === Math.min(20, total), cards + '/' + Math.min(20, total));
const topicTags = cnt(store.cardGrid.innerHTML, /class="tag topic-tag/g);
check('特性标签已渲染', topicTags > 0, topicTags + ' 个');
check('特性标签可点击筛选', store.cardGrid.innerHTML.indexOf('onclick="toggleTopic(') > 0);
check('特性标签显示中文名', store.cardGrid.innerHTML.indexOf('多色与废料') > 0 || store.cardGrid.innerHTML.indexOf('KliTek 换嘴') > 0);
const pTags = cnt(store.cardGrid.innerHTML, /class="tag p-tag/g);
check('问题点标签已渲染', pTags > 0, pTags + ' 个');
check('问题点标签可点击跳转', cnt(store.cardGrid.innerHTML, /onclick="setProblem\(/g) === pTags, pTags + ' 个可点');

console.log('\n--- 明细分页（每页 20 条 + 页码下拉） ---');
clearDate();
K.clearAllFilters();
const pages = Math.ceil(total / 20);
check('分页控件出现（多页）', store.countLine.innerHTML.indexOf('上一页') >= 0 && store.countLine.innerHTML.indexOf('下一页') >= 0);
check('页码下拉（可直接跳页）', cnt(store.countLine.innerHTML, /class="page-select"/g) === 1 && cnt(store.countLine.innerHTML, /<option value="/g) === pages, cnt(store.countLine.innerHTML, /<option value="/g) + ' 个选项');
check('首页选中第 1 页', store.countLine.innerHTML.indexOf('<option value="1" selected>第 1 页</option>') >= 0);
check('首页显示区间 1–20', store.countLine.innerHTML.indexOf('1–20') >= 0);
check('首页卡片数 = 20', cnt(store.cardGrid.innerHTML, /class="card/g) === 20, cnt(store.cardGrid.innerHTML, /class="card/g));
gotoPage(2);
check('翻页后选中第 2 页', store.countLine.innerHTML.indexOf('<option value="2" selected>第 2 页</option>') >= 0);
check('第 2 页卡片数 = 20', cnt(store.cardGrid.innerHTML, /class="card/g) === 20);
gotoPage(pages);
check('末页卡片数 = 余数', cnt(store.cardGrid.innerHTML, /class="card/g) === total - (pages - 1) * 20, cnt(store.cardGrid.innerHTML, /class="card/g) + '/' + (total - (pages - 1) * 20));
gotoPage(pages + 1);
check('越界翻页被拦截（仍停末页）', store.countLine.innerHTML.indexOf('<option value="' + pages + '" selected') >= 0);
gotoPage(2);
K.setGroup('overseaDirect');
check('筛选变化后自动回第 1 页', store.countLine.innerHTML.indexOf('<option value="1" selected') >= 0);
check('筛选后首页卡片 = min(20, 组条数)', cnt(store.cardGrid.innerHTML, /class="card/g) === Math.min(20, K.items().filter(function(x){ return K.groupOf(x.platform) === 'overseaDirect'; }).length));
K.clearAllFilters();
renderAll();

console.log('\n--- 特性标签 <-> 专项卡联动 ---');
toggleTopic('multicolor');
check('点击后筛选生效', activeFilters.topic === 'multicolor');
check('专项卡高亮', store.topicGrid.innerHTML.indexOf('class="topic on"') > 0);
check('卡片标签高亮', cnt(store.cardGrid.innerHTML, /topic-tag on/g) > 0);
console.log('   多色筛选后条数 =', applyFilters().length);
toggleTopic('multicolor');
check('再次点击取消', activeFilters.topic === 'all');

console.log('\n--- 渠道来源占比 ---');
const ch = store.channelBody.innerHTML;
const gOrder = K.GROUP_ORDER, gMeta = K.GROUP_META;
const gcnt = {}; K.items().forEach(x => { const g = groupOf(x.platform); gcnt[g] = (gcnt[g] || 0) + 1; });
console.log('   渠道组分布 =', gOrder.map(g => gMeta[g].name + ':' + (gcnt[g] || 0)).join(' | '));
check('渠道组归并后总数 = 样本数', gOrder.reduce((a, g) => a + (gcnt[g] || 0), 0) === total);
check('堆叠段数 = 非零渠道组数', cnt(ch, /<span style="width:/g) === gOrder.filter(g => gcnt[g]).length);
check('图例覆盖全部渠道组', cnt(ch, /class="sl legend-clk/g) === gOrder.length, cnt(ch, /class="sl legend-clk/g));
check('0 值预期组标「缺口」', cnt(ch, /<span class="t-flag">缺口<\/span>/g) === gOrder.filter(g => !gcnt[g] && gMeta[g].expect).length);
// 平台行数按数据动态算，不写死。2026-10-15 起榜单切到 site（站点级）口径：
// Makers101 与 Makers101（引 r/Creality）合并为一行，>=2 条的站点从 6 个降到 5 个
const pcnt2 = {}; K.items().forEach(x => { pcnt2[x.site || x.platform] = (pcnt2[x.site || x.platform] || 0) + 1; });
const topPlatN = Object.keys(pcnt2).filter(k => pcnt2[k] >= 2).length;
const tailPlatN = Object.keys(pcnt2).filter(k => pcnt2[k] < 2).length;
check('站点行已渲染（>=2 条者）', cnt(ch, /class="hbar clk/g) === topPlatN, cnt(ch, /class="hbar clk/g) + '/' + topPlatN);
check('长尾站点折叠行', ch.indexOf('个站点各仅 1 条') > 0 && ch.indexOf('已折叠') > 0);
check('Makers101 已按站点合并为一行', (pcnt2['Makers101'] || 0) >= 6 && cnt(ch, /data-p="Makers101"/g) === 1, 'site 计数=' + (pcnt2['Makers101'] || 0));
// 折叠交互（2026-10-15 新增）：折叠行可展开，展开后长尾以完整条形行呈现，可再收起
check('折叠行可点击（toggleTail source）', ch.indexOf("toggleTail('source')") > 0);
toggleTail('source');
check('展开后长尾条形行渲染（top + tail 全量）',
  cnt(store.channelBody.innerHTML, /class="hbar clk/g) === topPlatN + tailPlatN,
  cnt(store.channelBody.innerHTML, /class="hbar clk/g) + '/' + (topPlatN + tailPlatN));
check('展开后出现收起入口', store.channelBody.innerHTML.indexOf('收起各仅 1 条的') > 0);
// 2026-10-15：收起入口必须在长尾行**之前**（原折叠行位置），不用滚到几十行末尾才能收
const chOpen = store.channelBody.innerHTML;
check('收起入口位于长尾行之前（source）',
  chOpen.indexOf('收起各仅 1 条的') >= 0 &&
  chOpen.indexOf('收起各仅 1 条的') < chOpen.indexOf('class="hbar clk"', chOpen.indexOf('收起各仅 1 条的')));
check('展开态长尾之后无第二个收起入口', cnt(chOpen, /收起各仅 1 条的/g) === 1);
toggleTail('source');
check('再次收起后恢复折叠行', cnt(store.channelBody.innerHTML, /class="hbar clk/g) === topPlatN && store.channelBody.innerHTML.indexOf('已折叠') > 0);
check('口径警示（归并帖）', ch.indexOf('不等于') > 0 && ch.indexOf('个独立来源') > 0);
check('采集缺口提示', ch.indexOf('采集覆盖缺口') > 0);
// 2026-10-14：Reddit 接入后海外一手社区不再为 0；2026-10-15：YouTube 接入后海外视频不再为 0
check('海外一手社区已有一手声量（Reddit 接入）', (gcnt.overseaDirect || 0) > 0, gcnt.overseaDirect || 0);
check('海外视频已有一手声量（YouTube 接入）', (gcnt.overseaVideo || 0) > 0, gcnt.overseaVideo || 0);

setGroup('cnCommunity');
check('setGroup 生效', applyFilters().length === gcnt.cnCommunity, applyFilters().length + '/' + gcnt.cnCommunity);
check('渠道组筛选 chip 出现（摘要条）', store.filterSummary.innerHTML.indexOf('渠道组：国内社区') > 0);
setPlatform('什么值得买');
// 站点筛选必须收敛到「该站点」而不是「该渠道组」——
// B 站接入前国内社区 100% 是什么值得买，写死组数也能过，现在会露馅
const nSmzdm = K.items().filter(x => (x.site || x.platform) === '什么值得买').length;
check('setPlatform 生效（只留该站点）', applyFilters().length === nSmzdm, applyFilters().length + '/' + nSmzdm);
// 2026-10-29：页面 chip 文案已由「站点：」改为「渠道：」，断言同步（检查意图不变）
check('站点筛选 chip 出现（摘要条）', /(站点|渠道)：什么值得买/.test(store.filterSummary.innerHTML));
setPlatform('什么值得买');
setGroup('cnCommunity');   // 先取消组筛选，Makers101 属海外聚合站，挂着组筛选会得 0
check('再次点击取消（渠道组）', activeFilters.group === 'all');
// 站点合并的关键用例：Makers101 承载两个 platform 值，点击必须把两条都留下
const nM101 = K.items().filter(x => (x.site || x.platform) === 'Makers101').length;
setPlatform('Makers101');
check('setPlatform 按站点合并过滤（Makers101）', applyFilters().length === nM101 && nM101 >= 6, applyFilters().length + '/' + nM101);
setPlatform('Makers101');
check('再次点击取消（平台）', activeFilters.platform === 'all');

// ── KPI 口径：厂商官方单列（2026-10-19）─────────────────────────────
// 论坛帖天然是求助/吐槽（won't move past 0% / clogged / not working），
// 与官方 FAQ 一起混入会让负面率被渠道结构机械性拉高，所以官方组单列、不计入用户声量。
console.log('\n--- KPI 口径：厂商官方单列 ---');
const _offN = items().filter(x => groupOf(x.platform) === 'official').length;
const _userN = items().length - _offN;
const _userNeg = items().filter(x => groupOf(x.platform) !== 'official' && /负面/.test(x.sentiment)).length;
const _kv = String(store.kpiRow.innerHTML);
check('总声量已排除厂商官方', _kv.indexOf('>' + _userN + '</div>') > 0, _userN + ' / 全量 ' + items().length);
check('总声量副标题注明官方单列', _kv.indexOf('另有厂商官方 ' + _offN + ' 条单列') > 0, _offN + ' 条');
// 2026-10-19 评价类接入后，负面占比改为**混合口径**且保留 1 位小数
// 2026-10-20 用户定稿：分析口径进一步收窄为「有效档」—— 泛讨论（105 条，其中 81 条中性）
// 只计声量、不进情感，否则「K3 上市了吗」这类会把负面率机械性压低。
const _rate = function(a, b) { return b ? Math.round(a / b * 1000) / 10 : 0; };
const _validUser = function(x) { return x.reviewGrade === '有效' && groupOf(x.platform) !== 'official'; };
const _validN = items().filter(_validUser).length;
const _validNeg = items().filter(function(x) { return _validUser(x) && /负面/.test(x.sentiment); }).length;
check('负面占比按「分析口径 = 有效档」计算', _kv.indexOf(_rate(_validNeg, _validN) + '%</div>') > 0,
  _rate(_validNeg, _validN) + '% = ' + _validNeg + '/' + _validN);
check('总声量仍为全量用户声量（泛讨论可见）', _kv.indexOf('>' + _userN + '</div>') > 0, _userN + ' 条');
check('总声量副标注明含泛讨论', /含泛讨论 \d+ 条/.test(_kv));
check('负面占副标注明分析口径', /分析口径 · 有效 \d+/.test(_kv));
check('总声量副标题给出载体构成', /评价 \d+/.test(_kv) && /图文 \d+/.test(_kv), String(_kv).replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').slice(180, 300));

console.log('\n--- 渠道覆盖清单 ---');
const cl = store.chanListBody.innerHTML;
const CM = K.CHANNEL_MATRIX;
check('覆盖清单已渲染', cl.length > 500, cl.length + ' 字节');
check('清单行数 = CHANNEL_MATRIX 条数', cnt(cl, /class="chrow/g) === CM.length, cnt(cl, /class="chrow/g) + '/' + CM.length);
check('分组标题数 = 有清单项的组数', cnt(cl, /class="chgroup"/g) === new Set(CM.map(c => c.group)).size, cnt(cl, /class="chgroup"/g));
check('自动/人工标注齐全',
  cnt(cl, /class="chm auto"/g) === CM.filter(c => c.method === 'auto').length &&
  cnt(cl, /class="chm manual"/g) === CM.filter(c => c.method === 'manual').length,
  cnt(cl, /class="chm auto"/g) + ' 自动 / ' + cnt(cl, /class="chm manual"/g) + ' 人工');
check('不可自动标注数正确', cnt(cl, /class="chst blocked"/g) === CM.filter(c => c.state === 'blocked').length, cnt(cl, /class="chst blocked"/g));
// 2026-10-19：Hackaday 通路实测可通（WP REST 返回 20 篇），但 Creality 相关无 K3 内容 → 标 todo。
// 所以 todo 不再要求为 0，而是要求每个 todo 渠道都在 note 里写明实测结论、且数量受控。
const todoRows = CM.filter(c => c.state === 'todo');
check('todo 渠道均写明实测原因', todoRows.every(c => /实测/.test(c.note || '')), todoRows.map(c => c.site).join(',') || '无');
check('todo 渠道数受控（≤1）', cnt(cl, /class="chst todo"/g) <= 1, cnt(cl, /class="chst todo"/g));
check('新增渠道已入清单：Creality 官方论坛 / All3DP / Hackaday / Chiphell',
  ['Creality 官方论坛', 'All3DP', 'Hackaday', 'Chiphell'].every(s => cl.indexOf(s) > 0));
check('All3DP / Chiphell 已如实标不可自动',
  CM.filter(c => ['All3DP', 'Chiphell'].indexOf(c.site) >= 0).every(c => c.state === 'blocked'));
check('论坛渠道接入状态 = ok 且注明厂商官方单列',
  (CM.filter(c => c.site === 'Creality 官方论坛')[0] || {}).state === 'ok' &&
  /官方/.test((CM.filter(c => c.site === 'Creality 官方论坛')[0] || {}).note || ''));
check('仅量级标注 = 1（TikTok）', cnt(cl, /class="chst partial"/g) === 1 && cl.indexOf('仅量级') > 0);
check('待探标注 = 1（Amazon）', cnt(cl, /class="chst unknown"/g) === 1, cnt(cl, /class="chst unknown"/g));
check('0 条渠道置灰', cnt(cl, /class="chrow zero"/g) > 0, cnt(cl, /class="chrow zero"/g) + ' 行');
check('清单合计行说明来源限制', cl.indexOf('人工投喂') > 0 && cl.indexOf('商业数据服务') > 0);
check('清单含条目级采集方式统计', cl.indexOf('条的采集方式') > 0 && cl.indexOf('脚本自动') > 0);
check('采集方式 / 渠道能力口径区分说明', cl.indexOf('条目级') > 0 && cl.indexOf('渠道级') > 0);
check('多站点渠道显示实际站点数', cnt(cl, /class="chsub"/g) > 0, cnt(cl, /class="chsub"/g) + ' 处');
const smzdmRow = CM.filter(c => /什么值得买/.test(c.site))[0];
const smzdmN = K.K3_FEEDBACK_DATA.items.filter(x => smzdmRow.re.test(x.platform)).length;
const smzdmM = cl.match(/chsite">什么值得买<\/span><span class="chm auto">自动<\/span><span class="chst ok">已有数据<\/span><span class="chnum">(\d+)/);
check('清单条数与实际数据一致（什么值得买）', smzdmM && Number(smzdmM[1]) === smzdmN, smzdmM ? smzdmM[1] : 'N/A');
['B 站','小红书','抖音','Reddit','X (Twitter)','Facebook','Instagram','TikTok'].forEach(function(s){
  check('用户点名渠道已入清单：' + s, cl.indexOf(s) > 0);
});
['国内媒体','海外视频','海外电商'].forEach(function(n){
  check('渠道组已就位：' + n, K.GROUP_ORDER.some(function(g){ return K.GROUP_META[g].name === n; }) && cl.indexOf(n) > 0);
});

console.log('\n--- 情感结构联动 + 渠道×情感矩阵（方案 B，2026-10-15）---');
activeFilters.dateKey = 'all'; activeFilters.problem = 'all'; activeFilters.dim = 'all';
activeFilters.group = 'all'; activeFilters.platform = 'all'; activeFilters.sentiment = 'all';
activeFilters.q = ''; activeFilters.topic = 'all'; activeFilters.channel = 'all'; activeFilters.sourceType = 'all';
renderAll();
const _vk = function(x){ return x.reviewGrade === '有效' && K.groupOf(x.platform) !== 'official'; };
const sentAllN = K.items().filter(_vk).length;
check('情感结构初始分母 = 有效档用户声量', String(store.sentDenom.textContent) === String(sentAllN), store.sentDenom.textContent + '/' + sentAllN);
check('初始无「查看全部」入口', store.sentStack.innerHTML.indexOf('查看全部') < 0);
K.setGroup('overseaDirect');
const nDirect = K.items().filter(function(x){ return K.groupOf(x.platform) === 'overseaDirect' && _vk(x); }).length;
check('点渠道组后情感结构跟随（海外一手社区）', String(store.sentDenom.textContent) === String(nDirect), store.sentDenom.textContent + '/' + nDirect);
check('筛选态出现「查看全部」入口', store.sentStack.innerHTML.indexOf('查看全部') >= 0);
check('矩阵选中行高亮 = 1', cnt(store.matrixBody.innerHTML, /class="mrow on"/g) === 1, cnt(store.matrixBody.innerHTML, /class="mrow on"/g));
check('矩阵为 10 渠道组行', cnt(store.matrixBody.innerHTML, /class="mrow/g) === 10, cnt(store.matrixBody.innerHTML, /class="mrow/g));
check('矩阵为纯展示（无任何 onclick）', cnt(store.matrixBody.innerHTML, /onclick=/g) === 0, cnt(store.matrixBody.innerHTML, /onclick=/g) + ' 个');
check('矩阵缺口标 = 1（海外电商）', cnt(store.matrixBody.innerHTML, /t-flag/g) === 1, cnt(store.matrixBody.innerHTML, /t-flag/g));
activeFilters.sentiment = '负面';
renderPanels();
check('点「负面」后情感结构不塌缩（跳过自身）', String(store.sentDenom.textContent) === String(nDirect), store.sentDenom.textContent);
activeFilters.sentiment = 'all';
renderPanels();
K.setGroup('overseaDirect');   // 先取消组筛选（YouTube 属海外视频组，挂着组筛选会得 0）
K.setPlatform('YouTube');
const nYt = K.items().filter(function(x){ return (x.site || x.platform) === 'YouTube' && _vk(x); }).length;
check('点站点后情感结构跟随（YouTube）', String(store.sentDenom.textContent) === String(nYt), store.sentDenom.textContent + '/' + nYt);
K.setPlatform('YouTube');
const cl2 = store.chanListBody.innerHTML;
const expSent = K.CHANNEL_MATRIX.filter(function(c){ return K.items().some(function(x){ return c.re.test(x.platform || ""); }); }).length;
check('覆盖清单 mini 情感条 = 有数据渠道数', cnt(cl2, /class="chsent"/g) === expSent, cnt(cl2, /class="chsent"/g) + '/' + expSent);
check('情感条 title 含五档明细', cl2.indexOf('情感分布：') >= 0);
K.clearAllFilters();
check('clearAllFilters 后情感结构恢复全部', String(store.sentDenom.textContent) === String(sentAllN), store.sentDenom.textContent);
check('恢复后无「查看全部」入口', store.sentStack.innerHTML.indexOf('查看全部') < 0);
check('恢复后矩阵无选中行', cnt(store.matrixBody.innerHTML, /class="mrow on"/g) === 0);

/* ---- 明细反馈流四个下沉筛选（2026-10-20 用户诉求 2：不用点上方也能直接定位）---- */
console.log('\n--- 明细定位条：渠道 / 专题 / 关注维度 / Top 问题 ---');
K.clearAllFilters();
const _df = String(store.deepFilters.innerHTML);
check('明细区有独立的定位条', _df.length > 300, _df.length + ' 字节');
check('定位条含 4 个下拉', cnt(_df, /<select/g) === 4, cnt(_df, /<select/g));
['渠道', '专题', '关注维度', 'Top 问题'].forEach(function(lb) {
  check('定位条含「' + lb + '」', _df.indexOf(lb) >= 0);
});
check('定位条说明「数字 = 选它之后的条数」', _df.indexOf('选项后的数字') >= 0);
check('定位条与上方面板同源（同一份 activeFilters）',
  /onchange="setF\('group'/.test(_df) && /onchange="setF\('topic'/.test(_df) &&
  /onchange="setF\('dim'/.test(_df) && /onchange="setF\('problem'/.test(_df));

// ① 专题：选项上的数字必须等于选了它之后的明细条数（所见即所得）
const _tBase = K.applyFilters('topic');
const _tc = {};
_tBase.forEach(function(x){ (x.topics || []).forEach(function(t){ _tc[t] = (_tc[t] || 0) + 1; }); });
const _tTop = Object.keys(_tc).sort(function(a, b){ return _tc[b] - _tc[a]; })[0];
K.setF('topic', _tTop);
check('选专题 → 明细条数 = 下拉里的数字', K.applyFilters().length === _tc[_tTop],
  K.applyFilters().length + ' / 下拉 ' + _tc[_tTop] + ' (' + _tTop + ')');
check('选专题 → 摘要条出 chip', String(store.filterSummary.innerHTML).indexOf('专项：') >= 0,
  String(store.filterSummary.innerHTML).replace(/<[^>]+>/g, ' ').slice(0, 90));
K.setF('topic', 'all');

// ② Top 问题：必须用归并后的类目，不是原始 141 个标签
const _pBase = K.applyFilters('problem');
const _pc = {};
_pBase.forEach(function(x){
  const seen = {};
  (x.problemPoints || []).map(K.normProblem).forEach(function(p){ seen[p] = 1; });
  Object.keys(seen).forEach(function(p){ _pc[p] = (_pc[p] || 0) + 1; });
});
const _pTop = Object.keys(_pc).sort(function(a, b){ return _pc[b] - _pc[a]; })[0];
K.setF('problem', _pTop);
check('选 Top 问题 → 明细条数 = 下拉里的数字', K.applyFilters().length === _pc[_pTop],
  K.applyFilters().length + ' / 下拉 ' + _pc[_pTop] + ' (' + _pTop + ')');
// 归并后主榜 16 类 + 少量未被规则覆盖的长尾（如实保留，不丢弃）
check('Top 问题类目远少于原始标签数（141 → 20 上下）', Object.keys(_pc).length <= 30,
  Object.keys(_pc).length + ' 类 / 原始 141 个标签');
K.setF('problem', 'all');

// ③ 渠道组：与矩阵联动
const _gBase = K.applyFilters('group');
const _gc = {};
_gBase.forEach(function(x){ const g = K.groupOf(x.platform); _gc[g] = (_gc[g] || 0) + 1; });
const _gTop = Object.keys(_gc).sort(function(a, b){ return _gc[b] - _gc[a]; })[0];
K.setF('group', _gTop);
check('选渠道组 → 明细条数 = 下拉里的数字', K.applyFilters().length === _gc[_gTop],
  K.applyFilters().length + ' / 下拉 ' + _gc[_gTop] + ' (' + _gTop + ')');
check('选渠道组 → 矩阵对应行高亮', cnt(store.matrixBody.innerHTML, /class="mrow on"/g) === 1);
K.setF('group', 'all');

// ④ 关注维度：Top 15 + 其他维度
const _dBase = K.applyFilters('dim');
const _dc = {};
_dBase.forEach(function(x){
  const seen = {};
  K.topDims(x).forEach(function(d){ seen[d] = 1; });
  Object.keys(seen).forEach(function(d){ _dc[d] = (_dc[d] || 0) + 1; });
});
const _dSorted = Object.keys(_dc).sort(function(a, b){ return _dc[b] - _dc[a]; });
const _dTop = _dSorted[0];
K.setF('dim', _dTop);
check('选关注维度 → 明细条数 = 下拉里的数字', K.applyFilters().length === _dc[_dTop],
  K.applyFilters().length + ' / 下拉 ' + _dc[_dTop] + ' (' + _dTop + ')');
K.setF('dim', 'all');
check('维度下拉只列 Top 15 + 一档「其他」', K.DIM_TOP.length === Math.min(15, _dSorted.length),
  K.DIM_TOP.length + ' / 共 ' + _dSorted.length + ' 个维度');
const _otherExp = K.items().filter(function(x){
  return K.topDims(x).some(function(d){ return K.DIM_TOP.indexOf(d) < 0; });
}).length;
K.setF('dim', K.DIM_OTHER);
check('「其他维度」能筛出长尾', K.applyFilters().length === _otherExp,
  K.applyFilters().length + ' / ' + _otherExp);
K.setF('dim', 'all');

K.clearAllFilters();
check('清空后定位条回到全部', String(store.deepFilters.innerHTML).indexOf('selected') < 0);
check('清空后明细恢复全量', K.applyFilters().length === K.items().length, K.applyFilters().length + '');

console.log('\n--- 问题点 Top -> 明细下钻 ---');
clearPanelFilters();
const pb = store.problemsBody.innerHTML;
check('问题点行可点击', cnt(pb, /class="hbar clk/g) > 0, cnt(pb, /class="hbar clk/g) + ' 行');
check('问题点行带就地筛选提示', pb.indexOf('点击就地筛选明细') > 0);
check('问题点长尾折叠行', pb.indexOf('展开全部') > 0);
check('问题点面板标注分母', store.probNote.innerHTML.indexOf('分母 = 当前筛选后') > 0);

// ── 归并规则扩容（2026-10-19：10 → 16 条）──────────────────────────
// 扩容前实测：类目 67 / 主榜 9 / 长尾 58 / 覆盖率 54.0%
// 扩容后实测：类目 21 / 主榜 15 / 长尾  6 / 覆盖率 95.2%
check('归并规则数 = 16（2026-10-19 扩容）', K.PROBLEM_MERGE.length === 16, K.PROBLEM_MERGE.length);
const _pcnt = {};
items().forEach(it => (it.problemPoints || []).forEach(p => { const k = normProblem(p); _pcnt[k] = (_pcnt[k] || 0) + 1; }));
const _pcats = Object.keys(_pcnt).length;
const _ptail = Object.keys(_pcnt).filter(k => _pcnt[k] === 1).length;
const _praw = items().reduce((a, it) => a + (it.problemPoints || []).length, 0);
const _pcov = Object.keys(_pcnt).filter(k => _pcnt[k] >= 2).reduce((a, k) => a + _pcnt[k], 0);
check('归并后类目数 ≤ 25（扩容前 67）', _pcats <= 25, _pcats);
check('长尾（仅提及 1 次）≤ 8（扩容前 58）', _ptail <= 8, _ptail);
check('归并覆盖率 ≥ 90%（扩容前 54.0%）', _pcov / _praw >= 0.90, (_pcov / _praw * 100).toFixed(1) + '%');
check('6 个新增盲区类目均在规则表内',
  ['交付与履约','信息透明度与沟通','宣传口径与实测落差','喷嘴与耗材规格','竞品对比与定位','品牌与品控信任']
    .every(l => K.PROBLEM_MERGE.some(x => x[0] === l)));
check('交付与履约已收敛为独立类目（原为隐形长尾）', (_pcnt['交付与履约'] || 0) >= 4, _pcnt['交付与履约'] || 0);
check('宣传口径与实测落差已收敛', (_pcnt['宣传口径与实测落差'] || 0) >= 4, _pcnt['宣传口径与实测落差'] || 0);
check('原有主榜类目计数未下降（无被新规则抢走）',
  ['换色/换头实际耗时长','能力未经第三方验证','软件与配套滞后','头数/尺寸/配件局限','价格与首发信心']
    .every(l => (_pcnt[l] || 0) >= [13, 12, 11, 9, 8][['换色/换头实际耗时长','能力未经第三方验证','软件与配套滞后','头数/尺寸/配件局限','价格与首发信心'].indexOf(l)]),
  ['换色','验证','软件','头数','价格'].map((n, i) => n + '=' + (_pcnt[['换色/换头实际耗时长','能力未经第三方验证','软件与配套滞后','头数/尺寸/配件局限','价格与首发信心'][i]] || 0)).join(' '));

// 所见即所得：面板数字 === 点击后明细条数
const truthProblem = (p) => items().filter(it => (it.problemPoints || []).map(normProblem).indexOf(p) >= 0).length;
const topProblem = (K.PROBLEM_MERGE.map(x => x[0]).filter(p => truthProblem(p) >= 4).sort((a, b) => truthProblem(b) - truthProblem(a))[0]);
setProblem(topProblem);
check('点击问题点后筛选生效', activeFilters.problem === topProblem, topProblem);
check('所见即所得：明细条数 = 面板数字', applyFilters().length === truthProblem(topProblem), applyFilters().length + '/' + truthProblem(topProblem));
check('问题点 chip 出现（摘要条）', store.filterSummary.innerHTML.indexOf('问题点：' + topProblem) > 0);
check('问题点行高亮 on', store.problemsBody.innerHTML.indexOf('class="hbar clk on"') > 0);
check('摘要条命中数与明细一致', store.filterSummary.innerHTML.indexOf('命中 <b>' + applyFilters().length + '</b> 条') > 0, applyFilters().length);
setProblem(topProblem);
check('再次点击取消（问题点）', activeFilters.problem === 'all');
check('取消后摘要条隐藏', store.filterSummary.className.indexOf('show') < 0);
check('取消后明细恢复全量', applyFilters().length === total, applyFilters().length);

// 长尾展开
toggleTail('problem');
check('长尾展开后行数增加', cnt(store.problemsBody.innerHTML, /class="hbar clk/g) > cnt(pb, /class="hbar clk/g));
check('长尾展开后出现收起', store.problemsBody.innerHTML.indexOf('收起仅被提及') > 0);
const pbOpen = store.problemsBody.innerHTML;
check('收起入口位于长尾行之前（problem）',
  pbOpen.indexOf('收起仅被提及') < pbOpen.indexOf('class="fold-sep"'));
check('展开态长尾之后无第二个收起入口（problem）', cnt(pbOpen, /收起仅被提及/g) === 1);
toggleTail('problem');
check('长尾可收起', store.problemsBody.innerHTML.indexOf('展开全部') > 0);

console.log('\n--- 关注维度分布 -> 明细下钻 ---');
const db = store.dimsBody.innerHTML;
check('维度行可点击', cnt(db, /class="brow clk/g) > 0, cnt(db, /class="brow clk/g) + ' 行');
check('维度行带就地筛选提示', db.indexOf('点击就地筛选明细') > 0);
check('维度长尾折叠', db.indexOf('展开全部') > 0 || cnt(db, /class="brow clk sm/g) > 0);
check('维度面板标注分母', store.dimsNote.innerHTML.indexOf('当前筛选后') > 0);

const truthDim = (d) => items().filter(it => topDims(it).indexOf(d) >= 0).length;
const allDims = {}; items().forEach(it => topDims(it).forEach(d => { allDims[d] = (allDims[d] || 0) + 1; }));
const topDim = Object.keys(allDims).sort((a, b) => allDims[b] - allDims[a])[0];
setDim(topDim);
check('点击维度后筛选生效', activeFilters.dim === topDim, topDim);
check('所见即所得：维度明细条数 = 面板数字', applyFilters().length === truthDim(topDim), applyFilters().length + '/' + truthDim(topDim));
check('维度 chip 出现（摘要条）', store.filterSummary.innerHTML.indexOf('维度：' + topDim) > 0);

console.log('\n--- 两面板口径独立性（skip 逻辑）---');
// 选中问题点后，问题点面板自身排除该条件（保证撤销可用），维度面板保留该条件
setProblem(topProblem);
const probPanelN = cnt(store.problemsBody.innerHTML, /class="hbar clk/g);
check('问题点面板排除自身条件（仍显示全部分组）', store.problemsBody.innerHTML.indexOf(topProblem) > 0 && probPanelN >= 1);
// 维度面板应「保留 problem 条件、排除 dim 自身」→ 结果恰好等于只施加 problem 的条数。
// 原断言写的是「等于全量筛选结果」，只在 dim 条件对 problem 子集不产生额外过滤时才成立，属巧合。
const dimBackup = activeFilters.dim;
activeFilters.dim = 'all';
const problemOnlyN = applyFilters().length;
activeFilters.dim = dimBackup;
check('维度面板保留 problem 条件、排除 dim 自身', applyFilters('dim').length === problemOnlyN,
  applyFilters('dim').length + '/' + problemOnlyN);
clearPanelFilters();
check('clearPanelFilters 清空两个面板筛选', activeFilters.problem === 'all' && activeFilters.dim === 'all');
check('清空后明细恢复全量', applyFilters().length === total, applyFilters().length);

console.log('\n--- 需求1：面板下钻改为就地筛选（不跳转） ---');
clearAllFilters();
check('jumpToDetail 已下线（无滚动跳转入口）', eval('typeof jumpToDetail') === 'undefined', eval('typeof jumpToDetail'));
check('flashCards 仍存在（保留「已生效」反馈）', eval('typeof flashCards') === 'function');
setProblem(topProblem);
check('点问题点不改变滚动位置（就地筛选）', String(store.problemsBody.innerHTML).indexOf(topProblem) > 0 && activeFilters.problem === topProblem);
setProblem(topProblem);
setDim(topDim);
check('点维度不改变滚动位置（就地筛选）', activeFilters.dim === topDim);
setDim(topDim);
clearAllFilters();

console.log('\n--- 需求2：渠道筛选入口收敛 ---');
check('矩阵 body 无 onclick（纯展示）', cnt(store.matrixBody.innerHTML, /onclick=/g) === 0);
check('占比榜图例仍可点（组入口）', cnt(store.channelBody.innerHTML, /onclick="setGroup/g) >= 1, cnt(store.channelBody.innerHTML, /onclick="setGroup/g) + ' 个');
check('占比榜平台行仍可点（站点入口）', cnt(store.channelBody.innerHTML, /onclick="setPlatform/g) >= 1, cnt(store.channelBody.innerHTML, /onclick="setPlatform/g) + ' 行');
const clkRows = cnt(store.chanListBody.innerHTML, /class="chrow clk/g);
check('覆盖清单出现可点行（唯一命中站点的渠道）', clkRows >= 3, clkRows + ' 行');
// 覆盖清单点击 = 筛该站点，且必须真的筛到那个站
const mSmzdm = store.chanListBody.innerHTML.match(/data-p="([^"]+)"/);
if (mSmzdm) {
  K.setPlatform(mSmzdm[1]);
  const nSite = K.items().filter(function(x){ return (x.site || x.platform) === mSmzdm[1]; }).length;
  check('覆盖清单点击后只留该站点明细', applyFilters().length === nSite && nSite > 0, applyFilters().length + '/' + nSite + ' @' + mSmzdm[1]);
  K.setPlatform(mSmzdm[1]);
  check('覆盖清单再次点击取消', activeFilters.platform === 'all');
} else {
  check('覆盖清单可点行带 data-p', false, 'no data-p');
}
check('覆盖清单不可点行为 0 条渠道（灰色 —）', cnt(store.chanListBody.innerHTML, /class="chrow zero"/g) > 0);

console.log('\n--- 需求3：当前筛选摘要条 ---');
clearAllFilters();
check('无筛选时摘要条隐藏', store.filterSummary.className.indexOf('show') < 0 && store.filterSummary.innerHTML === '');
setGroup('overseaVideo');
setF('sentiment', '负面');
setProblem(topProblem);
const sumHtml = store.filterSummary.innerHTML;
check('摘要条显示并计数（3）', sumHtml.indexOf('当前筛选（3）') > 0, sumHtml.indexOf('当前筛选（3）'));
check('摘要条含渠道组 chip', sumHtml.indexOf('渠道组：海外视频') > 0);
check('摘要条含情感 chip', sumHtml.indexOf('情感：负面') > 0);
check('摘要条含问题点 chip', sumHtml.indexOf('问题点：' + topProblem) > 0);
check('摘要条命中数 = 明细条数', sumHtml.indexOf('命中 <b>' + applyFilters().length + '</b> 条') > 0, applyFilters().length + ' 条');
check('摘要条带清空全部', sumHtml.indexOf('清空全部') > 0);
check('筛选栏不再重复渲染已选 chip', store.filters.innerHTML.indexOf('问题点：' + topProblem) < 0 && store.filters.innerHTML.indexOf('渠道组：海外视频') < 0);
// 单个 chip 移除
K.removeFilter('sentiment');
check('单个 chip 移除生效', activeFilters.sentiment === 'all' && activeFilters.group === 'overseaVideo' && activeFilters.problem === topProblem);
check('移除后 chip 数降为 2', store.filterSummary.innerHTML.indexOf('当前筛选（2）') > 0);
K.removeFilter('problem');
check('移除问题点后问题点面板恢复全量', activeFilters.problem === 'all');
clearAllFilters();
// 时间 chip 要连区间一起清
setDatePreset('d7');
check('时间 chip 出现', store.filterSummary.innerHTML.indexOf('时间：') > 0);
K.removeFilter('date');
check('移除时间 chip 后区间与自定义态一并清空', activeFilters.dateKey === 'all' && activeFilters.dateFrom === '' && activeFilters.dateTo === '');
clearAllFilters();
check('clearAllFilters 后摘要条隐藏', store.filterSummary.className.indexOf('show') < 0);

console.log('\n--- 需求4：数据更新条 + 更新历史 ---');
const ub = store.updateBar.innerHTML;
check('更新条渲染更新时间', ub.indexOf('数据更新至 ' + K.K3_FEEDBACK_DATA.updated) > 0);
check('更新条标注更新节奏（工作日 03:30）', ub.indexOf('工作日 03:30 自动更新') > 0);
check('更新条累计条数 = 数据总量', ub.indexOf('累计 <b style="color:#e6edf3">' + total + '</b> 条') > 0, total);
check('更新条显示本批新增', /本批 \+\d+/.test(ub), (ub.match(/本批 \+\d+/) || [''])[0]);
check('更新条显示批次数', ub.indexOf('个批次') > 0);
check('默认不展开历史', store.updHist.className.indexOf('open') < 0 && store.updHist.innerHTML === '');
K.toggleUpdHist();
const hist = store.updHist.innerHTML;
const log = K.buildUpdateLog();
check('展开后历史表出现', store.updHist.className.indexOf('open') >= 0 && cnt(hist, /class="upd-row/g) === Math.min(log.length, 10), cnt(hist, /class="upd-row/g) + '/' + Math.min(log.length, 10));
check('历史行数 = 采集日批次数', log.length === Object.keys(K.items().reduce(function(m, x){ m[x.date] = 1; return m; }, {})).length, log.length);
check('最新一批标「最新」且高亮', cnt(hist, /class="upd-row cur"/g) === 1 && hist.indexOf('（最新）') > 0);
check('历史逐批累计单调递增', log.slice().reverse().every(function(r, i, a){ return i === 0 || r.total > a[i-1].total; }));
check('最后一批累计 = 数据总量', log[0].total === total, log[0].total + '/' + total);
check('历史口径说明（按采集日派生）', hist.indexOf('采集入库日') > 0 && hist.indexOf('不是「0 条」') > 0);
K.toggleUpdHist();
check('再次点击收起历史', store.updHist.className.indexOf('open') < 0);
// 派生口径必须与「按采集日」筛选一致
const lastDate = log[0].at;
activeFilters.dateMode = 'collection'; setDatePreset('all');
activeFilters.dateFrom = lastDate; activeFilters.dateTo = lastDate; activeFilters.dateKey = 'custom';
check('更新条最新批次条数 = 按采集日筛选该日条数', applyFilters().length === log[0].add, applyFilters().length + '/' + log[0].add + ' @' + lastDate);
activeFilters.dateFrom = ''; activeFilters.dateTo = ''; activeFilters.dateKey = 'all'; activeFilters.dateMode = 'published';
clearAllFilters();

// ── 载体维度：视频 / 图文 / 评价（2026-10-19 新增）──────────────────────
// 用户定稿：三种形式都属于反馈，总览不切开，只在明细里分 + 卡片上标识。
// 所以这里要验三件事：① 默认全部计入；② 载体是独立筛选项且能就地生效；
// ③ 评价卡片必须带「来自哪个主体」并可回溯。
console.log('\n--- 载体维度（视频 / 图文 / 评价）---');
clearAllFilters();
const _kinds = K.KIND_ORDER || ['视频', '图文', '评价'];
const _kCount = function(k){ return items().filter(function(x){ return (x.contentKind || '图文') === k; }).length; };
check('三类载体都已在数据中落位', _kinds.every(function(k){ return _kCount(k) > 0; }),
  _kinds.map(function(k){ return k + ' ' + _kCount(k); }).join(' · '));
check('默认口径 = 全部（不做载体切换）', activeFilters.kind === 'all' && applyFilters().length === items().length,
  applyFilters().length + '/' + items().length);
check('更新条显示载体构成', store.updateBar.innerHTML.indexOf('载体构成') > 0);

const _nEval = _kCount('评价');
setF('kind', '评价');
check('载体筛选：评价类条数正确', applyFilters().length === _nEval, applyFilters().length + '/' + _nEval);
check('载体筛选进摘要条并写明载体名', store.filterSummary.innerHTML.indexOf('载体：评价') > 0);
// ⚠️ activePage 是 let 声明的，不会逃逸到 vm 全局（function 才会）→ 只能从 countLine 反推
check('载体切换后回到第 1 页', store.countLine.innerHTML.indexOf('1–') >= 0,
  (store.countLine.innerHTML.match(/当前显示 <b>[^<]*<\/b>/) || [''])[0]);
setF('kind', '视频');
check('载体筛选：视频类条数正确', applyFilters().length === _kCount('视频'), applyFilters().length + '/' + _kCount('视频'));
setF('kind', 'all');
check('载体选回全部后恢复全量', applyFilters().length === items().length);

// 评价卡片的语境回溯：必须有 parent 行，且 parentTitle 不为空
setF('kind', '评价');
const _cardHtml = store.cardGrid.innerHTML;
check('评价卡片带「来自」主体行', _cardHtml.indexOf('c-parent') > 0 && _cardHtml.indexOf('来自') > 0);
check('评价卡片带「自动标注」标识', _cardHtml.indexOf('auto-tag') > 0);
const _noParent = items().filter(function(x){ return (x.contentKind === '评价') && !x.parentId; }).length;
check('每条评价都有 parentId', _noParent === 0, _noParent + ' 条缺 parentId');
const _noUid = items().filter(function(x){ return !x.uid; }).length;
check('评价类全部带 uid（幂等主键）', items().filter(function(x){ return x.contentKind === '评价' && !x.uid; }).length === 0);
setF('kind', 'all');
clearAllFilters();

// 情感结构里的载体分解（可分解 ≠ 可切换，这里验它存在且三类都在）
const _stackHtml = store.sentStack.innerHTML;
check('情感结构给出载体分解（负面/样本）', _stackHtml.indexOf('载体分解') > 0 &&
  _kinds.filter(function(k){ return _kCount(k) > 0; }).every(function(k){ return _stackHtml.indexOf(k) > 0; }));

// ---------------- 评价审核 + 原文/译文（2026-10-19） ----------------
// 纪律：无效档在采集阶段就丢弃，界面不得出现「无效」这个概念。
const _ev = items().filter(function(x){ return x.contentKind === '评价'; });
const _ok = _ev.filter(function(x){ return x.reviewGrade === '有效'; }).length;
const _mid = _ev.filter(function(x){ return x.reviewGrade === '泛讨论'; }).length;
check('评价只有「有效 / 泛讨论」两档', _ok + _mid === _ev.length,
  '有效 ' + _ok + ' · 泛讨论 ' + _mid + ' · 共 ' + _ev.length);
// 只查「有没有可点的无效档」，不查文本里是否出现「无效」二字——
// 全部按钮的 tooltip 里本来就写着「无效评价已在采集阶段剔除」。
const _reviewBtns = (store.filters.innerHTML.match(/setF\('review'/g) || []).length;
check('界面不存在「无效」筛选项',
  store.filters.innerHTML.indexOf("setF('review','无效')") < 0 && _reviewBtns === 3,
  _reviewBtns + ' 个审核按钮');
const _invalid = items().filter(function(x){ return x.reviewGrade === '无效'; }).length;
check('数据中不存在无效档条目', _invalid === 0, _invalid + ' 条');

// 泛讨论不进问题点榜：数据层已清空语义标签
const _midWithProb = _ev.filter(function(x){ return x.reviewGrade === '泛讨论' && (x.problemPoints || []).length; }).length;
check('泛讨论不带问题点（不进榜）', _midWithProb === 0, _midWithProb + ' 条');

// 审核筛选可用
setF('review', '有效');
const _nOk = applyFilters().length;
check('审核筛选：有效档条数正确', _nOk === items().filter(function(x){ return x.reviewGrade === '有效'; }).length,
  _nOk + ' 条');
check('审核筛选进摘要条', store.filterSummary.innerHTML.indexOf('审核：有效') > 0);
setF('review', '泛讨论');
const _nMid = applyFilters().length;
check('审核筛选：泛讨论档条数正确', _nMid === _mid, _nMid + ' 条');
setF('review', 'all');
clearAllFilters();
check('清除筛选后恢复全量', applyFilters().length === items().length);

// 原文 + 译文：非中文必出双段，中文只出一段
const _tr = _ev.filter(function(x){ return x.language !== 'ZH'; });
const _noTr = _tr.filter(function(x){ return !(x.textCn || '').trim(); }).length;
check('非中文评价全部有译文', _noTr === 0, _tr.length - _noTr + '/' + _tr.length);
const _zhTr = _ev.filter(function(x){ return x.language === 'ZH' && (x.textCn || '').trim(); }).length;
check('中文评价不重复出译文', _zhTr === 0, _zhTr + ' 条多出译文');

// 卡片渲染：非中文评价必须原文 + 译文双段；中文评价只出原文一段
setF('kind', '评价');
renderAll();
const _cardsHtml = store.cardGrid.innerHTML;
check('评价卡片同时展示原文与译文',
  _cardsHtml.indexOf('原文 · 英文') > 0 && _cardsHtml.indexOf('译文') > 0 &&
  _cardsHtml.indexOf('机器翻译') > 0);
check('评价卡片带审核档标识', _cardsHtml.indexOf('chip g-ok') > 0 || _cardsHtml.indexOf('chip g-mid') > 0);
setQ('的');
renderAll();
const _zhCards = store.cardGrid.innerHTML;
check('中文评价卡片只出原文一段（无译文档）',
  _zhCards.indexOf('原文 · 中文') > 0 && _zhCards.indexOf('译文') < 0);
setQ('');
setF('kind', 'all');

console.log('\n--- 合计 ---');
console.log(fail === 0 ? 'ALL PASS' : fail + ' CHECK(S) FAILED');
process.exit(fail === 0 ? 0 : 1);
