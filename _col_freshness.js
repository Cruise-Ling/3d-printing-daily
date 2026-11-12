#!/usr/bin/env node
/* _col_freshness.js — 全站专栏「当日新鲜度」硬闸门
 *
 * 为什么需要它（2026-10-30 事故）：
 *   主链 Step 2/4.2/4.3 整段没执行，但页面文件被更早的一次构建重写过、
 *   渲染校验 ALL PASS、线上 HTTP 200 —— 三项检查全绿，
 *   实际条目还停在昨天。原 Step 5 只校验「渲染正确」和「能访问」，
 *   不校验「内容是不是当天的」，所以这种静默跳过无人发现。
 *
 * 判据（不用「页面有没有当日条目」一刀切，避免 0 新增日天天误报）：
 *   专栏三页（sw / mbox / fc）
 *     RED    采集产物 fetchedAt 不是今天          → 采集或归一化没跑
 *     RED    产物是今天但页面 meta.updatedDate 不是今天 → 采了没重建
 *     YELLOW 两者都是今天且 deltaToday=0            → 当日确实 0 新增（合法）
 *     GREEN  两者都是今天且 deltaToday>0
 *   K3
 *     RED    _k3_candidates_<今日>.json 不存在      → Step 3 完全没跑
 *     YELLOW 候选池在但当日 0 条有效新增            → 设计内结果
 *     GREEN  当日有新增入库
 *   用户吐槽（无采集产物，用批次日期判定）
 *     GREEN  当日批次已注入
 *     RED    当日无批次                              → Step 2 未落当日口碑
 *            可用 --allow uc 降级为 YELLOW（当确实主动跳过并已记录原因时）
 *
 * 用法：
 *   node _col_freshness.js                  # 默认今天（本机时区）
 *   node _col_freshness.js --date 2026-10-30
 *   node _col_freshness.js --allow uc,k3    # 显式豁免（降级为 YELLOW 并打印原因）
 *   node _col_freshness.js --json           # 只输出 JSON，便于程序消费
 *
 * 退出码：0 = 无 RED；1 = 存在 RED（应告警，不得静默通过）
 */
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const DIR = __dirname;
const GREEN = 'GREEN', YELLOW = 'YELLOW', RED = 'RED';

/* ---------- 参数 ---------- */
const argv = process.argv.slice(2);
function argOf(name) {
  const i = argv.indexOf(name);
  return i >= 0 && argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[i + 1] : null;
}
const AS_JSON = argv.includes('--json');
const ALLOW = new Set(String(argOf('--allow') || '').split(',').map(s => s.trim()).filter(Boolean));
const TODAY = argOf('--date') || localYmd(new Date());

function localYmd(d) {
  const t = new Date(d.getTime() - d.getTimezoneOffset() * 60000);
  return t.toISOString().slice(0, 10);
}
function datePart(s) {
  if (!s) return null;
  const m = String(s).match(/(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})/);
  return m ? `${m[1]}-${String(m[2]).padStart(2, '0')}-${String(m[3]).padStart(2, '0')}` : null;
}

/* ---------- 从页面抽取 JS 对象字面量 ---------- */
function sliceObject(src, tok) {
  const i = src.indexOf(tok);
  if (i < 0) return null;
  const start = src.indexOf('{', i + tok.length - 1);   // 兼容 tok 以 '=' 或 '{' 结尾
  if (start < 0) return null;
  let depth = 0, inStr = false, quote = '', esc = false;
  for (let j = start; j < src.length; j++) {
    const c = src[j];
    if (inStr) {
      if (esc) { esc = false; continue; }
      if (c === '\\') { esc = true; continue; }
      if (c === quote) inStr = false;
      continue;
    }
    if (c === '"' || c === "'" || c === '`') { inStr = true; quote = c; continue; }
    if (c === '{') depth++;
    else if (c === '}') { depth--; if (depth === 0) return src.slice(start, j + 1); }
  }
  return null;
}

