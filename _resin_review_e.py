# -*- coding: utf-8 -*-
"""光固化 E 批 · AI 逐条语义复核落盘（2026-11-13）

本脚本一次性把「AI 逐条语义判定」写进 _resin_labels.json 与 _resin_tr.json。
判定依据是逐条读标题 + 原文摘录 + 作者，不是规则词表命中；脚本本身不含任何情感词表。

纪律
----
1. problemPoints 只取 resin_config.json 的 12 类受控词表（这里用短码映射），不自造类目；
2. 纯提问 / 纯展示 / 配件商品页 / listicle 榜单 / 联盟带货 → countInVolume=false（动态），不进情感分母；
3. 品牌官方频道（作者名含品牌）→ sourceType=官方，同样不进分母（K3「官方纯营销帖」同纪律）；
4. 超出单机型采样上限（我方 10 / 竞品 5）的条目保留原文，标动态 + 采样说明，不做静默删除；
5. 拿不准的宁可标动态留待下次，不为凑数硬标。

用法：python _resin_review_e.py [--dry-run]
"""
import collections
import datetime as dt
import glob
import json
import os
import re
import sys

import _resin_models as RM

BASE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(BASE, "resin_config.json"), encoding="utf-8"))
LABELS = os.path.join(BASE, "_resin_labels.json")
TR = os.path.join(BASE, "_resin_tr.json")

NAME = {
    "acc": "打印精度与尺寸误差", "exp": "曝光与光源一致性", "flm": "离型膜与料槽寿命",
    "rsn": "树脂适配与气味", "adh": "平台附着力", "scr": "屏幕寿命与坏点",
    "sft": "软件与切片", "pst": "清洗固化配套", "prc": "价格与首发信心",
    "cmp": "竞品对比与定位", "svc": "售后与配件供应", "lgs": "包装与物流",
}
OFFICIAL = re.compile(r"(anycubic|elegoo|phrozen|creality|创想三维|爱乐酷|crealityhalot)", re.I)
CAP_C, CAP_O = 5, 10


