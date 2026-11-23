/* ===================================================================
   明细反馈流 · 批量导出核心（三页共用，勿单独改页面内副本）
   2026-11-23 改版：默认导出「当前筛选列表」，纯前端生成 xlsx/csv，
   不依赖本地服务；「补全评论」与「粘贴外部链接」才需要服务。
   校验器断言：EXP_VER 三页一致。
   =================================================================== */
(function () {
"use strict";
var EXP_VER = "2026-11-23a", SVC = "http://127.0.0.1:8765";
var online = false, jobId = null, timer = null, fmt = "xlsx", scope = "all",
    foldOn = false, pollN = 0, pollTimer = null, busy = false;

function $(id) { return document.getElementById(id); }
function escH(s) {
  return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
  });
}

/* ================= 适配层 START（每页唯一差异） ================= */
var ADAPTER = {
  kind: "col",
  title: "",
  ref: "",
  fields: function () { return []; },
  rows: function () { return []; },
  scope: function () { return ""; }
};
/* ================= 适配层 END ================= */

/* ================= 取值与分类 ================= */
function cellVal(v) {
  if (v == null || v === "") return "";
  if (typeof v === "boolean") return v ? "是" : "否";
  if (Object.prototype.toString.call(v) === "[object Array]") return v.join("、");
  if (typeof v === "object") return JSON.stringify(v);
  return v;
}
function urlOf(it) {
  return String(it.url || it.sourceLink || it.link || "");
}
function typeOf(it) {
  var hay = String((it.platform || "") + " " + urlOf(it));
  if (/youtube|youtu\.be/i.test(hay)) return "yt";
  if (/reddit/i.test(hay)) return "rd";
  return "other";
}
function allRows() {
  try { var r = ADAPTER.rows(); return (r || []).slice(); } catch (e) { return []; }
}
function scopeRows(rows) {
  if (scope === "all") return rows;
  return rows.filter(function (it) { return typeOf(it) === scope; });
}
function countBy(rows) {
  var c = { all: rows.length, yt: 0, rd: 0, other: 0 };
  rows.forEach(function (it) { c[typeOf(it)]++; });
  return c;
}

