# -*- coding: utf-8 -*-
"""把 _exp_core.js（+ 各页 ADAPTER）注入三套模板的抽屉位置。

幂等：重复执行结果一致。
用法：python _inject_exp.py
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
CORE = os.path.join(ROOT, "_exp_core.js")
PANEL = os.path.join(ROOT, "_exp_panel.html")
STYLE = os.path.join(ROOT, "_exp_style.css")

TARGETS = [
    ("_col_shell.html", "_exp_adapter_col.js"),
    ("creality-k3.html", "_exp_adapter_k3.js"),
    ("resin_tpl.html", "_exp_adapter_resin.js"),
]

ADAPTER_RE = re.compile(
    r"/\* ================= 适配层 START（每页唯一差异） ================= \*/"
    r".*?"
    r"/\* ================= 适配层 END ================= \*/", re.S)

BLOCK_RE = re.compile(
    r'<aside class="exp-drawer".*?</aside>\s*<script>.*?</script>', re.S)

MARK = "/* EXP_V2 */"


def read(p):
    with io.open(p, encoding="utf-8") as f:
        return f.read()


def write(p, s):
    with io.open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)


def build_core(adapter_path):
    core = read(CORE)
    ad = read(adapter_path).strip()
    block = ("/* ================= 适配层 START（每页唯一差异） ================= */\n"
             + ad + "\n"
             "/* ================= 适配层 END ================= */")
    new, n = ADAPTER_RE.subn(lambda m: block, core)
    if n != 1:
        raise SystemExit("ADAPTER 占位未命中（%d 次）：%s" % (n, adapter_path))
    return new


def main():
    panel = read(PANEL).strip()
    style = read(STYLE).strip()
    for html_name, ad_name in TARGETS:
        p = os.path.join(ROOT, html_name)
        if not os.path.exists(p):
            print("SKIP  %s（不存在）" % html_name)
            continue
        html = read(p)
        before = len(html)
        # 0) 清掉历史重复的样式标记（早期版本会写两次）
        html = re.sub(re.escape(MARK) + r"\s*" + re.escape(MARK), MARK, html)

        # 1) 样式：只在缺失时补，避免重复
        if ".exp-chips{" not in html:
            if "</style>" not in html:
                raise SystemExit("%s 找不到 </style>" % html_name)
            html = html.replace("</style>", style + "\n</style>", 1)
            css_state = "added"
        else:
            css_state = "exists"

        # 2) 抽屉 + 脚本
        core = build_core(os.path.join(ROOT, ad_name))
        block = panel + "\n<script>\n" + core + "\n</script>"
        html, n = BLOCK_RE.subn(lambda m: block, html)
        if n != 1:
            raise SystemExit("%s 抽屉块命中 %d 次（应为 1）" % (html_name, n))

        write(p, html)
        print("OK    %-22s css=%-6s js=%d->%d chars" % (html_name, css_state, before, len(html)))

    print("\n提示：改完必须重建 H3C 与其余同源页：")
    print("  python _build_column.py && python _build_h3c.py && python _build_resin.py")


if __name__ == "__main__":
    main()