function readPage(file, tok) {
  const p = path.join(DIR, file);
  if (!fs.existsSync(p)) return { error: '页面文件不存在' };
  const html = fs.readFileSync(p, 'utf8');
  const objSrc = sliceObject(html, tok);
  if (!objSrc) return { error: '未找到数据对象（token 不匹配？）' };
  let data;
  try {
    data = vm.runInNewContext('(' + objSrc + ')');
  } catch (e) {
    return { error: '数据对象解析失败：' + String(e.message).slice(0, 80) };
  }
  return { data, bytes: html.length };
}

function readJson(file) {
  const p = path.join(DIR, file);
  if (!fs.existsSync(p)) return null;
  try { return JSON.parse(fs.readFileSync(p, 'utf8')); } catch (e) { return null; }
}

/* ---------- 各页面判定 ---------- */
function checkColumn(key, file, metaFile, artifactFiles) {
  const r = readPage(file, 'var COL=');
  if (r.error) return { key, file, verdict: RED, reason: r.error, cells: {} };
  const meta = (r.data && r.data.meta) || {};
  const items = (r.data && r.data.items) || [];
  const builtDate = datePart(meta.updatedDate);
  const deltaToday = Number(meta.deltaToday || 0);
  const pageMax = items.reduce((a, x) => (x.date && x.date > a ? x.date : a), '');
  const newToday = items.filter(x => datePart(x.date) === TODAY).length;

  // 采集产物时间：优先 meta 文件里的 fetchedAt，否则退回落盘文件的 mtime
  let artRaw = null, artSrc = '';
  for (const f of artifactFiles.concat(metaFile ? [metaFile] : [])) {
    const p = path.join(DIR, f);
    if (!fs.existsSync(p)) continue;
    const j = readJson(f);
    if (j && j.fetchedAt) { artRaw = j.fetchedAt; artSrc = f; break; }
    if (j && j.generatedAt) { artRaw = j.generatedAt; artSrc = f; break; }
    const st = fs.statSync(p);
    artRaw = localYmd(st.mtime); artSrc = f + '（mtime）';
    break;
  }
  const artDate = datePart(artRaw);

  let verdict, reason;
  if (!artDate) {
    verdict = RED; reason = '未找到当日采集产物';
  } else if (artDate !== TODAY) {
    verdict = RED; reason = `采集产物停留在 ${artDate}（${artSrc}）`;
  } else if (builtDate !== TODAY) {
    verdict = RED; reason = `产物已更新到 ${TODAY}，但页面构建日仍是 ${builtDate || '未知'}（采了没重建）`;
  } else if (deltaToday <= 0) {
    verdict = YELLOW; reason = '当日采集正常、0 条新增';
  } else {
    verdict = GREEN; reason = `当日新增 ${deltaToday} 条`;
  }

  return {
    key, file, verdict, reason,
    cells: { newToday, deltaToday, artRaw, artSrc, builtDate, pageMax, items: items.length },
  };
}

function checkK3() {
  const key = 'k3', file = 'creality-k3.html';
  const r = readPage(file, 'const K3_FEEDBACK_DATA = {');
  if (r.error) return { key, file, verdict: RED, reason: r.error, cells: {} };
  const d = r.data || {};
  const items = d.items || [];
  const newToday = items.filter(x => datePart(x.date) === TODAY).length;
  const pageMax = items.reduce((a, x) => (x.date && x.date > a ? x.date : a), '');

  const candFile = `_k3_candidates_${TODAY.replace(/-/g, '')}.json`;
  const cand = readJson(candFile);

  let verdict, reason;
  if (!cand) {
    verdict = RED; reason = `候选池 ${candFile} 不存在（Step 3 未跑）`;
  } else if (newToday > 0) {
    verdict = GREEN; reason = `当日入库 ${newToday} 条`;
  } else {
    verdict = YELLOW; reason = '候选池已生成、当日 0 条有效新增（设计内）';
  }
  const counts = (cand && (cand.counts || {})) || {};
  return {
    key, file, verdict, reason,
    cells: { newToday, deltaToday: null, artRaw: cand ? `候选池 ${candFile}` : null,
             builtDate: datePart(d.updated), pageMax, items: items.length,
             candCounts: Object.keys(counts).length ? counts : null },
  };
}