# idx: (情感, 问题点短码, 是否计入声量, 复核依据)
# 情感取值：非常负面 / 负面 / 中性 / 正面 / 非常正面
DEC = {
    # ---- B站 / 论坛 / 值得买（国内 + 一手用户）----
    0: ("中性", ["pst"], 0, "清洗固化二合一设备介绍，非整机口碑，无观点表述"),
    1: ("负面", [], 1, "UP 主吐槽光固化吃灰、对新手不友好，属易用性负面；12 类词表无对应用户体验类目，细节写入摘要"),
    2: ("正面", [], 1, "HALOT-ONE 开箱实测，首打微缩模型细节获肯定（B站转载 The Outer Circle 评测）"),
    3: ("正面", [], 0, "作者为 CrealityHalot 官方号，属官方宣传物料，不计声量"),
    4: ("正面", [], 1, "Elegoo Saturn 4 Ultra 16K 评测，评价精度与上手体验良好"),
    5: ("负面", ["adh"], 1, "用户反馈连续多件打印不粘平台、树脂塌陷，属平台附着力失败"),
    6: ("非常负面", ["svc"], 1, "官方渠道购买后无保修无换机、客服两个月未解决、寄来故障机，命中售后拒保 P0"),
    7: ("中性", [], 0, "泛选购指南，主体为 FDM 家用机，光固化仅一段泛述，无具体机型观点"),
    # ---- Anycubic ----
    8: ("中性", ["cmp"], 1, "以 Photon P1 MAX 与在售机型做成型尺寸对比，属竞品横向讨论"),
    9: ("中性", [], 1, "等待数月后到货的开箱记录，情绪偏期待但无明确评价"),
    10: ("中性", [], 0, "405nm 光敏树脂耗材商品页，非整机口碑"),
    11: ("中性", [], 0, "榜单类内容（6 Best 3D Printers），无单一机型立场"),
    12: ("中性", [], 0, "离型膜配件榜单，非整机口碑"),
    13: ("中性", [], 1, "M7 Max 评测，在大尺寸与细节/成本间做权衡，结论中性"),
    14: ("正面", ["prc"], 1, "评测认为 13.6 寸 7K 机型在同等尺寸里更省成本，价格维度正面"),
    15: ("中性", [], 0, "大尺寸机型榜单，无单一机型立场"),
    16: ("中性", [], 0, "榜单类对比，无单一机型立场"),
    17: ("中性", [], 0, "AliExpress 榜单，含联盟导流"),
    18: ("中性", ["cmp"], 1, "K1C（FDM）与 M7 Pro 跨工艺对比，属选型讨论"),
    19: ("中性", ["cmp"], 1, "Mars 5 Ultra 与 M7 Pro 横向对比，结论中性"),
    20: ("正面", [], 1, "意语评测，肯定 14K 精度与打印速度"),
    21: ("中性", [], 0, "新手装机教程，无评价性表述"),
    22: ("中性", [], 0, "按成型体积排名的榜单，无单一机型立场"),
    # ---- Creality YouTube ----
    23: ("中性", [], 0, "Nebula 摄像头配件商品页，非整机口碑"),
    24: ("正面", [], 1, "Halot X1 Neo 预算档高细节打印效果获肯定"),
    25: ("正面", [], 1, "X1 Neo 打印微缩道具质量评价正面"),
    26: ("中性", [], 0, "Ender 3V3 Neo（FDM）内容，光固化误召回"),
    27: ("中性", [], 0, "HALOT-MAGE 原厂 LCD 屏配件商品页"),
    28: ("中性", [], 0, "HALOT-MAGE 原厂 LCD 屏配件商品页（重复条目）"),
    29: ("中性", ["cmp"], 1, "Halot X1 与 Mage S 自家选型对比"),
    30: ("中性", [], 0, "HALOT-MAGE 原厂屏配件商品页"),
    31: ("中性", [], 0, "MAGE / MAGE Pro 黑白屏套件商品页"),
    32: ("中性", [], 1, "Halot Mage 8K 开箱，未给出结论性评价"),
    33: ("中性", [], 1, "MAGE S 高速机型评测，正负兼有，结论中性"),
    34: ("中性", [], 0, "模型成品展示，无机器评价"),
    35: ("中性", [], 0, "14K 精度宣传口吻，接近官方物料，不计声量"),
    36: ("中性", [], 0, "Mage 专用加热模块配件商品页"),
    37: ("中性", [], 0, "MAGE / MAGE Pro 原厂屏套件商品页"),
    38: ("中性", [], 0, "MAGE Pro 成型平台套件商品页"),
    39: ("中性", [], 0, "模型打印与涂装展示，无机器评价"),
    40: ("中性", [], 1, "Mage Pro 评测，以设问方式讨论是否值得，结论中性"),
    41: ("中性", ["cmp"], 1, "Mage Pro 与 Mage S 自家选型对比"),
    42: ("中性", ["sft"], 1, "第三方 NOODL3D 补丁，涉及两段式运动、Wi-Fi 打印与 PC 控制，属软件生态讨论"),
    43: ("中性", [], 0, "FEP 离型膜配件商品页"),
    44: ("正面", [], 1, "用 Halot R6 做 RPG 微缩件并有收益，使用体验正面"),
    45: ("中性", [], 1, "Halot Sky 俄语开箱初印象，未给结论"),
    46: ("负面", ["prc"], 1, "评论认为 1800 欧定价过高、个人买不起，价格维度负面"),
    47: ("中性", [], 0, "X1 Max 开箱与装机教程，无评价性表述"),
    48: ("中性", [], 1, "评论希望出厂即完成校准以便量产，属改进建议，无明确褒贬"),
    49: ("负面", ["flm"], 1, "评论肯定曝光均匀性，但明确批评 NFEP 膜质量（Honte A Creality），按负向问题计"),
    50: ("中性", [], 0, "评论询问清洗固化机与耗材在英国是否上市，纯提问"),
    51: ("中性", [], 0, "评论询问料管与排风管长度，纯提问"),
    52: ("中性", [], 1, "葡语介绍 X1 Max 工业化产能，宣传口吻较强，结论中性"),
    53: ("中性", [], 1, "X1 Max Combo 技术解析与产能评测，结论中性"),
    54: ("中性", [], 0, "新品发布告知，官方物料"),
    # ---- Elegoo ----
    55: ("中性", [], 0, "榜单类内容，无单一机型立场"),
    56: ("中性", [], 0, "Saturn 3/4 系列原厂屏配件商品页"),
    57: ("正面", ["prc"], 1, "Saturn 3 Ultra 评测认为 12K 细节对应 300 美元价位很值"),
    58: ("中性", [], 1, "Mars 5 Ultra 泰米尔语开箱装机，无结论性评价"),
    59: ("中性", ["cmp"], 1, "Mars 5 Ultra 与 Halot-Mage S 横向对比，结论中性"),
    60: ("中性", ["cmp"], 1, "HALOT-X1 Neo 与 Mars 5 Ultra 横向对比"),
    61: ("中性", [], 0, "评论正文为 Amazon 联盟链接清单，属低信号带货"),
    62: ("中性", ["cmp"], 1, "Mars 5 Ultra 与 Photon Mono 4 Ultra 横向对比"),
    63: ("中性", [], 1, "Saturn 4 Ultra 开箱与测试，未给明确结论"),
    64: ("中性", [], 0, "榜单类内容，无单一机型立场"),
    65: ("中性", ["cmp"], 1, "Jupiter 2 与 Saturn 4 Ultra 同品牌选型对比"),
    66: ("中性", ["cmp"], 1, "Jupiter 2 与 Saturn 4 Ultra 成型体积对比"),
    67: ("中性", [], 0, "按细节规格排名的榜单，无单一机型立场"),
    68: ("中性", [], 0, "微缩机型横评榜单，无单一机型立场"),
    69: ("中性", ["cmp"], 1, "Photon P1 与 Saturn 4 Ultra 16K 横向对比"),
    70: ("中性", [], 0, "4.0 寸彩屏配件商品页"),
    71: ("中性", [], 1, "Saturn 4 Ultra 16K 配置综述，未给评价结论"),
    # ---- Phrozen ----
    72: ("正面", [], 1, "Sonic Mighty 12K 评测，认为适合微缩件"),
    73: ("中性", [], 0, "模型成品展示短视频，无机器评价"),
    74: ("中性", [], 0, "年度榜单，无单一机型立场"),
    75: ("中性", [], 1, "Sonic Mighty 8K 评测，以设问讨论是否最优，结论中性"),
    76: ("中性", ["cmp"], 1, "Sonic Mighty 8K 与 Saturn 3 Ultra 横向对比"),
    77: ("中性", ["cmp"], 1, "Sonic Mighty 8K 与 Saturn 4 Ultra 横向对比"),
    78: ("中性", [], 0, "Phrozen 官方调平指南，官方物料"),
    79: ("中性", [], 0, "Phrozen 官方 Z 轴补偿指南，官方物料"),
    80: ("中性", [], 1, "西语评测，讨论大尺寸树脂打印表现，结论中性"),
    81: ("中性", [], 0, "Phrozen 官方分区曝光测试说明，官方物料"),
    82: ("中性", [], 1, "官方频道功能卖点介绍，接近物料，结论中性"),
    83: ("中性", [], 1, "WOL 3D 评测，明确列优缺点，结论中性"),
}