/* ================= xlsx（零依赖，zip store 模式） ================= */
var CRC_T = null;
function crcTable() {
  if (CRC_T) return CRC_T;
  CRC_T = new Uint32Array(256);
  for (var n = 0; n < 256; n++) {
    var c = n;
    for (var k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    CRC_T[n] = c >>> 0;
  }
  return CRC_T;
}
function crc32(u8) {
  var t = crcTable(), c = 0xffffffff;
  for (var i = 0; i < u8.length; i++) c = t[(c ^ u8[i]) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}
function utf8(s) { return new TextEncoder().encode(s); }
function concatU8(list) {
  var n = 0, i;
  for (i = 0; i < list.length; i++) n += list[i].length;
  var out = new Uint8Array(n), off = 0;
  for (i = 0; i < list.length; i++) { out.set(list[i], off); off += list[i].length; }
  return out;
}
function zipStore(files) {
  var parts = [], central = [], offset = 0;
  for (var fi = 0; fi < files.length; fi++) {
    var f = files[fi];
    var name = utf8(f.name);
    var data = typeof f.data === "string" ? utf8(f.data) : f.data;
    var crc = crc32(data);
    var lh = new Uint8Array(30 + name.length), dv = new DataView(lh.buffer);
    dv.setUint32(0, 0x04034b50, true); dv.setUint16(4, 20, true);
    dv.setUint16(6, 0x0800, true); dv.setUint16(8, 0, true);
    dv.setUint16(10, 0, true); dv.setUint16(12, 0x21, true);
    dv.setUint32(14, crc, true); dv.setUint32(18, data.length, true);
    dv.setUint32(22, data.length, true); dv.setUint16(26, name.length, true);
    dv.setUint16(28, 0, true); lh.set(name, 30);
    parts.push(lh, data);

    var cd = new Uint8Array(46 + name.length), cv = new DataView(cd.buffer);
    cv.setUint32(0, 0x02014b50, true); cv.setUint16(4, 20, true);
    cv.setUint16(6, 20, true); cv.setUint16(8, 0x0800, true);
    cv.setUint16(10, 0, true); cv.setUint16(12, 0, true);
    cv.setUint16(14, 0x21, true); cv.setUint32(16, crc, true);
    cv.setUint32(20, data.length, true); cv.setUint32(24, data.length, true);
    cv.setUint16(28, name.length, true); cv.setUint32(42, offset, true);
    cd.set(name, 46);
    central.push(cd);
    offset += lh.length + data.length;
  }
  var cdSize = 0;
  for (var ci = 0; ci < central.length; ci++) cdSize += central[ci].length;
  var eocd = new Uint8Array(22), ev = new DataView(eocd.buffer);
  ev.setUint32(0, 0x06054b50, true);
  ev.setUint16(8, files.length, true); ev.setUint16(10, files.length, true);
  ev.setUint32(12, cdSize, true); ev.setUint32(16, offset, true);
  return concatU8(parts.concat(central).concat([eocd]));
}
function xEsc(s) {
  return String(s == null ? "" : s).replace(/[\x00-\x08\x0b\x0c\x0e-\x1f]/g, "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
function colLetter(n) {
  var s = "";
  while (n > 0) { var r = (n - 1) % 26; s = String.fromCharCode(65 + r) + s; n = (n - r - 1) / 26; }
  return s;
}
function xCell(ref, v, st) {
  if (v == null || v === "") return "";
  if (typeof v === "number" && isFinite(v)) return '<c r="' + ref + '" s="' + st + '"><v>' + v + "</v></c>";
  var t = xEsc(v).slice(0, 32767);
  if (!t) return "";
  return '<c r="' + ref + '" s="' + st + '" t="inlineStr"><is><t xml:space="preserve">' + t + "</t></is></c>";
}
function sheetXml(header, rows, widths) {
  var ncol = Math.max(header.length, 1), i;
  for (i = 0; i < rows.length; i++) if (rows[i].length > ncol) ncol = rows[i].length;
  var nrow = rows.length + 1;
  var o = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
    '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">' +
    '<dimension ref="A1:' + colLetter(ncol) + nrow + '"/>' +
    '<sheetViews><sheetView workbookViewId="0">' +
    '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>' +
    '<selection pane="bottomLeft" activeCell="A2" sqref="A2"/></sheetView></sheetViews>' +
    '<sheetFormatPr defaultRowHeight="15"/>';
  if (widths && widths.length) {
    o += "<cols>";
    for (i = 0; i < widths.length && i < ncol; i++) {
      o += '<col min="' + (i + 1) + '" max="' + (i + 1) + '" width="' + widths[i] + '" customWidth="1"/>';
    }
    o += "</cols>";
  }
  o += "<sheetData>";
  o += '<row r="1" ht="20" customHeight="1">';
  for (i = 0; i < header.length; i++) o += xCell(colLetter(i + 1) + "1", header[i], 1);
  o += "</row>";
  for (var ri = 0; ri < rows.length; ri++) {
    var rn = ri + 2;
    o += '<row r="' + rn + '">';
    for (i = 0; i < rows[ri].length; i++) o += xCell(colLetter(i + 1) + rn, rows[ri][i], 0);
    o += "</row>";
  }
  o += "</sheetData>";
  if (nrow > 1 && ncol) o += '<autoFilter ref="A1:' + colLetter(ncol) + nrow + '"/>';
  return o + "</worksheet>";
}
function buildXlsx(sheets) {
  var ct = "", wb = "", rels = "", i;
  for (i = 0; i < sheets.length; i++) {
    ct += '<Override PartName="/xl/worksheets/sheet' + (i + 1) + '.xml" ' +
      'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>';
    wb += '<sheet name="' + xEsc(sheets[i].name) + '" sheetId="' + (i + 1) + '" r:id="rId' + (i + 1) + '"/>';
    rels += '<Relationship Id="rId' + (i + 1) + '" ' +
      'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" ' +
      'Target="worksheets/sheet' + (i + 1) + '.xml"/>';
  }
  rels += '<Relationship Id="rId' + (sheets.length + 1) + '" ' +
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>';

  var files = [
    { name: "[Content_Types].xml", data: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
      '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">' +
      '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>' +
      '<Default Extension="xml" ContentType="application/xml"/>' +
      '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>' +
      '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>' +
      ct + "</Types>" },
    { name: "_rels/.rels", data: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
      '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' +
      '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>' +
      "</Relationships>" },
    { name: "xl/workbook.xml", data: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
      '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" ' +
      'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">' +
      "<sheets>" + wb + "</sheets></workbook>" },
    { name: "xl/_rels/workbook.xml.rels", data: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
      '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' +
      rels + "</Relationships>" },
    { name: "xl/styles.xml", data: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
      '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">' +
      '<fonts count="2"><font><sz val="10"/><name val="Microsoft YaHei"/></font>' +
      '<font><b/><sz val="10"/><name val="Microsoft YaHei"/></font></fonts>' +
      '<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>' +
      '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>' +
      '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>' +
      '<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>' +
      '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs>' +
      '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>' +
      "</styleSheet>" }
  ];
  for (i = 0; i < sheets.length; i++) {
    files.push({ name: "xl/worksheets/sheet" + (i + 1) + ".xml",
      data: sheetXml(sheets[i].header, sheets[i].rows, sheets[i].widths) });
  }
  return zipStore(files);
}

/* ================= 下载 ================= */
function stamp() {
  var d = new Date(), p = function (n) { return (n < 10 ? "0" : "") + n; };
  return d.getFullYear() + "-" + p(d.getMonth() + 1) + "-" + p(d.getDate()) +
    " " + p(d.getHours()) + ":" + p(d.getMinutes());
}
function safeName(s) { return String(s || "").replace(/[\\/:*?"<>|]/g, "_").slice(0, 90); }
function dl(u8, name, mime) {
  try {
    var blob = new Blob([u8], { type: mime });
    if (window.navigator && window.navigator.msSaveBlob) { window.navigator.msSaveBlob(blob, name); return; }
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url; a.download = name;
    document.body.appendChild(a); a.click();
    setTimeout(function () {
      try { document.body.removeChild(a); } catch (e) {}
      URL.revokeObjectURL(url);
    }, 1500);
  } catch (e) { alert("下载失败：" + e.message); }
}
function csvText(header, rows) {
  function line(arr) {
    return arr.map(function (v) {
      var s = String(v == null ? "" : v);
      return /[",\n\r]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
    }).join(",");
  }
  return "\ufeff" + [line(header)].concat(rows.map(line)).join("\r\n");
}
function fileBase() {
  var d = String(ADAPTER.ref || "").replace(/[^0-9]/g, "").slice(0, 8) || "export";
  var s = scope === "all" ? "全部" : (scope === "yt" ? "YouTube" : (scope === "rd" ? "Reddit" : "其他"));
  return safeName(ADAPTER.kind + "_" + d + "_" + s);
}

/* ================= 导出主流程（纯前端） ================= */
function doLocal() {
  if (busy) return;
  var rows = scopeRows(allRows());
  if (!rows.length) return;
  var fields = ADAPTER.fields();
  var header = fields.map(function (f) { return f[1]; });
  var data = rows.map(function (it) {
    return fields.map(function (f) { return cellVal(it[f[0]]); });
  });
  var meta = [
    ["导出时间", stamp()],
    ["专栏", ADAPTER.title || ADAPTER.kind],
    ["数据快照", ADAPTER.ref || "—"],
    ["导出范围", scope === "all" ? "当前筛选全部" : ("当前筛选 · 仅 " + (scope === "yt" ? "YouTube" : scope === "rd" ? "Reddit" : "其他"))],
    ["记录数", rows.length],
    ["字段数", fields.length],
    ["筛选状态", ADAPTER.scope() || "—"],
    ["时区", "页面本地时间；源数据含 UTC 字段者按字段原值导出"],
    ["口径声明", "本文件为页面已收录内容的快照，不含评论区原文与译文；评论与访问量等未收录字段需勾选「补全评论」另行抓取。"],
    ["情感/判定", "由标注层规则预标，未经需求方人工签字，引用前请抽检。"],
    ["生成器", "网页内联零依赖 xlsx（zip store 模式），未使用任何第三方库。"]
  ];
  var okBox = $("expDone");
  try {
    if (fmt === "csv") {
      dl(csvText(header, data), fileBase() + ".csv", "text/csv;charset=utf-8");
    } else {
      var widths = fields.map(function (f) {
        var k = f[0];
        return (k === "originalText" || k === "textCn") ? 52 : (f[1].length > 5 ? 16 : 10);
      });
      var bytes = buildXlsx([
        { name: "明细 " + rows.length + " 条", header: header, rows: data, widths: widths },
        { name: "导出说明", header: ["项", "值"], rows: meta, widths: [16, 84] }
      ]);
      dl(bytes, fileBase() + ".xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
    }
    okBox.classList.add("on");
    okBox.innerHTML = '<div class="exp-file"><span>' + escH(fileBase() + (fmt === "csv" ? ".csv" : ".xlsx")) +
      " · " + rows.length + " 条 · " + fields.length + " 列</span><span>已下载</span></div>" +
      '<div class="exp-tip">含“导出说明”页：记录筛选状态、数据快照与口径声明，可直接随文件转发。</div>';
  } catch (e) {
    okBox.classList.add("on");
    okBox.innerHTML = '<div class="exp-err">生成失败：' + escH(e.message) + "</div>";
  }
}

/* ================= 服务探测 ================= */
function svcNote(cls, title, sub, retry) {
  var el = $("expSvc");
  el.className = "exp-note" + (cls ? " " + cls : "");
  el.innerHTML = '<div class="exp-ntx"><b>' + escH(title) + "</b><span>" + sub + "</span></div>" +
    (retry ? '<button type="button" id="expRetry">重试</button>' : "");
  if (retry) { var b = $("expRetry"); if (b) b.onclick = function () { pollN = 0; checkSvc(false); }; }
  syncSvcVisible();
}
function needSvc() {
  return (!!($("expDeep") && $("expDeep").checked)) || (foldOn && parseCount() > 0);
}
function syncSvcVisible() {
  var el = $("expSvc");
  if (!el) return;
  if (needSvc()) el.classList.remove("exp-hide"); else el.classList.add("exp-hide");
}
function checkSvc(silent) {
  if (!silent) svcNote("", "正在检测本地服务…", "端口 8765 · 只监听本机");
  var ctl = window.AbortController ? new AbortController() : null;
  var to = setTimeout(function () { if (ctl) { try { ctl.abort(); } catch (e) {} } }, 2600);
  var opt = { cache: "no-store" };
  if (ctl) opt.signal = ctl.signal;
  fetch(SVC + "/api/ping", opt).then(function (r) { return r.json(); }).then(function (d) {
    clearTimeout(to);
    online = true; pollN = 0;
    if (pollTimer) { clearTimeout(pollTimer); pollTimer = null; }
    svcNote("ok", "本地服务已连接", "端口 " + d.port + " · 文件同时落在 _exports/");
    syncGo();
  }).catch(function () {
    clearTimeout(to);
    online = false;
    svcNote("bad", "本地服务未启动",
      "双击 automation-claw-20260423184755 目录下的 <b>_link_export_start.bat</b>，窗口保持打开", true);
    syncGo();
    if (pollN < 15 && needSvc()) {
      pollN++;
      pollTimer = setTimeout(function () { checkSvc(true); }, 4000);
    }
  });
}

/* ================= 补全评论（走服务） ================= */
function linksOf(rows) {
  var seen = {}, out = [];
  rows.forEach(function (it) {
    if (typeOf(it) === "other") return;
    var u = urlOf(it);
    if (!u || seen[u]) return;
    seen[u] = 1; out.push(u);
  });
  return out;
}
function doDeep() {
  if (busy || jobId) return;
  var rows = scopeRows(allRows());
  var links = linksOf(rows);
  if (!links.length) {
    var box = $("expDone");
    box.classList.add("on");
    box.innerHTML = '<div class="exp-err">当前范围里没有 YouTube / Reddit 条目，无需补全。' +
      "切到「全部」或换筛选条件后再试。</div>";
    return;
  }
  if (!online) { checkSvc(false); return; }
  busy = true;
  $("expGo").disabled = true;
  $("expGo").textContent = "提交中…";
  $("expProg").classList.add("on");
  $("expDone").classList.remove("on");
  $("expBar").style.width = "6%";
  $("expLog").innerHTML = "";
  fetch(SVC + "/api/export", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: links.join("\n"), format: fmt, maxComments: 300, translate: true, replies: true })
  }).then(function (r) {
    return r.json().then(function (d) { if (!r.ok) throw new Error(d.error || ("HTTP " + r.status)); return d; });
  }).then(function (d) {
    jobId = d.jobId;
    timer = setInterval(poll, 1500);
    poll();
  }).catch(function (e) {
    busy = false;
    $("expGo").disabled = false;
    syncGo();
    $("expDone").classList.add("on");
    $("expDone").innerHTML = '<div class="exp-err">提交失败：' + escH(e.message) + "</div>";
  });
}
function poll() {
  fetch(SVC + "/api/job?id=" + jobId).then(function (r) { return r.json(); }).then(function (j) {
    renderLog(j.logs || []);
    if (j.status === "done") { $("expBar").style.width = "100%"; finish(j); return; }
    if (j.status === "error") { $("expBar").style.width = "100%"; fail(j.error); return; }
    $("expBar").style.width = Math.min(90, 8 + j.elapsed * 1.8) + "%";
  }).catch(function () {});
}
function renderLog(logs) {
  var h = "";
  for (var i = 0; i < logs.length; i++) h += "<div><em>" + escH(logs[i].t) + "</em>" + escH(logs[i].m) + "</div>";
  var box = $("expLog"); box.innerHTML = h; box.scrollTop = box.scrollHeight;
}
function finish(j) {
  var jid = jobId;
  clearInterval(timer); timer = null; jobId = null; busy = false;
  var kb = ((j.size || 0) / 1024).toFixed(0);
  $("expDone").classList.add("on");
  $("expDone").innerHTML = '<div class="exp-file"><span>' + escH(j.file) + " · " + kb + ' KB</span>' +
    '<a href="' + SVC + "/api/download?id=" + jid + '" download>下载</a></div>' +
    '<div class="exp-tip">文件同时已落在本机 _exports/ 目录，浏览器若拦截下载可直接去取。</div>';
  syncGo();
}
function fail(msg) {
  clearInterval(timer); timer = null; jobId = null; busy = false;
  $("expDone").classList.add("on");
  $("expDone").innerHTML = '<div class="exp-err">导出失败：' + escH(msg || "未知错误") + "</div>";
  syncGo();
}

/* ================= 外部链接解析 ================= */
var RE_YT = /(?:youtube\.com\/(?:watch\?(?:[^#\s]*&)?v=|shorts\/|embed\/|live\/)|youtu\.be\/)([A-Za-z0-9_-]{11})/gi;
var RE_RD = /(?:reddit\.com\/(?:r\/[^\/\s]+\/)?comments\/|redd\.it\/)([a-z0-9]{4,10})/gi;
function parseCount() {
  try {
    var t = ($("expText") || {}).value || "", yt = {}, rd = {}, m;
    RE_YT.lastIndex = 0; while ((m = RE_YT.exec(t))) yt[m[1]] = 1;
    RE_RD.lastIndex = 0; while ((m = RE_RD.exec(t))) rd[m[1].toLowerCase()] = 1;
    return Object.keys(yt).length + Object.keys(rd).length;
  } catch (e) { return 0; }
}
function scanLinks() {
  var el = $("expText");
  if (!el) return;
  var t = el.value || "", yt = {}, rd = {}, m;
  RE_YT.lastIndex = 0; while ((m = RE_YT.exec(t))) yt[m[1]] = 1;
  RE_RD.lastIndex = 0; while ((m = RE_RD.exec(t))) rd[m[1].toLowerCase()] = 1;
  var ny = Object.keys(yt).length, nr = Object.keys(rd).length, n = ny + nr;
  var out = $("expParse");
  if (!t.trim()) {
    out.innerHTML = '待输入链接<span class="dim"> · 支持 YouTube / Reddit 帖子页</span>';
  } else if (!n) {
    out.innerHTML = '未识别到可用链接<span class="bad"> · 检查是否为视频页 / 帖子页，或链接被截断</span>';
  } else {
    out.innerHTML = "已识别 <b>" + n + "</b> 条 · YouTube " + ny + " · Reddit " + nr;
  }
  var b = $("expGo2");
  if (b) { b.disabled = !n || busy || !!jobId; b.textContent = n ? ("导出这些链接 · " + n + " 条") : "导出这些链接"; }
  syncSvcVisible();
}

/* ================= UI 装配 ================= */
function syncGo() {
  var rows = scopeRows(allRows());
  var deep = $("expDeep") && $("expDeep").checked;
  var b = $("expGo");
  if (!b) return;
  b.disabled = busy || !!jobId || !rows.length || (deep && !online);
  b.textContent = !rows.length ? "当前范围没有条目"
    : (deep ? "导出 " + rows.length + " 条 + 补全评论" : "导出这 " + rows.length + " 条 · " + fmt);
  var cols = $("expCols");
  if (cols) cols.textContent = ADAPTER.fields().length + " 列";
}
function renderChips() {
  var rows = allRows(), c = countBy(rows), box = $("expChips");
  if (!box) return;
  var defs = [["all", "全部", c.all], ["yt", "YouTube", c.yt], ["rd", "Reddit", c.rd], ["other", "其他渠道", c.other]];
  box.innerHTML = defs.map(function (d) {
    return '<button type="button" class="exp-chip' + (scope === d[0] ? " on" : "") + '" data-s="' + d[0] + '"' +
      (d[2] || d[0] === "all" ? "" : " disabled") + ">" + d[1] + "<b>" + d[2] + "</b></button>";
  }).join("");
  Array.prototype.forEach.call(box.querySelectorAll(".exp-chip"), function (ch) {
    ch.onclick = function () { scope = ch.getAttribute("data-s"); renderChips(); syncGo(); };
  });
  var sc = $("expScope");
  if (sc) sc.textContent = "共 " + c.all + " 条 · " + ADAPTER.fields().length + " 列";
}
function openDrawer() {
  $("expMask").classList.add("on");
  $("expDrawer").classList.add("on");
  $("expDrawer").setAttribute("aria-hidden", "false");
  document.body.style.overflow = "hidden";
  renderChips(); syncGo(); scanLinks();
  checkSvc(true);
  var t = $("expText"); if (t) setTimeout(function () { try { t.focus(); } catch (e) {} }, 240);
}
function closeDrawer() {
  $("expMask").classList.remove("on");
  $("expDrawer").classList.remove("on");
  $("expDrawer").setAttribute("aria-hidden", "true");
  document.body.style.overflow = "";
  if (timer) { clearInterval(timer); timer = null; }
  if (pollTimer) { clearTimeout(pollTimer); pollTimer = null; }
}

function init() {
  if (!$("expOpen")) return;
  function on(el, ev, fn) { if (el && el.addEventListener) el.addEventListener(ev, fn); }
  $("expOpen").onclick = openDrawer;
  var c = $("expClose"); if (c) c.onclick = closeDrawer;
  var m = $("expMask"); if (m) m.onclick = closeDrawer;
  on(document, "keydown", function (e) {
    if (e.key === "Escape" && $("expDrawer") && $("expDrawer").classList.contains("on")) closeDrawer();
  });
  on($("expText"), "input", scanLinks);
  on($("expText"), "paste", function () { setTimeout(scanLinks, 30); });

  var box = $("expFmt");
  if (box && box.querySelectorAll) {
    Array.prototype.forEach.call(box.querySelectorAll("button"), function (bt) {
      bt.onclick = function () {
        Array.prototype.forEach.call(box.querySelectorAll("button"), function (x) { x.classList.remove("on"); });
        bt.classList.add("on"); fmt = bt.getAttribute("data-v"); syncGo();
      };
    });
  }
  var go = $("expGo");
  if (go) go.onclick = function () { if ($("expDeep") && $("expDeep").checked) doDeep(); else doLocal(); };
  var go2 = $("expGo2");
  if (go2) go2.onclick = function () { if (!online) { checkSvc(false); return; } submitLinks(); };
  var deep = $("expDeep");
  if (deep) deep.onchange = function () {
    if (deep.checked) { pollN = 0; checkSvc(online); } else { syncSvcVisible(); }
    syncGo();
  };
  var fold = $("expFold"), fb = $("expFoldBody");
  if (fold && fb) fold.onclick = function () {
    foldOn = !foldOn;
    fold.classList.toggle("on", foldOn);
    fb.classList.toggle("on", foldOn);
    syncSvcVisible();
    if (foldOn) { scanLinks(); if (parseCount()) checkSvc(online); }
  };
  try { if (location.hash.indexOf("exp") >= 0) setTimeout(openDrawer, 300); } catch (e) {}
}

function submitLinks() {
  if (busy || jobId) return;
  var text = ($("expText") || {}).value || "";
  if (!parseCount()) return;
  busy = true;
  $("expGo2").disabled = true;
  $("expGo2").textContent = "提交中…";
  $("expProg").classList.add("on");
  $("expDone").classList.remove("on");
  $("expBar").style.width = "6%";
  $("expLog").innerHTML = "";
  fetch(SVC + "/api/export", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: text, format: fmt, maxComments: 300, translate: true, replies: true })
  }).then(function (r) {
    return r.json().then(function (d) { if (!r.ok) throw new Error(d.error || ("HTTP " + r.status)); return d; });
  }).then(function (d) {
    jobId = d.jobId;
    timer = setInterval(poll, 1500);
    poll();
  }).catch(function (e) {
    busy = false;
    $("expGo2").disabled = false;
    scanLinks();
    $("expDone").classList.add("on");
    $("expDone").innerHTML = '<div class="exp-err">提交失败：' + escH(e.message) + "</div>";
  });
}

window.expApi = { ver: EXP_VER, adapter: ADAPTER, rows: allRows, fields: ADAPTER.fields, xlsx: buildXlsx };
try { init(); } catch (e) {}
})();