/* H3C 专栏（2026-11-12 并入 10:00 增量链后纳入闸门判定）
 * 此前 H3C 只出现在下方「增量健康度」告警段，不参与 VERDICT —— 于是链 PASS 而
 * H3C 页面停在 11-11 也照样过闸（11-09~11-11 连续 3 天 0 新增未被拦下）。
 * 判定与 K3 同构：页面构建日必须是今天（注入了没重建 → RED），当日 0 条 → YELLOW。
 */
function checkH3C() {
  const key = 'h3c', file = 'bambu-h3c.html';
  const r = readPage(file, 'const H3C_FEEDBACK_DATA = {');
  if (r.error) return { key, file, verdict: RED, reason: r.error, cells: {} };
  const d = r.data || {};
  const items = d.items || [];
  const newToday = items.filter(x => datePart(x.date) === TODAY).length;
  const pageMax = items.reduce((a, x) => (x.date && x.date > a ? x.date : a), '');
  const builtDate = datePart(d.updated);   // 由 _build_h3c.py 的 REF_DATE 注入

  // 论坛采集痕迹：raw 存档是 append 的，mtime 能区分「今日没采」与「采了没新帖」
  let rawDate = null;
  const rawP = path.join(DIR, '_h3c_forum_raw.json');
  if (fs.existsSync(rawP)) rawDate = localYmd(fs.statSync(rawP).mtime);

  let verdict, reason;
  if (!items.length) {
    verdict = RED; reason = '页面无条目（数据块为空）';
  } else if (builtDate !== TODAY) {
    verdict = RED; reason = `页面构建日停留在 ${builtDate || '未知'}（标注/注入后没重建，跑 python _build_h3c.py）`;
  } else if (newToday > 0) {
    verdict = GREEN; reason = `当日入库 ${newToday} 条`;
  } else if (rawDate && rawDate !== TODAY) {
    verdict = YELLOW; reason = `当日 0 条新增，且论坛今日未采（raw 停在 ${rawDate}）`;
  } else {
    verdict = YELLOW; reason = '当日 0 条高置信新增（设计内）';
  }
  if (verdict === RED && ALLOW.has('h3c')) { verdict = YELLOW; reason += '（已按 --allow h3c 豁免）'; }

  return {
    key, file, verdict, reason,
    cells: { newToday, deltaToday: newToday, artRaw: rawDate,
             artSrc: '_h3c_forum_raw.json（mtime）', builtDate, pageMax, items: items.length },
  };
}

/* 光固化专栏（2026-11-12 B3 并入 10:00 增量链后纳入主闸门判定）
 * 本页数据对象是 var DATA = {，与专栏三页的 var COL= 不同，不能复用 checkColumn()。
 * 判据：当日采集产物缺失/过期 → RED；页面 meta.updatedDate 不是今天 → RED；
 *       当日 0 条新增 → YELLOW（设计内，不影响 VERDICT PASS）。
 */
function checkResin() {
  const key = 'resin', file = 'resin-line.html';
  const r = readPage(file, 'var DATA = {');
  if (r.error) return { key, file, verdict: RED, reason: r.error, cells: {} };
  const d = r.data || {};
  const m = d.meta || {};
  const items = d.items || [];
  const builtDate = datePart(m.updatedDate || m.refDate);
  const deltaToday = Number(m.deltaToday || 0);
  const pageMax = items.reduce((a, x) => (x.pubDate && x.pubDate > a ? x.pubDate : a), '');

  let artRaw = null, artSrc = '';
  const daily = `_resin_candidates_daily_${TODAY.replace(/-/g, '')}.json`;
  const cands = fs.readdirSync(DIR).filter(f => /^_resin_candidates_.*\.json$/.test(f)).sort();
  const pick = cands.indexOf(daily) >= 0 ? daily : (cands.length ? cands[cands.length - 1] : null);
  if (pick) {
    const j = readJson(pick);
    artRaw = (j && j.meta && (j.meta.generatedAt || j.meta.fetchedAt)) || null;
    artSrc = pick;
    if (!artRaw) { artRaw = localYmd(fs.statSync(path.join(DIR, pick)).mtime); artSrc = pick + '（mtime）'; }
  }

  let verdict, reason;
  if (!items.length) {
    verdict = RED; reason = '页面无条目（数据块为空）';
  } else if (!artRaw || datePart(artRaw) !== TODAY) {
    verdict = RED; reason = `当日采集产物缺失或停留在 ${datePart(artRaw) || '未知'}（${artSrc || '无'}）`;
  } else if (builtDate !== TODAY) {
    verdict = RED; reason = `产物已更新到 ${TODAY}，但页面构建日仍是 ${builtDate || '未知'}（采了没重建）`;
  } else if (deltaToday <= 0) {
    verdict = YELLOW; reason = '当日采集正常、0 条新增（设计内）';
  } else {
    verdict = GREEN; reason = `当日新增 ${deltaToday} 条`;
  }
  if (verdict === RED && ALLOW.has('resin')) { verdict = YELLOW; reason += '（已按 --allow resin 豁免）'; }

  return {
    key, file, verdict, reason,
    cells: { newToday: deltaToday, deltaToday, artRaw, artSrc, builtDate, pageMax, items: items.length },
  };
}

