# -*- coding: utf-8 -*-
"""_k3_sort_today.py — 把本次新注入的条目按 publishedAt 倒序重排（注入脚本只在块首 unshift，不保证块内顺序）"""
import io
import re
import sys

PAGE = "creality-k3.html"
TAG = sys.argv[1] if len(sys.argv) > 1 else "K3-20261102-"

s = io.open(PAGE, encoding="utf-8", newline="").read()
nl = "\r\n" if "\r\n" in s else "\n"
lines = s.split(nl)

idx = [i for i, l in enumerate(lines) if l.lstrip().startswith('{id:"%s' % TAG)]
if not idx:
    print("[sort] 未找到 %s 条目" % TAG)
    raise SystemExit(1)
contiguous = idx == list(range(idx[0], idx[0] + len(idx)))
print("[sort] 命中 %d 行，连续块=%s" % (len(idx), contiguous))

blk = [lines[i] for i in idx]


def pub(l):
    m = re.search(r'publishedAt:"([^"]+)"', l)
    return m.group(1) if m else ""


blk.sort(key=lambda l: (pub(l), l), reverse=True)

# 重排后按新位置重编 id（001..N），否则页面上会出现 004/008/001 这种乱序 id。
for n, l in enumerate(blk, 1):
    blk[n - 1] = re.sub(r'id:"[^"]*"', 'id:"%s%03d"' % (TAG, n), l, count=1)

for i, l in zip(idx, blk):
    lines[i] = l
io.open(PAGE, "w", encoding="utf-8", newline="").write(nl.join(lines))

print("[sort] 已按 publishedAt 倒序重排：")
for l in blk:
    print("   ", re.search(r'id:"([^"]+)"', l).group(1), pub(l))
