# -*- coding: utf-8 -*-
"""生成 resin_config.json V1.2（生成到 _resin_config_v12_draft.json，不覆盖现网配置）

用法：python _make_config_v12.py [--apply]
  --apply  把结果写回 resin_config.json（只在 10:00 抓取链跑完之后用）

为什么用脚本而不是直接手改 JSON：
  V1.2 要新增 brands / modelAliasBlock / brandHints，替换 models，更新 channels，
  手写整份 JSON 极易漏掉 queries / problemPoints / sentimentLexicon / p0Rules 等段。
  以现配置为基底做「按键替换 + 新增」，能保证一个键都不丢。
"""
import glob
import json
import os
import shutil
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BASE, "resin_config.json")
OUT = os.path.join(BASE, "_resin_config_v12_draft.json")

BRANDS = [
    {"code": "creality", "name": "创想三维", "fullName": "Creality 创想三维", "isOwn": True, "order": 1},
    {"code": "elegoo", "name": "Elegoo", "fullName": "Elegoo 智能派", "isOwn": False, "order": 2},
    {"code": "anycubic", "name": "Anycubic", "fullName": "Anycubic 纵维立方", "isOwn": False, "order": 3},
    {"code": "phrozen", "name": "Phrozen", "fullName": "Phrozen 普罗森", "isOwn": False, "order": 4},
]


def M(code, name, brand, aliases, tier, prio, on_sale, pos):
    return {"code": code, "name": name, "brand": brand, "aliases": aliases,
            "tier": tier, "priority": prio, "onSale": on_sale, "confirmed": False,
            "launchDate": None, "positioning": pos}