function checkUC() {
  const key = 'uc', file = 'user-complaints.html';
  const r = readPage(file, 'const OVERSEAS_FEEDBACK_DATA = {');
  if (r.error) return { key, file, verdict: RED, reason: r.error, cells: {} };
  const items = (r.data && r.data.items) || [];
  const newToday = items.filter(x => datePart(x.date) === TODAY).length;
  const pageMax = items.reduce((a, x) => (x.date && x.date > a ? x.date : a), '');

  let verdict, reason;
  if (newToday > 0) {
    verdict = GREEN; reason = `当日批次 ${newToday} 条`;
  } else if (ALLOW.has('uc')) {
    verdict = YELLOW; reason = `当日无批次（已按 --allow uc 豁免，最新 ${pageMax || '未知'}）`;
  } else {
    verdict = RED; reason = `当日无批次（最新 ${pageMax || '未知'}），Step 2 未落当日口碑`;
  }
  return { key, file, verdict, reason, cells: { newToday, artRaw: null, builtDate: null, pageMax, items: items.length } };
}

/* ---------- 增量健康度（2026-11-11 A 批次） ---------------------------------
 * 只输出，不改变上方判据 / VERDICT / 退出码。
 * 原因：10:00 拆链用本脚本的 GREEN/RED 做幂等基线（「YELLOW 不影响 PASS」是写进
 * 任务 memory 的规则）。把 YELLOW 升级成 FAIL 会导致每天重复采集，所以告警必须旁路。
 *
 * 新增能力：
 *   ① 每专栏「当日新增 / 近 7 日新增 / 连续 0 新增工作日数 / 最后有新增日」
 *   ② 近 10 天按平台新增计数 + 零产出平台清单
 *   ③ 四平台（抖音/小红书/X/知乎，11-06 起无供料方）常驻提示
 *   ④ streak >= --gap-threshold（默认 3 个工作日）输出 GAP: ALERT
 * 节假日口径：按周一~周五近似（不引 _holidays 表），仅用于告警，不影响闸门。
 * ------------------------------------------------------------------------- */
const GAP_THRESHOLD = Number(argOf('--gap-threshold') || 3);
const GAP_WINDOW = Number(argOf('--gap-window') || 10);
const WATCH_PLATFORMS = ['抖音', '小红书', 'X', '知乎'];
const GAP_PAGES = [
  { key: 'k3',   name: 'K3 反馈', file: 'creality-k3.html',          tok: 'const K3_FEEDBACK_DATA = {' },
  { key: 'h3c',  name: 'H3C',    file: 'bambu-h3c.html',            tok: 'const H3C_FEEDBACK_DATA = {' },
  { key: 'sw',   name: '软件',   file: 'software-columns.html',      tok: 'var COL=' },
  { key: 'mbox', name: 'mBox',   file: 'creality-mbox.html',         tok: 'var COL=' },
  { key: 'fc',   name: '全彩',   file: 'fullcolor-columns.html',     tok: 'var COL=' },
  { key: 'resin',name: '光固化',file: 'resin-line.html',            tok: 'var DATA = {' },
  { key: 'uc',   name: '口碑',   file: 'user-complaints.html',       tok: 'const OVERSEAS_FEEDBACK_DATA = {' },
];

