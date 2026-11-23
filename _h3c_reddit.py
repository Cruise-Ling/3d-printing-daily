# -*- coding: utf-8 -*-
"""_h3c_reddit.py — 拓竹 H3C 专栏的 Reddit 采集（2026-11-23 补）

为什么现在才补
--------------------------------------------------------------------------
2026-11-23 用户提出「Reddit 有些专栏没接入」，排查发现 H3C 是六个专栏里
唯一**代码层从未接过 Reddit** 的（`_h3c_collect.py` 只有 collect_bili /
collect_seed）。主链 prompt 当时写着「Reddit 403 不要重试」——那是对的
（匿名通道确实全挂），但正确的处理是「接了、标成不可用」，而不是「不接、
让页面看起来像用户没讨论」。用户决策：H3C 与其余五页统一。

通道现状（2026-11-23 实测，详见 `_col_channels.py` 的注释）
--------------------------------------------------------------------------
匿名 RSS 已关闭：www 429/404、old 302 跳登录、.json 403、
RSSHub 公共实例全挂、PullPush 429。
唯一可达的是 `api/v1/access_token`（401，缺 OAuth 凭据）。
所以本模块**当前预期产出 0 条**，但会如实记录 status=blocked 与原因，
而不是静默返回空列表。凭据补上后（任何人提供 clientId/clientSecret），
`_reddit_search.py` 的 OAuth 路径一通，本模块自动开始产出。

职责边界（与 _h3c_collect 同一纪律）
--------------------------------------------------------------------------
只抓取 + 去重，**不写语义字段**（sentiment / topics / problemPoints）。
产出候选池 `_h3c_reddit_candidates.json`，经人工标注后才由注入器上页。

闸门直接复用 `_h3c_collect.gate`（3D 打印语境 ∧ H3C 线索 ∧ 非新华三）——
不复制第二份，避免 H3C 是「拓竹九头」还是「新华三交换机」这个双主体坑
在两个文件里各写一遍、各漏一半。

用法
--------------------------------------------------------------------------
    python _h3c_reddit.py --days 30          # 抓近 30 天
    python _h3c_reddit.py --probe            # 只探通道，不写文件
"""
import argparse
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

OUT = os.path.join(HERE, "_h3c_reddit_candidates.json")

# 拓竹社区主版 + 泛 3D 打印版。H3C 是竞品机型，讨论主要集中在 r/BambuLab，
# 主版用来捞「H3C 值不值 / 与 H2C 对比」这类决策讨论。
SUBS = [
    ("r/BambuLab", "BambuLab"),
    ("r/3Dprinting", "3Dprinting"),
    ("r/3dprinter", "3dprinter"),
]


def _gate():
    """延迟导入：`_h3c_collect` 将来若 import 本模块，不会形成循环。"""
    from _h3c_collect import gate
    return gate


def collect(days=30, sources=None, errors=None):
    """返回 (rows, sources, errors)，与 _h3c_collect 的 collect_* 同签名。"""
    sources = sources if sources is not None else []
    errors = errors if errors is not None else []

    try:
        import _reddit_search as RD
    except Exception as e:
        errors.append({"site": "Reddit", "err": "模块不可用: %s" % type(e).__name__})
        sources.append({"source": "Reddit", "status": "error", "count": 0})
        return []

    try:
        gate = _gate()
    except Exception as e:
        errors.append({"site": "Reddit", "err": "闸门不可用: %s" % type(e).__name__})
        sources.append({"source": "Reddit", "status": "error", "count": 0})
        return []

    try:
        items, src, err = RD.search(
            SUBS,
            gate=lambda t, b: gate(t, b),
            days=days,
            label="Reddit",
        )
    except Exception as e:
        errors.append({"site": "Reddit", "err": "%s: %s" % (type(e).__name__, str(e)[:120])})
        sources.append({"source": "Reddit", "status": "error", "count": 0})
        return []

    for s in src or []:
        sources.append(s)
    for e in err or []:
        errors.append(e)

    rows = []
    for it in items or []:
        rows.append({
            "platform": "Reddit",
            "site": it.get("site") or "Reddit",
            "channel": "海外",
            "sourceType": "用户",
            "contentKind": "图文",
            "country": it.get("country") or "",
            "language": it.get("language") or "EN",
            "publishedAt": it.get("date") or "",
            "date": it.get("date") or "",
            "title": it.get("title") or "",
            "originalText": it.get("originalText") or "",
            "sourceLink": it.get("url") or "",
            "author": it.get("author") or "",
            "collectMethod": "auto",
            "foundBy": it.get("foundBy") or "",
            # 语义字段一律留空，等人工标注 —— 采集器不判情感
            "sentiment": "",
            "topics": [],
            "dimensions": [],
            "problemPoints": [],
            "summaryCn": "",
            "translation": "",
        })
    return rows


