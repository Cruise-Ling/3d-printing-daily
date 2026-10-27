# -*- coding: utf-8 -*-
"""
3D 打印软件专栏 · 采集器
=============================================================================
数据源（实测可用）：
  · Creality 官方论坛 Software 板块  /c/creality-slicingsoftware/10.json  至少 17 页
  · 标签端点 tag/{crealityprint,slicingsoftware,bug-report,firmware,feature-need}.json
  · 帖子正文 /t/{slug}/{id}.json  -> post_stream.posts[].cooked
  · 外部信源（2026-10-27 起）：Reddit / B站 / YouTube / 什么值得买
    —— 专栏定位是「全行业 3D 打印软件」，只采自家论坛撑不起这个定位。
    见 _col_sw_external.py；默认采外部源，--no-ext 可跳过（调试用）。

规则全部来自 _sw_rules.py（唯一事实来源），本文件不另写判定逻辑。

用法：
    python _col_collect_sw.py                # 默认 12 页板块 + 5 个标签
    python _col_collect_sw.py --pages 20     # 更深翻页
    python _col_collect_sw.py --no-body      # 只取标题，不拉正文（快速盘点）
"""

import argparse
import hashlib
import html as _html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _sw_rules as R
import _col_sw_external as EXT

HOST = "https://forum.creality.com"
SW_CAT = "/c/creality-slicingsoftware/10.json"
SW_TAGS = ["crealityprint", "slicingsoftware", "bug-report", "firmware", "feature-need"]
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
OUT = "_sw_items.json"

_RATE = 0.35          # 每请求最小间隔（线程内）
_WORKERS = 4


def _strip_html(s):
    s = re.sub(r"<br\s*/?>", "\n", s or "")
    s = re.sub(r"</p>", "\n", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = _html.unescape(s)
    s = re.sub(r"[ \t\u00a0]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def http_json(url, timeout=25, retries=2):
    last = None
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA, "Accept": "application/json",
                "Accept-Language": "en-US,en;q=0.9",
            })
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception as e:
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


def guess_lang(text):
    t = text or ""
    if re.search(r"[\u3040-\u30ff]", t):
        return "JA"
    if re.search(r"[\uac00-\ud7af]", t):
        return "KO"
    if re.search(r"[\u4e00-\u9fff]", t):
        return "ZH"
    if re.search(r"[\u0400-\u04ff]", t):
        return "RU"
    if re.search(r"[äöüß]", t):
        return "DE"
    if re.search(r"[éèêàç]", t):
        return "FR"
    if re.search(r"[\u0600-\u06ff]", t):
        return "AR"
    return "EN"


def uid_of(url, title):
    key = re.sub(r"\s+", " ", (url or "")).strip() + "|" + re.sub(r"\s+", " ", (title or "")).strip()[:200]
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# 主题列表
# ---------------------------------------------------------------------------
def fetch_topic_list(pages, errors):
    """板块翻页 + 标签端点，返回 tid -> {topic 元信息, in_cat}"""
    seen = {}
    for pg in range(1, pages + 1):
        url = "%s%s?page=%d" % (HOST, SW_CAT, pg)
        try:
            j = http_json(url)
        except Exception as e:
            errors.append({"url": url, "err": str(e)[:160]})
            break
        ts = ((j.get("topic_list") or {}).get("topics") or [])
        if not ts:
            break
        for t in ts:
            tid = t.get("id")
            if not tid:
                continue
            if tid not in seen:
                seen[tid] = {"t": t, "in_cat": True}
        time.sleep(0.5)
        print("  board page %-2d -> %d topics (cum %d)" % (pg, len(ts), len(seen)))

    for tg in SW_TAGS:
        url = "%s/tag/%s.json" % (HOST, tg)
        try:
            j = http_json(url)
        except Exception as e:
            errors.append({"url": url, "err": str(e)[:160]})
            continue
        ts = ((j.get("topic_list") or {}).get("topics") or [])
        for t in ts:
            tid = t.get("id")
            if not tid:
                continue
            if tid in seen:
                seen[tid].setdefault("tags_extra", set()).add(tg)
            else:
                seen[tid] = {"t": t, "in_cat": False, "tags_extra": {tg}}
        print("  tag %-16s -> %d topics (cum %d)" % (tg, len(ts), len(seen)))
        time.sleep(0.5)
    return seen


