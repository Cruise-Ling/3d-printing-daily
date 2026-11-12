# -*- coding: utf-8 -*-
"""光固化口碑 · 25 条 AI 逐条语义复核（2026-11-12）

参照 K3 标注纪律（.workbuddy/memory/k3-feedback.md §12.4）：
  1. 候选池只是候选，逐条读标题 + 正文做语义判定，不靠关键词词表；
  2. problemPoints 只从 resin_config.json 的 12 类受控词表选，长尾描述写进 summaryCn，
     不自造类目（§12.4「规则永远追不上这种写法，治本靠标注侧」）；
  3. 同一内容多帖按 mirrors 纪律声量只算 1；纯公告 / 纯自我介绍 / 品类误召回不计声量；
  4. 不为平衡情感分布硬标正面；求助型故障帖按语义判中性或负面；
  5. confirmed=true 后规则预标不得覆盖（K3 的 lock 列同义），保留人工改判通道。

产出：_resin_labels.json（改判）、_resin_tr.json（机翻）、_resin_ai_review.md（留痕）
用法：python _resin_ai_review.py
"""
import datetime as dt
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(BASE, "resin_config.json"), encoding="utf-8"))
LABELS = os.path.join(BASE, "_resin_labels.json")
TR = os.path.join(BASE, "_resin_tr.json")
REVIEW_MD = os.path.join(BASE, "_resin_ai_review.md")