# 中文译文：idx -> (标题中译, 摘要)
TRX = {
    1: ("光固化太容易吃灰：新手不友好，创想 X1 光固化吐槽", "UP 主认为光固化门槛高、耗材与后处理繁琐，机器容易闲置，属于劝退型内容；该条对「易用性」维度有参考价值，但 12 类问题点词表未覆盖易用性，故不计问题点。"),
    2: ("创想三维 HALOT-ONE 开箱实测：首打微缩模型细节惊艳", ""),
    4: ("ELEGOO 爱乐酷 Saturn 4 Ultra 16K 评测：10 寸 12K 家用桌面级", "评测认为实际 12K 屏幕细节出色、打印稳定、界面友好，新手易上手。"),
    5: ("HALOT-LITE 反复重启", "法语帖：最近多次打印不粘平台或整件失败，树脂塌成一团；机器仅成功打印 3 件后开始异常。"),
    6: ("客户服务", "英文帖：官网购买后无保修、不换机，客服两个月未寄出替换机，收到的 Halot X1 本身有故障。"),
    7: ("创想三维 3D 打印机怎么样：选 3D 打印机看这篇就够了", ""),
    8: ("有人问 Photon P1 MAX 的成型体积能否与在售机型相比", ""),
    9: ("等了几个月终于到货：Anycubic 光固化打印机开箱", ""),
    13: ("ANYCUBIC Photon Mono M7 Max 评测：14.7L 大体积与细节、成本的取舍", ""),
    14: ("Anycubic Photon Mono M7 Max 评测：13.6 寸 7K 省钱之选", "评测认为同尺寸下更省成本，细节与速度平衡。"),
    18: ("创想 K1C 与 Anycubic Photon Mono M7 Pro 关键差异对比", ""),
    19: ("Elegoo Mars 5 Ultra 与 Anycubic Photon Mono M7 Pro 对比", ""),
    20: ("ANYCUBIC Photon Mono M7 Pro 评测：14K 精度与高速打印", "意语评测肯定 14K 精度与打印速度。"),
    24: ("预算档高细节树脂打印：创想 Halot X1 Neo", ""),
    25: ("创想 Halot X1 Neo 打印高质量微缩道具", ""),
    29: ("创想 Halot X1 与 Halot Mage S 该买哪个？", ""),
    32: ("开箱：创想 Halot Mage 8K 树脂打印机", ""),
    33: ("创想 HALOT MAGE S 高速树脂打印机评测", ""),
    40: ("创想 Halot Mage Pro 评测：最强 8K 树脂打印机？", ""),
    41: ("创想 Halot Mage Pro 与 Halot Mage S 该买哪个？", ""),
    42: ("NOODL3D HALOT-MAGE PRO 补丁：两段式运动、Wi-Fi 打印与 PC 控制", ""),
    44: ("用创想 Halot R6 做 RPG 微缩模型：桌游副业", ""),
    45: ("创想 Halot Sky 2025 开箱与初印象", ""),
    46: ("太贵了！对 HALOT X1 MAX 的反应", "评论认为 1800 欧元定价过高，个人用户难以承受。"),
    48: ("评论：希望机器出厂即完成校准，便于批量生产", ""),
    49: ("评论：曝光均匀性惊人，但 NFEP 膜质量令人失望", "评论称实测曝光均匀性极佳，甚至超过两台 Saturn 3 Ultra，但批评原厂 NFEP 膜质量。"),
    52: ("桌面上的工业级产能：了解全新创想 Halot-X1 Max", ""),
    53: ("创想 Halot-X1 Max Combo 技术解析与产能表现", ""),
    57: ("ELEGOO Saturn 3 Ultra 评测：300 美元的 12K 细节", "评测认为该价位下 12K 细节表现突出。"),
    58: ("Elegoo Mars 5 Ultra 泰米尔语开箱与装机", ""),
    59: ("Elegoo Mars 5 Ultra 与创想 Halot-Mage S 哪个更好？", ""),
    60: ("创想 HALOT-X1 Neo 与 Mars 5 Ultra 该选哪台？", ""),
    62: ("Elegoo Mars 5 Ultra 与 Anycubic Photon Mono 4 Ultra 对比", ""),
    63: ("树脂 3D 打印机开箱与测试", ""),
    65: ("Elegoo Jupiter 2 与 Saturn 4 Ultra 哪个更好？", ""),
    66: ("Elegoo Jupiter 2 与 Saturn 4 Ultra 对比：成型体积", ""),
    69: ("Anycubic Photon P1 与 Elegoo Saturn 4 Ultra 16K 对比", ""),
    71: ("ELEGOO Saturn 4 Ultra 16K：你需要知道的全部", ""),
    72: ("评测：Phrozen Sonic Mighty 12K，微缩件最佳树脂机？", "评测认为该机型适合微缩模型打印。"),
    75: ("Phrozen Sonic Mighty 8K 评测：最强树脂打印机？", ""),
    76: ("Phrozen Sonic Mighty 8K 与 Elegoo Saturn 3 Ultra 该买哪个？", ""),
    77: ("Phrozen Sonic Mighty 8K 与 Elegoo Saturn 4 Ultra 该买哪个？", ""),
    80: ("Phrozen Sonic Mighty Revo 16K Max：大尺寸树脂打印", ""),
    82: ("你可能不知道但很需要的功能：Phrozen Sonic Mighty Revo 16K", ""),
    83: ("WOL 3D 评测：Phrozen Sonic Mini 8K 优缺点", ""),
}


