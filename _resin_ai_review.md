# 光固化专栏 · AI 逐条语义复核留痕

复核日期：2026-11-12 · 复核主体：AI 辅助语义复核（**非需求方人工签字**），保留人工改判通道。
判定依据：K3 标注纪律（受控词表优先、不自造类目、镜像只算 1 条、不硬标正面、低信号投放丢弃）。

# 一、复核结果

| 项 | 值 |
|---|---|
| 复核条目 | 30 |
| 计声量（有效样本） | 19 |
| 动态 · 不计声量 | 11 |
| 情感分布（全量） | {'中性': 19, '负面': 10, '正面': 1} |
| 待复核 | 0（保留改判通道） |

存量 25 条的原始规则预标分布见 `00_台账/变更点_20261112_光固化专栏上线.md`。
其中 6 条判为「动态」：1 条同帖镜像、2 条 FDM 品类误召回、3 条官方/活动公告、1 条纯自我介绍；
另有 5 条 YouTube 日更新增，全部是联盟带货 / 商品页文案，按 K3 低信号纪律不计声量，仅保留竞品被点名与对比语境。

# 二、逐条改判明细

| candKey | 标题 | 预标 → 复核 | 声量 | 判定依据 |
|---|---|---|---|---|
| post:118423 | Creality Automated Resin Feeder (4005010123) | 中性 | 计 | 新款自动供料器 4005010123 标称兼容 MAGE PRO，却无对应安装说明与视频，网上资料多为老款泵；去掉「树脂适配与气味」。 |
| post:113080 | Halot Mage Pro / Lychee | 中性 | 计 | 法语：Mage Pro 8K 未采纳 Lychee 的 TSMC 双速与曝光前延迟参数，固件与软件均最新；属第三方切片兼容性问题。 |
| post:112183 | Screw size for Mage Pro resin bath | 中性 | 计 | MAGE PRO 料槽螺丝滑牙、询问螺纹规格与长度，反映备件规格无公开渠道；去掉「树脂适配与气味」「包装与物流」两个误标。 |
| post:110794 | Halot Mage 8K cleaning help. | 中性 | 计 | 二手机 Mage 8K 因 LCD 破损闲置、树脂渗漏污染 UV 反光镜，新手求助清理；保留三类证据链，去掉「曝光与光源一致性」。 |
| post:109778 | Halot one problemas de impresion. | 中性 | 计 | 西班牙语：HALOT-ONE 打印件总留在 FEP，试多个切片软件都一样，但云端文件直出正常；证据指向切片参数而非硬件，保留两类问题点。 |
| post:108144 | HALOT-SKY 2025 User Guide | 中性 | 不计 | 官方 HALOT-SKY 2025 用户指南目录，sourceType=官方且为文档清单，不构成用户评价；清空因目录关键词误命中的三个问题点。 |
| post:105688 | Halot r6 - webcam Creality | 中性 | 计 | 意大利语求助：Halot R6 搭配 Creality CRCC S7 摄像头生成 0KB / 0 秒延时视频；属配件软件功能异常，保留求助语气判中性。 |
| post:110085 | No option in Halot Box for Printer Halot Pla | 中性 | 计 | 官方 HALOT BOX 无 HALOT PLAY 机型选项，客服建议降级旧版，用户已改用 Chitubox 绕过；陈述平实判中性。 |
| post:108515 | The FIRST wave of Creality stickers is final | 中性 | 不计 | Creality 贴纸活动公告，与产品口碑无关；清空误标的「曝光与光源一致性」。 |
| post:102091 | Prints sticking to FEP and not the Print Pla | 中性 | 不计 | 与 post:102008 同一主题帖、同一段正文（topic 46600），属跨帖镜像；按 K3 mirrors 纪律声量只算 1，本条不计入分母。 |
| post:109228 | Creality LD 003 Resin printer | 中性 | 计 | LD003 更换触摸屏后触屏固件与主板不匹配，属软硬件适配求助；规则因「Good day」误判正面，按语义转中性，去掉「树脂适配与气味」。 |
| post:106021 | K2 Series Flagship Printers - Bed Leveling a | 中性 | 不计 | K2 Pro 热床调平长贴，正文「Resin is PLA」为 FDM 语境，与光固化无关；第五道品类语境闸门误召回，剔除出声量并清空两个误标问题点。 |
| post:103105 | Case Studies & Featured Interviews | 中性 | 不计 | 官方案例征集 / 访谈邀约，无任何产品评价；纯活动信息不计声量，清空规则误标。 |
| post:109981 | MY ENDER 3V3 MAKES A SHORT TERM CLATTERING L | 中性 | 不计 | Ender 3V3（FDM）机架异响求助，与光固化无关；品类语境闸门误召回，剔除出声量。 |
| yt:xE-XEI6e2gw | Gente, sério... olha que achado perfeito! 😱✨ | 中性 | 不计 | 葡语促销短视频（#CrealityHalotR6 #GarimpoDeOfertas 淘优惠），全文为「快看这个完美的捡漏」类营销话术，无实质评价；按 K3 低信号投放纪律不计声量。 |
| yt:NBKRrIi7MKk | Creality Halot R6 Review: Beginner Resin Pri | 中性 | 不计 | 标题为「Halot R6 Review: Worth It?」疑问句，简介全部是 Amazon 联盟链接与「Check Current Price」导流，无评测结论；不构成口碑表述，不计声量。 |
| yt:pZj5MXHdCeU | Formlabs Form Studio 1: Saturn 4 Ultra 16K f | 中性 | 不计 | 竞品 Saturn 4 Ultra 16K 选购清单，简介为章节 + 商品链接；保留「被点名」用于 M4 竞品统计，但无实质评价，不计声量。 |
| yt:d7uvVvH6hLM | Elegoo Saturn 4 Ultra 16K vs Mars 5 Ultra: P | 中性 | 不计 | 竞品横评标题（Saturn 4 Ultra 16K vs Mars 5 Ultra）但简介仅联盟链接，无可核实结论；保留对比语境，不计声量。 |
| yt:q5tYfuood6k | ANYCUBIC 405nm UV Standard Resin / Standard  | 中性 | 不计 | Anycubic 405nm 树脂商品页文案搬运，属耗材产品说明而非用户声音；不计声量。 |
| post:108331 | Hello everyone | 正面 | 计 | 新人自我介绍中明确表示 HALOT R6 打印质量令其满意、并据此开办 3D 打印业务，属真实正面原声；清空误标的「售后与配件供应」。 |
| post:113112 | Problems with Model sticking to build Plate  | 负面 | 计 | MAGE PRO 模型反复不粘平台、换新平台与新料槽仍失败，停机近一年后复现；明确困扰，去掉「树脂适配与气味」「清洗固化配套」误标。 |
| post:103845 | HALOT - MAGE PRO z axis problem | 负面 | 计 | MAGE PRO「z axis jams」，正文极短但故障表述明确；12 类受控词表无机械结构类目，按 K3 纪律不自造类目，描述写入中文摘要。 |
| post:119646 | Printing Issue with Creality Halot Mage S 14 | 负面 | 计 | Mage S 14K 单侧成型完美、另一侧缺肉变形且局部未固化，跨模型与两种树脂复现、调曝光无效；指向光源不均，去掉两个无关误标。 |
| post:102008 | Prints sticking to FEP and not the Print Pla | 负面 | 计 | Mage S 14K 连续六次打印只粘 FEP 不粘平台，换离型膜仅成功一次；反复失效且语气受挫，规则预标中性偏保守，按语义上调负面。 |
| post:104651 | My z-axis of my halot one is sometimes not t | 负面 | 计 | HALOT-ONE Z 轴偶发不转、紧固螺丝无效，已导致完全无法打印；同样不映射受控类目。 |
| post:102855 | HALOT SKY 2022 – LCD does not display layer  | 负面 | 计 | HALOT SKY 2022 换全新原装 9.25 寸 6K LCD 后仍不显示层图像，作者自称 serious issue；去掉与内容无关的「树脂适配与气味」。 |
| post:120379 | creality halot one build plate rises 3 times | 负面 | 计 | HALOT-ONE 平台上升三次即停止、「No matter what I do this keeps happening」；正文极短但反复故障成立，不映射受控类目。 |
| post:113987 | Bonjour tout le monde | 负面 | 计 | 法语：2023 年购入 HALOT LITE 始终无法正常工作、长期闲置，自称「第一台也是最后一台 3D 打印机」；无具体故障类别，不自造类目。 |
| post:102464 | HALOT BOX is crashing | 负面 | 计 | HALOT BOX 点击 RESIN 切片时反复崩溃，更新驱动 / 重装软件 / 恢复出厂后仍复发；去掉仅因机型名含 resin 而误标的「树脂适配与气味」。 |
| post:119033 | Parts and service | 负面 | 计 | 备件无官方购买渠道、需 PayPal 转账且核验流程冗长，用户明言「a good reason to look at other printers」；属明确流失风险，去掉「树脂适配与气味」。 |

# 三、纪律与边界

1. 问题点只取 `resin_config.json` 的 12 类受控词表，长尾描述写进 `summaryCn`；本次 6 条机械故障未自造类目。
2. 正面样本仅 1 条且均有原文明证，未为平衡情感分布硬标；论坛样本天然偏负面，页面与报告不得外推。
3. `confirmed=true` 后 `_resin_prelabel.py` 不再覆盖；如需改判，直接编辑 `_resin_labels.json` 并重跑注入与建页。
4. 中文译文与摘要由本脚本的 `TRANSLATIONS` 提供，日更新增条目须由 10:00 增量链内补译后写入 `_resin_tr.json`。
