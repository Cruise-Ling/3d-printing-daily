#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_gen_briefing.py — 日报生成器（通用入口，替代「一天一个新脚本」）。

背景：2026-10 之前每天现写一个 _gen_briefing_YYYYMMDD.py，内容与代码耦合，
导致「改版式要改十几份脚本」「补跑时无脚本可用」。本脚本把内容抽成 JSON，
结构固定、可复用、可回放。

用法：
  1) 准备内容文件 _briefing_YYYYMMDD.json：
     {
       "hot": ["热点1", "热点2", ...],                       # 5 条
       "items": [
         ["general", "标题", "https://...", "来源名", "摘要"],  # zone 见 ZONE_ORDER
         ...
       ]
     }
  2) python _gen_briefing.py --date 20261022
     python _gen_briefing.py --date 20261022 --content-date 2026-10-21
     python _gen_briefing.py --date 20261022 --from-file 其它内容.json

模板：自动取「比目标日期早的、最近一份」briefing_*.html 作为版式来源（只取 <div class='card'> 之前）。
"""
import os
import re
import io
import json
import glob
import argparse
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))

ZONE_ORDER = ["general", "specific", "consumer", "niche", "scenario", "global", "feedback"]

ZONE_TITLE = {
    "general": "泛行业资讯（工业/资本/政策）",
    "specific": "细分领域动态（医疗/航天/材料）",
    "consumer": "消费级（新品/评测/品牌）",
    "niche": "细分市场（汽车/建筑/医疗等）",
    "scenario": "场景×3D打印 Scenario（教育/文创/家居/食品）",
    "global": "海外资讯（国际/3Dnatives/3DPrint.com）",
    "feedback": "用户口碑（国外评测/国内实测）",
}

# 来源 → 颜色标签类名（页面样式 `.from-<tag>`）
SRC_TAG = {
    "腾讯新闻": "other", "中证网": "gov", "中国政府网": "gov", "中国经济网": "gov",
    "上海市税务局": "gov", "3D打印资源库": "dayinpai", "南极熊": "dayinpai",
    "3D打印技术参考": "other", "上海人工智能实验室": "other", "长三角G60激光联盟": "other",
    "今日头条": "other", "国资潇湘": "other", "Creality官方商城": "other",
    "Stack Archive": "3dprint", "智通财经": "other", "什么值得买": "other",
    "什么值得买社区": "other", "证券日报": "other", "同花顺财经": "other",
    "Gigahertz": "other", "搜狐网": "other", "新湖南": "other", "网易": "163",
    "东莞发布": "other", "腾讯网": "other", "诺彩数码": "other", "YallahTech": "other",
    "GoKawiil": "3dprint", "Skyorbits": "other", "Gadgetify": "other",
    "Makers101": "3dprint", "金融界": "other",
}

WEEK_CN = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]


def pick_template(target_yyyymmdd):
    """取比目标日期早的最近一份 briefing 作版式来源。"""
    cands = []
    for p in glob.glob(os.path.join(HERE, "briefing_*.html")):
        m = re.search(r"briefing_(\d{8})\.html$", p)
        if m and m.group(1) < target_yyyymmdd:
            cands.append((m.group(1), p))
    if not cands:
        raise SystemExit("找不到可用的模板 briefing（需要至少一份更早日期的 briefing_*.html）")
    cands.sort()
    return cands[-1][1]


def item_html(num, title, url, source, summary):
    tag = SRC_TAG.get(source, "other")
    return (
        "    <div class='item'>\n"
        "      <div class='item-head'>\n"
        "        <span class='num-dot'>%d</span>\n"
        "        <div class='item-title'>\n"
        "          <a href='%s' target='_blank'>%s</a>\n"
        "          <span class='score-badge score-badge-a'>✅ A级</span>\n"
        "        </div>\n"
        "      </div>\n"
        "      <div class='item-summary'>%s</div>\n"
        "      <div class='item-source'>来源：<a href='%s' target='_blank'>%s</a>"
        "<span class='from-tag from-%s'>%s</span></div>\n"
        "    </div>\n"
    ) % (num, url, title, summary, url, source, tag, source)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True, help="页面日期 YYYYMMDD")
    ap.add_argument("--content-date", default="", help="内容日期 YYYY-MM-DD，默认取上一个工作日")
    ap.add_argument("--from-file", default="", help="内容 JSON 路径")
    ap.add_argument("--out", default="", help="输出路径，默认 briefing_YYYYMMDD.html")
    args = ap.parse_args()

    d = datetime.datetime.strptime(args.date, "%Y%m%d").date()
    dash = d.strftime("%Y-%m-%d")
    cn_date = "%d年%d月%d日" % (d.year, d.month, d.day)

    if args.content_date:
        cd = datetime.datetime.strptime(args.content_date, "%Y-%m-%d").date()
    else:
        cd = d - datetime.timedelta(days=1)
        while cd.weekday() >= 5:           # 跳过周末
            cd -= datetime.timedelta(days=1)
    cn_cd = "%d年%d月%d日" % (cd.year, cd.month, cd.day)

    src_file = args.from_file or os.path.join(HERE, "_briefing_%s.json" % args.date)
    if not os.path.exists(src_file):
        raise SystemExit("缺少内容文件：%s" % src_file)
    with io.open(src_file, encoding="utf-8") as f:
        data = json.load(f)

    hot = data.get("hot") or []
    items = data.get("items") or []
    if len(hot) < 3:
        raise SystemExit("热点不足 3 条")
    if len(items) < 20:
        raise SystemExit("资讯不足 20 条（当前 %d）" % len(items))

    # zone 归组
    by_zone = {z: [] for z in ZONE_ORDER}
    n = 0
    for row in items:
        zone, title, url, source, summary = row[0], row[1], row[2], row[3], row[4]
        if zone not in by_zone:
            raise SystemExit("未知 zone：%s" % zone)
        n += 1
        by_zone[zone].append((n, title, url, source, summary))

    sections_html = ""
    for z in ZONE_ORDER:
        sec = ("    <div class='section-title %s' id=\"%s\">\n"
               "      <span class='icon'></span>%s</div>\n" % (z, z, ZONE_TITLE[z]))
        sec += "    <div class='%s-zone'>\n" % z
        for (num, title, url, source, summary) in by_zone[z]:
            sec += item_html(num, title, url, source, summary)
        sec += "    </div>\n"
        sections_html += sec

    hot_li = "".join("      <li>%s</li>\n" % h for h in hot)

    body = (
        "<div class='card'>\n\n"
        "<div class='header'>\n"
        "  <a class='header-back' href=\"index.html\">← 首页</a>\n"
        "  <h1>3D打印行业每日资讯</h1>\n"
        "  <div class='date'>" + cn_date + " · " + WEEK_CN[d.weekday()] + "</div>\n"
        "  <div class='source-note'>内容来源：3D打印资源库 / 3DPrint.com / 3Dnatives / 证券日报 / 中国经济网 等</div>\n"
        "</div>\n"
        "<div class='stats-bar'>\n"
        "  <span class='stats-pill'>资讯 <b>" + str(n) + "</b> 条</span>\n"
        "  <span class='stats-pill'>分区 <b>7</b> 大</span>\n"
        "  <span class='stats-pill warn'>内容日期 <b>" + cn_cd + "</b></span>\n"
        "</div>\n"
        "<div class='hot-summary'>\n"
        "  <h3>🔥 今日热点速递</h3>\n"
        "    <ul><ul>\n" + hot_li + "    </ul></ul>\n"
        "  </div>\n"
        + sections_html +
        "<div class='footer'>\n"
        "  <p>3D打印行业每日资讯 · " + cn_date + " （" + WEEK_CN[d.weekday()] + "）· 内容日期 " + cn_cd + "</p>\n"
        "  <p>数据来源见各条目标注 · <a href=\"index.html\">返回首页</a></p>\n"
        "</div>\n"
        "</div>\n"
        "</body>\n"
        "</html>\n"
    )

    tpl_path = pick_template(args.date)
    with io.open(tpl_path, encoding="utf-8") as f:
        tpl = f.read()
    head = tpl[: tpl.index("<div class='card'>")]
    # 标题行替换（模板里是上一份的日期）
    head = re.sub(r"<title>[^<]*</title>",
                  "<title>3D打印行业每日资讯 - " + cn_date + "</title>", head, count=1)

    out = args.out or os.path.join(HERE, "briefing_%s.html" % args.date)
    with io.open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(head + body)

    missing = [z for z in ZONE_ORDER if not by_zone[z]]
    print("written %s" % out)
    print("模板：%s" % os.path.basename(tpl_path))
    print("资讯 %d 条 · 热点 %d 条 · 分区 %d" % (n, len(hot), len(ZONE_ORDER)))
    print("分区明细：%s" % json.dumps({z: len(by_zone[z]) for z in ZONE_ORDER}, ensure_ascii=False))
    if missing:
        print("⚠️ 空分区：%s" % ", ".join(missing))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