def load(fn, default):
    if not os.path.exists(fn):
        return default
    try:
        return json.load(open(fn, encoding="utf-8"))
    except (ValueError, OSError):
        return default


def all_candidates():
    by = {}
    for fn in sorted(glob.glob(os.path.join(BASE, "_resin_candidates_*.json"))):
        try:
            d = json.load(open(fn, encoding="utf-8"))
        except (ValueError, OSError):
            continue
        for it in d.get("items", []):
            k = it.get("candKey")
            if not k:
                continue
            if k in by:
                by[k].update({kk: vv for kk, vv in it.items() if vv is not None})
            else:
                by[k] = dict(it)
    return by


def pick_capped(cands):
    """按单机型采样上限挑出入页条目，与采集侧同一规则。"""
    buck = collections.defaultdict(list)
    for k, x in cands.items():
        buck[(x.get("brand") or "none", x.get("model") or "brand-only")].append(x)
    keep = []
    for key, v in buck.items():
        v.sort(key=lambda x: x.get("pubDate") or "", reverse=True)
        keep.extend(v[:CAP_C if key[0] != "creality" else CAP_O])
    keep.sort(key=lambda x: (x.get("channel") or "", x.get("brand") or "",
                             x.get("model") or "", x.get("pubDate") or ""))
    return keep


