# -*- coding: utf-8 -*-
"""光固化口碑 · 注入器（标注 -> _resin_items.json + CSV）

用法：python _resin_inject.py

纪律：
  1. uid 按发布日连续分配并持久化 _resin_uid_map.json，重跑不换号
  2. 合并全部候选池（回填 + 每日增量），按 candKey upsert，绝不重复写入
  3. 问题点按条去重，保证「面板数字 = 点开后明细条数」（H3C 遗留 P0 的教训）
  4. 中文译文 / 摘要从 _resin_tr.json 读取，证据存档从 _resin_evidence/index.json 读取；
     缺一则如实标「译文待补」，绝不编造
  5. meta 补 updatedDate / deltaToday / fetchedAt，供 _col_freshness.js 的 checkResin() 判定
"""
import csv
import datetime as dt
import glob
import json
import os
import re

BASE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(BASE, "resin_config.json"), encoding="utf-8"))
ITEMS = os.path.join(BASE, "_resin_items.json")
UIDMAP = os.path.join(BASE, "_resin_uid_map.json")
CSVOUT = os.path.join(BASE, "_resin_items.csv")
LABELS = os.path.join(BASE, "_resin_labels.json")
TR = os.path.join(BASE, "_resin_tr.json")
EVIDENCE = os.path.join(BASE, "_resin_evidence", "index.json")
LIFECYCLE_HISTORY = os.path.join(BASE, "_resin_lifecycle_history.json")


def brief(text, n=90):
    t = re.sub(r"\s+", " ", text or "").strip()
    return t[:n] + ("…" if len(t) > n else "")


def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        return json.load(open(path, encoding="utf-8"))
    except (ValueError, OSError):
        return default


def all_candidates():
    """合并回填批 + 每日增量批，按 candKey 去重；同时返回最新 fetchedAt 与当日日更条数。"""
    by_key, fetched = {}, None
    daily_today = 0
    tag = dt.date.today().strftime("%Y%m%d")
    for fn in sorted(glob.glob(os.path.join(BASE, "_resin_candidates_*.json"))):
        try:
            d = json.load(open(fn, encoding="utf-8"))
        except (ValueError, OSError):
            continue
        if os.path.basename(fn) == "_resin_candidates_daily_%s.json" % tag:
            daily_today += len(d.get("items", []))
        g = (d.get("meta") or {}).get("generatedAt")
        if g and (fetched is None or g > fetched):
            fetched = g
        for it in d.get("items", []):
            k = it.get("candKey")
            if not k:
                continue
            if k in by_key:
                by_key[k].update({kk: vv for kk, vv in it.items() if vv is not None})
            else:
                by_key[k] = dict(it)
    return list(by_key.values()), fetched, daily_today


def lifecycle_states(items, today, th):
    """按入库批次统计问题点频次，判定 新出现 / 持续存在 / 已改善。

    首版按 crawlDate 批次（不是发布时间）记账，需 >=2 个日更批次才会出现后两态；
    同一天重跑幂等。人工在标注表里显式写「已闭环」的条目不被覆盖。
    """
    hist = load_json(LIFECYCLE_HISTORY, {})
    cur = {}
    for x in items:
        if not x.get("countInVolume"):
            continue
        for p in x.get("problemPoints") or []:
            cur[p] = cur.get(p, 0) + 1
    hist[today] = cur
    hist = dict(sorted(hist.items())[-30:])
    with open(LIFECYCLE_HISTORY, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, indent=2)
    ratio = float((th or {}).get("lifecycleImproveRatio", 0.5))
    prev = [v for k, v in sorted(hist.items()) if k != today]
    out = {}
    for p, n in cur.items():
        earlier = [d.get(p, 0) for d in prev if d.get(p, 0) > 0]
        if not earlier:
            out[p] = "新出现"
        else:
            avg = sum(earlier) / len(earlier)
            out[p] = "持续存在" if n >= avg * ratio else "已改善"
    return out