function ymdOffset(ymd, delta) {
  const d = new Date(ymd + 'T12:00:00');
  d.setDate(d.getDate() + delta);
  return localYmd(d);
}
function isWorkday(ymd) {
  const w = new Date(ymd + 'T12:00:00').getDay();
  return w >= 1 && w <= 5;
}
function platOf(x) {
  // 归一空格：页面里「B站」与「B 站」是同一平台，不归一会造出假的零产出渠道
  return String(x.platform || x.site || x.source || x.channel || '未知')
    .replace(/\s+/g, '');
}

function gapReport() {
  const days = [];
  for (let i = GAP_WINDOW - 1; i >= 0; i--) days.push(ymdOffset(TODAY, -i));
  const workdays = days.filter(isWorkday);
  const last7 = days.slice(-7);
  const platRecent = {}, platAll = {};
  const pages = [];

  for (const p of GAP_PAGES) {
    const r = readPage(p.file, p.tok);
    const items = (r.data && r.data.items) || [];
    const byDate = {};
    for (const x of items) {
      const d = datePart(x.date || x.pubDate);
      if (!d) continue;
      byDate[d] = (byDate[d] || 0) + 1;
      const pl = platOf(x);
      platAll[pl] = (platAll[pl] || 0) + 1;
      if (days.indexOf(d) >= 0) platRecent[pl] = (platRecent[pl] || 0) + 1;
    }
    let streak = 0;
    for (let i = workdays.length - 1; i >= 0; i--) {
      if ((byDate[workdays[i]] || 0) > 0) break;
      streak++;
    }
    const last = Object.keys(byDate).filter(d => d <= TODAY).sort().pop() || '—';
    const recent7 = last7.reduce((a, d) => a + (byDate[d] || 0), 0);
    pages.push({ key: p.key, name: p.name, today: byDate[TODAY] || 0,
                 recent7, streak, last, error: r.error || null });
  }

  const zeroPlat = Object.keys(platAll).filter(pl => !platRecent[pl] && pl !== '未知').sort();
  const watchZero = WATCH_PLATFORMS.filter(w =>
    !Object.keys(platRecent).some(pl => pl === w || pl.indexOf(w) === 0));
  const alerts = pages.filter(x => x.streak >= GAP_THRESHOLD);
  return {
    threshold: GAP_THRESHOLD, window: GAP_WINDOW, days, workdays,
    pages, platRecent, platAll, zeroPlat, watchZero,
    alerts, verdict: alerts.length ? 'ALERT' : 'OK',
  };
}

function gapPad(s, n) {
  let w = 0;
  for (const ch of String(s)) w += /[\u4e00-\u9fff（）]/.test(ch) ? 2 : 1;
  return String(s) + ' '.repeat(Math.max(0, n - w));
}

function printGap(g) {
  console.log('');
  console.log(`== 增量健康度 · 近 ${g.window} 天（只告警，不改变 VERDICT / 退出码） ==`);
  console.log(gapPad('页面', 14) + gapPad('当日', 7) + gapPad('近7日', 8) +
              gapPad('连续0新增', 13) + '最后有新增');
  console.log('-'.repeat(96));
  for (const x of g.pages) {
    const flag = x.error ? ' (读取失败)' : '';
    console.log(gapPad(x.name, 14) + gapPad(String(x.today), 7) + gapPad(String(x.recent7), 8) +
                gapPad(String(x.streak) + ' 工作日', 13) + x.last + flag);
  }
  console.log('-'.repeat(96));
  const top = Object.keys(g.platRecent).sort((a, b) => g.platRecent[b] - g.platRecent[a]).slice(0, 10);
  console.log('近 10 天有产出平台: ' + (top.length ? top.map(pl => `${pl} ${g.platRecent[pl]}`).join(' · ') : '无'));
  console.log('零产出平台（全量有条目、近 10 天 0 新增）: ' + (g.zeroPlat.join(' / ') || '无'));
  console.log('重点监控四平台: ' + (g.watchZero.length
    ? `${g.watchZero.length}/4 零产出（${g.watchZero.join(' / ')}）· 11-06 起无供料方`
    : '4/4 均有产出'));
  console.log(`GAP: ${g.verdict}` + (g.alerts.length
    ? `（${g.alerts.length} 项连续 0 新增 ≥ ${g.threshold} 工作日）`
    : `（各专栏连续 0 新增均 < ${g.threshold} 工作日）`));
  for (const x of g.alerts) {
    console.log(`  · ${x.name} 连续 ${x.streak} 个工作日 0 新增，最后有新增 ${x.last}`);
  }
}

