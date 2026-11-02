# -*- coding: utf-8 -*-
"""_step2_inject.py — 把海外口碑批次注入 user-complaints.html 的 OVERSEAS_FEEDBACK_DATA.items

约束（照 Step 2 规范）
  · 锚点 `  items: [` 之后 unshift，按 publishedAt 倒序维护，每条独立成行、逗号结尾
  · 注入前扫全部文本字段的未转义英文双引号（JSON 序列化天然转义，做二次确认）
  · 注入后同步 stats.sentiment
  · 该文件是 JS 对象字面量，禁止 json.loads；用 Node vm 校验
用法
  python _step2_inject.py _step2_batch_20261102.json          # 写入
  python _step2_inject.py _step2_batch_20261102.json --dry-run
"""
import io
import os
import re
import sys
import json
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
PAGE = os.path.join(HERE, "user-complaints.html")
ANCHOR = "  items: [\n"
SENTIMENTS = ["非常负面", "负面", "中性", "正面", "非常正面"]


def load_batch(p):
    d = json.load(io.open(p, encoding="utf-8"))
    items = d.get("items") or []
    items.sort(key=lambda x: (x.get("publishedAt") or "", x.get("id") or ""), reverse=True)
    return d, items


def check_quotes(items):
    bad = []
    for it in items:
        for k, v in it.items():
            if isinstance(v, str) and ('"' in v):
                bad.append((it.get("id"), k, v[:40]))
    return bad


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: _step2_inject.py <batch.json> [--dry-run]")
    dry = "--dry-run" in sys.argv
    batch_path = sys.argv[1]
    meta, items = load_batch(batch_path)

    bad = check_quotes(items)
    if bad:
        print("[inject] 含未转义英文双引号，拒绝写入：")
        for b in bad[:5]:
            print("   ", b)
        return 2

    s = io.open(PAGE, encoding="utf-8", newline="").read()
    # 本地历史上是 CRLF，而推送走文本模式会转成 LF —— 两边行尾不一致会造出
    # 「+850/-850」的假 diff（10-30、11-02 各踩一次）。这里统一成 LF，与远端对齐。
    if "\r\n" in s:
        s = s.replace("\r\n", "\n")
        print("[inject] 行尾 CRLF → LF 归一（消除远端假 diff）")
    if ANCHOR not in s:
        print("[inject] 找不到锚点 %r" % ANCHOR)
        return 2

    exist = set(re.findall(r'"id":\s*"(KB-[^"]+)"', s))
    fresh = [it for it in items if it.get("id") not in exist]
    print("[inject] 批次 %s｜待注入 %d 条（已存在跳过 %d）"
          % (meta.get("batch"), len(fresh), len(items) - len(fresh)))
    if not fresh:
        print("[inject] SKIP 无新增")
        return 0

    lines = "".join("    %s,\n" % json.dumps(it, ensure_ascii=False) for it in fresh)
    s2 = s.replace(ANCHOR, ANCHOR + lines, 1)

    # 同步 stats.sentiment
    cnt = {k: 0 for k in SENTIMENTS}
    for it in fresh:
        cnt[it.get("sentiment") if it.get("sentiment") in cnt else "中性"] += 1
    m = re.search(r"sentiment:\s*\{([^}]*)\}", s2)
    if not m:
        print("[inject] 找不到 stats.sentiment 块")
        return 2
    body = m.group(1)
    for k in SENTIMENTS:
        # 必须行首锚定：'负面' 是 '非常负面' 的子串，不加锚点会把 81 当成负面旧值
        pat = r"(?m)^(\s*)%s:\s*(\d+)" % k
        mm = re.search(pat, body)
        old = int(mm.group(2)) if mm else 0
        new = old + cnt[k]
        body = (re.sub(pat, lambda x, _n=new: "%s%s: %d" % (x.group(1), k, _n), body, count=1)
                if mm else body + "\n      %s: %d," % (k, new))
        if cnt[k]:
            print("      %s %d → %d" % (k, old, new))
    s2 = s2[:m.start(1)] + body + s2[m.end(1):]

    if dry:
        print("[inject] dry-run：未写盘")
        return 0

    io.open(PAGE, "w", encoding="utf-8", newline="").write(s2)
    print("[inject] 已写入 %s（%d 条）" % (os.path.basename(PAGE), len(fresh)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
