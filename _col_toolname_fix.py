# -*- coding: utf-8 -*-
"""给软件专栏条目补 toolName（具体工具名）字段。

只加字段，**不重跑归一化** —— 重跑会改 originalText，与已翻译的 502+51 条译文错位。

一致性铁律：
  toolName 只在「tool 已定类别」的候选里取值，
  因此「自家工具 337」下面各工具名之和恒等于 337，不会出现一级行与二级明细对不上。
"""
import argparse
import io
import json
import os
import re
from collections import Counter

ROOT = os.path.dirname(os.path.abspath(__file__))
TARGETS = ["_sw_items_norm.json", "_gh_items_sw.json"]

# 顺序敏感：同一类别内取「标题命中优先 → 列表顺序」
SELF_RULES = [
    ("Creality Print",  [r"creality\s*print"]),
    ("Creality Cloud",  [r"creality\s*cloud", r"crealitycloud"]),
    ("Creality Slicer", [r"creality\s*slicer"]),
    ("Creality App",    [r"creality\s*app"]),
    ("Creality Scan",   [r"creality\s*scan"]),
    ("Creality Park",   [r"creality\s*park"]),
    ("Falcon",          [r"\bfalcon\b"]),
    ("CFS 多色系统",     [r"\bcfs\b"]),
    # 放最后：Klipper 是泛固件词，正文里一带而过不该抢走 Creality Print 的主体地位
    ("Klipper 固件",     [r"\bklipper\b"]),
]
# 仓库是最硬的信号：CrealityPrint 仓库的 issue 不提产品名也一定是在说 Creality Print
REPO_FALLBACK = {
    "CrealityOfficial/CrealityPrint": "Creality Print",
    "CrealityOfficial/K1_Series_Klipper": "Klipper 固件",
    "CrealityOfficial/K2_Series_Klipper": "Klipper 固件",
}
COMP_RULES = [
    ("OrcaSlicer",      [r"orca\s*slicer", r"\borca\b"]),
    ("Bambu Studio",    [r"bambu\s*studio", r"\bbambu\b"]),
    ("PrusaSlicer",     [r"prusa\s*slicer"]),
    ("Cura",            [r"\bcura\b"]),
    ("SuperSlicer",     [r"super\s*slicer"]),
    ("Slic3r",          [r"slic3r"]),
    ("Simplify3D",      [r"simplify3d"]),
    ("OctoPrint",       [r"octoprint"]),
    ("Fluidd",          [r"fluidd"]),
    ("Mainsail",        [r"mainsail"]),
    ("KAMP",            [r"\bkamp\b"]),
    ("IdeaMaker",       [r"idea\s*maker"]),
]
FALLBACK = {"self": "其他自家工具", "competitor": "其他竞品工具"}

# 工具 → 功能类型（用户 2026-10-20：取消「自家/竞品」一级分类，改按功能类型分）。
# 归属（self/competitor）保留在 tool 字段，只在二级用色点区分，不再当一级维度。
TOOL_TYPE = {
    # 切片软件
    "Creality Print": "slice", "Creality Slicer": "slice", "OrcaSlicer": "slice",
    "Cura": "slice", "PrusaSlicer": "slice", "Bambu Studio": "slice",
    "SuperSlicer": "slice", "Slic3r": "slice", "Simplify3D": "slice",
    # 建模软件
    "FreeCAD": "model", "Fusion 360": "model", "Blender": "model",
    "TinkerCAD": "model", "Onshape": "model", "SolidWorks": "model", "Shapr3D": "model",
    # 云平台 / 手机端
    "Creality Cloud": "cloud", "Creality App": "cloud",
    # 多色与耗材
    "CFS 多色系统": "multicolor",
    # 固件与主机控制
    "Klipper 固件": "firmware", "Fluidd": "firmware", "OctoPrint": "firmware",
    "Mainsail": "firmware", "KAMP": "firmware",
    # 激光 / 扫描等配套硬件工具
    "Falcon": "hardware", "Creality Scan": "hardware",
    # 兜底项：2026-10-27 多源接入后新增工具名，漏映射会让「有工具名但无功能类型」自检失败。
    # IdeaMaker 是切片器；两个「其他」是 pick() 的 FALLBACK，按竞品/自家工具的构成看也以切片器为主 ——
    # 归 slice 比归「未提具体工具」更接近事实（后者会让它们从工具×环节矩阵里消失）。
    "IdeaMaker": "slice", "其他竞品工具": "slice", "其他自家工具": "slice",
}
TYPE_ORDER = ["slice", "model", "cloud", "multicolor", "firmware", "hardware"]
TYPE_NAME = {"slice": "切片软件", "model": "建模软件", "cloud": "云平台 / App",
             "multicolor": "多色与耗材", "firmware": "固件与主机控制",
             "hardware": "激光 / 扫描", "": "未提具体工具"}


