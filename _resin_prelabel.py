# -*- coding: utf-8 -*-
"""光固化口碑 · 标注层（规则预标 + 人工改判通道）

用法：python _resin_prelabel.py

输出：
  _resin_labels.json                      标注表（键 = candKey），人工可直接编辑
  _resin_review_inbox_YYYYMMDD.md          待复核清单（可贴飞书）

规则：
  1. 规则预标不等于定论，每条 needsReview=true，页面必须显性标注
  2. 人工把某条 confirmed 改为 true 后，重跑本脚本不会覆盖该条
  3. 有观点判据与 K3 的 classify_entry() 一致：问题点非空 / 情感非中性 / isP0
"""
import datetime as dt
import glob
import json
import os
import re

BASE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(BASE, "resin_config.json"), encoding="utf-8"))
LABELS = os.path.join(BASE, "_resin_labels.json")


def classify(cand):
    text = (cand.get("title", "") + " " + cand.get("originalText", "")).lower()
    lex = CFG["sentimentLexicon"]

    def score(key):
        return sum(1 for w in lex[key] if w.lower() in text)

    sentiment, confidence = "中性", 0.30
    for key, label, conf in (
        ("veryNegative", "非常负面", 0.80),
        ("negative", "负面", 0.60),
        ("veryPositive", "非常正面", 0.80),
        ("positive", "正面", 0.60),
    ):
        if score(key) > 0:
            sentiment, confidence = label, conf
            break
    # 正负同时命中：降为中性并要求人工复核，避免规则误判
    if score("negative") + score("veryNegative") > 0 and score("positive") + score("veryPositive") > 0:
        sentiment, confidence = "中性", 0.20

    # 求助/故障型标题是规则词表的最大误判源（实测 "Prints sticking to FEP and not the
    # Print Plate" 因正文出现 good/love 被判正面）。这类标题一律转中性并强制复核。
    help_pat = re.compile(
        r"how\s+to|\bhelp\b|\bproblem\b|\bissue\b|not\s+working|won'?t|doesn'?t|"
        r"\bfail|stuck|sticking|\berror\b|\bcrash|\bquestion\b|\bnot\b|\bno\b|never|cannot|can'?t|"
        r"\?|？|求助|怎么|为什么|无法|不能|不显示|没|不",
        re.I)
    force_review = bool(help_pat.search(cand.get("title", "")))
    if force_review and sentiment in ("正面", "非常正面"):
        sentiment, confidence = "中性", 0.20

    problems = []
    for p in CFG["problemPoints"]:
        n = sum(1 for k in p["keywords"] if k.lower() in text)
        if n:
            problems.append({"code": p["code"], "name": p["name"], "hits": n})
    problems.sort(key=lambda x: -x["hits"])
    problems = problems[:3]

    p0, p0reason = False, []
    for r in CFG["p0Rules"]:
        if any(k.lower() in text for k in r["keywords"]):
            p0 = True
            p0reason.append(r["name"])

    has_opinion = bool(problems) or sentiment != "中性" or p0
    return {
        "candKey": cand["candKey"],
        "sentiment": sentiment,
        "confidence": confidence,
        "problemPoints": [p["name"] for p in problems],
        "problemDetail": problems,
        "isP0": p0,
        "p0Reason": p0reason,
        "entryKind": "有效" if has_opinion else "动态",
        "countInVolume": has_opinion,
        "lifecycle": "新出现",
        "needsReview": True,
        "forceReview": force_review,
        "confirmed": False,
        "labelSource": "rule-prelabel",
    }


def all_candidates():
    """合并全部候选池（回填 + 每日增量），按 candKey 去重。

    2026-11-12 修复：原实现只读 files[-1]，日更首跑会把历史未确认标注整批冲掉。
    同日多次采集用不同文件名（backfill / daily），所以必须按 candKey 合并而不是按文件。
    """
    by_key = {}
    for fn in sorted(glob.glob(os.path.join(BASE, "_resin_candidates_*.json"))):
        try:
            d = json.load(open(fn, encoding="utf-8"))
        except (ValueError, OSError):
            continue
        for it in d.get("items", []):
            k = it.get("candKey")
            if not k:
                continue
            if k in by_key:
                by_key[k].update({kk: vv for kk, vv in it.items() if vv is not None})
            else:
                by_key[k] = dict(it)
    return list(by_key.values())


def main():
    files = sorted(glob.glob(os.path.join(BASE, "_resin_candidates_*.json")))
    if not files:
        raise SystemExit("未找到候选池，请先跑 _resin_collect.py --backfill")
    cand_items = all_candidates()
    old = json.load(open(LABELS, encoding="utf-8")) if os.path.exists(LABELS) else {}

    out, changed, kept = {}, 0, 0
    for it in cand_items:
        k = it["candKey"]
        if k in old and old[k].get("confirmed"):
            out[k] = old[k]
            kept += 1
        else:
            out[k] = classify(it)
            changed += 1
    with open(LABELS, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    today = dt.date.today()
    inbox = os.path.join(BASE, "_resin_review_inbox_%s.md" % today.strftime("%Y%m%d"))
    pending = [x for x in out.values() if x["needsReview"]]
    lines = [
        "# 光固化专栏 · 待复核清单",
        "",
        "本批共 %d 条，其中待复核 %d 条、人工已确认 %d 条。" % (len(out), len(pending), len(out) - len(pending)),
        "规则预标仅供初筛，情感与问题点必须人工确认或改判后才可作为洞察结论。",
        "编辑 `_resin_labels.json` 对应条目：改完把 `confirmed` 设为 `true`、`needsReview` 设为 `false`，再重跑本脚本与 `_resin_inject.py`。",
        "",
        "# 待复核明细",
        "",
        "| candKey | 标题 | 预标情感 | 预标问题点 | P0 | 置信度 |",
        "|---|---|---|---|---|---|",
    ]
    by_key = {x["candKey"]: x for x in cand_items}
    for x in pending[:200]:
        c = by_key.get(x["candKey"], {})
        lines.append("| %s | %s | %s | %s | %s | %.2f |" % (
            x["candKey"], (c.get("title") or "")[:60].replace("|", "/"),
            x["sentiment"], "、".join(x["problemPoints"]) or "—",
            "是" if x["isP0"] else "否", x["confidence"]))
    lines += ["", "# 规则边界", "",
              "1. 正负词同时命中一律降为「中性」，置信度 0.20，强制人工复核。",
              "2. 问题点最多保留 3 个，按命中词数降序，避免一条内容污染多个面板。",
              "3. 无观点条目自动落「动态 · 不计声量」，与 K3 的 `classify_entry()` 判据一致。",
              "4. 海外原文中文摘要需机翻服务，本期标「译文待补」，不编造译文。", ""]
    with open(inbox, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print("[PRELABEL] %s | total=%d new=%d kept_confirmed=%d pending=%d" %
          (os.path.basename(LABELS), len(out), changed, kept, len(pending)))
    print("[PRELABEL] inbox=%s" % os.path.basename(inbox))


if __name__ == "__main__":
    main()
