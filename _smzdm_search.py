# -*- coding: utf-8 -*-
"""_smzdm_search.py — 什么值得买采集公共模块（2026-10-27）

为什么接这个源
--------------------------------------------------------------------------
用户 2026-10-27：mBox 要接「什么值得买」，软件专栏也要。它是国内导购站，
提供的是**价格带信号**而不是用户反馈 —— 这一点必须写进字段，不能混进声量统计。

实测约束（改之前先读）
--------------------------------------------------------------------------
  1. search.smzdm.com 全站搜索返回 **202 + JS 挑战页**（209 字节壳），无任何内容
     → 关键词搜索不可用，不要浪费时间试 cookie，那是前端 challenge 不是登录态问题。
  2. 分类页 https://www.smzdm.com/fenlei/3ddayinji/ 可用，返回完整 HTML。
     每页 9 条，卡片锚点是 class="haojia-card-container"。
  3. **分页无效**：/p2/ 与 /p1/ 交集 8/9，/p3/ 也是同一批 —— 实为 SPA，
     翻页靠 JS。所以本模块只抓首屏，条目靠 /p/{id}/ 跨次去重慢慢累积。
  4. 卡片里的 article-date-box 是 YY-MM-DD，但实测出现 21-09-14 / 22-03-26 这类
     与「国家补贴」政策时间矛盾的值 —— 它不是发布日（疑为商品上架或抓取残留）。
     **不采信，date 一律记为抓取日**，页面上标「抓取日」。宁可标不确定，
     也不要编一个看起来精确的错日期。

内容性质判断（决定它能不能进 KPI）
--------------------------------------------------------------------------
2026-10-27 实测 9 条 3D 打印机分类内容全部为整机好价：
    Bambu Lab A1 / P1S / X2D、纵维立方 Kobra X …
用「切片|slicer|Orca|Cura|Studio|软件|固件」过滤命中 **0 条**。
所以：
  · 对 mBox —— 价值高（竞品价格带，直接对标家庭价格锚点）
  · 对软件专栏 —— 无软件内容，只作「周边消费信号」，countInVolume=False

用法
--------------------------------------------------------------------------
    import _smzdm_search as SM
    items, sources, errors = SM.search(price_max=3000, gate=my_gate)
"""

import html as _html
import os
import re
import time
import urllib.error
import urllib.request
from datetime import date

for _k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy",
           "ALL_PROXY", "all_proxy"):
    os.environ.pop(_k, None)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# 3D 打印整机分类。实测只有这一个可用（3ddayinhao / 3ddayin 均 404）。
CATS = [
    ("3D 打印机", "https://www.smzdm.com/fenlei/3ddayinji/"),
]

TIMEOUT = 25
_RATE = 2.0

_RE_BLOCK = re.compile(r'class="haojia-card-container')
_RE_TITLE = re.compile(r'class="title-normal-box card-right-box-title"[^>]*>(.*?)</a>', re.S)
_RE_PRICE = re.compile(r'class="sub-title-box card-right-box-sub-title"[^>]*>(.*?)</a>', re.S)
_RE_URL = re.compile(r'href="(https://www\.smzdm\.com/p/(\d+)/)"')
_RE_ABS = re.compile(r'contentsingle="([^"]*)"')
_RE_TAG = re.compile(r"<[^>]+>")


def _clean(s):
    s = _html.unescape(_html.unescape(s or ""))
    s = _RE_TAG.sub(" ", s)
    s = re.sub(r"[ \t\u00a0]+", " ", s)
    return s.strip()


def parse_list(html):
    """按卡片切块解析。返回 [{aid,title,price,priceNum,abstract,url}]"""
    out = []
    blocks = _RE_BLOCK.split(html or "")
    for blk in blocks[1:]:
        t = _RE_TITLE.search(blk)
        if not t:
            continue
        title = _clean(t.group(1))
        if not title:
            continue
        u = _RE_URL.search(blk)
        p = _RE_PRICE.search(blk)
        price = _clean(p.group(1)) if p else ""
        pm = re.search(r"([\d.]+)\s*元", price)
        a = _RE_ABS.search(blk)
        out.append({
            "aid": u.group(2) if u else "",
            "title": title,
            "price": price,
            "priceNum": float(pm.group(1)) if pm else 0.0,
            "abstract": _clean(a.group(1)) if a else "",
            "url": u.group(1) if u else "",
        })
    return out


def _get(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "zh-CN,zh;q=0.9",
    })
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            if r.status != 200:
                return "", r.status
            return r.read().decode("utf-8", "replace"), 200
    except urllib.error.HTTPError as e:
        return "", e.code
    except Exception as e:
        return "", type(e).__name__


def search(gate=None, price_max=None, categories=None, label="什么值得买",
           sources=None, errors=None):
    """抓分类首屏，转统一契约。gate(title, abstract) -> bool 可过滤。
    price_max: 只要价格 <= 该值的条目（None 不限）。"""
    if sources is None:
        sources = []
    if errors is None:
        errors = []
    cats = categories or CATS
    today = date.today().isoformat()
    items = []

    for i, (disp, url) in enumerate(cats):
        if i:
            time.sleep(_RATE)
        html, st = _get(url)
        if not html:
            sources.append({"source": "%s %s" % (label, disp), "status": "error",
                            "count": 0, "note": str(st)})
            errors.append({"source": disp, "url": url, "status": st})
            continue

        rows = parse_list(html)
        kept = 0
        for r in rows:
            if not r["aid"]:
                continue
            if gate and not gate(r["title"], r["abstract"]):
                continue
            if price_max and r["priceNum"] and r["priceNum"] > price_max:
                continue
            items.append({
                "uid": "sm_%s" % r["aid"],
                # 好价条目没有可信发布日，date 记抓取日并显式标明（见模块头注释第 4 条）
                "platform": label,
                "site": "smzdm.com",
                "channel": "国内导购",
                "country": "CN",
                "language": "ZH",
                "date": today,
                "dateKind": "fetched",
                "title": r["title"],
                "originalText": r["abstract"] or r["title"],
                "url": r["url"],
                "price": r["price"],
                "priceNum": r["priceNum"],
                "sourceType": "导购",
                # 导购不是用户反馈：不计入声量，不进问题结构。与 GitHub 缺陷单「单列不计声量」同理。
                "countInVolume": False,
                "foundBy": "%s · %s" % (label, disp),
            })
            kept += 1
        sources.append({"source": "%s %s" % (label, disp),
                        "status": "ok" if kept else "empty",
                        "count": kept, "scanned": len(rows)})
    return items, sources, errors


if __name__ == "__main__":
    its, src, err = search()
    print("items=%d" % len(its))
    for s in src:
        print("  %-26s %-6s %s / 扫描 %s" % (s["source"], s["status"],
                                            s.get("count"), s.get("scanned")))
    for it in its:
        print("   - %-8s %s" % (it["price"] or "—", it["title"][:56]))