def main():
    cand_items, fetched, daily_today = all_candidates()
    labels = load_json(LABELS, {})
    if not cand_items or not labels:
        raise SystemExit("缺少候选池或标注表，请先跑 _resin_collect.py 与 _resin_prelabel.py")
    tr = load_json(TR, {})
    ev = load_json(EVIDENCE, {})
    uidmap = load_json(UIDMAP, {})
    existing = load_json(ITEMS, {"meta": {}, "items": []})
    by_key = {x["candKey"]: x for x in existing["items"]}

    seq = {}
    for k, uid in uidmap.items():
        m = re.match(r"RSN-(\d{8})-(\d+)", uid)
        if m:
            seq[m.group(1)] = max(seq.get(m.group(1), 0), int(m.group(2)))

    added = 0
    for c in cand_items:
        k = c["candKey"]
        lab = labels.get(k)
        if not lab:
            continue
        if k in uidmap:
            uid = uidmap[k]
        else:
            d = c["pubDate"].replace("-", "")
            seq[d] = seq.get(d, 0) + 1
            uid = "RSN-%s-%03d" % (d, seq[d])
            uidmap[k] = uid
            added += 1

        is_zh = c.get("language") == "zh"
        t = tr.get(k) or {}
        has_tr = bool(t.get("t") or t.get("b"))
        src = lab.get("labelSource", "rule-prelabel")
        if lab["needsReview"]:
            grade = "待复核"
        elif src.startswith("ai-"):
            grade = "AI语义复核"
        else:
            grade = "人工已确认"

        row = {
            "id": uid,
            "candKey": k,
            "model": c.get("model"),
            "modelName": c.get("modelName"),
            "platform": c.get("platform"),
            "channel": c.get("channel"),
            "channelGroup": c.get("channelGroup"),
            "region": c.get("region"),
            "language": c.get("language"),
            "sourceLink": c.get("sourceLink"),
            "pubDate": c.get("pubDate"),
            "crawlDate": c.get("crawlDate"),
            "title": c.get("title"),
            "originalText": c.get("originalText"),
            "titleCn": t.get("t") or (brief(c.get("title")) if is_zh else None),
            "textCn": t.get("b") or (brief(c.get("originalText")) if is_zh else None),
            "summaryCn": t.get("s") or (brief(c.get("originalText")) if is_zh else None),
            "translationStatus": "无需机翻" if is_zh else ("已补译" if has_tr else "译文待补"),
            "author": c.get("author"),
            "sentiment": lab["sentiment"],
            "confidence": lab["confidence"],
            "problemPoints": list(dict.fromkeys(lab["problemPoints"])),
            "isP0": lab["isP0"],
            "p0Reason": lab["p0Reason"],
            "sourceType": c.get("sourceType"),
            "heat": c.get("heat", 0),
            "replyCount": c.get("replyCount", 0),
            "collectMethod": c.get("collectMethod"),
            "batchKind": c.get("batchKind"),
            "contentKind": c.get("contentKind"),
            "entryKind": lab["entryKind"],
            "countInVolume": lab["countInVolume"],
            "reviewGrade": grade,
            "needsReview": lab["needsReview"],
            "forceReview": lab.get("forceReview", False),
            "labelSource": src,
            "reviewNote": lab.get("reviewNote"),
            "lifecycle": lab.get("lifecycle", "新出现"),
            "isPromo": c.get("isPromo", False),
            "noiseFlags": c.get("noiseFlags", []),
            "competitorMentioned": c.get("competitorMentioned", []),
            "screenshot": ev.get(k),
            "closedState": "待处理",
        }
        by_key[k] = row

    items = sorted(by_key.values(), key=lambda x: (x.get("pubDate") or "", x["id"]))
    today = dt.date.today().isoformat()
    states = lifecycle_states(items, today, CFG.get("thresholds", {}))
    for x in items:
        if x.get("lifecycle") == "已闭环":
            continue
        probs = x.get("problemPoints") or []
        x["lifecycle"] = states.get(probs[0], "新出现") if probs else "新出现"
    models = [{"code": m["code"], "name": m["name"], "tier": m["tier"],
               "onSale": m["onSale"], "confirmed": m["confirmed"]} for m in CFG["models"]]
    gaps = [{"key": c["key"], "name": c["name"], "state": c["state"], "tier": c["tier"], "note": c["note"]}
            for c in CFG["channels"] if c["state"] != "auto"]
    valid = [x for x in items if x["countInVolume"] and not x["isPromo"] and x["sourceType"] not in ("官方", "媒体")]
    review = [x for x in items if x["needsReview"]]

    meta = {
        "column": CFG["columnKey"],
        "line": CFG["line"],
        "version": CFG["version"],
        "generatedAt": dt.datetime.now().isoformat(timespec="seconds"),
        "fetchedAt": fetched,
        "updatedDate": today,
        # 按当日日更批次计数，幂等重跑不会把当天新增抹成 0（uidmap 已存在时 added=0）
        "deltaToday": daily_today if daily_today else added,
        "refDate": today,
        "dataThrough": max((x["pubDate"] for x in items), default=None),
        "totalItems": len(items),
        "validItems": len(valid),
        "needsReviewItems": len(review),
        "models": models,
        "channels": [{"key": c["key"], "name": c["name"], "state": c["state"], "tier": c["tier"]}
                      for c in CFG["channels"]],
        "channelGaps": gaps,
        "thresholds": CFG.get("thresholds", {}),
        "paidAdapters": CFG.get("paidAdapters", []),
        "modelListUnconfirmed": any(not m["confirmed"] for m in CFG["models"]),
        "disclaimer": "情感与问题点为逐条语义复核结果（AI 辅助，非需求方签字），保留改判通道；入库样本 ≠ 全量口碑，禁止外推。",
        "translationNotice": "海外原文保留原文与直链，中文译文与摘要由 _resin_tr.json 提供；缺失条目标「译文待补」，不编造译文。",
        "sampleDisclosure": "主源为 Creality 官方论坛 Discourse 公开帖与 YouTube 公开视频/评论，属问题导向样本，不能代表全渠道口碑水位。",
    }
    with open(ITEMS, "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "items": items}, f, ensure_ascii=False, indent=2)
    with open(UIDMAP, "w", encoding="utf-8") as f:
        json.dump(uidmap, f, ensure_ascii=False, indent=2)

    cols = ["id", "model", "modelName", "platform", "channel", "region", "language", "pubDate",
            "sourceLink", "title", "originalText", "titleCn", "textCn", "summaryCn",
            "translationStatus", "sentiment", "confidence", "problemPoints", "isP0", "sourceType",
            "heat", "replyCount", "collectMethod", "batchKind", "entryKind", "countInVolume",
            "reviewGrade", "needsReview", "labelSource", "lifecycle", "isPromo", "noiseFlags",
            "competitorMentioned", "screenshot"]
    with open(CSVOUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for x in items:
            r = dict(x)
            for k in ("problemPoints", "noiseFlags", "competitorMentioned", "p0Reason"):
                r[k] = "、".join(r.get(k) or [])
            w.writerow(r)

    print("[INJECT] items=%d new_uid=%d valid=%d pending_review=%d | updatedDate=%s deltaToday=%d" %
          (len(items), added, len(valid), len(review), today, meta["deltaToday"]))
    print("[INJECT] %s | %s" % (os.path.basename(ITEMS), os.path.basename(CSVOUT)))


if __name__ == "__main__":
    main()