# key -> (情感, 受控问题点, 是否 P0, 是否计声量, 置信度, 判定依据)
REVIEW = {
    "post:102008": ("负面", ["平台附着力", "离型膜与料槽寿命"], False, True, 0.90,
        "Mage S 14K 连续六次打印只粘 FEP 不粘平台，换离型膜仅成功一次；反复失效且语气受挫，规则预标中性偏保守，按语义上调负面。"),
    "post:102091": ("中性", [], False, False, 0.95,
        "与 post:102008 同一主题帖、同一段正文（topic 46600），属跨帖镜像；按 K3 mirrors 纪律声量只算 1，本条不计入分母。"),
    "post:102464": ("负面", ["软件与切片"], False, True, 0.88,
        "HALOT BOX 点击 RESIN 切片时反复崩溃，更新驱动 / 重装软件 / 恢复出厂后仍复发；去掉仅因机型名含 resin 而误标的「树脂适配与气味」。"),
    "post:102855": ("负面", ["屏幕寿命与坏点", "曝光与光源一致性"], False, True, 0.90,
        "HALOT SKY 2022 换全新原装 9.25 寸 6K LCD 后仍不显示层图像，作者自称 serious issue；去掉与内容无关的「树脂适配与气味」。"),
    "post:103105": ("中性", [], False, False, 0.95,
        "官方案例征集 / 访谈邀约，无任何产品评价；纯活动信息不计声量，清空规则误标。"),
    "post:103845": ("负面", [], False, True, 0.70,
        "MAGE PRO「z axis jams」，正文极短但故障表述明确；12 类受控词表无机械结构类目，按 K3 纪律不自造类目，描述写入中文摘要。"),
    "post:104651": ("负面", [], False, True, 0.78,
        "HALOT-ONE Z 轴偶发不转、紧固螺丝无效，已导致完全无法打印；同样不映射受控类目。"),
    "post:105688": ("中性", ["软件与切片"], False, True, 0.75,
        "意大利语求助：Halot R6 搭配 Creality CRCC S7 摄像头生成 0KB / 0 秒延时视频；属配件软件功能异常，保留求助语气判中性。"),
    "post:106021": ("中性", [], False, False, 0.95,
        "K2 Pro 热床调平长贴，正文「Resin is PLA」为 FDM 语境，与光固化无关；第五道品类语境闸门误召回，剔除出声量并清空两个误标问题点。"),
    "post:108144": ("中性", [], False, False, 0.95,
        "官方 HALOT-SKY 2025 用户指南目录，sourceType=官方且为文档清单，不构成用户评价；清空因目录关键词误命中的三个问题点。"),
    "post:108331": ("正面", [], False, True, 0.72,
        "新人自我介绍中明确表示 HALOT R6 打印质量令其满意、并据此开办 3D 打印业务，属真实正面原声；清空误标的「售后与配件供应」。"),
    "post:108515": ("中性", [], False, False, 0.95,
        "Creality 贴纸活动公告，与产品口碑无关；清空误标的「曝光与光源一致性」。"),
    "post:109228": ("中性", ["软件与切片", "屏幕寿命与坏点"], False, True, 0.82,
        "LD003 更换触摸屏后触屏固件与主板不匹配，属软硬件适配求助；规则因「Good day」误判正面，按语义转中性，去掉「树脂适配与气味」。"),
    "post:109778": ("中性", ["离型膜与料槽寿命", "软件与切片"], False, True, 0.85,
        "西班牙语：HALOT-ONE 打印件总留在 FEP，试多个切片软件都一样，但云端文件直出正常；证据指向切片参数而非硬件，保留两类问题点。"),
    "post:109981": ("中性", [], False, False, 0.95,
        "Ender 3V3（FDM）机架异响求助，与光固化无关；品类语境闸门误召回，剔除出声量。"),
    "post:110085": ("中性", ["软件与切片", "售后与配件供应"], False, True, 0.82,
        "官方 HALOT BOX 无 HALOT PLAY 机型选项，客服建议降级旧版，用户已改用 Chitubox 绕过；陈述平实判中性。"),
    "post:110794": ("中性", ["屏幕寿命与坏点", "清洗固化配套", "离型膜与料槽寿命"], False, True, 0.82,
        "二手机 Mage 8K 因 LCD 破损闲置、树脂渗漏污染 UV 反光镜，新手求助清理；保留三类证据链，去掉「曝光与光源一致性」。"),
    "post:112183": ("中性", ["售后与配件供应"], False, True, 0.80,
        "MAGE PRO 料槽螺丝滑牙、询问螺纹规格与长度，反映备件规格无公开渠道；去掉「树脂适配与气味」「包装与物流」两个误标。"),
    "post:113080": ("中性", ["软件与切片", "曝光与光源一致性"], False, True, 0.82,
        "法语：Mage Pro 8K 未采纳 Lychee 的 TSMC 双速与曝光前延迟参数，固件与软件均最新；属第三方切片兼容性问题。"),
    "post:113112": ("负面", ["平台附着力", "离型膜与料槽寿命"], False, True, 0.88,
        "MAGE PRO 模型反复不粘平台、换新平台与新料槽仍失败，停机近一年后复现；明确困扰，去掉「树脂适配与气味」「清洗固化配套」误标。"),
    "post:113987": ("负面", [], False, True, 0.85,
        "法语：2023 年购入 HALOT LITE 始终无法正常工作、长期闲置，自称「第一台也是最后一台 3D 打印机」；无具体故障类别，不自造类目。"),
    "post:118423": ("中性", ["售后与配件供应"], False, True, 0.82,
        "新款自动供料器 4005010123 标称兼容 MAGE PRO，却无对应安装说明与视频，网上资料多为老款泵；去掉「树脂适配与气味」。"),
    "post:119033": ("负面", ["售后与配件供应"], False, True, 0.90,
        "备件无官方购买渠道、需 PayPal 转账且核验流程冗长，用户明言「a good reason to look at other printers」；属明确流失风险，去掉「树脂适配与气味」。"),
    "post:119646": ("负面", ["曝光与光源一致性", "打印精度与尺寸误差"], False, True, 0.90,
        "Mage S 14K 单侧成型完美、另一侧缺肉变形且局部未固化，跨模型与两种树脂复现、调曝光无效；指向光源不均，去掉两个无关误标。"),
    "post:120379": ("负面", [], False, True, 0.70,
        "HALOT-ONE 平台上升三次即停止、「No matter what I do this keeps happening」；正文极短但反复故障成立，不映射受控类目。"),
    "yt:xE-XEI6e2gw": ("中性", [], False, False, 0.95,
        "葡语促销短视频（#CrealityHalotR6 #GarimpoDeOfertas 淘优惠），全文为「快看这个完美的捡漏」类营销话术，无实质评价；按 K3 低信号投放纪律不计声量。"),
    "yt:NBKRrIi7MKk": ("中性", [], False, False, 0.95,
        "标题为「Halot R6 Review: Worth It?」疑问句，简介全部是 Amazon 联盟链接与「Check Current Price」导流，无评测结论；不构成口碑表述，不计声量。"),
    "yt:pZj5MXHdCeU": ("中性", [], False, False, 0.92,
        "竞品 Saturn 4 Ultra 16K 选购清单，简介为章节 + 商品链接；保留「被点名」用于 M4 竞品统计，但无实质评价，不计声量。"),
    "yt:d7uvVvH6hLM": ("中性", [], False, False, 0.92,
        "竞品横评标题（Saturn 4 Ultra 16K vs Mars 5 Ultra）但简介仅联盟链接，无可核实结论；保留对比语境，不计声量。"),
    "yt:q5tYfuood6k": ("中性", [], False, False, 0.95,
        "Anycubic 405nm 树脂商品页文案搬运，属耗材产品说明而非用户声音；不计声量。"),
}