MODELS = [
    # ---- 创想三维（我方）11 个 ----
    M("halot-x1-max", "HALOT-X1 MAX", "creality",
      ["HALOT-X1 MAX", "HALOT X1 MAX", "X1 MAX", "HALOT-X1"], "主力旗舰", "高", True,
      "大尺寸量产级光固化，面向小型工作室与代工（B 站 2026-09 已有开箱内容）"),
    M("halot-mage-pro", "HALOT-MAGE PRO", "creality",
      ["HALOT-MAGE PRO", "HALOT MAGE PRO", "MAGE PRO", "MagePro", "MAGE-PRO"], "主力旗舰", "高", True,
      "大尺寸高分辨率旗舰，面向重度用户与小型工作室"),
    M("halot-mage", "HALOT-MAGE", "creality",
      ["HALOT-MAGE", "HALOT MAGE", "Halot Mage"], "中端主销", "高", True,
      "主流尺寸机型，面向进阶爱好者"),
    M("halot-r6", "HALOT-R6", "creality",
      ["HALOT-R6", "HALOT R6", "Halot R6"], "中端主销", "高", True,
      "2026 主力机型，存量样本已有多条真实讨论（V1.2 新增）"),
    M("halot-sky", "HALOT-SKY", "creality",
      ["HALOT-SKY", "HALOT SKY"], "中端主销", "中", True,
      "中大尺寸机型（在售状态待确认）"),
    M("halot-one", "HALOT-ONE", "creality",
      ["HALOT-ONE PLUS", "HALOT ONE PLUS", "HALOT-ONE PRO", "HALOT ONE PRO", "HALOT-ONE", "HALOT ONE"],
      "入门机型", "中", True, "小尺寸入门机，面向新手与家庭用户"),
    M("halot-play", "HALOT-PLAY", "creality",
      ["HALOT-PLAY", "HALOT PLAY", "Halot Play"], "入门机型", "中", True,
      "入门娱乐向机型，存量样本有 Halot Box 适配讨论（V1.2 新增）"),
    M("halot-lite", "HALOT-LITE", "creality",
      ["HALOT-LITE", "HALOT LITE"], "入门机型", "中", True,
      "轻量入门机型（在售状态待确认）"),
    M("halot-max", "HALOT-MAX", "creality",
      ["HALOT-MAX", "HALOT MAX"], "主力旗舰", "低", True,
      "大尺寸专业机型（在售状态待确认）"),
    M("halot-ray", "HALOT-RAY", "creality",
      ["HALOT-RAY", "HALOT RAY"], "历史机型", "低", False,
      "仅保留口碑趋势追踪，不做问题下钻"),
    M("ld-003", "LD-003", "creality",
      ["LD-003", "LD 003", "LD003"], "历史机型", "低", False,
      "早期 LCD 光固化机型，仅做历史口碑留存（V1.2 新增）"),
    # ---- Elegoo 5 个 ----
    M("elegoo-saturn-4-ultra-16k", "Saturn 4 Ultra 16K", "elegoo",
      ["Saturn 4 Ultra 16K", "Saturn4 Ultra 16K", "土星4 Ultra 16K"], "主力旗舰", "高", True,
      "16K 分辨率旗舰，对标大尺寸高精度需求"),
    M("elegoo-saturn-4-ultra", "Saturn 4 Ultra", "elegoo",
      ["Saturn 4 Ultra", "Saturn4 Ultra", "土星4 Ultra"], "主力旗舰", "高", True,
      "倾斜离型 + 高速打印主力机"),
    M("elegoo-mars-5-ultra", "Mars 5 Ultra", "elegoo",
      ["Mars 5 Ultra", "Mars5 Ultra", "火星5 Ultra"], "中端主销", "高", True,
      "中尺寸高速机型，面向进阶用户"),
    M("elegoo-mars-4-ultra", "Mars 4 Ultra", "elegoo",
      ["Mars 4 Ultra", "Mars4 Ultra", "火星4 Ultra"], "中端主销", "中", True,
      "中尺寸 9K 机型"),
    M("elegoo-jupiter-2", "Jupiter 2", "elegoo",
      ["Jupiter 2", "Jupiter2", "木星2"], "大尺寸", "中", True,
      "超大成型尺寸，面向手办与工业样件"),
    # ---- Anycubic 5 个 ----
    M("anycubic-photon-mono-m7-pro", "Photon Mono M7 Pro", "anycubic",
      ["Photon Mono M7 Pro", "Mono M7 Pro", "M7 Pro"], "主力旗舰", "高", True,
      "14K 旗舰，自动进退料"),
    M("anycubic-photon-mono-m7", "Photon Mono M7", "anycubic",
      ["Photon Mono M7", "Mono M7"], "主力旗舰", "高", True,
      "高分辨率主力机"),
    M("anycubic-photon-mono-m5s-pro", "Photon Mono M5s Pro", "anycubic",
      ["Photon Mono M5s Pro", "Mono M5s Pro", "M5s Pro"], "中端主销", "中", True,
      "免调平中端机"),
    M("anycubic-photon-mono-x2", "Photon Mono X2", "anycubic",
      ["Photon Mono X2", "Mono X2"], "中端主销", "低", True,
      "中尺寸 4K+ 机型"),
    M("anycubic-photon-mono-2", "Photon Mono 2", "anycubic",
      ["Photon Mono 2", "Mono 2"], "入门机型", "低", True,
      "入门级 4K 机型"),
    # ---- Phrozen 5 个 ----
    M("phrozen-sonic-mighty-revo-16k", "Sonic Mighty Revo 16K", "phrozen",
      ["Sonic Mighty Revo 16K", "Mighty Revo 16K", "Mighty Revo"], "主力旗舰", "高", True,
      "16K 旗舰，面向高精度手办"),
    M("phrozen-sonic-mighty-8k", "Sonic Mighty 8K", "phrozen",
      ["Sonic Mighty 8K", "Mighty 8K"], "中端主销", "高", True,
      "中大尺寸 8K 经典机型"),
    M("phrozen-sonic-mega-8k-s", "Sonic Mega 8K S", "phrozen",
      ["Sonic Mega 8K S", "Mega 8K S", "Sonic Mega 8K"], "大尺寸", "中", True,
      "超大成型尺寸机型"),
    M("phrozen-sonic-mini-8k-s", "Sonic Mini 8K S", "phrozen",
      ["Sonic Mini 8K S", "Mini 8K S", "Sonic Mini 8K"], "入门机型", "中", True,
      "小尺寸 8K 高精度机型"),
    M("phrozen-sonic-mini-4k", "Sonic Mini 4K", "phrozen",
      ["Sonic Mini 4K"], "历史机型", "低", False,
      "上一代小尺寸机型，仅做趋势追踪"),
]

