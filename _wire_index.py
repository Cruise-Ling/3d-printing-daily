# -*- coding: utf-8 -*-
"""把指定日期的日报接入 index.html（列表卡片 + BRIEFING_DATA），幂等。

用法：
  python _wire_index.py 20261027
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
IDX = os.path.join(HERE, "index.html")

# 首页卡片标题的图标序列（按热点顺序取用）
ICONS = ["\U0001F3C6", "\U0001F5A8\uFE0F", "\U0001F52C", "\U0001F1FA\U0001F1F8",
         "\U0001F4B0", "\U0001F4C8", "\U0001F6D2", "\U0001F3ED"]


def build_title(date8):
    """从当日 _briefing_YYYYMMDD.json 的 hot 生成首页卡片标题。

    2026-10-28 修复：此前 TITLE 是写死在脚本里的常量，
    结果 10-28 的首页卡片显示的是 10-27 的热点摘要。
    """
    import json
    p = os.path.join(HERE, "_briefing_%s.json" % date8)
    if not os.path.exists(p):
        return ""
    d = json.load(io.open(p, encoding="utf-8"))
    hot = [t.strip() for t in d.get("hot", []) if t and t.strip()]
    out = []
    for i, t in enumerate(hot[:6]):
        # 卡片标题要短：截到第一个分隔符或 26 字以内
        t = re.split(r"[，,。；;：:]", t)[0].strip()
        if len(t) > 26:
            t = t[:25] + "\u2026"
        out.append(ICONS[i % len(ICONS)] + " " + t)
    return "".join(out)

WD_CN = {0: "星期一", 1: "星期二", 2: "星期三", 3: "星期四", 4: "星期五", 5: "星期六", 6: "星期日"}
WD_EN = {0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday", 4: "Friday", 5: "Saturday", 6: "Sunday"}


def wire(date8):
    import datetime

    d = datetime.date(int(date8[:4]), int(date8[4:6]), int(date8[6:8]))
    iso = d.isoformat()
    # newline="" —— 必须保持文件原有行尾，否则写回时会把整份 index 的 LF 翻成 CRLF，
    # 导致 _index_dedupe.py（按 "[\n" 匹配锚点）结构异常（2026-10-27 踩过一次）。
    h = io.open(IDX, encoding="utf-8", newline="").read()

    TITLE = build_title(date8)
    assert TITLE, "无法从 _briefing_%s.json 生成首页标题" % date8

    if "href:'briefing_%s.html'" % date8 in h or 'href="briefing_%s.html"' % date8 in h:
        # 已接入：只刷新标题（幂等更新），不再重复插入
        n = 0
        pat = re.compile(r"(date:'%s',href:'briefing_%s\.html',title:')(.*?)(')" % (iso, date8))
        h, k1 = pat.subn(lambda m: m.group(1) + TITLE.replace("\\", "\\\\").replace("'", "\\'") + m.group(3), h)
        pat2 = re.compile(r'(<a class="briefing-item" href="briefing_%s\.html">[\s\S]{0,400}?<div class="title-line">)(.*?)(</div>)' % date8)
        h, k2 = pat2.subn(lambda m: m.group(1) + TITLE + m.group(3), h)
        if k1 or k2:
            io.open(IDX, "w", encoding="utf-8", newline="").write(h)
        print("ALREADY_WIRED %s (title refreshed: bdata=%d card=%d)" % (date8, k1, k2))
        return 0

    # ---- 1) BRIEFING_DATA 头部插入 ----
    anchor = "const BRIEFING_DATA = [\n"
    assert anchor in h, "BRIEFING_DATA anchor not found"
    entry = ("  {date:'%s',href:'briefing_%s.html',title:'%s',count:35,sections:7,"
             "weekdayCn:'%s',weekdayEn:'%s'},\n"
             % (iso, date8, TITLE.replace("\\", "\\\\").replace("'", "\\'"),
                WD_CN[d.weekday()], WD_EN[d.weekday()]))
    h = h.replace(anchor, anchor + entry, 1)

    # ---- 2) 列表卡片插到最前 ----
    card = (
        '<a class="briefing-item" href="briefing_%s.html">\n'
        '        <div class="date-badge">\n'
        '            <span class="day">%s</span>\n'
        '            <span class="month">%s</span>\n'
        '        </div>\n'
        '        <div class="briefing-info">\n'
        '            <div class="title-line">%s</div>\n'
        '        </div>\n'
        '    </a>\n'
        '    ' % (date8, d.strftime("%d"), d.strftime("%b").upper(), TITLE)
    )
    m = re.search(r'(\s*)<a class="briefing-item" href="briefing_\d{8}\.html">', h)
    assert m, "list card anchor not found"
    h = h[:m.start()] + "\n    " + card + h[m.start():].lstrip("\n")

    io.open(IDX, "w", encoding="utf-8", newline="").write(h)

    h2 = io.open(IDX, encoding="utf-8", newline="").read()
    print("card:", h2.count('href="briefing_%s.html"' % date8))
    print("bdata:", h2.count("date:'%s'" % iso))
    return 0


if __name__ == "__main__":
    sys.exit(wire(sys.argv[1] if len(sys.argv) > 1 else "20261027"))