# key -> {"t": 标题中译, "b": 正文中译, "s": 中文摘要（带结论）}
TRANSLATIONS = {
    "post:102008": {"t": "打印件粘在 FEP 离型膜上而不粘平台",
        "b": "你好，我用的是 Mage S 14K，一开始工作得很好，但后来打印件开始不粘平台，反而牢牢粘在 FEP 上。FEP 被压出凹痕后我换了新的，只成功打印了一次，之后又完全不粘。我在不同日子试了六次，还把小模型分散摆满整个平台排查是否为局部问题，结果一件都粘不住。从 FEP 上取下来很费劲，平台却什么都留不住。我不知道怎么修，翻了其他帖子也没看到真正的答案，有人能帮忙吗？",
        "s": "Mage S 14K 连续六次打印只粘 FEP 不粘平台，换离型膜仅生效一次，属反复性附着失效。"},
    "post:102091": {"t": "打印件粘在 FEP 离型膜上而不粘平台（同帖镜像）",
        "b": "本条与上一条为同一主题帖（topic 46600）内的重复抓取，正文内容相同，按声量只算 1 的纪律不再计入分母。",
        "s": "同主题帖重复镜像，正文与首条一致，不重复计入声量。"},
    "post:102464": {"t": "HALOT BOX 崩溃",
        "b": "大家好，我在点击 RESIN 继续切片时 HALOT BOX 会崩溃。第一次发生时我确认驱动和软件都是最新，没用；随后用官网版本卸载重装，也没用；最后把笔记本恢复出厂、只装最小化驱动与软件，重装后一度正常，今天又在同样环节崩溃。有人最近或以前遇到过吗？",
        "s": "HALOT BOX 在切片环节反复崩溃，重装系统与软件后仍复发，属软件稳定性问题。"},
    "post:102855": {"t": "HALOT SKY 2022 更换屏幕后 LCD 仍不显示层图像",
        "b": "我的 Creality HALOT SKY 2022 光固化打印机出现严重问题：机器正常开机、UV LED 工作、反光镜干净，但打印时 LCD 完全不显示层图像。UV 背光亮起时屏幕中心整片发黑，运行 Clean Screen 也一样。我已更换一块全新的原装 9.25 英寸 6K 单色 LCD，问题依旧，请协助。",
        "s": "HALOT SKY 2022 换全新原装 LCD 后仍无层图像，屏幕或光路故障未排除，影响正常打印。"},
    "post:103105": {"t": "案例征集与人物访谈",
        "b": "我正在收集 3D 打印行业案例、教育应用故事以及用户或创作者专访，入选内容将在 Creality 官方平台与社交账号展示。若你认为自己的故事值得分享，欢迎联系我。",
        "s": "官方案例征集公告，不含任何产品评价，不作为口碑样本。"},
    "post:103845": {"t": "HALOT-MAGE PRO Z 轴问题", "b": "Z 轴卡死。",
        "s": "MAGE PRO 用户反馈 Z 轴卡死，正文极短但故障指向明确。"},
    "post:104651": {"t": "我的 HALOT-ONE Z 轴有时不转",
        "b": "我的 Halot One 最近 Z 轴有问题，看起来像是有部件没拧紧。我试着拧紧底部螺丝但没有改善，结果现在完全没法打印。",
        "s": "HALOT-ONE Z 轴偶发停转，紧固排查无效，已导致无法打印。"},
    "post:105688": {"t": "HALOT R6 与 Creality 摄像头",
        "b": "（意大利语）我的 Halot R6 搭配 Creality CRCC S7 摄像头始终无法生成延时摄影，生成的视频是 0KB、0 秒。有什么建议或解决办法吗？",
        "s": "Halot R6 搭配原厂摄像头生成 0KB 延时视频，属配件软件功能异常。"},
    "post:106021": {"t": "K2 系列旗舰打印机——调平与维护",
        "b": "（节选）我的 K2 Pro 热床调平做得很完美，用纸片法把旋钮调到最佳，不需要打磨、铝箔胶带等极端手段，数值从 0.45 降到 0.25；即使之前倾斜，打印也一直正常。可按官方视频教程操作，调平方法从 6:24 开始，四角需按顺时针至少反复微调四次，别忘了调平后重跑全部校准。",
        "s": "K2 Pro（FDM）热床调平教程，与光固化品类无关，判为误召回并剔除声量。"},
    "post:108144": {"t": "HALOT-SKY 2025 用户指南",
        "b": "官方资料目录：快速入门指南、用户手册、安装操作指南、切片教程、触屏操作、打印设置、调平教程、WiFi 打印、HALOT BOX 操作与切片参数说明、故障排查、平台附着问题解决方案、FAQ、维护、料槽清洁、Z 轴维护、离型膜更换、LCD 更换、保护盖 / 主板 / 电源 / 限位开关更换等。",
        "s": "官方用户指南目录，属文档清单而非用户评价，不计入口碑声量。"},
    "post:108331": {"t": "大家好（新用户报到）",
        "b": "（节选）大家好，我叫 Keagan Stephens，来自南非，31 岁，是执业药剂助理，也经营 Sculptured Realities。半年前为了给女儿做玩具模型接触 3D 打印，朋友有台 Creality Ender KE，我很喜欢成品效果，就买了当时能找到最便宜的机器。五个月前攒钱买了打折的 Creality Halot R6，我很喜欢它的打印质量，于是决定围绕 3D 打印开一家店。",
        "s": "新用户自我介绍，明确表示对 HALOT R6 打印质量满意并据此创业，属正面原声。"},
    "post:108515": {"t": "第一批 Creality 贴纸终于来了",
        "b": "第一批 Creality 贴纸到货了！感谢设计团队，希望大家喜欢这套「Cuva」贴纸。后续还有第二批，以及卡通 3D 打印机主题的第三批。想集齐全套的话在下面留言登记意向即可。",
        "s": "官方贴纸活动公告，与产品口碑无关，不计入声量。"},
    "post:109228": {"t": "Creality LD 003 光固化打印机",
        "b": "大家好，有人能帮我找 Creality LD003 光固化打印机配套的软件吗？我更换了触摸屏，也刷了屏幕对应的软件，但触屏软件和主板软件不匹配。",
        "s": "LD003 更换触摸屏后触屏固件与主板不兼容，属软硬件适配求助。"},
    "post:109778": {"t": "HALOT-ONE 打印问题",
        "b": "（西班牙语）我的 HALOT-ONE 有打印问题，打印件总是留在 FEP 上，试过好几个切片软件都一样；但直接从云端下载到打印机打印就完全正常。灰色那张是云端文件，图 2 是打印三小时后的结果，图 3 是用 HALOT BOX 切片后从 Creality 云端下载的新打印。",
        "s": "同文件云端直出正常、HALOT BOX 切片后粘 FEP，指向切片参数而非硬件故障。"},
    "post:109981": {"t": "ENDER 3V3 机架处传出短促金属异响",
        "b": "（节选）声音突然出现，检查不出松动件。这是这台机器第一次出问题，用了快一年一直很可靠。耗材是 PLA，这卷之前效果都不错，我用的是 Creality Print 7 和 7.1，有谁知道该查哪里吗？",
        "s": "Ender 3V3（FDM）异响求助，与光固化无关，判为误召回并剔除声量。"},
    "post:110085": {"t": "HALOT BOX 里没有 HALOT PLAY 机型选项",
        "b": "Creality 客服最终回复说当前版本的 HALOT BOX 不支持 HALOT PLAY，建议我安装旧版本。但在他们回复前我已经下载了 Chitubox，在里面找到了 HALOT PLAY，之后就一直使用它。",
        "s": "官方切片软件缺少 HALOT PLAY 机型配置，用户改用第三方切片软件绕过。"},
    "post:110794": {"t": "HALOT MAGE 8K 清理求助",
        "b": "你好，我收了一台因 LCD 破损而闲置的 Halot Mage 8K，换屏不难，但前任机主把树脂留在机器里，树脂漏到了 LCD 与 UV 灯之间的反光面上。我是光固化新手，想请教清理这块反光镜的最佳方法，看这台机器还能不能用。",
        "s": "二手机树脂渗漏污染反光镜，用户求助清理方式，涉及屏幕与料槽密封。"},
    "post:112183": {"t": "MAGE PRO 料槽螺丝规格",
        "b": "第一次发帖。我把 MAGE PRO 料槽上一颗螺丝的头拧滑了，内六角只会空转。有人知道这颗螺丝的螺纹规格和长度吗？下次换离型膜时我可以自己量，但希望提前备好替换件，免得等快递。",
        "s": "料槽螺丝滑牙后缺少公开备件规格，用户需自行测量，属配件信息缺口。"},
    "post:113080": {"t": "HALOT MAGE PRO 与 Lychee 切片",
        "b": "（法语）你好，我有一台 Halot Mage Pro 8K，切片用 Lychee，固件和软件都是最新。我注意到打印机没有采纳 Lychee 里设置的部分打印参数，比如双速（TSMC）和曝光前延迟。请问为什么，该怎么处理？",
        "s": "第三方切片软件的 TSMC 与曝光前延迟参数未被固件采纳，属切片兼容性问题。"},
    "post:113112": {"t": "HALOT MAGE PRO 模型粘不住平台",
        "b": "（节选）新人报到。模型怎么都粘不住平台，能试的都试了，打印几层后就粘到离型膜上。我调过参数、反复重新调平，还换了全新的平台和树脂槽（原本料槽螺纹和平台固定孔有一个滑牙）。因为家里装修停机近一年，之前一直正常，复工后第一次小件打印成功，之后就一直这样，不知道还能怎么办。",
        "s": "MAGE PRO 长期停机后反复附着失效，换新平台与料槽仍无法解决。"},
    "post:113987": {"t": "大家好（法国用户报到）",
        "b": "（法语）大家好，我叫 Walter，明年 50 岁，法国人，住在 ORSAY 附近。2023 年我买了 Creality HALOT LITE 光固化打印机，那是我的第一台，也是最后一台 3D 打印机，因为一直没法让它正常工作，之后就搁在柜子里。当初买它是因为我在 eBay 上订人偶花了太多钱。今天来论坛是因为受够了一台睡大觉的机器。",
        "s": "HALOT LITE 购入后始终无法正常使用、长期闲置，用户明确表达放弃该品类。"},
    "post:118423": {"t": "HALOT-MAGE PRO 自动供料器（4005010123）安装求助",
        "b": "大家好，我有台 HALOT-MAGE PRO 8K，最近买了 Creality 自动 / 智能供料器，料号 4005010123（欧版）。包装明确写兼容 HALOT-MAGE PRO / HALOT-MAGE S，但找不到清晰的安装说明，也找不到这个版本装在 MAGE PRO 上的视频；网上多数资料都是老款树脂泵。有人装过 4005010123 吗？这是新款泵。",
        "s": "新款自动供料器标称兼容 MAGE PRO，却缺少对应安装文档，属配套说明缺口。"},
    "post:119033": {"t": "备件与售后",
        "b": "（节选）不知道该发哪里，就放这儿，希望有人看到。首先客服同事很好，我的问题是怎么买到非零售备件。树脂滴到 Halot Mage S 的电源分配板上把板子烧了，官方没有专门的备件购买渠道，这本身就足够成为去看别家打印机的理由。花了一周才说明白是我自己的责任并拿到所需信息。流程是先通过 PayPal 往某个链接打钱，再把发票号发回去，等两三天后对方说已把发票号转给其他人核验，然后再继续。",
        "s": "备件采购无官方渠道、流程冗长且需 PayPal 转账，用户明确表示会考虑竞品。"},
    "post:119646": {"t": "HALOT MAGE S 14K 一侧打印正常、另一侧不成型",
        "b": "（节选）我的 Creality Halot Mage S 14K 有个反复出现的打印问题，想问是否有人遇到：照片里模型一部分打印完美、细节清晰，另一侧却明显缺陷——打印不完整、变形、局部树脂似乎没固化好。换不同模型、两种树脂（Fast Cast SuperCast 粉色、Liqcreate Wax Castable 蓝色）都复现；已多次试打印并调整曝光、模型朝向与支撑，仍无法解决。",
        "s": "MAGE S 14K 单侧成型不全，跨模型跨树脂复现且调曝光无效，指向曝光或光源不均。"},
    "post:120379": {"t": "HALOT-ONE 平台上升三次后停止工作",
        "b": "不管我怎么弄，都是这样。",
        "s": "HALOT-ONE 平台上升三次即停机且反复复现，正文极短但故障明确。"},
    "yt:xE-XEI6e2gw": {"t": "不是吧…快看这个完美的捡漏（葡语带货短视频）",
        "b": "（葡萄牙语）不是吧，快看这个完美的捡漏！如果你一直在找一台能让你终于入门 3D 打印、创作自己作品的设备……（话题标签：3D打印 / CrealityHalotR6 / 淘优惠）",
        "s": "葡语促销短视频，只有营销话术与优惠标签，无实质产品评价。"},
    "yt:NBKRrIi7MKk": {"t": "Creality Halot R6 评测：入门光固化打印机值得买吗？（2026）",
        "b": "标题为评测疑问句，简介内容为：查看亚马逊当前价格（附联盟短链），收藏并在任意亚马逊购物时使用本链接以支持频道。未提供评测结论或实测数据。",
        "s": "标题为评测疑问句但正文纯联盟导流，无评测结论，不进口碑分母。"},
    "yt:pZj5MXHdCeU": {"t": "Formlabs Form Studio 第 1 期：Saturn 4 Ultra 16K 适合新手吗？",
        "b": "按成型尺寸与工作流程挑选光固化打印机，章节与链接如下：#1 ELEGOO Saturn 4 Ultra 16K（亚马逊链接）……（其余为商品链接清单）",
        "s": "竞品选购清单，仅有章节与购买链接，保留竞品被点名但无实质评价。"},
    "yt:d7uvVvH6hLM": {"t": "Elegoo Saturn 4 Ultra 16K 对比 Mars 5 Ultra：像素还是平台面积？（2026）",
        "b": "标题为竞品横评疑问句，简介内容为：查看亚马逊当前价格（附联盟短链），收藏并在任意亚马逊购物时使用本链接以支持频道。未给出对比结论。",
        "s": "竞品横评标题但正文仅联盟链接，保留对比语境、不计入口碑声量。"},
    "yt:q5tYfuood6k": {"t": "ANYCUBIC 405nm UV 标准树脂 / V2，适用于 Photon Mono M7 等 LCD 光固化打印机",
        "b": "ANYCUBIC 405nm UV 标准树脂 / 标准树脂 V2，适用于 LCD 3D 打印机 Photon Mono M7 等机型，为 UV 光敏树脂产品说明。",
        "s": "竞品耗材商品页文案搬运，属产品说明而非用户声音。"},
}