def probe():
    """只探通道可达性，不写候选池。返回 (status, detail)。"""
    import urllib.error
    import urllib.request
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    ua = {"User-Agent": "python:col-monitor:v1.0 (by /u/colmonitor)"}
    checks = [
        ("www  new.rss", "https://www.reddit.com/r/BambuLab/new.rss?limit=5"),
        ("old  new.rss", "https://old.reddit.com/r/BambuLab/new.rss?limit=5"),
        ("json", "https://www.reddit.com/r/BambuLab/new.json?limit=5"),
        ("oauth token", "https://www.reddit.com/api/v1/access_token"),
    ]
    detail = {}
    for name, u in checks:
        try:
            r = op.open(urllib.request.Request(u, headers=ua), timeout=20)
            b = r.read()
            is_xml = b[:80].lstrip().startswith(b"<?xml") or b"<feed" in b[:400]
            detail[name] = {"code": r.status, "bytes": len(b), "rss": is_xml,
                            "final": r.geturl()[:70]}
        except urllib.error.HTTPError as e:
            detail[name] = {"code": e.code}
        except Exception as e:
            detail[name] = {"err": type(e).__name__}
    ok = any(v.get("rss") for v in detail.values())
    return ("ok" if ok else "blocked"), detail


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--probe", action="store_true", help="只探通道，不写文件")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args(argv)

    if a.probe:
        st, d = probe()
        print("Reddit 通道: %s" % st)
        for k, v in d.items():
            print("  %-14s %s" % (k, json.dumps(v, ensure_ascii=False)))
        return 0 if st == "ok" else 1

    sources, errors = [], []
    rows = collect(a.days, sources, errors)

    print("Reddit 抓取 %d 条" % len(rows))
    for s in sources:
        print("  %-24s %-8s %s" % (s.get("source"), s.get("status"), s.get("count")))

    if errors:
        print("错误 %d 条（前 3）：" % len(errors))
        for e in errors[:3]:
            print("  ", json.dumps(e, ensure_ascii=False)[:150])

    if not rows:
        print("！0 条产出。Reddit 匿名通道已关闭，需 OAuth 凭据 —— "
              "详见 _col_channels.py。这不是失败，是通道状态。")
        return 0

    old = {}
    if os.path.exists(a.out):
        try:
            with io.open(a.out, encoding="utf-8") as f:
                old = json.load(f)
        except Exception:
            old = {}
    old_rows = old.get("items") or [] if isinstance(old, dict) else []
    seen = {x.get("sourceLink") for x in old_rows}
    merged = list(old_rows) + [r for r in rows if r.get("sourceLink") not in seen]

    payload = {
        "updatedAt": __import__("time").strftime("%Y-%m-%d %H:%M"),
        "sources": sources,
        "errors": errors[:20],
        "items": merged,
    }
    tmp = a.out + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(payload, ensure_ascii=False, indent=1))
    os.replace(tmp, a.out)
    print("写入 %s（累计 %d 条）" % (os.path.basename(a.out), len(merged)))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
