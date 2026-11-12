# -*- coding: utf-8 -*-
"""光固化专栏生成器：_resin_items.json + resin_tpl.html -> resin-line.html

用法：python _build_resin.py

自包含单文件，数据内联，零外部依赖 / 零 CDN（沿用 K3 与 H3C 的形态）。
不修改 K3 或任何现网页面；导航从共享 _nav.html 渲染，但只写进本页。
"""
import datetime as dt
import json
import os
import re

BASE = os.path.dirname(os.path.abspath(__file__))


def read(fn):
    with open(os.path.join(BASE, fn), encoding="utf-8") as f:
        return f.read()


def write(fn, s):
    with open(os.path.join(BASE, fn), "w", encoding="utf-8", newline="\n") as f:
        f.write(s)


def jcount(fn):
    p = os.path.join(BASE, fn)
    if not os.path.exists(p):
        return 0
    try:
        d = json.load(open(p, encoding="utf-8"))
        return len(d["items"]) if isinstance(d, dict) else len(d)
    except Exception:
        return 0


def counts():
    c = {"K3": 0, "MBOX": 0, "SW": 0, "FC": 0, "H3C": 0, "RESIN": 0}
    c["K3"] = len(re.findall(r'\{id:"K3-', read("creality-k3.html"))) if os.path.exists(os.path.join(BASE, "creality-k3.html")) else 0
    c["H3C"] = len(re.findall(r'"id":"H3C-', read("bambu-h3c.html"))) if os.path.exists(os.path.join(BASE, "bambu-h3c.html")) else 0
    c["MBOX"] = jcount("_mbox_items.json")
    c["SW"] = jcount("_sw_items_norm.json")
    c["FC"] = jcount("_fc_items_norm.json")
    c["RESIN"] = jcount("_resin_items.json")
    return c


def render_nav():
    nav = read("_nav.html")
    c = counts()
    for k, v in c.items():
        nav = nav.replace("__C_%s__" % k, str(v))
        nav = nav.replace("__ON_%s__" % k, "active" if k == "RESIN" else "")
    return nav


def main():
    data = json.load(open(os.path.join(BASE, "_resin_items.json"), encoding="utf-8"))
    tpl = read("resin_tpl.html")
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    # 防止正文里的 </script> 提前闭合脚本块；同时处理 JS 行分隔符
    payload = payload.replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    html = tpl.replace("__RESIN_DATA__", payload).replace("__RESIN_NAV__", render_nav())
    if "__RESIN_DATA__" in html or "__RESIN_NAV__" in html:
        raise SystemExit("模板占位符未全部替换")
    write("resin-line.html", html)

    dm = data.get("meta") or {}
    meta = {"date": dt.date.today().isoformat(),
            "generatedAt": dt.datetime.now().isoformat(timespec="seconds"),
            "fetchedAt": dm.get("fetchedAt"),
            "updatedDate": dm.get("updatedDate") or dt.date.today().isoformat(),
            "deltaToday": dm.get("deltaToday", 0),
            "count": len(data["items"]),
            "page": "resin-line.html"}
    write("_resin_items.json.meta.json", json.dumps(meta, ensure_ascii=False, indent=2))

    print("[BUILD] resin-line.html | %d items | %.1f KB | nav counts=%s"
          % (len(data["items"]), os.path.getsize(os.path.join(BASE, "resin-line.html")) / 1024, counts()))


if __name__ == "__main__":
    main()
