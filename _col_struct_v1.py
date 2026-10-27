# -*- coding: utf-8 -*-
"""专栏结构规范 v1.0 落地改造器（幂等）

对 creality-mbox.html / software-columns.html 应用同一套五段骨架改造：
  S2 总体概览 -> S3 专项分析 -> S4 渠道结构 -> S5 明细反馈流
两文件 JS 同构，故用同一份替换文本；KIND 分支处理差异。

用法：python _col_struct_v1.py
"""
import re, sys, io

TARGETS = ["creality-mbox.html", "software-columns.html"]

CSS_ADD = """
/* ===== 专栏结构规范 v1.0 : S3 专项分析 / S4 渠道结构 / S5 四列卡片 ===== */
.topic-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;margin-top:12px}
.tcard{background:#161b22;border:1px solid #21262d;border-radius:10px;padding:12px 14px;cursor:pointer;transition:border-color .16s,background .16s}
.tcard:hover{border-color:#30475e;background:#1a2029}
.tcard.on{border-color:#58a6ff;background:rgba(88,166,255,.08)}
.tcard.zero{cursor:default}
.tcard.zero:hover{border-color:#21262d;background:#161b22}
.tcard .tn{display:flex;align-items:baseline;justify-content:space-between;gap:8px;font-size:13px;font-weight:600;color:#e6edf3}
.tcard .tn b{font-size:15px;font-variant-numeric:tabular-nums}
.tcard .td{font-size:11.5px;color:#6e7681;margin-top:5px;line-height:1.5}
.tcard .tflag{font-size:10.5px;color:#d29922;border:1px solid rgba(210,153,34,.35);border-radius:5px;padding:1px 6px;margin-top:7px;display:inline-block}
.chan-row{display:flex;align-items:center;gap:10px;padding:7px 0;border-bottom:1px dashed #21262d;font-size:12.5px}
.chan-row:last-child{border-bottom:none}
.chan-row .cn{flex:0 0 168px;color:#c9d1d9}
.chan-row .cst{flex:0 0 88px;font-size:11.5px}
.chan-row .cnum{flex:0 0 72px;text-align:right;font-variant-numeric:tabular-nums}
.chan-row .cwhy{flex:1;color:#6e7681;font-size:11.5px}
.chan-row.ok .cst{color:#3fb950}
.chan-row.todo .cst{color:#d29922}
.chan-row.blocked .cst{color:#f85149}
.chan-row.zero .cn{color:#8b949e}
.card-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:12px;align-items:start}
.card-grid .card{margin-bottom:0;display:flex;flex-direction:column;height:100%}
.c-sum{font-size:12.5px;line-height:1.62;color:#c9d1d9;margin-top:8px;
  display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical;overflow:hidden}
.card.open .c-sum{-webkit-line-clamp:unset;display:block;overflow:visible}
.c-more{margin-top:8px;font-size:11.5px;color:#58a6ff;cursor:pointer;user-select:none}
.c-more:hover{text-decoration:underline}
.card .fold{display:none;margin-top:9px;padding-top:9px;border-top:1px solid #21262d}
.card.open .fold{display:block}
</style>"""

DOM_OLD = """  <h2 class="sec-title">总体概览</h2>
  <div class="kpi-row" id="kpiRow"></div>

  <div class="grid-2" id="panelsA"></div>
  <div class="grid-2" id="panelsB"></div>

  <h2 class="sec-title">明细反馈流 <span class="hint" id="flowHint"></span></h2>
  <div class="filters" id="filters"></div>
  <div class="fsum" id="filterSummary"></div>
  <div id="countLine"></div>
  <div id="cardGrid"></div>
  <div class="pager" id="pager"></div>"""

DOM_NEW = """  <h2 class="sec-title">总体概览<span class="hint" id="ovHint"></span></h2>
  <div class="kpi-row" id="kpiRow"></div>
  <div class="grid-2" id="ovA"></div>
  <div class="grid-2" id="ovB"></div>

  <h2 class="sec-title">专项分析<span class="hint" id="topicHint"></span></h2>
  <div class="topic-grid" id="topicGrid"></div>
  <div id="topicDist"></div>

  <h2 class="sec-title">渠道结构<span class="hint" id="chanHint"></span></h2>
  <div id="chanCover"></div>
  <div id="chanShare"></div>

  <h2 class="sec-title">明细反馈流<span class="hint" id="flowHint"></span></h2>
  <div class="filters" id="filters"></div>
  <div class="fsum" id="filterSummary"></div>
  <div id="countLine"></div>
  <div class="card-grid" id="cardGrid"></div>
  <div class="pager" id="pager"></div>"""


def patch_css(s):
    if "专栏结构规范 v1.0" in s:
        return s, "css:skip"
    if "</style>" not in s:
        return s, "css:NO-STYLE-TAG"
    s = s.replace("</style>", CSS_ADD.strip(), 1)
    return s, "css:ok"


def patch_dom(s):
    if 'id="topicGrid"' in s:
        return s, "dom:skip"
    if DOM_OLD not in s:
        return s, "dom:NO-MATCH"
    s = s.replace(DOM_OLD, DOM_NEW, 1)
    return s, "dom:ok"


def main():
    for f in TARGETS:
        raw = io.open(f, encoding="utf-8").read()
        s = raw
        s, r1 = patch_css(s)
        s, r2 = patch_dom(s)
        if s != raw:
            io.open(f, "w", encoding="utf-8").write(s)
        print("%-28s %-10s %-10s len %d -> %d" % (f, r1, r2, len(raw), len(s)))


if __name__ == "__main__":
    main()