def main():
    dry = "--dry-run" in sys.argv
    # 只对本批新增候选池做复核排序（存量 30 条上一轮已复核，索引不能混排）
    batch = json.load(open(os.path.join(BASE, "_resin_candidates_backfill_20261113.json"),
                          encoding="utf-8"))["items"]
    cands = {x["candKey"]: x for x in batch}
    keep = pick_capped(cands)
    keep_keys = [x["candKey"] for x in keep]
    labels = load(LABELS, {})
    tr = load(TR, {})
    today = dt.date.today().isoformat()

    missing = []
    changed = 0
    for i, x in enumerate(keep):
        k = x["candKey"]
        d = DEC.get(i)
        if not d:
            missing.append((i, k, (x.get("title") or "")[:50]))
            continue
        sent, codes, vol, note = d
        author = x.get("author") or ""
        is_off = bool(OFFICIAL.search(author)) or (x.get("channel") == "bilibili" and "CREALITY" in author.upper())
        problems = [NAME[c] for c in codes if c in NAME]
        p0, p0r = False, []
        if "售后拒保" in " ".join(problems) or "No warranty" in (x.get("originalText") or ""):
            pass
        if i == 6:
            p0, p0r = True, ["售后拒保"]
        if vol and is_off:
            vol = 0
        labels[k] = {
            "candKey": k,
            "sentiment": sent,
            "confidence": 0.88 if not is_off else 0.9,
            "problemPoints": problems,
            "problemDetail": [{"code": c, "name": NAME[c], "hits": 1} for c in codes if c in NAME],
            "isP0": p0,
            "p0Reason": p0r,
            "entryKind": "有效" if vol else "动态",
            "countInVolume": bool(vol),
            "lifecycle": "新出现",
            "needsReview": False,
            "forceReview": False,
            "confirmed": True,
            "labelSource": "ai-semantic-review",
            "reviewNote": ("官方频道，不计声量；" if is_off and d[2] else "") + note,
            "reviewedAt": today,
            "sourceTypeOverride": "官方" if is_off else None,
        }
        changed += 1
        t = TRX.get(i)
        if t:
            tr[k] = {"t": t[0], "b": t[1] or "", "s": t[1] or ""}

    # 超出采样上限的条目：保留原文，标动态 + 采样说明（不静默删除）
    kept_set = set(keep_keys)
    capped = 0
    for k, x in cands.items():
        if k in kept_set or k in labels and labels[k].get("labelSource") == "ai-semantic-review":
            continue
        labels[k] = {
            "candKey": k,
            "sentiment": "中性",
            "confidence": 0.5,
            "problemPoints": [],
            "problemDetail": [],
            "isP0": False,
            "p0Reason": [],
            "entryKind": "动态",
            "countInVolume": False,
            "lifecycle": "新出现",
            "needsReview": False,
            "forceReview": False,
            "confirmed": True,
            "labelSource": "ai-semantic-review",
            "reviewNote": "超出单机型采样上限（我方 10 / 竞品 5），本期不计入情感分母；原文保留，可在全量口径查看",
            "reviewedAt": today,
            "sourceTypeOverride": None,
        }
        capped += 1

    if missing:
        print("[REVIEW] 未覆盖 %d 条，索引：%s" % (len(missing), missing[:6]))
        if not dry:
            print("[REVIEW] 存在未覆盖条目，拒绝落盘")
            sys.exit(1)

    print("[REVIEW] keep=%d 复核=%d 超限标动态=%d 译文=%d" % (len(keep), changed, capped, len(tr)))
    if dry:
        return
    with open(LABELS, "w", encoding="utf-8") as f:
        json.dump(labels, f, ensure_ascii=False, indent=2)
    with open(TR, "w", encoding="utf-8") as f:
        json.dump(tr, f, ensure_ascii=False, indent=2)
    print("[REVIEW] 落盘 %s / %s" % (os.path.basename(LABELS), os.path.basename(TR)))


if __name__ == "__main__":
    main()