# 机型未命中时的品牌兜底词（按命中数取最强，同分优先我方）
BRAND_HINTS = {
    "_comment": "机型未命中时按品牌词兜底归属到品牌级（modelName 为空，页面显示品牌 chip），避免大量「未归属」。",
    "creality": ["creality", "创想三维", "创想", "halot", "halot box"],
    "elegoo": ["elegoo", "土星", "mars", "jupiter", "智能派"],
    "anycubic": ["anycubic", "纵维立方", "纵维", "photon mono", "photon"],
    "phrozen": ["phrozen", "普罗森", "sonic mighty", "sonic mini", "sonic mega"],
}

ALIAS_BLOCK = ["one", "max", "lite", "sky", "ray", "pro", "plus", "mini", "mono",
               "mars", "saturn", "jupiter", "mega", "mighty", "revo", "sonic",
               "mage", "r6", "play"]

CHANNELS = [
    {"key": "creality_forum", "name": "Creality 官方论坛", "type": "discourse", "region": "海外",
     "tier": "P0", "endpoint": "https://forum.creality.com", "state": "auto",
     "note": "Discourse /search.json + /t/{id}.json，2026-11-12 实测可用；日更按 3 天窗口"},
    {"key": "youtube", "name": "YouTube", "type": "api", "region": "海外", "tier": "P0", "state": "auto",
     "note": "Data API v3 可用（_k3_creds.json 的 youtube.apiKey）；RESIN_STRICT + FDM_MARKERS 双过滤；按机型×时间窗精算 quota"},
    {"key": "bilibili", "name": "Bilibili", "type": "api", "region": "国内", "tier": "P0", "state": "auto",
     "note": "2026-11-13 复测：warmup GET 首页拿 cookie + 带 Referer 打 search/type 即 code=0，20 条真实结果；取代 V1.0「直连 412」的 blocked 结论。稀疏渠道按 120 天滚动召回"},
    {"key": "smzdm", "name": "什么值得买", "type": "html", "region": "国内", "tier": "P0", "state": "auto",
     "note": "2026-11-13 复测：search 页 202 空壳不可用，但分类页 /fenlei/3ddayinji/ 返回真实 SSR HTML（28+ 文章链接），文章页可取标题/发布时间/正文；按 180 天滚动召回"},
    {"key": "reddit", "name": "Reddit", "type": "rss", "region": "海外", "tier": "P1", "state": "blocked",
     "note": "2026-11-13 复测：www 搜 403；old.reddit 返回 HTTP 200 但正文是「Welcome to Reddit」HTML 中间页（Content-Type text/html、0 条 entry），非 Atom feed。判定不可程序化采集"},
    {"key": "review_sites", "name": "专业评测站", "type": "manual", "region": "海外", "tier": "P1",
     "state": "manual", "note": "WP REST 401，按 K3 现有 search 补录路径人工补录"},
    {"key": "xiaohongshu", "name": "小红书", "type": "login_wall", "region": "国内", "tier": "P1",
     "state": "login_wall", "note": "11-06 实测未登录 0 条"},
    {"key": "douyin", "name": "抖音", "type": "login_wall", "region": "国内", "tier": "P1",
     "state": "login_wall", "note": "11-06 实测搜索页空白"},
    {"key": "zhihu_weibo_tieba", "name": "知乎 / 微博 / 贴吧", "type": "login_wall", "region": "国内",
     "tier": "P1", "state": "login_wall", "note": "登录态可读，仅能截图抄录"},
    {"key": "ecom", "name": "Amazon / 京东 / 天猫 / 淘宝", "type": "paid", "region": "海外+国内",
     "tier": "P2", "state": "unavailable", "note": "官方 API 不给评价；需 Keepa / Rainforest 或商业服务"},
    {"key": "x_facebook", "name": "X / Facebook 群组", "type": "paid", "region": "海外", "tier": "P2",
     "state": "unavailable", "note": "官方 API 贵或只能读自家主页"},
]

QUERIES = {
    "model": [
        "HALOT-X1 MAX", "HALOT-MAGE PRO", "HALOT-MAGE", "HALOT-R6", "HALOT-SKY",
        "HALOT-ONE", "HALOT-PLAY", "HALOT-LITE", "HALOT-MAX", "HALOT-RAY", "LD-003",
        "Creality Halot", "创想三维 光固化",
    ],
    "category": [
        "Creality resin printer", "Creality HALOT resin", "光固化打印机 树脂",
        "SLA 打印机 曝光", "MSLA 离型膜", "Creality 光固化 评测",
        "resin printer comparison", "光固化 打印机 对比",
    ],
    "scenario": [
        "树脂 气味", "清洗固化机", "离型膜 破损", "曝光 不均",
        "屏幕 坏点", "平台 附着力", "成型尺寸 误差", "打印失败 底曝",
    ],
}

