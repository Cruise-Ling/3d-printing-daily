# -*- coding: utf-8 -*-
"""收拾 GitHub issue 的表单骨架（不重翻，原文与译文同算法处理）

问题：CrealityPrint 的 issue 用 GitHub 表单模板提交，正文长这样 ——
    ### Is there an existing issue for this problem?
    ### CrealityPrint Version
    7.2
    ### Operating System (OS)
    Windows
    ...
直接展示会有两个毛病：① 一堆空 section（用户没填的字段）占版面；
② `###` 这种 markdown 标题在卡片里不渲染，变成裸井号。

处理：`### X` → `【X】`，空 section（无内容 / 只有 _No response_ / _无回复_）整段丢弃。
原文与译文用同一算法 → 两边保留的 section 数一致，不会错位。

用法：python _col_beautify_issue.py [--dry-run]
"""
import argparse
import io
import json
import re

GH = "_gh_items_sw.json"
TR = "_col_tr_github.json"

RE_SEC = re.compile(r"^#{2,4}\s*(.+?)\s*$")
RE_EMPTY = re.compile(r"^_?(No response|无回复|无响应|无|None)_?\.?$", re.I)
RE_IMG = re.compile(r"<img[^>]*>?", re.I)
RE_HTML = re.compile(r"<[^>]{1,60}>")


def beautify(text):
    text = RE_IMG.sub(" ", text or "")
    text = RE_HTML.sub(" ", text)
    lines = text.split("\n")

    secs, cur_name, cur_body = [], "", []
    for ln in lines:
        m = RE_SEC.match(ln)
        if m:
            secs.append((cur_name, cur_body))
            cur_name, cur_body = m.group(1), []
        else:
            cur_body.append(ln)
    secs.append((cur_name, cur_body))

    out = []
    for name, body in secs:
        body = [x.rstrip() for x in body]
        body = [x for x in body if x.strip() and not RE_EMPTY.match(x.strip())]
        if name and not body:
            continue                      # 用户没填的空 section，整段丢掉
        if name:
            out.append("【%s】" % name)
        out.extend(body)
    s = "\n".join(out)
    s = re.sub(r"\n{3,}", "\n\n", s).strip()
    return s


def count_sec(s):
    return len(re.findall(r"^【", s, re.M))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    items = json.load(io.open(GH, encoding="utf-8"))
    tr = json.load(io.open(TR, encoding="utf-8"))

    before = sum(len(x["originalText"]) for x in items)
    drop = 0
    for x in items:
        new = beautify(x["originalText"])
        if new != x["originalText"]:
            drop += 1
        x["originalText"] = new
        if len(new) < 40:
            x["grade"] = "泛讨论"          # 清完只剩骨架 = 用户没写内容
    after = sum(len(x["originalText"]) for x in items)

    tr_drop, mism = 0, []
    for uid, v in tr.items():
        nb = beautify(v["b"])
        if nb != v["b"]:
            tr_drop += 1
        v["b"] = nb
        v["t"] = (v.get("t") or "").strip()

    by_uid = {x["uid"]: x for x in items}
    for uid, v in tr.items():
        it = by_uid.get(uid)
        if not it:
            continue
        a1, a2 = count_sec(it["originalText"]), count_sec(v["b"])
        if a1 != a2:
            mism.append((uid, a1, a2))

    print("原文改动 %d / %d 条  %d → %d 字符（-%d）" % (
        drop, len(items), before, after, before - after))
    print("译文改动 %d / %d 条" % (tr_drop, len(tr)))
    print("原文/译文 section 数不一致: %d 条" % len(mism))
    for m in mism[:8]:
        print("  %s  原文 %d / 译文 %d" % m)

    if a.dry_run:
        print("\n（dry-run，未写盘）")
        for x in items[:2]:
            print("\n== " + x["uid"])
            print(x["originalText"][:300])
        return

    io.open(GH, "w", encoding="utf-8").write(json.dumps(items, ensure_ascii=False, indent=1))
    io.open(TR, "w", encoding="utf-8").write(json.dumps(tr, ensure_ascii=False, indent=0))
    print("\n已写回 %s + %s" % (GH, TR))


if __name__ == "__main__":
    main()