/* ---------- 执行 ---------- */
const results = [
  checkUC(),
  checkK3(),
  checkH3C(),
  checkColumn('sw', 'software-columns.html', '_sw_items_norm.json.meta.json', ['_sw_items_norm.json']),
  checkColumn('mbox', 'creality-mbox.html', '_mbox_items.json.meta.json', ['_mbox_items.json']),
  checkColumn('fc', 'fullcolor-columns.html', '_fc_items_norm.json.meta.json', ['_fc_items_norm.json']),
  checkResin(),
];

const nRed = results.filter(r => r.verdict === RED).length;
const nYellow = results.filter(r => r.verdict === YELLOW).length;
const GAP = gapReport();

// 只在查「今天」时落盘；--date 回看历史不覆盖当日状态。
// 状态文件供 dashboard / 飞书橙卡消费，本脚本不主动推送，避免天天刷屏。
if (TODAY === localYmd(new Date())) {
  const snapshot = {
    date: TODAY,
    generatedAt: new Date().toISOString(),
    threshold: GAP.threshold,
    window: GAP.window,
    verdict: GAP.verdict,
    alerts: GAP.alerts,
    pages: GAP.pages,
    platRecent: GAP.platRecent,
    zeroPlat: GAP.zeroPlat,
    watchZero: GAP.watchZero,
  };
  try {
    fs.writeFileSync(path.join(DIR, '_col_gap_status.json'),
                     JSON.stringify(snapshot, null, 2) + '\n', 'utf8');
  } catch (e) {
    console.log('[GAP] 状态文件写入失败（不影响闸门）: ' + e.message);
  }
}

if (AS_JSON) {
  console.log(JSON.stringify({ date: TODAY, red: nRed, yellow: nYellow, results, gap: GAP }, null, 2));
  process.exit(nRed > 0 ? 1 : 0);
}

const LABEL = { uc: '用户吐槽', k3: 'K3 反馈', h3c: 'H3C 专栏', sw: '软件专栏', mbox: 'mBox 专栏', fc: '全彩专栏' };
console.log(`== 全站专栏新鲜度闸门 · ${TODAY} ==`);
const pad = (s, n) => {
  // 中文按 2 列宽估算，保证表头对齐
  let w = 0;
  for (const ch of String(s)) w += /[\u4e00-\u9fff（）]/.test(ch) ? 2 : 1;
  return String(s) + ' '.repeat(Math.max(0, n - w));
};
console.log(pad('页面', 24) + pad('判定', 9) + '说明');
console.log('-'.repeat(96));
for (const r of results) {
  const mark = r.verdict === GREEN ? 'OK  ' : r.verdict === YELLOW ? 'WARN' : 'FAIL';
  console.log(pad(`${r.file}`, 24) + pad(`${mark} ${r.verdict}`, 16) + r.reason);
}
console.log('-'.repeat(96));
console.log(`VERDICT: ${nRed === 0 ? 'PASS' : 'FAIL'} (RED=${nRed} YELLOW=${nYellow})`);
if (nRed > 0) {
  console.log('');
  console.log('处置：RED 项必须在 Step 5 收尾前补齐——补采 → 归一 → 构建 → 再跑一次本闸门；');
  console.log('      确实要跳过时用 --allow <key>（key 见上表：uc / k3 / h3c / sw / mbox / fc / resin），并在台账记录原因。');
}
printGap(GAP);
process.exit(nRed > 0 ? 1 : 0);