# 竞品检索词：让「竞品自有样本」有稳定召回，而不是只靠对比语境顺带提到
COMPETITOR_QUERIES = [
    "Elegoo Saturn 4 Ultra 16K review",
    "Elegoo Saturn 4 Ultra resin review",
    "Elegoo Mars 5 Ultra review",
    "Anycubic Photon Mono M7 Pro review",
    "Anycubic Photon Mono M7 review",
    "Phrozen Sonic Mighty Revo 16K review",
    "Phrozen Sonic Mighty 8K review",
    "Saturn 4 Ultra vs Photon Mono M7 vs Sonic Mighty",
]

FDM_MARKERS_EXTRA = ["k2 series", "k1 series", "k1 max", "ender 3", "ender3",
                     "bambu lab", "x1 carbon", "prusa", "voxelab"]


def main():
    cfg = json.load(open(SRC, encoding="utf-8"))
    old_models = cfg.get("models") or []
    cfg["_comment"] = ("光固化产品线口碑专栏配置包 V1.2（2026-11-13 E 批）。四品牌 26 机型同构建谱系，"
                       "机型名基于公开型号整理，上市日/在售状态/官方定位仍待产品中心与竞品调研正式清单确认，"
                       "故 confirmed 全为 false 且页面显式披露；换机型只改本文件，不改代码。")
    cfg["version"] = "1.2"
    cfg["brands"] = BRANDS
    cfg["models"] = MODELS
    cfg["brandHints"] = BRAND_HINTS
    cfg["modelAliasBlock"] = ALIAS_BLOCK
    cfg["_aliasBlockComment"] = (
        "裸通用词禁用作机型别名：2026-11-13 实测子串匹配下 MAGE 命中 image、RAY 命中 gray/array、"
        "ONE 命中任意 one，30 条存量里 5 条机型错归属（17%）。改为词边界正则 + 最长匹配优先后仍禁用这些裸词。")
    cfg["queries"] = QUERIES
    cfg["competitorQueries"] = COMPETITOR_QUERIES
    cfg["channels"] = CHANNELS
    cfg["fdmMarkers"] = FDM_MARKERS_EXTRA

    # competitors 段保留为「竞品品牌摘要」，真正的机型清单在 models 里（brand != creality）
    cfg["competitors"] = [
        {"code": "elegoo", "name": "Elegoo", "aliases": ["Elegoo", "智能派"],
         "note": "机型见 models 中 brand=elegoo 的 5 个"},
        {"code": "anycubic", "name": "Anycubic", "aliases": ["Anycubic", "纵维立方"],
         "note": "机型见 models 中 brand=anycubic 的 5 个"},
        {"code": "phrozen", "name": "Phrozen", "aliases": ["Phrozen", "普罗森"],
         "note": "机型见 models 中 brand=phrozen 的 5 个"},
    ]

    # 保持 problemPoints 12 类受控词表不变（跨批次可比），只补「竞品」关键词
    for p in cfg.get("problemPoints") or []:
        if p.get("code") == "competitor":
            for k in ("elegoo", "anycubic", "phrozen", "土星", "火星"):
                if k not in p["keywords"]:
                    p["keywords"].append(k)

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

    n_old = len(old_models)
    print("[CFG] %s | models %d -> %d | brands=%d | channels=%d" %
          (os.path.basename(OUT), n_old, len(MODELS), len(BRANDS), len(CHANNELS)))
    print("[CFG] keys kept: %s" % ", ".join(sorted(cfg.keys())))

    if "--apply" in sys.argv:
        bak = os.path.join(BASE, "_bak_resin_config_%s.json" % __import__("datetime").date.today().strftime("%Y%m%d"))
        shutil.copy2(SRC, bak)
        shutil.copy2(OUT, SRC)
        print("[CFG] applied -> resin_config.json（备份 %s）" % os.path.basename(bak))


if __name__ == "__main__":
    main()