def main():
    old = json.load(open(LABELS, encoding="utf-8"))
    missing = set(old) - set(REVIEW)
    extra = set(REVIEW) - set(old)
    if missing or extra:
        raise SystemExit("复核表与标注表不一致：缺 %s / 多 %s" % (sorted(missing), sorted(extra)))
    if set(TRANSLATIONS) != set(old):
        raise SystemExit("译文表与标注表条目不一致")

    name2code = {p["name"]: p["code"] for p in CFG["problemPoints"]}
    before = {k: (v["sentiment"], list(v["problemPoints"]), bool(v["countInVolume"]))
              for k, v in old.items()}

    for k, v in old.items():
        sent, probs, p0, cnt, conf, note = REVIEW[k]
        bad = [p for p in probs if p not in name2code]
        if bad:
            raise SystemExit("%s 使用了受控词表外的问题点：%s" % (k, bad))
        v.update({
            "sentiment": sent,
            "confidence": conf,
            "problemPoints": probs,
            "problemDetail": [{"code": name2code[p], "name": p, "hits": 0,
                               "source": "semantic"} for p in probs],
            "isP0": p0,
            "p0Reason": [],
            "entryKind": "有效" if cnt else "动态",
            "countInVolume": cnt,
            "lifecycle": "新出现",
            "needsReview": False,
            "forceReview": False,
            "confirmed": True,
            "labelSource": "ai-semantic-review",
            "reviewNote": note,
        })

    with open(LABELS, "w", encoding="utf-8") as f:
        json.dump(old, f, ensure_ascii=False, indent=2)
    with open(TR, "w", encoding="utf-8") as f:
        json.dump(TRANSLATIONS, f, ensure_ascii=False, indent=2)

    titles = {}
    for fn in os.listdir(BASE):
        if fn.startswith("_resin_candidates_") and fn.endswith(".json"):
            d = json.load(open(os.path.join(BASE, fn), encoding="utf-8"))
            for it in d.get("items", []):
                titles[it["candKey"]] = it.get("title") or ""

    valid = sum(1 for v in old.values() if v["countInVolume"])
    from collections import Counter
    dist = Counter(v["sentiment"] for v in old.values())
    dyn = len(old) - valid
    yt_new = sum(1 for k in old if k.startswith(("yt:", "ytc:")))
    lines = [
        "# 光固化专栏 · AI 逐条语义复核留痕",
        "",
        "复核日期：%s · 复核主体：AI 辅助语义复核（**非需求方人工签字**），保留人工改判通道。" % dt.date.today().isoformat(),
        "判定依据：K3 标注纪律（受控词表优先、不自造类目、镜像只算 1 条、不硬标正面、低信号投放丢弃）。",
        "",
        "# 一、复核结果",
        "",
        "| 项 | 值 |",
        "|---|---|",
        "| 复核条目 | %d |" % len(old),
        "| 计声量（有效样本） | %d |" % valid,
        "| 动态 · 不计声量 | %d |" % dyn,
        "| 情感分布（全量） | %s |" % dict(dist),
        "| 待复核 | %d（保留改判通道） |" % sum(1 for v in old.values() if v["needsReview"]),
        "",
        "存量 25 条的原始规则预标分布见 `00_台账/变更点_20261112_光固化专栏上线.md`。",
        "其中 %d 条判为「动态」：1 条同帖镜像、2 条 FDM 品类误召回、3 条官方/活动公告、1 条纯自我介绍；" % (dyn - yt_new),
        "另有 %d 条 YouTube 日更新增，全部是联盟带货 / 商品页文案，按 K3 低信号纪律不计声量，仅保留竞品被点名与对比语境。" % yt_new,
        "",
        "# 二、逐条改判明细",
        "",
        "| candKey | 标题 | 预标 → 复核 | 声量 | 判定依据 |",
        "|---|---|---|---|---|",
    ]
    for k in sorted(old, key=lambda x: before[x][0]):
        b = before[k]
        v = old[k]
        chg = ("%s → %s" % (b[0], v["sentiment"])) if (
            b[0] != v["sentiment"] or b[2] != v["countInVolume"]) else v["sentiment"]
        lines.append("| %s | %s | %s | %s | %s |" % (
            k, titles.get(k, "")[:44].replace("|", "/"),
            chg, "计" if v["countInVolume"] else "不计",
            v["reviewNote"].replace("|", "/")))
    lines += ["", "# 三、纪律与边界", "",
              "1. 问题点只取 `resin_config.json` 的 12 类受控词表，长尾描述写进 `summaryCn`；本次 6 条机械故障未自造类目。",
              "2. 正面样本仅 1 条且均有原文明证，未为平衡情感分布硬标；论坛样本天然偏负面，页面与报告不得外推。",
              "3. `confirmed=true` 后 `_resin_prelabel.py` 不再覆盖；如需改判，直接编辑 `_resin_labels.json` 并重跑注入与建页。",
              "4. 中文译文与摘要由本脚本的 `TRANSLATIONS` 提供，日更新增条目须由 10:00 增量链内补译后写入 `_resin_tr.json`。", ""]
    with open(REVIEW_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print("[AI_REVIEW] total=%d valid=%d sentiment=%s | labels/tr/md written" %
          (len(old), valid, dict(dist)))


if __name__ == "__main__":
    main()
