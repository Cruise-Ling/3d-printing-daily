# -*- coding: utf-8 -*-
"""_k3_merge_hub.py — 把豆包投喂的 K3 条目并入当日候选池，供 _k3_inject_candidates.py 消费

为什么单独一步：
  豆包料走 `_hub/pending_k3.json`（跨日常驻池），而 K3 注入脚本读的是当日候选池
  `_k3_candidates_YYYYMMDD.json`（采集器产物）。这里做一次格式对齐，不合并语义判定——
  标注仍然只在 _k3_inject_candidates.py 的 LABELS 里写，保持「判定单一来源」。

用法
  python _k3_merge_hub.py                # 全量并入（按 uid 去重）
  python _k3_merge_hub.py --only K3-HUB-01,K3-HUB-02
"""
import os
import io
import sys
import json
import argparse
import datetime
import importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
POOL = os.path.join(HERE, "_hub", "pending_k3.json")
TODAY = datetime.date.today()


def load_engine():
    spec = importlib.util.spec_from_file_location("_eng", os.path.join(HERE, "_k3_feishu_delta.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


ENG = load_engine()


def heat_str(h):
    if isinstance(h, str):
        return h
    if not isinstance(h, dict):
        return ""
    parts = []
    for k, label in (("likes", "赞"), ("comments", "评论"), ("collects", "收藏"),
                     ("views", "播放"), ("reply", "评论")):
        if h.get(k):
            parts.append("%s %s" % (h[k], label))
    return " / ".join(parts) if parts else ""


def to_cand(it):
    plat = (it.get("platform") or "").strip()
    src = (it.get("sourceLink") or it.get("url") or "").strip()
    c = {
        "platform": plat,
        "site": it.get("site") or plat,
        "channel": it.get("channel") or ("国内" if (it.get("country") or "CN") == "CN" else "海外"),
        "country": it.get("country") or "CN",
        "language": it.get("language") or "ZH",
        "sourceType": it.get("sourceType") or "用户",
        "sourceLink": src,
        "publishedAt": (it.get("publishedAt") or "")[:10],
        "titleCn": it.get("title") or "",
        "originalText": it.get("originalText") or "",
        "heat": heat_str(it.get("heat")),
        "collectMethod": "hub",
        "foundBy": "doubao",
        "_author": it.get("author") or "",
        "_sub": "",
        "mirrors": [],
        "_mirrorHosts": [],
        "uid": it.get("uid") or ENG.uid_of(it),
    }
    c["dedupKey"] = ENG.norm_url(src)
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="逗号分隔的标题关键词，只并这些")
    ap.add_argument("--date", default=TODAY.strftime("%Y%m%d"))
    a = ap.parse_args()

    pool_path = os.path.join(HERE, "_k3_candidates_%s.json" % a.date)
    if not os.path.exists(pool_path):
        print("[merge] 候选池不存在: %s" % os.path.basename(pool_path))
        return 2
    if not os.path.exists(POOL):
        print("[merge] 无豆包待并池")
        return 0

    pool = json.load(io.open(pool_path, encoding="utf-8"))
    items = pool.get("items") or pool
    have = {x.get("uid") for x in items} | {ENG.norm_url(x.get("sourceLink") or "") for x in items}

    hub = json.load(io.open(POOL, encoding="utf-8")).get("items", [])
    keys = [k.strip() for k in a.only.split(",") if k.strip()]

    added = 0
    for it in hub:
        title = it.get("title") or ""
        if keys and not any(k in title for k in keys):
            continue
        c = to_cand(it)
        if c["uid"] in have or c["dedupKey"] in have:
            print("  SKIP 已在池中: %s" % title[:40])
            continue
        items.append(c)
        have.add(c["uid"])
        added += 1
        print("  + [%s] %s" % (c["platform"], title[:48]))

    if added:
        pool["items"] = items
        io.open(pool_path, "w", encoding="utf-8").write(
            json.dumps(pool, ensure_ascii=False, indent=1))
    print("[merge] 并入 %d 条 → %s（池内共 %d）" %
          (added, os.path.basename(pool_path), len(items)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