def fetch_body(tid, slug):
    url = "%s/t/%s/%d.json" % (HOST, slug, tid)
    j = http_json(url, retries=2)
    posts = ((j.get("post_stream") or {}).get("posts") or [])
    texts = []
    for p in posts[:3]:
        txt = _strip_html(p.get("cooked") or "")
        if txt:
            texts.append(txt)
    return {
        "body": "\n\n".join(texts),
        "views": j.get("views") or 0,
        "like_count": j.get("like_count") or 0,
        "posts_count": j.get("posts_count") or 0,
        "tags": j.get("tags") or [],
        "created_at": (j.get("created_at") or "")[:10],
        "last_posted": (j.get("last_posted_at") or "")[:10],
    }


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=12, help="板块翻页数，每页 30")
    ap.add_argument("--no-body", action="store_true", help="不拉正文")
    ap.add_argument("--limit", type=int, default=0, help="只处理前 N 个主题（调试）")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--no-ext", action="store_true", help="跳过外部信源（只采官方论坛）")
    ap.add_argument("--ext-days", type=int, default=180, help="外部信源时间窗口（天）")
    args = ap.parse_args()

    errors = []
    print("[1/3] 拉取主题列表 ...")
    pool = fetch_topic_list(args.pages, errors)
    print("  合计主题: %d" % len(pool))

    tids = list(pool.keys())
    if args.limit:
        tids = tids[: args.limit]

    print("[2/3] 拉取正文 (%d 个主题, %d 线程) ..." % (len(tids), _WORKERS))
    bodies = {}
    done = 0
    if not args.no_body:
        def work(tid):
            t = pool[tid]["t"]
            time.sleep(_RATE)
            return tid, fetch_body(tid, t.get("slug") or ("t%d" % tid))

        with ThreadPoolExecutor(max_workers=_WORKERS) as ex:
            futs = {ex.submit(work, tid): tid for tid in tids}
            for f in as_completed(futs):
                tid = futs[f]
                try:
                    k, v = f.result()
                    bodies[k] = v
                except Exception as e:
                    errors.append({"topic": tid, "err": str(e)[:160]})
                done += 1
                if done % 25 == 0 or done == len(tids):
                    print("  %d/%d" % (done, len(tids)))

    print("[3/3] 归类 ...")
    items, dropped = [], {"off-topic": 0, "excluded": 0}
    for tid in tids:
        meta = pool[tid]
        t = meta["t"]
        title = _html.unescape((t.get("title") or "")).strip()
        if not title:
            continue
        b = bodies.get(tid, {})
        tags = list(set((t.get("tags") or []) + list(b.get("tags") or []) +
                        list(meta.get("tags_extra") or [])))
        body = b.get("body") or ""
        # 标题太短且无正文 -> 拿描述兜底
        if not body and t.get("excerpt"):
            body = _strip_html(t.get("excerpt"))

        blob = title + " " + body
        ok, reason = R.is_software_related(title, body, tags, in_sw_category=meta["in_cat"])
        if not ok:
            dropped[reason] = dropped.get(reason, 0) + 1
            continue

        product = R.classify_product(blob, tags)
        if not product:
            # Software 板块里的兜底：默认归 Creality Print（该板块 90% 是切片问题）
            product = "print"
        version = R.extract_version(title, product, body)
        problem = R.classify_problem(title, body)
        model = R.extract_model(blob, tags)
        grade = R.grade(title, body, problem, reason)
        if grade == R.GRADE_VOID:
            dropped["grade-void"] = dropped.get("grade-void", 0) + 1
            continue
        if grade == R.GRADE_GENERAL:
            problem = ""          # 泛讨论不进问题榜

        pub = (b.get("created_at") or (t.get("created_at") or "")[:10])
        url = "%s/t/%s/%d" % (HOST, t.get("slug") or ("t%d" % tid), tid)
        items.append({
            "uid": uid_of(url, title),
            "topicId": tid,
            "platform": "Creality 官方论坛",
            "site": "Creality 官方论坛",
            "channel": "官方论坛",
            "country": "US",
            "language": guess_lang(title + " " + body),
            "date": pub,
            "lastActive": b.get("last_posted") or pub,
            "title": title,
            "originalText": body or title,
            "url": url,
            "productLine": product,
            "version": version,
            "problemType": problem,
            "model": model,
            "grade": grade,
            "replyCount": b.get("posts_count") or t.get("posts_count") or 0,
            "views": b.get("views") or t.get("views") or 0,
            "likeCount": b.get("like_count") or t.get("like_count") or 0,
            "tags": tags,
            "relReason": reason,
            "sourceType": "用户",
        })

    # ---------------- 外部信源（全行业） ----------------
    ext_stats = {"enabled": not args.no_ext, "items": 0, "sources": [], "errors": []}
    if not args.no_ext:
        print("[4/4] 采外部信源（Reddit / B站 / YouTube / 什么值得买）...")
        try:
            ext_items, ext_src, ext_err = EXT.collect_all(days=args.ext_days)
            items += ext_items
            errors += ext_err
            ext_stats.update({"items": len(ext_items), "sources": ext_src,
                              "errors": ext_err[:20]})
        except Exception as e:
            # 外部源整体失败不阻断论坛数据 —— 论坛是主源，缺了它这次采集就没意义
            print("  外部源整体失败，跳过: %s: %s" % (type(e).__name__, str(e)[:120]))
            ext_stats["errors"] = [{"err": "%s: %s" % (type(e).__name__, str(e)[:120])}]
    else:
        print("[4/4] 跳过外部信源（--no-ext）")

    # uid 唯一性断言（K3 踩过：一个 URL 一条内容不是普适假设）
    seen_uid = {}
    dups = 0
    for it in items:
        if it["uid"] in seen_uid:
            dups += 1
            it["uid"] = it["uid"][:12] + "%04x" % dups
        seen_uid[it["uid"]] = 1

    items.sort(key=lambda x: (x["date"] or ""), reverse=True)
    payload = {
        "updatedAt": time.strftime("%Y-%m-%d %H:%M"),
        "items": items,
        "stats": {
            "topics": len(tids),
            "kept": len(items),
            "dropped": dropped,
            "dupUid": dups,
            "errors": len(errors),
            "external": ext_stats,
        },
        "errors": errors[:40],
    }
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)

    # 盘点
    from collections import Counter
    print("\n=== 结果 ===")
    print("保留 %d 条 / 主题 %d / 丢弃 %s / 错误 %d" % (len(items), len(tids), dropped, len(errors)))
    print("产品线:", dict(Counter(x.get("productLine") or "(空)" for x in items)))
    print("问题类:", dict(Counter(x.get("problemType") or "(无)" for x in items)))
    # 外部信源不产出 version 字段，必须用 get —— 否则多源采集后收盘统计就 KeyError
    print("版本  :", dict(Counter(x.get("version") or "(未标注)" for x in items).most_common(10)))
    print("审核  :", dict(Counter(x.get("grade") or "(空)" for x in items)))
    print("机型  :", dict(Counter(x.get("model") or "(空)" for x in items).most_common(8)))
    print("平台  :", dict(Counter(x.get("platform") or "?" for x in items)))
    print("信源类型:", dict(Counter(x.get("sourceType") or "?" for x in items)))
    print("-> %s" % args.out)


if __name__ == "__main__":
    main()