def pick(it):
    cat = it.get("tool") or ""
    if not cat:
        return ""
    rules = SELF_RULES if cat == "self" else COMP_RULES
    title = it.get("title") or ""
    body = title + " " + (it.get("originalText") or "")

    # ① 标题明写哪个工具，就以哪个为主体（标题是作者自述的主语）
    for name, pats in rules:
        if any(re.search(p, title, re.I) for p in pats):
            return name
    # ② 标题没写，正文里出现次数最多的
    best, bestn = "", 0
    for name, pats in rules:
        n = sum(len(re.findall(p, body, re.I)) for p in pats)
        if n > bestn:
            bestn, best = n, name
    if best:
        return best
    # ③ 正文也没提 → 用仓库归属兜底（GitHub 条目）
    repo = it.get("ghRepo") or ""
    if repo in REPO_FALLBACK:
        return REPO_FALLBACK[repo]
    return FALLBACK[cat]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    for fn in TARGETS:
        p = os.path.join(ROOT, fn)
        if not os.path.exists(p):
            print("跳过 %s（不存在）" % fn)
            continue
        data = json.load(io.open(p, encoding="utf-8"))
        for it in data:
            it["toolName"] = pick(it)
            it["toolType"] = TOOL_TYPE.get(it["toolName"], "")

        print("=== %s（%d 条）===" % (fn, len(data)))
        # 一致性自检：类别总数 == 该类内各工具名之和
        okall = True
        for cat, label in (("self", "自家工具"), ("competitor", "竞品工具")):
            sub = [x for x in data if x.get("tool") == cat]
            if not sub:
                continue
            c = Counter(x["toolName"] for x in sub)
            print("  %s %d 条：" % (label, len(sub)))
            for k, v in c.most_common():
                print("     %-18s %4d" % (k, v))
            if sum(c.values()) != len(sub):
                okall = False
                print("     ✗ 二级明细之和与一级行不一致！")
        empty = sum(1 for x in data if x.get("tool") and not x.get("toolName"))
        if empty:
            okall = False
            print("  ✗ 有 %d 条定了类别但没有工具名" % empty)

        # 功能类型自检：每条有工具名的都必须归到一个类型，且类型之和 == 总数
        lost = [x for x in data if x.get("toolName") and not x.get("toolType")]
        if lost:
            okall = False
            print("  ✗ %d 条有工具名但没归到功能类型：%s"
                  % (len(lost), sorted({x["toolName"] for x in lost})))
        tc = Counter(x["toolType"] for x in data)
        print("  按功能类型：")
        for t in TYPE_ORDER + [""]:
            if tc.get(t):
                print("     %-14s %4d" % (TYPE_NAME[t], tc[t]))
        if sum(tc.values()) != len(data):
            okall = False
            print("  ✗ 类型之和 %d ≠ 总数 %d" % (sum(tc.values()), len(data)))
        print("  一致性：%s" % ("OK" if okall else "FAIL"))

        if not a.dry_run:
            io.open(p, "w", encoding="utf-8").write(
                json.dumps(data, ensure_ascii=False, indent=1))
            print("  已写回")
    print("\n（dry-run，未写盘）" if a.dry_run else "\n全部完成")


if __name__ == "__main__":
    main()
