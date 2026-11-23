#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_k3_inject_candidates.py — 把 B站 / Reddit 候选池里**已标注**的条目注入 creality-k3.html

为什么需要这一步（而不是让采集器直接写页面）：
  `sentiment` / `topics` / `dimensions` / `problemPoints` / `summaryCn` 是语义判断，
  自动猜会把噪声写成结论。所以采集器产出候选池，本脚本承载人工/模型的标注结果。

标注纪律（规范 §三 / §四）：
  - `topics` 只能用页面 TOPIC_META 的键；
  - `dimensions` 一级/二级只能沿用页面已有取值（否则维度面板会碎成一地长尾）；
  - `summaryCn` / `translation` / `originalText` **不得出现 ASCII 双引号**（P4 闸门）。
    英文原文里的 " 一律降级为 '，中文语境用「」。

用法：
  python _k3_inject_candidates.py            # 预检，不写文件
  python _k3_inject_candidates.py --apply    # 真正写入
"""
import os
import re
import sys
import json
import argparse
import datetime
import importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(HERE, "creality-k3.html")
# 运行日 = 入库日（`date` 字段），可用 --date 覆盖
DATE = datetime.date.today().strftime("%Y-%m-%d")
TODAY_TAG = DATE.replace("-", "")
CANDS = os.path.join(HERE, "_k3_candidates_%s.json" % TODAY_TAG)


def load_engine():
    spec = importlib.util.spec_from_file_location("_k3_engine", os.path.join(HERE, "_k3_feishu_delta.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ENG = load_engine()

# ---------------------------------------------------------------- 标注表
# key = sourceLink；未标注的候选会被跳过并告警（不猜、不自动补）。
LABELS = {
    # ========== 2026-11-23 新增（窗口 11-16~11-22，展示/开箱类 → 动态档只计声量）==========
    "https://www.youtube.com/watch?v=PS-lIe0EdjI": dict(
        sentiment="中性", topics=[], dimensions=[], problems=[],
        summary="用 K3 打印桌面摆件的创作展示视频，标题与简介均为作品展示与话题标签，无使用缺陷或观点反馈，本期只计声量。",
        trans="用 Creality K3 打印的桌面小摆件展示，看看 Wekster 带来的又一个充满个性的创作。",
        competitor="", p0=False, kind="动态"),
    "https://www.youtube.com/watch?v=3mtxHtoY9MA": dict(
        sentiment="中性", topics=[], dimensions=[], problems=[],
        summary="用 K3 快速完成多色 GTA VI 手柄支架的创作展示，简介只强调快速完成多色项目，无问题反馈，计声量。",
        trans="用我的 Creality K3 快速完成这个多色 GTA VI 手柄支架项目！",
        competitor="", p0=False, kind="动态"),
    "https://www.youtube.com/watch?v=cVjMJN2AEYc": dict(
        sentiment="中性", topics=[], dimensions=[], problems=[],
        summary="K3 四喷嘴换色减少废料的科普型短视频：4 个喷嘴、5 秒内换色、少浪费。属产品卖点复述，无用户实测观点，动态档。",
        trans="废料太多？该升级了！4 个喷嘴，5 秒内换色，更少浪费，更多创意！",
        competitor="", p0=False, kind="动态"),
    "https://www.youtube.com/watch?v=8iw6qHgigXk": dict(
        sentiment="中性", topics=[], dimensions=[], problems=[],
        summary="用 SparkX i8 仅 4 种耗材打出 16 种色阶的多色展示视频，简介为创作挑战，无缺陷反馈，计声量。",
        trans="只用 4 种耗材能打出 16 种不同色阶吗？用全新的 Creality SparkX i8 一小时内打印完成！",
        competitor="", p0=False, kind="动态"),
    "https://www.youtube.com/watch?v=VCjoDadBvpI": dict(
        sentiment="中性", topics=[], dimensions=[], problems=[],
        summary="西语 K3 参数介绍视频，简介罗列 CoreXY 架构、KliTek 四喷嘴四通道等规格，属规格科普，无使用观点，动态档。",
        trans="Creality K3 全新多喷头打印机。给极客的参数：CoreXY 架构、KliTek 系统，4 个喷嘴配 4 条耗材通道。",
        competitor="", p0=False, kind="动态"),
    "https://www.youtube.com/watch?v=UmSZIZ14uLw": dict(
        sentiment="中性", topics=[], dimensions=[], problems=[],
        summary="用 K3 与 SparkX i8 制作圣诞挂件的节日创作展示，简介为作品分享，无观点反馈，计声量。",
        trans="3D 打印圣诞挂件！本季第一个圣诞装饰作品，用 K3 和 SparkX i8 打印。",
        competitor="", p0=False, kind="动态"),
    "https://www.youtube.com/watch?v=ZbNX8MZxibM": dict(
        sentiment="中性", topics=[], dimensions=[], problems=[],
        summary="用 SparkX i8 打印全彩光影画、仅用迷你冲刷塔的多色创作展示，简介强调零冲刷浪费属卖点复述，动态档。",
        trans="用 Creality SparkX i8 打印全彩光影画，几乎零冲刷废料，只用了一个迷你的小塔！",
        competitor="", p0=False, kind="动态"),
    "https://www.youtube.com/watch?v=polfj3FPb2I": dict(
        sentiment="中性", topics=[], dimensions=[], problems=[],
        summary="用 K3 打印披萨形状糖果盒的创作展示视频，简介为作品分享，无问题反馈，计声量。",
        trans="披萨之夜？不如说是糖果时间！一个披萨形状的糖果盒，带点小巧思。",
        competitor="", p0=False, kind="动态"),
    "https://www.youtube.com/watch?v=BAruSKZzFIk": dict(
        sentiment="中性", topics=[], dimensions=[], problems=[],
        summary="用 K3 多喷嘴多色打印披萨模型的创作展示，简介为作品来源与工艺说明，无观点，动态档。",
        trans="用 Creality K3 多喷嘴多色打印的披萨模型，模型来自 Creality Cloud。",
        competitor="", p0=False, kind="动态"),
    "https://www.youtube.com/watch?v=MTQuBQnATFI": dict(
        sentiment="中性", topics=[], dimensions=[], problems=[],
        summary="用 Sermoon P1S 3D 扫描仪为 K3 制作顶盖的配件创作视频，简介为制作过程说明，无 K3 使用观点，计声量。",
        trans="我用 Creality Sermoon P1S 3D 扫描仪为全新的 Creality K3 打印机制作了一个顶盖。",
        competitor="", p0=False, kind="动态"),
    "https://www.youtube.com/watch?v=MJJJ_LwpkuU": dict(
        sentiment="中性", topics=[], dimensions=[], problems=[],
        summary="K3 规格与初印象视频，简介称涵盖开箱、规格与打印结果，但未给出明确好坏判断，按规范判动态档只计声量。",
        trans="Creality K3 规格与初印象：这个视频涵盖开箱、规格与打印效果。",
        competitor="", p0=False, kind="动态"),
    "https://www.youtube.com/watch?v=6KK7CqLhrwU": dict(
        sentiment="中性", topics=[], dimensions=[], problems=[],
        summary="葡语短视频：用 K3 花 50 多小时多色打印浩克与毒液合体模型，简介为创作展示，无观点，动态档。",
        trans="如果浩克被毒液感染会怎样？用 Creality K3 花 50 多小时多色打印出这个组合！",
        competitor="", p0=False, kind="动态"),
    "https://www.youtube.com/watch?v=lpGt0lwm1fg": dict(
        sentiment="中性", topics=[], dimensions=[], problems=[],
        summary="K3 值不值得买的评测视频，但简介仅为标题复述与购买链接，无实质观点可提取，按规范判动态档，不猜内容。",
        trans="Creality K3 评测：这台 3D 打印机值得买吗？",
        competitor="", p0=False, kind="动态"),
    "https://www.youtube.com/watch?v=xzhS9xR3vR4": dict(
        sentiment="中性", topics=[], dimensions=[], problems=[],
        summary="K3 开箱、设置与首次测试打印的流程视频，简介为教程引导，无使用观点，计声量。",
        trans="准备好上手 Creality K3 了吗？跟我一起开箱、完整设置并跑第一次测试打印。",
        competitor="", p0=False, kind="动态"),
    "https://www.youtube.com/watch?v=bknSatrmwss": dict(
        sentiment="中性", topics=[], dimensions=[], problems=[],
        summary="POV 形式的 K3 开箱短视频，简介为场景化展示与话题标签，无观点反馈，动态档。",
        trans="POV：你的新 Creality K3 刚到货。",
        competitor="", p0=False, kind="动态"),
    "https://www.youtube.com/watch?v=C3vSDss2zNE": dict(
        sentiment="中性", topics=[], dimensions=[], problems=[],
        summary="K3 开箱即用多色高速打印的展示短视频，简介为话题标签，无实质观点，计声量。",
        trans="K3 开箱即用的多色打印，速度前所未有！",
        competitor="", p0=False, kind="动态"),
    "https://www.bilibili.com/video/BV1i4sP6qEsy": dict(
        sentiment="中性", topics=[], dimensions=[], problems=[],
        summary="B站南极熊转发的极限测试视频：100 小时、1 万次换头、0 失败，候选简介仅为标题与外链，属转发展示，动态档。",
        trans="100 小时、1 万次换头、0 失败，创想三维 K3 的极限在哪？",
        competitor="", p0=False, kind="动态"),

    # ========== 2026-11-20 新增（窗口 11-17~11-20，YouTube 第三方长期使用/实测口径）==========
    "https://www.youtube.com/watch?v=NS4n-9tMFBU": dict(
        sentiment="正面", topics=["kliTek", "multicolor"],
        dimensions=["硬件性能 - 多喷头系统", "日常使用体验 - 稳定性"],
        problems=["（正向：一个多月长期使用后整体满意，KliTek 四喷嘴切换约 5 秒）"],
        summary="海外用户使用 K3 一个多月后的正面总评：明确表示喜欢这台机器，KliTek 在 4 个喷嘴间切换约需 5 秒，多色换色不需要长距离进退料。属长期使用场景的正向反馈，可与首发期「换色耗时」的质疑形成对照。",
        trans="我用 Creality K3 已经一个多月了，我很喜欢它。KliTek 系统在最多 4 个喷嘴之间切换大约只要 5 秒，所以换色时不用把旧料退回去再冲刷。",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=6ZByRwMduxs": dict(
        sentiment="正面", topics=["kliTek", "multicolor"],
        dimensions=["硬件性能 - 多色系统", "使用成本与兼容性 - 耗材浪费"],
        problems=["（正向：5 小时以上多色连续打印，废料相较单喷嘴冲刷方案明显更少）"],
        summary="长时多色实测：连续打印 5 小时以上，作者展示的废料量很少，并把原因归给 K3 的 4 喷嘴换头方案——颜色切换靠换喷嘴而不是把颜色从同一个喷嘴冲刷出去。可作为「多色废料」这一最常被质疑项的正向实测样本。",
        trans="超过 5 小时的多色 3D 打印，看看我们产生的废料有多少！这就是为什么 Creality K3 配 4 个喷嘴的原因——换色时它直接换喷嘴，而不是让同一个喷嘴把颜色冲出来。",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=99x01CDwVHI": dict(
        sentiment="中性", topics=["kliTek", "multicolor"],
        dimensions=["硬件性能 - 多色系统"],
        problems=["（说明：采用换喷嘴方案，因此整机不需要冲刷槽，废料与冲刷塔随之减少）"],
        summary="解释性内容：回应「K3 为什么没有冲刷槽」，指出机器会切到已经装好下一种颜色的喷嘴，因此不需要把颜色从单一喷嘴冲刷出来。属对产品设计逻辑的科普，不含使用缺陷，本期计声量但归为动态。",
        trans="为什么 Creality K3 没有冲刷槽？因为 K3 是多色打印机，它换到一个已经装好下一种颜色的喷嘴上，所以不需要冲刷。",
        competitor="", p0=False, kind="动态"),
    # ========== 2026-11-16 新增（B站 铜牌杰瑞 K3 评测，仅简介有观点 → 动态档）==========
    "https://www.bilibili.com/video/BV1tfWB6SE7u": dict(
        sentiment="中性", topics=[], dimensions=[], problems=[],
        summary="B站 UP「铜牌杰瑞」的 K3 评测与 KliTek 拆解（5:27，播放 2098 / 评论 20）：核心判断是混合喷嘴要选对使用场景，小模型上用大喷嘴打支撑不一定划算。属第三方评测视频主体，简介只有一句场景判断、无缺陷反馈，本期只计声量。",
        trans="创想三维K3评测+KliTek™拆解 混合喷嘴打印要找到适合的场景，小模型上用大喷嘴打印支撑不一定带来好处。",
        competitor="", p0=False, kind="动态"),
    # ========== 2026-11-13 新增（YouTube / The Next Layer 赞助极限测试）==========
    "https://www.youtube.com/watch?v=3kqcx5s3TEU": dict(
        sentiment="中性", topics=["kliTek", "multicolor"],
        dimensions=["硬件性能 - 多色系统", "软件与交互 - 固件"],
        problems=["多色默认 prime volume（废料塔挤出量）偏大，需手动下调约三分之二才明显省料，存在质量权衡",
                  "首发固件存在若干能力限制，靠后续更新补齐（视频称更新修复了大部分，仍有少量待完善项）"],
        summary="受 Creality 赞助的 K3 一周极限测试：梳理 8 项 quirks、实测多色废料优化，固件更新修复大部分限制，仍有待完善。",
        trans="我花了一周试图摸清 Creality K3 的极限……结果一次重大软件更新把大部分问题都修好了。本视频由 Creality 赞助。创想凭借 K3 和 KliTek 喷嘴切换技术杀入换头打印机赛道，我整理了下单前该知道的 8 个最有趣的怪癖与特性。真正的多材料打印能力还要等即将推出的 Creality TPU 套件解锁。目前我想测的是出厂状态 K3 的多色打印表现、原厂设置能推到什么程度：试了全光谱混色、用第三方耗材跑自动压力提前校准，还把 prime 体积砍到默认的三分之一——究竟能省多少料才会开始影响打印质量？就在我以为测试快结束时，创想推送了一个固件更新，所以我尽量把变了什么、还有哪些需要打磨展示给你看。",
        competitor="", p0=False),
    # ========== 2026-11-09 首批到手用户（Reddit 13 条候选里挑 4 条）==========
    # 口径：只收「真实到手 / 真实打印」的一手内容；媒体转述、官方短片、纯玩梗帖不收。
    # problemPoints 一律落在 PROBLEM_MERGE 的 16 类关键词内（发货 / 配套 / 噪音 / CFS）。
    "https://www.reddit.com/r/crealityk3/comments/1xq1u87/my_creality_k3_showed_up_friday_afternoon_via/": dict(
        sentiment="中性", topics=["ecosystem", "build"],
        dimensions=["日常使用体验 - 开箱装配", "软件与交互 - 固件"],
        problems=["首次开机装不上最新固件，自检无法执行，只能先跳过自检再手动升级（固件升级与自检流程配套不上）"],
        summary="r/crealityk3 首批到手用户记录（11-06 联邦快递送达）：约 30 分钟完成装配，说明书易懂、各部件装配顺畅，最费劲的是整机偏重、需两人抬上桌再进机柜；唯一问题是首次开机固件装不上，自检因此无法执行，只能跳过自检、等系统加载后手动升级。属首批典型的「硬件装配顺、首启流程卡壳」样本。",
        trans="我的 K3 周五下午通过联邦快递到了（11-06-2026）。收货后大约 30 分钟就装完了，说明书很好懂，各部件装配都很顺利。最费劲的是把这台大家伙抬上桌子、再抬进柜子，比我之前那台重多了。唯一的问题出在首次开机：它装不上最新固件，而固件不装好自检就跑不了。我只能先跳过自检，等系统加载完再手动升级固件，之后就正常启动并重启了。",
        competitor="", p0=False),
    "https://www.reddit.com/r/crealityk3/comments/1xq1q5y/my_first_creality_k3_print_multi_color_benchy/": dict(
        sentiment="正面", topics=["multicolor", "noise"],
        dimensions=["硬件性能 - 多色系统", "日常使用体验 - 噪音"],
        problems=["打印过程中噪音偏明显（原文未给分贝实测）"],
        summary="同批到手用户装好固件后打出第一件多色作品：创想云下载的四色小船，4 小时完成、约 400 次换色，自检全过、无失败打印。用户称换色「确实非常快」，仅提到打印时偶有噪音偏大。是首批用户对 KliTek 高频换色可靠性的一次正向实证（400 次换色 0 失败），噪音属可接受范围内的轻微抱怨。",
        trans="我的第一件 K3 打印作品——多色小船。周五晚上打完的，是从创想云下载的特别版多色小船，打了 4 小时、4 种颜色、大约 400 次换色。开机设置时遇到一点小波折，前面提过；装好最新固件后机器顺利启动、自检也全部通过，没有任何问题。看它打这只小船真的很惊艳，换色确实非常快。打印时有些时候声音偏大，但也就那样，不算什么。",
        competitor="", p0=False),
    "https://www.reddit.com/r/CrealityCloud/comments/1xq55fv/sharing_my_first_multicolor_3d_prints_on_the/": dict(
        sentiment="正面", topics=["multicolor", "slicer"],
        dimensions=["硬件性能 - 多色系统", "日常使用体验 - 效率"],
        problems=[],
        summary="r/CrealityCloud 用户从 K2 系列迁移到 K3 后的首批多色实测：核心变化是「不再需要预先按颜色切分的多色文件」，混色、零擦料废料与打印工作流随整件切片一起完成，工作流明显简化。用户按混色、零废料、工作流三点分别给出一手反馈。原文采集在第一条论述处截断，细节需回原帖补齐。",
        trans="分享我在 K3 上的第一批多色打印（混色、零擦料废料，以及打印工作流）。我从 K2 系列换过来，这台机器上多色的行为方式带来了真正的工作流变化：第一，工作流转变——不再需要预切分的多色文件。以前做多色打印，往往要先找到或准备好专门按颜色切分的文件……（原文采集在此截断）",
        competitor="", p0=False),
    "https://www.reddit.com/r/Creality/comments/1xpqqos/you_know_what_everyone_wants_when_they_preorder/": dict(
        sentiment="负面", topics=["support", "ecosystem"],
        dimensions=["售后与服务 - 订单与客服", "生态与配套 - 耗材"],
        problems=["发售后仅以邮件通知发货推迟到月底", "随机附赠四卷耗材全为绿色且不带 RFID 标签，CFS 无法识别"],
        summary="r/Creality 预订用户吐槽交付与随机耗材：发售后只收到一封邮件通知发货推迟到月底；随机的四卷耗材全是绿色，且不带 K3 读取所需的 RFID 标签，CFS 认不出，而机器本身还要再等数周。用户明确表示「已经开始有点后悔这次购买」。涉及发货沟通、随机耗材配色与 RFID 标签三个可修正点，属首批预售履约环节的负面情绪样本。",
        trans="你知道大家预订 K3 之后最想要什么吗？他们想要在发售后收到一封邮件，说发货推迟到月底……好吧，行吧，虽然烦人但也算了。但他们真正想要的是——买第一台多色打印机、随机附四卷耗材的时候——四卷全是绿色！而且不只是四卷绿色，还是四卷没有 RFID 标签的耗材，而我们还要再等好几周的那台 K3 恰恰要读这个标签……我和老公已经有点后悔这次购买了。",
        competitor="", p0=True),
    # ========== 2026-11-06 反解恢复：8 条历史标注误删后从页面回写 ==========
    # 起因：清理重复键时删除范围过大，连带删掉 11-02/11-03 的原始标注。
    # 来源：creality-k3.html 中 K3_FEEDBACK_DATA 已固化的条目（summaryCn/translation/
    # problemPoints/competitorMentioned/isP0 一一映射回 LABELS），内容与写入时一致。
    "https://www.iesdouyin.com/share/video/7703534043953974528": dict(
        sentiment="中性", topics=["nozzle", "slicer"],
        dimensions=["软件与交互 - 切片软件", "硬件性能 - 速度"],
        problems=["单个打印件所有喷嘴必须共用同一层高，无法按口径分工", "层高受最小喷嘴口径限制，0.4 与 0.8 组合最高只能到 0.3 至 0.32 左右", "大口径喷嘴提速不明显，用料反而增加"],
        summary="抖音 UP 主用 K3 实测不同口径喷嘴混打（9 赞 / 1 评论）：发现单个打印件所有喷嘴只能共用一套层高、不能按口径分别设置，层高还受最小口径限制，0.4 配 0.8 最高只能到 0.3 至 0.32 左右，导致 0.8 的出料优势难以发挥，实测提速不如预期且用料增加；要发挥大口径还得配合更高层高、更少墙数和更低填充。",
        trans="不同口径喷嘴混打真的更快吗？按理说口径越大打印越快，但实测下来速度提升并不明显，用料反而增加不少。想让大口径喷嘴真正发挥优势，还得配合更高的层高、更少的墙数和更低的填充比例。最近用创想三维 K3 专门测了不同口径混打：所有喷嘴只能使用相同层高，原本以为大喷嘴负责填充、小喷嘴负责精细，实际切片时单个打印件必须共用一套层高；层高还受最小喷嘴口径限制，0.4 和 0.8 组合最多只能到 0.3 至 0.32 左右，大口径的出料优势就很难完全发挥。",
        competitor="", p0=False),
    "https://www.iesdouyin.com/share/video/7702114605555830059": dict(
        sentiment="正面", topics=["build", "multicolor"],
        dimensions=["日常使用体验 - 开箱装配", "硬件性能 - 机械结构"],
        problems=["CFS 四个耗材架侧面无编号标识，四路装填容易装错位"],
        summary="抖音 UP 主 K3 开箱组装实录（19 赞 / 5 评论）：核对配件盒、自动送料器与四个热端，认为包装泡沫和机身用料比同级机型更扎实、整机明显更重，PEI 纹理板与四路耗材架已就位；同时指出耗材架侧面没有编号标识，只能按左一二右三四放置。",
        trans="创想的 K3 到了，10 月 15 号，正式开箱。这是创想三维新发布的 K3 四头多色打印机，评测分两期，一期开箱组装，一期实测打印。外包箱尺寸和闪铸 C5 差不多，但掂起来重很多。配件盒里有说明书、扳手、螺丝、特氟龙管、四个热端和一小卷耗材，旁边是自动送料器，26 年新品基本都用 CFS 配件。泡沫比 C5 那台更厚实，机身用料也很扎实，非常重。工具头和展会上看到的一致，废料槽上有个小磁铁。打印板是 PEI 纹理板，四个耗材架上有标序号，但侧面没有任何数字标识、长得都一样，按左边一二、右边三四放上去。",
        competitor="", p0=False),
    "https://x.com/H22vok/status/2117016051984830561": dict(
        sentiment="中性", topics=["price", "kliTek"],
        dimensions=["市场与定价", "竞品对比"],
        problems=[],
        summary="阿拉伯语用户在他人求推荐时回复：建议选 K2 Pro，或者再等等看 K3；若不想折腾可直接买 Bambu P2S，或再等等 P3S。显示 K3 在选购语境里被当作「可以等一等再看」的选项，而非首选。",
        trans="我建议你选 Creality K2 Pro，或者再等一等、等 K3 出来。如果你不想折腾，那直接买 P2S 更省心，说不定过阵子 P3S 也要出了。",
        competitor="Bambu Lab", p0=False),
    "https://www.xiaohongshu.com/explore/6ae6ae05000000001b01c173?xsec_token=ABZMlQqwmJlWP51bNY5iuF1RcaS9o166QS7uIoVL9UDkY=&xsec_source=pc_feed": dict(
        sentiment="正面", topics=["multicolor", "tpu"],
        dimensions=["日常使用体验 - 效率", "售后服务与社区"],
        problems=[],
        summary="小红书用户为 TPU 混打与多色专门购入 K3，称 PLA / PETG 打印顺滑、多色很省料，到手固件有小问题但客服很快安排专人跟进解决，目前使用正常，正在等 TPU 打印套件。是首发期少见的「问题被解决」型正面样本。",
        trans="K3 打印多色真的很省料，为了 TPU 混打和多色专门买的，PLA 和 PETG 打起来很丝滑。到手固件有一点小问题，联系客服后很快安排专人跟进解决，目前机器一切正常，等着 TPU 套件。",
        competitor="", p0=False),
    "https://x.com/PatrickLebel9/status/2115980837804245254": dict(
        sentiment="负面", topics=["kliTek", "support"],
        dimensions=["市场宣传", "品牌信任"],
        problems=["评测集中在陌生频道，可信度未经第三方验证", "疑似按官方宣传口径出稿，宣传与实测存在落差"],
        summary="X 用户注意到 K3 的推广集中在自己没听说过的 YouTube 频道上，怀疑与官方的评测指导有关。属对首批评测中立性的质疑，会影响观望用户对「首发好评」的采信度。",
        trans="我发现创想在把 K3 推给我从没听说过的那些 YouTuber，我猜这和他们给的评测指引有关？",
        competitor="", p0=False),
    "https://www.xiaohongshu.com/explore/6ae2ed960000000003014305?xsec_token=ABkKNP3Hqz0u_JUhS3IfcK7U3X4p47kfbmdqt1ndtCNGM=&xsec_source=pc_feed": dict(
        sentiment="中性", topics=["material", "nozzle", "tpu"],
        dimensions=["生态与配套"],
        problems=["打 ABS / PC 需自加顶罩否则易翘边", "多口径喷嘴套件尚未上架", "85A 软胶套件尚未上架", "配套配件缺少官方选购说明"],
        summary="小红书新用户 K3 到手后求助辅助配件：已知防潮重要、先买了干燥盒，但打 ABS / PC 需自行加顶罩防翘边，多口径喷嘴与软胶套件都还没上架，想玩 0.2mm 细节或 85A 软胶只能等。反映首发期配件生态与新手引导的缺口。",
        trans="K3 终于到了，第一台多喷嘴机器还在摸索。听说防潮重要已经先买了干燥盒，但看论坛说打 ABS 或 PC 必须加顶罩不然翘边，多口径喷嘴套装和软胶套件也都还没上架，想玩 0.2 细节或 85A 软胶还得等。有没有老车主给点必买配件建议。",
        competitor="", p0=False),
    "https://x.com/TheRedRanga/status/2115810915601772790": dict(
        sentiment="中性", topics=["ecosystem", "price"],
        dimensions=["市场与定价", "社区与期待"],
        problems=["多头机半年即被淘汰，旧机型迭代过快"],
        summary="X 用户感叹 K3 刚发布就已注定半年后被淘汰，同时说明自己只用过创想、整体满意但缺乏对比基准。属对旗舰迭代节奏的旁观式吐槽，非产品缺陷反馈。",
        trans="K3 才刚出，当然半年后所有东西都会过时。我一直只用创想，整体挺满意，但确实没别的可对比。",
        competitor="", p0=False),
    "https://www.iesdouyin.com/share/video/7701196205875020529": dict(
        sentiment="负面", topics=["kliTek", "sensor"],
        dimensions=["硬件性能 - 挤出/送料", "软件与交互 - 固件"],
        problems=["换喷嘴后空打仍未解决，喷嘴与耗材进给状态无法自检", "切换喷嘴时报错，怀疑耗材未卡到位", "无法判断是固件还是机械故障，需官方说明"],
        summary="抖音用户反馈升级固件后空打依旧，切换喷嘴时出现报错，质疑是耗材没有卡到位、还是固件或机器本身有问题。属首发期进退料与换嘴流程的实操阻塞，无错误码可对照。",
        trans="更新好固件后 K3 的空打还没有解决，切换喷嘴出来就报错，这是没有卡进耗材？固件问题还是机器有问题。",
        competitor="", p0=True),
    # ========== 2026-11-06 清存量：豆包池 11 条，标注并入 10 条 ==========
    # 来源：_hub/pending_k3.json（豆包 10-30 ~ 11-02 投喂，长期滞留未标注）
    # 未并入 1 条：X「いいなーほしいなー」+ ShareLab 通稿标题，正文仅一句感叹、
    #   媒体信息不完整（无原文），与页面已有媒体条目重复计声量 → 判无效，见台账。
    "https://x.com/carvingrabbit/status/2116248236310835676": dict(
        sentiment="正面", topics=["build"],
        dimensions=["硬件性能 - 机械结构"],
        problems=["用户认可产品力但明确表示要等更大成型尺寸的版本才买",
                  "260mm 立方的成型空间对部分海外用户仍是决策门槛"],
        summary="日语用户对 K3 的简短评价：看起来不错，如果出大尺寸版本就会买。互动极低（0 赞），但信息点明确——产品力本身没有拦住他，拦住他的是成型尺寸。北美与日本市场对大件打印的需求高于国内，260mm 立方在多头机里不算小，但对家具级模型与批量件仍不够用。这类诉求在 K2、K3 Plus 的讨论里反复出现，可作为尺寸路线图的输入。",
        trans="哦——创想 K3 看起来不错啊。要是出大尺寸的就买了。",
        competitor="", p0=False),
    # 【判重不入页】https://www.iesdouyin.com/share/video/7703394694335679784
    # 抖音《多头多色新黑马，KliTek 技术好用吗》（159 赞）与页面已存 B 站 版本
    # K3-20261103-007（喵星考拉同稿）为同一评测的跨平台分发，论点逐条对应。
    # 按「同一主题不重复采集」跳过，避免同一条评测双计声量（2026-11-06 判）。
    # ========== 2026-11-05 增量（Tom's Hardware 首评测定的两种声量） ==========
    # 媒体口径：r/MakerNewsEN 转述 Tom's Hardware 完整评测（sourceType 已在候选池标为「媒体」）
    "https://www.reddit.com/r/MakerNewsEN/comments/1xnkpz1/creality_k3_reviewed_fourtool_changer_at_849/": dict(
        sentiment="正面", topics=["kliTek", "multicolor", "noise"],
        dimensions=["硬件性能 - 多色系统", "日常使用体验 - 噪音"],
        problems=["料盘架尺寸过大，Prusa / Cookiecad / Ambrosia 等第三方料盘装不进",
                  "开放式机身导致噪音偏高（原文采集在此截断，末句仅到 open）"],
        summary="Tom's Hardware 对 K3 的首个完整第三方评测，经 r/MakerNewsEN 转述：确认四工具头 KliTek、每头陶瓷加热 + 0.4mm 硬化钢嵌件喷嘴 + 独立料路、260×260×260mm、Core XY 直驱、最高 300°C；实测换头动作可靠、全程无失败打印、废料显著低于 AMS 一类系统——这是 K3 换头架构首次拿到权威媒体的正面功能验证，可直接用于对抗「换色耗时长」的既有印象。批评集中两处：料盘架过大，装不进 Prusa、Cookiecad、Ambrosia 的料盘（属可低成本修正的配件问题）；开放式机身导致噪音偏高。注意原文采集在噪音一句处截断，末句只到 open，完整结论需回原评测补齐。",
        trans="K3 评测：849 美元的四工具头换头机。Tom's Hardware 评测了创想 K3——一台搭载四个工具头（KliTek 系统）的换头打印机。每个工具头配陶瓷加热器、0.4mm 带硬化钢嵌件的喷嘴，以及独立料路。成型尺寸 260×260×260mm，Core XY、近端直驱，最高 300°C。评测称换头动作可靠、没有出现失败打印，废料远低于 AMS 一类系统。批评包括：料盘架尺寸过大，来自 Prusa、Cookiecad、Ambrosia 的料盘装不进……（原文采集在此截断）",
        competitor="", p0=False),
    # 社区口径：r/BambuLab 对同一评测标题的二次传播（属舆论定调，不是独立事实源）
    "https://www.reddit.com/r/BambuLab/comments/1xnfxqw/toms_hardware_didnt_even_wait_for_the_h3c_to_drop/": dict(
        sentiment="负面", topics=["price"],
        dimensions=["生态与软件 - 竞品对比", "硬件性能 - 多色系统"],
        problems=["媒体将产品定位判定为换头机而非规则改变者，被竞品 slogan 反衬",
                  "评测标题影响首发信心，价格说服力被削弱"],
        summary="r/BambuLab 用户转发并调侃 Tom's Hardware 的 K3 评测标题《It's a Tool Changer, not a game changer》——恰与 Bambu 给 H3C 的官方口号《Tool Changer. Game Changer.》逐词对照，认为 K3 在 H3C 正式发布前就已被媒体文字游戏定调。单条帖子本身是舆论噪声，但信号明确：竞品已把「Tool Changer」这个品类词先一步据为己有，K3 的换头卖点被动落入跟随者语境。与同批 MakerNewsEN 媒体条目同源（同一评测），统计声量时应视为一个事件的两侧，不要重复计数。",
        trans="Tom's Hardware 甚至没等 H3C 发布，就把 K3 给埋了。今天看到这个，笑到停不下来。Tom's Hardware 把他们的 K3 评测命名为《Creality K3 Review: It's a Tool Changer, not a game changer》。作为对照，Bambu 给 H3C 的官方营销口号字面就是：Tool Changer. Game Changer. K3 在 H3C 正式发布之前，就已经被科技媒体的文字游戏彻底烤熟了。",
        competitor="Bambu Lab H3C", p0=True),
    # ========== 2026-11-04 增量（海外一手社区 · Reddit RSS） ==========
    "https://www.reddit.com/r/Creality_k2/comments/1xmvg1q/k3_plus/": dict(
        sentiment="正面", topics=["price", "build"],
        dimensions=["硬件性能 - 机械结构", "生态与软件 - 竞品对比"],
        problems=["现款 K3 打印尺寸小于 K2，用户希望以 K3 Plus 补足",
                  "以 H3C 框架为参照提出产品仿制诉求，结构定位被认为易被竞品抢先"],
        summary="Reddit r/Creality_k2 用户向 Creality 喊话做 K3 Plus：认为 H3C 的框架非常适合照搬到 K3 Plus，希望在新机上沿用 K2 的更大打印尺寸、同时保持 Creality 一贯的定价，并直言做到这几点就会立刻下单；语气戏谑但购买意愿明确（RSS 未提供互动数）。",
        trans="好吧 Creality，看来你有作业可以抄了。在我看来 H3C 就是 K3 Plus 的完美框架！给它加上 K2 多出来的那点尺寸，再给个 Creality 的定价，那我的钱你就直接收走好了。",
        competitor="Bambu Lab H3C", p0=False),
    "https://www.reddit.com/r/crealityk3/comments/1xm3qn4/creality_k3_update_shipping/": dict(
        sentiment="中性", topics=["support"],
        dimensions=["售后与服务 - 订单与客服", "日常使用体验 - 开箱装配"],
        problems=["首批订单已发货，但附赠耗材未单独生成运单，用户怀疑被漏发"],
        summary="Reddit r/crealityk3 用户核对联邦快递账户发现 Creality 已于 11 月 1 日创建运单（59.5 磅、加州发出），据此推断整机已从中国运抵美国仓；但他没有收到随机附赠耗材的独立运单，怀疑被遗漏，并提到已有多人收到货（RSS 未提供互动数）。属交付环节的正向进展，附带一处履约瑕疵疑问。",
        trans="Creality K3 发货更新：我今早查了联邦快递账户，显示 Creality 在 11 月 1 日创建了运单，重量 59.5 磅，有单号，从加州发出。所以机器看起来已经从中国运到这边了。我没有收到那份应该随机的耗材的单独单号，我觉得他们可能漏了，因为我知道已经有很多人收到了。",
        competitor="", p0=False),
    # ========== B 站（国内社区 · UGC · 一手实测视频） ==========
    "https://www.bilibili.com/video/BV1hJpo6KEP9": dict(
        sentiment="正面", topics=["kliTek", "multicolor"],
        dimensions=["硬件性能 - 多色系统", "硬件性能 - 机械结构"],
        problems=["轻量化喷嘴快换的长期可靠性仍待验证"],
        summary="B站 UP 主万魔寺（3.0 万播放 / 106 条评论）实测 K3 轻量化喷嘴快换：认为用料做工、技术含量与打印质量相比前代是质的飞跃，但对快换机构的长期耐用性留有疑问。",
        trans="创想三维发布旗下首台搭载多喷嘴更换技术的 FDM 多色 3D 打印机，用料做工、技术含量与打印质量均有质的飞跃；本期视频深入拆解这台旗舰机 K3，追问轻量化喷嘴快换方案到底行不行。",
        competitor="", p0=False),
    "https://www.bilibili.com/video/BV1g7po6qEwd": dict(
        sentiment="正面", topics=["kliTek", "multicolor"],
        dimensions=["硬件性能 - 多色系统", "日常使用体验 - 效率"],
        problems=[],
        summary="B站 UP 主阿文菌kk 用满 200 小时后给出实测：以实际模型和数据回答多色打印能快多少、废料能省多少、质量如何，整体评价「非常意外」（2.3 万播放 / 107 条评论）。",
        trans="创想三维 K3 已经用了 200 多个小时，本期聊这台四喷嘴换头机的真实体验：多色打印到底能快多少、废料能省多少、打印质量怎么样，这次直接用实际模型和数据说话。",
        competitor="", p0=False),
    "https://www.bilibili.com/video/BV1gjpo6ME82": dict(
        sentiment="正面", topics=["kliTek", "multicolor"],
        dimensions=["硬件性能 - 多色系统", "日常使用体验 - 效率"],
        problems=["后期维护的麻烦程度被列入实测项"],
        summary="B站 UP 主一言智造实测 K3 的省时省料幅度：覆盖多色打印、全彩混色与 PLA+PETG 异料支撑三种场景，并把换头速度、废料量与后期维护麻烦程度一并纳入实测（2.6 万播放 / 56 条评论）。",
        trans="这次聊创想三维 K3，实打下来省时省料到底能有多少：打了多色、全彩混色、PLA+PETG 异料支撑；换头快不快、废料能省多少、后期维护麻不麻烦，这期直接看实测。",
        competitor="", p0=False),
    "https://www.bilibili.com/video/BV1xFp96pEhG": dict(
        sentiment="负面", topics=["kliTek", "build"],
        dimensions=["硬件性能 - 机械结构", "日常使用体验 - 装配"],
        problems=["首发批次存在一批小问题（视频内逐条展开）"],
        summary="B站 UP 主陌上路途汇总 K3 首发批次的小问题清单（464 播放 / 20 条评论），面向首批到手用户逐条展开，可作为品控问题的入口索引。",
        trans="3D 打印机创想三维 K3 首发小问题合集，需要的可以了解一下。",
        competitor="", p0=False),
    "https://www.bilibili.com/video/BV1DQpn6qEXn": dict(
        sentiment="中性", topics=["ecosystem"],
        dimensions=["市场与定价", "生态与配套"],
        problems=["首发机型有需要额外的留意事项，被提示看好再买"],
        summary="B站 UP 主陌上路途以「看好再买」为题提示 K3 首发机型的注意事项（720 播放 / 20 条评论），属于购买前的风险提示类内容。",
        trans="创想三维 K3 首发机型需要注意的地方，看好再买。",
        competitor="", p0=False),
    "https://www.bilibili.com/video/BV1aqp569EkQ": dict(
        sentiment="中性", topics=["kliTek"],
        dimensions=["日常使用体验 - 开箱装配"],
        problems=[],
        summary="B站 UP 主陌上路途发布 K3 首发平民视角初体验（451 播放 / 18 条评论），聚焦普通用户到手后的上手感受。",
        trans="创想三维 K3 首发平民初体验。",
        competitor="", p0=False),
    "https://www.bilibili.com/video/BV1Fcpi6ZEhg": dict(
        sentiment="中性", topics=["kliTek"],
        dimensions=["日常使用体验 - 开箱装配", "社区与期待"],
        problems=[],
        summary="B站 UP 主（2652 播放 / 57 条评论）发布 K3 初步体验并公开征集问题，评论区成为首批到手用户的问题集中出口。",
        trans="创想三维 K3 初步体验，有啥问题可以问，这周放假再玩一玩。",
        competitor="", p0=False),
    "https://www.bilibili.com/video/BV1Zkpp6HEZ9": dict(
        sentiment="中性", topics=["price"],
        dimensions=["市场与定价", "品牌信任"],
        problems=["4599 首发价被拿来单独讨论是否值得"],
        summary="B站 UP 主星月造物工坊以「4599 还值得买吗」为题展开 K3 定价讨论（4464 播放 / 183 条评论），是首发期价格争议最集中的讨论场之一。",
        trans="创想三维 K3 价格 4599，还值得买吗。",
        competitor="", p0=False),
    "https://www.bilibili.com/video/BV19tHS6XEZs": dict(
        sentiment="中性", topics=["kliTek", "multicolor", "ai", "tpu"],
        dimensions=["硬件性能 - 多色系统", "软件与交互 - 切片软件"],
        problems=["标题堆叠卖点关键词，实测深度有限"],
        summary="B站 UP 主梦之长安发布 K3 实测拆解（828 播放），覆盖 4.8 秒换嘴、CMYK 物理混色、TPU 柔性打印与开源特性并列出优缺点；内容偏购买决策导览。",
        trans="创想三维 K3 实测体验：4.8 秒极速换嘴 + CMYK 物理混色，TPU 柔性打印强，开源桌面 3D 打印机，优缺点拆解，普通玩家该冲吗。",
        competitor="", p0=False),
    "https://www.bilibili.com/video/BV1nHeu6UEuH": dict(
        sentiment="中性", topics=["kliTek", "multicolor"],
        dimensions=["硬件性能 - 多色系统", "硬件性能 - 机械结构"],
        problems=["四换头方案的实际易用性待验证"],
        summary="B站 UP 主一言智造的首台到手视频（7160 播放 / 15 弹幕 / 145 条评论），聚焦四换头方案的细节升级是否真正好用，是 K3 到手内容里播放量最高的一条。",
        trans="创想 K3 到了！四换头方案，细节升级真的好用吗。",
        competitor="", p0=False),

    # ========== Reddit（海外一手社区 · UGC） ==========
    "https://www.reddit.com/r/crealityk3/comments/1xfd7nh/this_is_what_creality_does_when_a_review_isnt/": dict(
        sentiment="负面", topics=["support"],
        dimensions=["售后服务与社区", "品牌信任"],
        problems=["免费送测的好评也被下架，用户质疑品牌对不完美评价的处理方式"],
        summary="海外用户发帖提醒：自己分享了一篇来自英国的 K3 好评（机器为厂商免费送测），但 Creality 仍以评价不够完美为由将其下架，引发对品牌对待用户反馈与评测态度的信任质疑。",
        trans="这就是 Creality 在一条评测不够完美时会做的事，记住这一点。我分享了一篇来自英国的 K3 好评，那台机器是免费送测给他的，可他们还是把它删了。",
        competitor="", p0=False),
    "https://www.reddit.com/r/3dprintIndia/comments/1x5gcog/best_multi_nozzle_printer_around_1l/": dict(
        sentiment="中性", topics=["material", "price"],
        dimensions=["市场与定价", "硬件性能 - 腔体/过滤"],
        problems=["K3 与 U1 都没有主动加热仓，只能靠改装补足", "1L 价位段竞品密集"],
        summary="印度用户以约 1 万卢比档预算横向比价：K3（1.07L）｜快造 U1（1.04L）｜闪铸 Creator 5 Pro（0.97L，带主动加热仓）｜X2D（1.15L）；明确表示主动加热仓是硬需求，K3 与 U1 都要靠改装。",
        trans="1L 左右最好的多喷嘴打印机：创想 K3 约 1.07L、快造 U1 约 1.04L、闪铸 Creator 5 Pro 0.97L（带加热腔）、还有 X2D 约 1.15L，哪台更好？我是重度用户，不介意折腾机器，但主动加热仓对我是刚需；我知道 K3 和 U1 都没有加热腔，不过这两台都能靠改装补上。",
        competitor="Snapmaker U1 / Flashforge Creator 5 Pro / Bambu Lab X2D", p0=False),
    "https://www.reddit.com/r/3Dprinting/comments/1x44ihw/creality_k3_preorder_849/": dict(
        sentiment="负面", topics=["price"],
        dimensions=["市场与定价", "品牌信任"],
        problems=["$849 预售价与 U1 完全相同，缺少差异化卖点", "被直接质疑 K3 是否上市即失败"],
        summary="Reddit 用户指出 K3 预售 $849 与快造 U1 定价完全相同，而 U1 刚在 Prime Day 卖到 $721，质疑 K3 相对 U1 的实际卖点是什么，并直接发问 K3 是否 DOA。",
        trans="创想 K3 预售 $849。考虑到这和快造 U1 定价一模一样，K3 是不是一出生就死了？U1 最近 Prime Day 还卖到过 $721。那 K3 相对 U1 真正的卖点到底是什么？",
        competitor="Snapmaker U1", p0=False),
    "https://www.reddit.com/r/crealityk3/comments/1x3t1l7/k3_is_live_now/": dict(
        sentiment="中性", topics=["ecosystem"],
        dimensions=["电商渠道", "市场与定价"],
        problems=["首发库存偏紧：加购 30 台结账只剩 21 台"],
        summary="用户实测首发开卖库存：加购上限 30 台，结账时被压到 21 台，据此判断首发库存可能偏紧。",
        trans="K3 现在开卖了。我往购物车加了 30 台（上限），结账时数量被压到 21 台，所以可能是在售罄。",
        competitor="", p0=False),
    "https://www.reddit.com/r/crealityk3/comments/1x3s1en/my_creality_k3_never_shipped/": dict(
        sentiment="非常负面", topics=["support", "ecosystem"],
        dimensions=["售后服务与社区", "品牌信任"],
        problems=["定金用户的机器到 10 月 12 日仍未发货", "用户已取消其中一笔订单", "对创想的履约能力失去信心"],
        summary="海外定金用户投诉 K3 未按承诺发货：10 月 12 日仍无发货消息，已取消其中一笔订单并考虑全部取消；用户表示现在理解为什么大家对创想如此不满。",
        trans="我的创想 K3 根本没发货。很遗憾，创想又一次没有兑现它展示过的东西。今天已经 12 号了。我取消了其中一笔订单，看他们怎么说，可能两笔都取消。我现在明白为什么大家对创想这么失望了。",
        competitor="", p0=True),
    "https://www.reddit.com/r/Creality/comments/1x3fkg0/creality_k3_on_tiktok_shop/": dict(
        sentiment="中性", topics=["price"],
        dimensions=["电商渠道", "市场与定价"],
        problems=[],
        summary="用户提示 K3 已在 TikTok Shop 开卖：$849，附赠 4 卷 1kg 耗材与 $40 优惠券，海外销售渠道从官网扩展到社交电商。",
        trans="创想 K3 上了 TikTok Shop，$849 可以买，送 4 卷 1kg 耗材和一张 $40 优惠券。",
        competitor="", p0=False),
    "https://www.reddit.com/r/Creality/comments/1x2im2t/k3_pre_order_start_oct_12_849/": dict(
        sentiment="负面", topics=["price", "ecosystem"],
        dimensions=["市场与定价", "品牌信任"],
        problems=["与 U1 同价，看不到买 K3 的理由", "发货要等到 11 月 2 日"],
        summary="美区预售规则公布（10/12–11/1 预订、11/2 起发货、赠 3 个月换新保障与 4 卷 Hyper PLA），但用户直言「和 U1 同价看不出买 K3 的理由」，并提到自己几天前刚趁促销入了台 U1。",
        trans="K3 预购 10 月 12 日开启，$849。预订期 10 月 12 日至 11 月 1 日（太平洋时间），额外提供 3 个月换新保障，再送 4 卷 Hyper PLA 耗材，开箱即打。发货从 11 月 2 日起。如果和 U1 定价一样，我真看不出买 K3 的好处；我几天前刚趁促销又买了一台 U1。",
        competitor="Snapmaker U1", p0=False),
    "https://www.reddit.com/r/Creality_k3/comments/1wpri7p/will_the_creality_k3_allow_multiple_filaments_per/": dict(
        sentiment="中性", topics=["multicolor", "ecosystem"],
        dimensions=["硬件性能 - 多色系统", "生态与配套"],
        problems=["CFS Hub 与四喷嘴组合成「每喷嘴多料」的混合架构是否支持，官方口径未明"],
        summary="海外用户追问 K3 能否通过 CFS Hub 实现「每个喷嘴多料」：换头已内置切刀、官方又宣布兼容 CFS，四喷嘴加上自动供料盒组成的工具切换/AMS 混合架构到底支不支持，官方始终没给明确答复。",
        trans="创想 K3 会允许通过 CFS Hub 让每个喷嘴用多种耗材吗（混合工具切换 / AMS 方案）？我一直在关注即将发布的创想 K3 和它的 KliTek 工具切换系统。众所周知它原生使用 4 个独立喷嘴来实现无废料的四色/多材料打印。不过，既然工具头内置了切刀，而创想又已经……",
        competitor="", p0=False),
    "https://www.reddit.com/r/crealityk3/comments/1wnqv9w/how_soon_after_rollout_will_the_obxidian_make/": dict(
        sentiment="负面", topics=["kliTek", "material"],
        dimensions=["使用成本与兼容性", "硬件性能 - 多色系统"],
        problems=["KliTek 原厂喷嘴寿命短，用户不愿每 3-6 个月更换", "第三方耐磨喷嘴何时适配未知"],
        summary="海外用户担心 KliTek 喷嘴寿命：不愿每 3–6 个月更换一次，尤其在使用工程材料、而系统又支持 8 个喷嘴时成本更高；追问 E3D ObXidian 何时推出 KliTek 兼容的耐磨喷嘴。",
        trans="ObXidian 要多久才会推出 KliTek 喷嘴的替换件？他们和创想合作很久了，出产品应该只是时间问题。我可不想每 3 到 6 个月就换一次 KliTek 喷嘴，尤其是系统有 8 个喷嘴、又打工程材料的时候。",
        competitor="E3D ObXidian", p0=False),
    "https://www.reddit.com/r/crealityk3/comments/1wmxa58/k3_deposit_holders_will_finally_be_getting_the_k3/": dict(
        sentiment="中性", topics=["ecosystem"],
        dimensions=["电商渠道", "售后服务与社区"],
        problems=["$50 定金用户的等待期被进一步拉长"],
        summary="直播信息汇总：付 $50 定金预订的用户将在 10 月第一周收到付款邮件、10 月中旬发货，定金用户的等待期被进一步拉长。",
        trans="K3 定金用户终于能在 10 月拿到机器——创想 K3 系列（KliTek）用户群。看了直播，那些抢到 $50 定金名额的幸运儿，Hanna 说付款邮件会在 10 月第一周发出，10 月中旬发货。",
        competitor="", p0=False),
    "https://www.reddit.com/r/Creality/comments/1x51fdx/early_reviews_of_the_k3_comingout/": dict(
        sentiment="中性", topics=["kliTek"],
        dimensions=["社区与期待", "市场宣传"],
        problems=[],
        summary="海外用户汇总 4 条 YouTube 早期评测链接，认为信息有价值但自评「自己用不上」；反映 K3 首发期海外评测内容集中释出的节奏。",
        trans="K3 的早期评测出来了。附四条链接。就我个人而言用途有限，但觉得能拿到更多信息挺不错。",
        competitor="", p0=False),
    "https://www.reddit.com/r/Creality/comments/1x1wl03/is_it_worth_waiting_for_the_k3/": dict(
        sentiment="中性", topics=["material", "price"],
        dimensions=["市场与定价", "硬件性能 - 腔体/过滤"],
        problems=["木工房粉尘环境需要封闭机身，K3 开放式结构在这点上不利"],
        summary="3D 打印新人纠结是否等 K3：原本准备在 Costco 下单 K2 套装（899 加元含 12 卷耗材），因打印机要放在木工房、防尘需要封闭机身，而 K3 的开放式结构在这点上不占优。",
        trans="等 K3 值得吗？我是 3D 打印新手，本来准备下单 K2 套装（Costco 899 加元，含 12 卷耗材）。机器会放在我的木工房里，所以有个封闭机身对防尘挺重要。我主要用它做点工具、家里的小修小补，以及孩子想要的各种玩具小玩意。最近关于 K2 的评论好像都……",
        competitor="Creality K2", p0=False),
    "https://www.reddit.com/r/Creality/comments/1x0qpw8/what_kind_of_nozzles_with_the_k3/": dict(
        sentiment="负面", topics=["kliTek", "material"],
        dimensions=["使用成本与兼容性", "硬件性能 - 机械结构"],
        problems=["喷嘴材质未公开（硬化钢 / 碳化钨 / 黄铜不明）", "宣称兼容增强材料，但喷头是否按此设计存疑", "担心喷头快速磨损"],
        summary="海外用户追问 K3 喷嘴材质：官方宣称兼容增强材料，却没说明喷头用的是硬化钢、碳化钨还是黄铜；若材质不匹配，喷头快速磨损的成本风险无人回答。",
        trans="K3 用的是什么喷嘴？我一直没找到相关信息：K3 会用哪种喷嘴？硬化钢？碳化钨？还是黄铜？我看到宣传里说兼容增强材料，但那是指喷头也是按这个设计的，还是说我们要预期它很快磨损？",
        competitor="", p0=False),
    "https://www.reddit.com/r/Creality/comments/1wwwr5s/anyone_waiting_waiting_to_here_reviews_about_the/": dict(
        sentiment="中性", topics=["multicolor", "ecosystem"],
        dimensions=["社区与期待", "生态与配套"],
        problems=["决定等第三方评测出来再买", "对官方「兼容 CFS」的承诺持保留态度"],
        summary="已持有 Ender 5 Max 与 K1 SE（双 CFS）的老用户表示：虽然想要多色工具切换机，但会等 K3 评测出来再买；官方称将兼容 CFS，用户希望这次承诺能兑现。",
        trans="有人在等 K3 的评测出来再买多喷嘴/工具切换机吗？我有台 Ender 5 Max，喜欢它的速度和尺寸；还有台 K1 SE，用两个 CFS 供料盒，所以不用手动换料。虽然我很想要多工具机，但还是打算等 K3 的评测。官方说它会兼容 CFS，希望这次能说到做到。",
        competitor="", p0=False),
    "https://www.reddit.com/r/Creality/comments/1wwvxqw/k3_max_or_deluxe/": dict(
        sentiment="负面", topics=["ecosystem", "price"],
        dimensions=["市场与定价", "品牌信任"],
        problems=["担心买了基础版一个月后就出更好的型号", "机型路线图不透明"],
        summary="用户询问是否会有 Deluxe / Max 版本，直言不想咬牙买了基础版、一个月后就出现更好的型号；反映首发期机型路线图不透明带来的观望情绪。",
        trans="K3 买 Max 还是 Deluxe？我想要一台多色打印机，显然在看 K3，因为它很快就要上市。但有没有 Deluxe 或 Max 版本的消息？我就是不想咬牙买了基础版，结果一个月后就出了更好的。",
        competitor="", p0=False),
    "https://www.reddit.com/r/Creality/comments/1wutkuq/k3_or_creator_5_pro/": dict(
        sentiment="负面", topics=["material"],
        dimensions=["硬件性能 - 腔体/过滤", "市场与定价"],
        problems=["没有主动加热仓，工程材料这一环输给 Creator 5 Pro"],
        summary="用户在 K3 与闪铸 Creator 5 Pro 之间纠结：K3 整体评价不错、规格接近，但没有主动加热仓，打工程材料这一环输给 Creator 5 Pro。",
        trans="K3 还是 Creator 5 Pro？我想入手一台新的工具切换 3D 打印机。K3 看起来很棒，但 Creator 5 PRO 能打工程材料；K3 虽然已经很接近，但没有主动加热仓。你们怎么看？",
        competitor="Flashforge Creator 5 Pro", p0=False),
    "https://www.reddit.com/r/Creality/comments/1wo2qv7/why_choose_between_speed_and_detail_a_deep_dive/": dict(
        sentiment="中性", topics=["nozzle"],
        dimensions=["官方口径", "硬件性能 - 多色系统"],
        problems=[],
        summary="创想官方技术长文解释多口径混打：喷嘴直径不再是打印前的固定设置，而成为打印策略的一部分，同一模型可按区域切换 0.2–0.8mm 口径。",
        trans="何必在速度与细节之间二选一？深入解析 K3 混口径打印。喷嘴直径通常在打印开始前就选定了，一旦选定，从第一层到最后一层都用同一口径。K3 改变了这一点：多口径打印让喷嘴直径不再只是一个打印前设置，而成为模型打印策略的一部分。",
        competitor="", p0=False),
    "https://www.reddit.com/r/Creality/comments/1wl3d0d/what_is_mix_nozzle_printing_on_k3/": dict(
        sentiment="中性", topics=["nozzle"],
        dimensions=["官方口径", "硬件性能 - 多色系统"],
        problems=[],
        summary="创想官方以视频形式科普「混口径打印」与传统单喷嘴打印的差异，并引导用户前往官方 K3 子版块；属厂商口径，不计入用户声量。",
        trans="K3 上的混口径打印是什么？它和传统单喷嘴打印有什么不同？混用喷嘴尺寸能实现什么？所有问题在一个视频里解答。",
        competitor="", p0=False),
    "https://www.reddit.com/r/3Dprinting/comments/1wovdpw/creality_k3_pricing_is_going_to_be_under_900/": dict(
        sentiment="负面", topics=["price", "support"],
        dimensions=["市场与定价", "品牌信任"],
        problems=["定价信息只出现在官方 Discord，社区版主删帖", "官方信息发布渠道不透明"],
        summary="用户转述官方 Discord 口径：K3 定价低于 $900、北美 10/12 开启预售；并指出该信息发到 r/Creality 后被版主删除，由此引发对官方信息渠道与社区管控的讨论。",
        trans="创想 K3 定价会低于 $900（发在这里是因为创想版主在他们自己的版块里把我的帖删了，但这些信息来自官方创想 Discord 和官方账号）。创想官方账号在 Discord 上说 K3 定价将低于 $900，北美预售 10 月 12 日开启。不知道什么原因，创想版块的版主在我发帖时把这条信息删掉了。",
        competitor="", p0=False),
    "https://www.reddit.com/r/3Dprinting/comments/1wnvd39/looking_at_the_k3_for_wearable_projects_how/": dict(
        sentiment="中性", topics=["tpu"],
        dimensions=["硬件性能 - 挤出/送料", "硬件性能 - 多色系统"],
        problems=["85A 软料的实际送料稳定性尚待验证"],
        summary="做可穿戴项目的用户关注 K3 的 TPU 能力：原本只用过 95A，想尝试更软的料，K3 标称可打到 85A，对 FDM 而言已相当软，实际送料表现待验证。",
        trans="在考虑用 K3 做可穿戴项目，不同 TPU 硬度到底有多大用处？我最近在多做定制的可穿戴物件，所以开始尝试 TPU。以前主要用 95A，现在想试试更软的 TPU 来做真正贴身的部件。K3 吸引我的一点是它能打到 85A，这对 FDM 来说已经相当软了。",
        competitor="", p0=False),
    "https://www.reddit.com/r/3Dprinting/comments/1wf2weh/creality_k3_will_have_k3_pro_and_k3_plus/": dict(
        sentiment="中性", topics=["ecosystem"],
        dimensions=["市场与定价", "硬件性能 - 机械结构"],
        problems=["基础版成型尺寸 260mm 与 K2 相同，被认为偏小"],
        summary="海外用户推测 K3 后续会有 Pro 与 Plus 版本：基础版 260mm 成型尺寸与 K2 相同，预计 Pro 上到 300mm、Plus 到 310×330mm；属社区传闻，官方未确认。",
        trans="创想 K3 会有 K3 Pro 和 K3 Plus。创想最近放出了 K3 的信息，但它的成型尺寸是 260mm，和 K2 一样。我觉得会有 K3 Pro 是 300mm，Plus 是 310×330。",
        competitor="Creality K2", p0=False),
    "https://www.reddit.com/r/3Dprinting/comments/1wd3d8d/whats_k3_native_root_access_actually_for/": dict(
        sentiment="中性", topics=["ecosystem"],
        dimensions=["软件与交互 - 固件", "社区与期待"],
        problems=["原生 Root 权限的实际用途不清晰，缺少面向普通用户的说明"],
        summary="用户不解 K3 把「原生 Root 权限」当卖点到底能做什么——对普通用户意味着什么、能解锁哪些能力，社区说法不一，官方也缺少面向新手的说明。",
        trans="K3 的「原生 Root 权限」到底是干什么用的？我玩 3D 打印有一阵子了，总看到大家讨论 root 权限，但说实话从没太在意。最近注意到创想 K3 把原生 Root 权限作为卖点之一，于是开始想自己是不是错过了什么。真正用 root 权限的人，它到底能带来什么？",
        competitor="", p0=False),

    # ========== 2026-10-15 新增（B站 UGC，首发期横向科普 / 开箱初体验） ==========
    "https://www.bilibili.com/video/BV1ZEpy67Ef3": dict(
        sentiment="中性", topics=["ecosystem"],
        dimensions=["市场与定价", "生态与配套"],
        problems=[],
        summary="B站 UP 主陌上路途（283 播放 / 3 条评论）逐台拆解创想三维 K3、快造 U1 与闪铸 C5 三台多喷嘴/多色机器的核心区别，属首发期横向科普，未下质量结论。",
        trans="创想三维 K3 和快造 U1 以及闪铸 C5 三台机器的详细区别。",
        competitor="Snapmaker U1 / 闪铸 C5", p0=False),
    "https://www.bilibili.com/video/BV12cpd6bEq6": dict(
        sentiment="中性", topics=["kliTek"],
        dimensions=["日常使用体验 - 开箱装配", "社区与期待"],
        problems=[],
        summary="B站 UP 主 blender布的（856 播放 / 4 条评论）发布 K3 开箱初体验：认为底子很好、前景值得期待，是首批到手用户的平民视角开箱。",
        trans="创想三维 K3 开箱视频：值得期待！刚发布，底子很好、前景有期待！",
        competitor="", p0=False),

    # ========== YouTube（海外视频 · 2026-10-15 接入 Data API v3 · 补 overseaVideo 缺口） ==========
    # ---- 官方号（sourceType=官方，不计入用户声量） ----
    "https://www.youtube.com/watch?v=xmhfAyJcR1k": dict(
        sentiment="中性", topics=["material", "nozzle"],
        dimensions=["官方口径", "硬件性能 - 多色系统"],
        problems=[],
        summary="创想官方发布 K3 工程篇宣传视频（1.7 万播放 / 203 赞 / 43 评论）：主打「不止于喷嘴、征服工程材料」，强调多喷嘴之外的材料适配能力；属厂商口径。",
        trans="工程视角的创想 K3：不止于喷嘴，征服各类工程材料。",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=TrPC9k6_I70": dict(
        sentiment="中性", topics=["ecosystem"],
        dimensions=["官方口径", "市场宣传"],
        problems=[],
        summary="创想官方 K3 预热短视频（6.7 万播放 / 306 赞 / 30 评论），以「一机两用」为卖点；属厂商口径。",
        trans="一机两用！",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=whln20PcbTI": dict(
        sentiment="中性", topics=["ecosystem"],
        dimensions=["官方口径", "市场宣传"],
        problems=[],
        summary="创想官方 K3 有奖竞猜活动视频（22.3 万播放 / 559 赞 / 217 评论），属营销活动引流，不计入用户声量。",
        trans="猜一猜，赢好礼！",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=y1xxgcKhHDI": dict(
        sentiment="中性", topics=["nozzle"],
        dimensions=["官方口径", "硬件性能 - 多色系统"],
        problems=[],
        summary="创想官方演示 K3 混口径打印（35.6 万播放）：同一模型用不同打印策略与口径，展示 0.2–0.8mm 多口径协同；属厂商口径。",
        trans="同一个模型，不同的打印策略！",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=saTIp3iz2pw": dict(
        sentiment="中性", topics=["nozzle"],
        dimensions=["官方口径", "硬件性能 - 多色系统"],
        problems=[],
        summary="创想官方科普 K3 混口径打印（19.0 万播放 / 158 赞 / 12 评论），解释多口径如何在同一模型上协同；属厂商口径。",
        trans="K3 的混口径打印是什么？",
        competitor="", p0=False),

    # ---- 用户（海外一手视频声量） ----
    "https://www.youtube.com/watch?v=IYg2C9FlS30": dict(
        sentiment="中性", topics=["kliTek"],
        dimensions=["硬件性能 - 多色系统"],
        problems=[],
        summary="Frankly Built（1524 播放 / 76 赞 / 3 评论）发布 K3 + KliTek 换嘴系统短视频快览，属首发期内容。",
        trans="搭载 KliTek 换嘴系统的创想 K3！",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=944DVHQnSFc": dict(
        sentiment="中性", topics=["kliTek", "multicolor"],
        dimensions=["硬件性能 - 多色系统", "社区与期待"],
        problems=["标题以问句抛出，是否名副其实待看实测"],
        summary="TheLayeredWorkshop（1210 播放 / 13 赞 / 1 评论）以「你一直在等的那台打印机吗」为问句发布 K3 评测，指向多色换头卖点是否兑现的期待。",
        trans="创想 K3……你一直在等的那台打印机吗？",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=rR3MNVrjPGg": dict(
        sentiment="中性", topics=["kliTek"],
        dimensions=["硬件性能 - 多色系统"],
        problems=[],
        summary="德国频道 Crydteam 3D-Druck（866 播放）实测 K3 四喷嘴工具切换系统（德语），海外德语区一手评测。",
        trans="创想 K3：四喷嘴工具切换系统实测。",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=VRPhVa1lKJA": dict(
        sentiment="中性", topics=["kliTek"],
        dimensions=["硬件性能 - 多色系统", "日常使用体验 - 效率"],
        problems=["7 秒换头是宣传口径，实际耗时以实测为准"],
        summary="Michael Lydick（648 播放）聚焦 K3 换头速度，标题质疑「7 秒换头」宣传口径，围绕换嘴实际耗时展开。",
        trans="创想 K3 换头只要 7 秒？！",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=c993sSFq6-E": dict(
        sentiment="中性", topics=["kliTek", "multicolor"],
        dimensions=["硬件性能 - 多色系统", "市场与定价"],
        problems=["四喷嘴是否值得的性价比疑问"],
        summary="Crydteamprinting（1467 播放）以「四个喷嘴值不值」为题评测 K3，围绕四喷嘴方案的实际价值与成本展开。",
        trans="创想 K3 | 四个喷嘴——值吗？",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=asKzTH4ZJRM": dict(
        sentiment="负面", topics=["kliTek"],
        dimensions=["硬件性能 - 机械结构", "市场与定价"],
        problems=["被质疑为 Snapmaker U1 的仿制品"],
        summary="越南频道 Meme 3D（2493 播放）以「K3 是 Snapmaker U1 的翻版吗」为题，质疑 K3 与快造 U1 的设计雷同，属竞品对比性质的首发讨论。",
        trans="创想 K3——Snapmaker U1 的翻版吗？！",
        competitor="Snapmaker U1", p0=False),
    "https://www.youtube.com/watch?v=NXyYcB4O2dA": dict(
        sentiment="中性", topics=["kliTek"],
        dimensions=["硬件性能 - 多色系统"],
        problems=[],
        summary="3D Revolution（1407 播放）发布 K3 完整评测，属首发期海外评测内容。",
        trans="创想 K3 完整评测现已上线。",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=HDoQ0W_d5Lg": dict(
        sentiment="中性", topics=["multicolor"],
        dimensions=["硬件性能 - 多色系统"],
        problems=["多色废料量与其他机型对比，差异明显"],
        summary="Shoppin Clint（1564 播放）对比 K3 与其他 3D 打印机的多色废料差异，聚焦四喷嘴方案的废料节省幅度。",
        trans="这几台 3D 打印机之间的废料差异太夸张了——创想 K3。",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=upOgxB2Dx8k": dict(
        sentiment="中性", topics=["kliTek", "multicolor"],
        dimensions=["硬件性能 - 多色系统", "硬件性能 - 打印质量"],
        problems=[],
        summary="3D Revolution 发布 K3「诚实评测」（2.1 万播放 / 398 赞 / 86 评论），首发期海外高热度评测之一，评论区成为用户问题集中出口。",
        trans="创想 K3：我的诚实评测。",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=k3Qr3Wq7uIg": dict(
        sentiment="中性", topics=["kliTek", "multicolor"],
        dimensions=["硬件性能 - 多色系统", "日常使用体验 - 开箱装配"],
        problems=["「零废料」是宣传卖点，实际废料量需实测验证"],
        summary="BuildDanielBuild 发布 K3 开箱评测（2.7 万播放 / 294 赞 / 96 评论），聚焦四喷嘴方案「零废料」宣传是否成立，高热度首发开箱。",
        trans="四个喷嘴，零废料？创想 K3 开箱与评测。",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=VpCod4yLDRs": dict(
        sentiment="中性", topics=["kliTek"],
        dimensions=["硬件性能 - 多色系统", "日常使用体验 - 开箱装配"],
        problems=[],
        summary="JJ Shankles 发布 K3 上手初体验（2.0 万播放 / 251 赞 / 63 评论），海外首发期高热度开箱之一。",
        trans="创想 K3 上手初体验。",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=EB7LmaMh23c": dict(
        sentiment="中性", topics=["kliTek", "multicolor"],
        dimensions=["硬件性能 - 多色系统", "品牌信任"],
        problems=["「名不符实」的质疑被公开讨论"],
        summary="TheLayeredWorkshop 以「K3 是否名符其实」为题发布评测（5.1 万播放 / 875 赞 / 272 评论），是首发期热度最高的一条，围绕宣传与实际表现的落差展开讨论。",
        trans="创想 K3：它真的配得上这番宣传吗？",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=c3Qjj31h_Rg": dict(
        sentiment="中性", topics=["kliTek"],
        dimensions=["硬件性能 - 多色系统", "日常使用体验 - 开箱装配"],
        problems=[],
        summary="Main Cave 用一条视频完整呈现 K3 从开箱到打印 Benchy 的全过程（1.3 万播放 / 310 赞 / 65 评论），聚焦到手即可打的上手体验。",
        trans="创想 K3 上手：一条视频，从开箱到小船。",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=bAwEyS8_gIA": dict(
        sentiment="正面", topics=["kliTek", "multicolor"],
        dimensions=["硬件性能 - 多色系统", "日常使用体验 - 效率"],
        problems=[],
        summary="阿文菌发布 K3 200 小时深度体验（1.2 万播放 / 75 赞 / 14 评论），用 200 小时真实使用验证多喷嘴换头方案，整体评价「非常意外」偏正面。",
        trans="非常意外的一台多喷嘴 3D 打印机！创想三维 K3 200 小时深度体验！",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=t-5_b9EC3Ic": dict(
        sentiment="中性", topics=["kliTek"],
        dimensions=["市场与定价", "硬件性能 - 多色系统"],
        problems=["与 SparkX i8 定位差异被单独讨论"],
        summary="The Glorious Geeks 对比 K3 与 SparkX i8（1.0 万播放 / 98 赞 / 29 评论），结论是两者面向完全不同的人群，属首发期竞品定位讨论。",
        trans="创想 K3 vs SparkX i8：它们是为完全不同的人群打造的？！",
        competitor="SparkX i8", p0=False),
    "https://www.youtube.com/watch?v=NS_1UE_Sv_0": dict(
        sentiment="中性", topics=["kliTek"],
        dimensions=["市场与定价", "社区与期待"],
        problems=["K3 的目标人群定位被公开质疑"],
        summary="The Glorious Geeks 以「这台打印机到底是为谁造的」为题（6189 播放 / 56 赞 / 11 评论），质疑 K3 的目标人群定位不够清晰。",
        trans="创想 K3：这台打印机到底是为谁造的？！",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=wYTYAajn7dQ": dict(
        sentiment="正面", topics=["kliTek"],
        dimensions=["社区与期待"],
        problems=[],
        summary="Brandon Jackson（1778 播放 / 23 赞 / 1 评论）发布 K3 上线短视频，称其「传奇」，属首发期正面情绪表达。",
        trans="创想 K3 正式上线，这台机器太传奇了。",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=CANJ_10qJ8U": dict(
        sentiment="中性", topics=["kliTek", "multicolor"],
        dimensions=["硬件性能 - 多色系统", "硬件性能 - 打印质量"],
        problems=["「爆款还是翻车」的悬念式评测"],
        summary="Embrace Making 发布 K3 完整上手评测（1.9 万播放 / 272 赞 / 50 评论），以「爆款还是翻车」为悬念覆盖组装、打印测试与评价。",
        trans="创想 K3 初体验！爆款还是翻车？完整组装、打印测试与评测！",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=B9iyK3srmtA": dict(
        sentiment="正面", topics=["kliTek", "multicolor"],
        dimensions=["硬件性能 - 多色系统", "日常使用体验 - 效率"],
        problems=[],
        summary="3D Printing One 发布 K3 深度实测（1874 播放 / 4 赞 / 2 评论），标题强调四喷嘴快换系统省时省料 70%+，属中文海外分发评测。",
        trans="省时省料 70%+ KliTek™四喷嘴快换系统 创想三维 K3 深度实测。",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=l_DkkHiaHG0": dict(
        sentiment="中性", topics=["price", "ecosystem"],
        dimensions=["市场与定价", "生态与配套"],
        problems=["配件/套件分批到货，完整成本不透明"],
        summary="Layer Shift 3D Store（3181 播放 / 28 赞 / 13 评论）拆解 K3 到手价：现在给什么、后续要加购什么，围绕首发配置与后续套件成本展开。",
        trans="创想 K3：你现在拿到什么、哪些要加钱、之后还会出什么。",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=ggKwkyz4WlI": dict(
        sentiment="正面", topics=["kliTek"],
        dimensions=["硬件性能 - 多色系统"],
        problems=[],
        summary="123-3D 以「有希望的开局」评价 K3（1.3 万播放 / 254 赞 / 45 评论），整体偏正面，属首发期正面评测。",
        trans="创想 K3……一个有希望的开局？？",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=Gu1E70nVtmM": dict(
        sentiment="中性", topics=["ecosystem"],
        dimensions=["市场宣传", "生态与配套"],
        problems=[],
        summary="德国频道 StoneTime（1.8 万播放 / 528 赞 / 40 评论）汇总 Bambu S1、xTool X1/C1 与创想 K3 的行业新品动态，K3 作为多色换头机被并列报道。",
        trans="突发新闻：Bambu S1、xTool X1 与 C1、创想 K3。",
        competitor="Bambu Lab S1 / xTool X1 / xTool C1", p0=False),
    "https://www.youtube.com/watch?v=9dXlmXJRz6o": dict(
        sentiment="中性", topics=["kliTek"],
        dimensions=["硬件性能 - 多色系统"],
        problems=[],
        summary="Shoppin Clint（1133 播放）展示 K3 四 KliTek 喷嘴配置，属首发期快览内容。",
        trans="搭载 4 个 KliTek 喷嘴的创想 K3。",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=T_o-XT7bmuI": dict(
        sentiment="中性", topics=["multicolor"],
        dimensions=["硬件性能 - 多色系统"],
        problems=[],
        summary="PNWDad206（3630 播放 / 44 赞 / 4 评论）发布 K3 多色打印短视频展示。",
        trans="创想 K3 多色打印机。",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=t8IPosfQJ08": dict(
        sentiment="中性", topics=["kliTek"],
        dimensions=["硬件性能 - 多色系统"],
        problems=[],
        summary="Shoppin Clint（869 播放）发布标题仅为「Creality K3」的简短视频，信息量有限。",
        trans="创想 K3。",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=tuA57kbLoH4": dict(
        sentiment="中性", topics=["kliTek"],
        dimensions=["硬件性能 - 多色系统", "日常使用体验 - 效率"],
        problems=[],
        summary="TheLayeredWorkshop（1.1 万播放 / 73 赞 / 11 评论）用正/俯双视角实时演示 K3 换头过程，聚焦换嘴的实际流畅度。",
        trans="创想 K3 实时换嘴！正面与顶部视角。",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=qROGkf6FbRs": dict(
        sentiment="中性", topics=["kliTek"],
        dimensions=["硬件性能 - 打印质量"],
        problems=[],
        summary="捷克频道 3D Stisk（3665 播放 / 63 赞 / 1 评论）发布 K3 首个较大尺寸打印测试（捷克语），海外中欧区一手实测。",
        trans="创想 K3——首个更大的打印件。",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=_2zv9Mh4ZxM": dict(
        sentiment="中性", topics=["kliTek"],
        dimensions=["硬件性能 - 打印质量"],
        problems=[],
        summary="3D Print Lab（3196 播放 / 50 赞 / 8 评论）发布 K3 首个打印件测试，聚焦首次打印的实际表现。",
        trans="创想 K3 首件打印。",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=TX8q6y463nI": dict(
        sentiment="中性", topics=["ecosystem"],
        dimensions=["市场宣传", "生态与配套"],
        problems=[],
        summary="LT3D（4721 播放 / 18 赞 / 9 评论）汇总创想本轮发布的新品（含 K3 与扫描仪），属行业资讯盘点。",
        trans="创想刚刚发布的一切！新 3D 打印机与扫描仪。",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=VscemaspnjM": dict(
        sentiment="中性", topics=["price"],
        dimensions=["市场与定价"],
        problems=[],
        summary="BigFloridaCountry 发布 K3 价格公布与 10/12 限量预售预告（654 播放），属价格信息类短视频。",
        trans="创想 K3 价格公布，10/12 限量预售。",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=KWqNsfKUfog": dict(
        sentiment="中性", topics=["price", "kliTek"],
        dimensions=["市场与定价"],
        problems=[],
        summary="BigFloridaCountry 发布 K3 四 KliTek 喷嘴版价格公布与预售预告（1878 播放），与同频道多条价格信息重复。",
        trans="创想 K3（4 KliTek 喷嘴版）价格公布，10/12 限量预售。",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=9wFQjoH9l50": dict(
        sentiment="中性", topics=["kliTek"],
        dimensions=["社区与期待", "日常使用体验 - 开箱装配"],
        problems=[],
        summary="Evan Funk 提前拿到 K3 并公开征集问题（6637 播放 / 90 赞 / 32 评论），评论区成为首发期用户问题集中出口。",
        trans="全新创想 K3！我们提前拿到了，有什么想问的！",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=z3wFArGzTFY": dict(
        sentiment="正面", topics=["tpu", "multicolor"],
        dimensions=["硬件性能 - 多色系统", "硬件性能 - 挤出/送料"],
        problems=[],
        summary="Infinite Layers 3D（3500 播放 / 36 赞 / 2 评论）认为 K3 可能成为赢家，标题提及 TPU 与多色能力，属首发期正面展望。",
        trans="创想新 K3 或许是个赢家！",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=bitntloiL48": dict(
        sentiment="中性", topics=["kliTek"],
        dimensions=["市场宣传", "硬件性能 - 多色系统"],
        problems=[],
        summary="CoshTech（2.2 万播放 / 87 赞 / 7 评论）系统汇总 K3 已知规格、特性与 KliTek 情报，属首发期信息汇总类视频。",
        trans="关于创想 K3 与 KliTek 我们已知的一切：规格、特性与新闻！",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=XPQsro_XMOM": dict(
        sentiment="中性", topics=["kliTek"],
        dimensions=["硬件性能 - 多色系统"],
        problems=[],
        summary="3D Printing Doctor（6563 播放 / 60 赞 / 9 评论）发布 K3 运行中的初体验，聚焦实际打印动作。",
        trans="创想 K3 运行初体验。",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=g1i7mxaN8jU": dict(
        sentiment="中性", topics=["kliTek"],
        dimensions=["日常使用体验 - 开箱装配", "社区与期待"],
        problems=[],
        summary="Embrace Making 提前拿到未发布的 K3（4.1 万播放 / 742 赞 / 48 评论），首发期高热度提前上手内容。",
        trans="我提前拿到了还没发布的创想 K3！",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=zTY4fpZDrtM": dict(
        sentiment="中性", topics=["kliTek"],
        dimensions=["日常使用体验 - 开箱装配"],
        problems=[],
        summary="CowabungaCreation 发布 K3 开箱（1.2 万播放 / 131 赞 / 36 评论），海外首发期开箱之一。",
        trans="创想 K3 开箱。",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=4Lkv5XfByGc": dict(
        sentiment="中性", topics=["multicolor", "kliTek"],
        dimensions=["硬件性能 - 多色系统", "硬件性能 - 打印质量"],
        problems=[],
        summary="Git IT 3D 发布 K3 初次打印测试，聚焦极限多色场景（1.7 万播放 / 188 赞 / 51 评论）。",
        trans="创想 K3 初次打印！极限多色！",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=la0LdpjCNvE": dict(
        sentiment="中性", topics=["price"],
        dimensions=["市场与定价"],
        problems=[],
        summary="BigFloridaCountry 发布 K3（KliTek）10 月中旬开售预告（1770 播放），属价格/上市信息类短视频。",
        trans="创想 K3（KliTek）10 月中旬开售。",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=vPPA4A4Pf08": dict(
        sentiment="中性", topics=["price", "kliTek"],
        dimensions=["市场与定价"],
        problems=[],
        summary="BigFloridaCountry 发布 K3 基础版（4 KliTek 喷嘴）10/12 开售预告（2143 播放），与同频道多条价格信息重复。",
        trans="创想 K3（基础版，4 KliTek 喷嘴）10 月中旬 10/12 开售。",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=kTIJWj2399I": dict(
        sentiment="中性", topics=["kliTek"],
        dimensions=["硬件性能 - 多色系统", "市场与定价"],
        problems=["「碾压竞品」的悬念式标题，实际竞争格局待验证"],
        summary="3DELWORLD（2279 播放 / 27 赞 / 5 评论）以「K3 换头系统要碾压竞品吗」为题讨论 KliTek 的竞争力，属首发期竞争格局讨论。",
        trans="创想 K3 的换头系统要碾压竞品吗？",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=eykFGX0oiMA": dict(
        sentiment="中性", topics=["kliTek"],
        dimensions=["日常使用体验 - 开箱装配"],
        problems=[],
        summary="TheLayeredWorkshop 发布 K3 到货开箱（4379 播放 / 44 赞 / 11 评论），属首发期到货开箱。",
        trans="特别到货：创想 K3 来了！",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=Q8vIbsW-gsQ": dict(
        sentiment="中性", topics=["kliTek", "multicolor"],
        dimensions=["市场宣传", "硬件性能 - 多色系统"],
        problems=[],
        summary="巴西频道 CAÇADORES DE RENDA（1.3 万播放 / 263 赞 / 31 评论）发布 K3 全解析（葡萄牙语），称其为年度最受期待的 3D 打印机，海外葡语区一手内容。",
        trans="关于全新创想 K3 的一切——今年最受期待的 3D 打印机。",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=p_hX1006PCI": dict(
        sentiment="中性", topics=["kliTek"],
        dimensions=["日常使用体验 - 打印质量"],
        problems=[],
        summary="捷克频道 3D Stisk（543 播放 / 24 赞 / 2 评论）发布 K3 回抽（Retrakce）设置实测，属首发期海外小语种一手内容。",
        trans="Creality K3——回抽设置实测？ #3Dtisk #CrealityK3 #K3",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=CqiIiOcmapw": dict(
        sentiment="中性", topics=["kliTek", "multicolor"],
        dimensions=["日常使用体验 - 打印质量", "硬件性能 - 多色系统"],
        problems=[],
        summary="Crydteamprinting（871 播放 / 5 赞）用 MPOX 通用测试件做 K3 首打测试，称悬垂干净、流量开箱准确、压力提前表现好，属首发期实测。",
        trans="Creality K3：首次测试打印。用 MPOX 通用测试件做 K3 首打，悬垂干净、流量开箱即准、压力提前表现良好。",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=w8AwNa_wPgs": dict(
        sentiment="正面", topics=["kliTek", "multicolor"],
        dimensions=["硬件性能 - 多色系统", "市场宣传"],
        problems=[],
        summary="Jake Myers（1.3 万播放 / 477 赞 / 18 评论）自述升级到新款 Creality K3，属首发期海外创作者自发推荐。",
        trans="新款 K3 打印机。我升级到了新款 @Creality3D K3 打印机！#k3 #3dprinting #creality #3dprint",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=T59qM2C0ApU": dict(
        sentiment="中性", topics=["ecosystem"],
        dimensions=["生态与软件 - 生态整合"],
        problems=[],
        summary="The Glorious Geeks（1149 播放 / 15 赞 / 2 评论）评述 Creality Maker House 发布会，称其超越 K3 与 SPARKX i8，关注真正吸引人的发布内容，属生态层面讨论。",
        trans="Creality Maker House：这次发布什么值得关注？Creality 的 Maker House 发布会不止有 K3 和 SPARKX i8——哪些发布真正吸引了我的注意？",
        competitor="", p0=False),
    "https://www.bilibili.com/video/BV1iEJy6qE1X": dict(
        sentiment="中性", topics=["kliTek"],
        dimensions=["日常使用体验 - 开箱装配"],
        problems=[],
        summary="创想三维官方（505 播放 / 2 弹幕 / 15 评论）发布 K3 开箱视频，属官方首发物料。",
        trans="创想三维K3 开箱视频",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=kOarEWUkDNM": dict(
        sentiment="中性", topics=["kliTek"],
        dimensions=["日常使用体验 - 开箱装配"],
        problems=[],
        summary="SUVIDI（3089 播放 / 18 赞 / 5 评论）发布 K3 开箱与简易安装实测，属首发期海外开箱。",
        trans="和我一起开箱全新 Creality K3（安装超简单）。想看我用 K3 接下来打印什么？看看我的短视频……即将推出，感兴趣可访问官网……",
        competitor="", p0=False),
    "https://www.bilibili.com/video/BV1topr6REk5": dict(
        sentiment="中性", topics=["multicolor", "kliTek"],
        dimensions=["硬件性能 - 多色系统"],
        problems=[],
        summary="风禾阅物（204 播放 / 3 评论）发布 K3 多色实测「不踩坑」经验分享，属国内社区首发期多色实测。",
        trans="多色3D打印，K3实测不踩坑！",
        competitor="", p0=False),
    "https://www.bilibili.com/video/BV1wupk62EJo": dict(
        sentiment="中性", topics=["kliTek", "multicolor"],
        dimensions=["生态与软件 - 竞品对比", "硬件性能 - 多色系统"],
        problems=[],
        summary="一声无忧无虑（227 播放 / 1 弹幕 / 4 评论）将 K3 与拓竹 P2S、快造 U1、Snapmaker U1 横评对比，属国内社区竞品对比讨论。",
        trans="创想三维K3对比P2S、U1",
        competitor="拓竹 P2S / 快造 U1 / Snapmaker U1", p0=False),
    # ========== 2026-10-19 批次新增（L2 周一回捞 · 非官方候选） ==========
    "https://www.youtube.com/watch?v=swyDmkXhQHQ": dict(
        sentiment="中性", topics=["kliTek", "multicolor"],
        dimensions=["市场与定价", "生态与配套 - 耗材"],
        problems=[],
        summary="创作者 Evan Funk 预告 K3 将于 11 月 2 日发货并附赠 4 卷耗材，属上市节点信息类内容（1091 播放）。",
        trans="自带 4 卷免费耗材的多色 3D 打印机？全新 Creality K3 将于 11 月 2 日发货。",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=Da6kGPk0XMQ": dict(
        sentiment="中性", topics=["kliTek", "competitor"],
        dimensions=["市场与定价", "竞品对比"],
        problems=[],
        summary="西语创作者 En3D 盘点 K3 已知信息，并将其多喷头方案与 Snapmaker U1 类比（638 播放）。",
        trans="Creality K3。大家对新推出的多喷头 K3 了解多少？和 Snapmaker U1 类似吗？",
        competitor="Snapmaker U1", p0=False),
    "https://www.youtube.com/watch?v=D5bkhmgAq-g": dict(
        sentiment="中性", topics=["kliTek"],
        dimensions=["硬件性能 - 机械结构", "日常使用体验 - 开箱装配"],
        problems=[],
        summary="创作者 omar_ime 提前拿到未发布的 K3 并展示打印效果，视频含官方商城返利链接，属早期体验类内容（6694 播放）。",
        trans="提前拿到了未发布的 Creality K3，打印效果展示。",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=tFJgo6wXiRM": dict(
        sentiment="正面", topics=["kliTek", "multicolor"],
        dimensions=["硬件性能 - 多色系统"],
        problems=[],
        summary="创作者 MySmoosh 以正在改变多色打印游戏规则为题力赞 K3 更快更智能，属正向种草内容（4309 播放）。",
        trans="Creality K3 正在改变多色 3D 打印的游戏规则！更快、更智能、为更高水平的打印而生。",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=8PKuY1xXnTE": dict(
        sentiment="中性", topics=["kliTek", "model"],
        dimensions=["生态与配套 - 模型资源", "社区与期待"],
        problems=[],
        summary="创作者 AF Inventions 用 K3 打印圣诞烟囱掉落特效模型，视频获 310 万播放 / 4.2 万赞，是首发期传播度最高的 K3 相关内容之一，反映社区话题热度。",
        trans="用你的 K3 打印圣诞烟囱掉落特效。",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=Zdqp1KIXZMM": dict(
        sentiment="中性", topics=["kliTek", "benchmark", "competitor"],
        dimensions=["硬件性能 - 速度", "竞品对比"],
        problems=[],
        summary="创作者 Main Cave 将 K3 与 Snapmaker U1 做正面对速度实测（3.4 万播放 / 135 评论），是首发期少有的横向竞品对比内容。",
        trans="谁更快？Snapmaker U1 vs Creality K3 速度测试！",
        competitor="Snapmaker U1", p0=False),
    "https://www.youtube.com/watch?v=afjgQMCtZp8": dict(
        sentiment="正面", topics=["kliTek"],
        dimensions=["硬件性能 - 打印质量"],
        problems=[],
        summary="创作者 Shoppin Clint 展示 K3 首个非 Benchy 实物打印，评价效果惊艳（came out awesome），属正向首打体验（2398 播放）。",
        trans="新机 K3 的首个非 Benchy 打印，效果超棒！",
        competitor="", p0=False),
    "https://www.bilibili.com/video/BV1bonM6fEwZ": dict(
        sentiment="中性", topics=["kliTek", "build"],
        dimensions=["硬件性能 - 机械结构", "日常使用体验 - 交互"],
        problems=["未能拍到换头动作，现场信息不完整"],
        summary="B站 UP 主在 2026 TCT 深圳展现场近距离体验 K3：四头换热端 FDM 结构简约、触摸屏顺滑，但未能拍到换头动作（384 播放）。",
        trans="2026 TCT 深圳展，现场近距离体验创想三维新品 K3，四头换热端 FDM 打印机。结构确实很简约，触摸屏很顺滑。可惜没有拍到换头动作。",
        competitor="", p0=False),
    "https://www.bilibili.com/video/BV1eRJb6oEDZ": dict(
        sentiment="正面", topics=["kliTek", "quality", "competitor"],
        dimensions=["硬件性能 - 打印质量", "竞品对比"],
        problems=[],
        summary="B站 UP 主（工业设计师 HAKU）实测结论 K3 没有翻车、效果与 Bambu P1S 相近，属正向质量背书（251 播放）。",
        trans="创想三维 K3 没有翻车，效果和 P1S 差不多，后续有新的打印再来分享。",
        competitor="Bambu P1S", p0=False),
    "https://www.reddit.com/r/Creality_k2/comments/1x8hr2w/k2plus_conversion_to_k3_heads/": dict(
        sentiment="中性", topics=["kliTek", "upgrade", "ecosystem"],
        dimensions=["生态与配套 - 升级路径", "硬件性能 - 机械结构"],
        problems=["用户希望提供 K2 Plus 升级 K3 头部/导轨/电机的改件套件，而非整机替换"],
        summary="Reddit 用户 jdoug22（r/Creality_k2）希望创想提供 K2 Plus 升级 K3 头部/导轨/电机的改件套件，而非整机替换，正用 AI 探讨可行性，反映存量用户的升级诉求。",
        trans="K2 Plus 改 K3 头部。有没有人也希望创想卖个套件，而不是为了升级导轨、电机和喷头就得换整台机器？我正拿 AI 试能不能用 K3 的替换件把 K2 Plus 改出来。",
        competitor="", p0=False),
    "https://www.reddit.com/r/Creality/comments/1x7fga8/trying_to_cancel_my_k3_order_feels_impossible/": dict(
        sentiment="负面", topics=["service", "preorder", "support", "competitor"],
        dimensions=["售后与服务 - 订单与客服", "品牌信任"],
        problems=["预购取消流程冗长，客服反复推诿需上级团队审批，5 次联系仍未取消，引发信任危机与竞品流失"],
        summary="Reddit 用户 airjordanballa20（r/Creality）投诉 K3 预购取消极难：已联系客服 5 次，对方以等待上级团队审批拖延，而发货在 11 月本应容易取消；用户已改买 Snapmaker U1 特价机，直言虽仍爱创想但体验糟糕。",
        trans="想取消 K3 预购简直不可能。我已联系创想客服约 5 次要求取消 K3 预购，结果上周买了 Snapmaker U1 的特价机。创想一直说在等上级团队审批才能取消，明明 11 月才发货，为什么这么简单的事却做不到？我其实很喜欢创想，所以…",
        competitor="Snapmaker U1", p0=True),
    "https://www.youtube.com/watch?v=RNEHNtXATMc": dict(
        sentiment="正面", topics=["kliTek", "multicolor"],
        dimensions=["硬件性能 - 多色系统", "硬件性能 - 机械结构"],
        problems=[],
        summary="海外 UP 主 MySmoosh 以「你的打印机可能已经过时了」为题评测 K3，认为 K3 把多色换头体验拉到新高度（播放 1251 / 赞 18 / 评 7）。",
        trans="你的 3D 打印机可能已经过时了！Creality K3 正把多色打印拉升到新层级……",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=q0Q64z91hlo": dict(
        sentiment="正面", topics=["kliTek", "multicolor"],
        dimensions=["硬件性能 - 多色系统", "日常使用体验 - 打印质量"],
        problems=[],
        summary="海外创作者 Michael Lydick 长期对 Creality 口碑存疑，但在 K3 上打印数百小时后改观，认为多色等体验打动了他（播放 829 / 赞 11）。",
        trans="我曾经看错 Creality。在 K3 上打印数百小时后，它改变了我的看法。从多色……",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=zVFKZoAN6qI": dict(
        sentiment="中性", topics=["kliTek", "competitor"],
        dimensions=["市场与定价", "竞品对比"],
        problems=[],
        summary="海外频道 3D Prints By Vic 在「本周 3D 打印新动态」中盘点 K3 与 Formlabs Form Studio 1 等新品，顺带对比起售价（播放 1992 / 赞 30 / 评 7）。",
        trans="本周 3D 打印有什么新鲜事：Creality K3、Formlabs Form Studio 1 等。一台 699 美元的 Formlabs 打印机本周引起我注意……",
        competitor="Formlabs", p0=False),
    "https://www.youtube.com/watch?v=GRnWK-5Zons": dict(
        sentiment="中性", topics=["kliTek", "nozzle"],
        dimensions=["硬件性能 - 多色系统"],
        problems=[],
        summary="海外用户 Shoppin Clint 发布 K3 多喷嘴机型短视频，展示换头结构（播放 1114 / 赞 10）。",
        trans="Creality K3 多喷嘴 3D 打印机……",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=Ol-Wa6esjcM": dict(
        sentiment="中性", topics=["kliTek", "multicolor", "price"],
        dimensions=["硬件性能 - 多色系统", "市场与定价"],
        problems=["849 美元定价是否值回票价存疑"],
        summary="海外频道 Project Artifact 出 K3 评测与选购指南，围绕四喷嘴多色与更少废料展开，但对其 849 美元定价是否值回票价持保留（播放 1342 / 赞 5）。",
        trans="Creality K3：四喷嘴对阵多色耗材浪费问题。K3 评测与购买指南：四喷嘴、多色打印与更少废料——但它值 849 美元吗？我们拆解……",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=swyDmkXhQHQ": dict(
        sentiment="正面", topics=["kliTek", "multicolor", "preorder"],
        dimensions=["硬件性能 - 多色系统", "生态与配套 - 耗材"],
        problems=[],
        summary="海外创作者 Evan Funk 首测 K3，强调随机附赠 4 卷耗材、11 月发货，整体正面（播放 1326 / 赞 15 / 评 3）。",
        trans="自带 4 卷免费耗材的多色 3D 打印机？！全新一代 Creality K3 将于 11 月发货……",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=Da6kGPk0XMQ": dict(
        sentiment="中性", topics=["kliTek", "competitor"],
        dimensions=["竞品对比", "社区与期待"],
        problems=[],
        summary="西语创作者 En3D 发问大家对创想 K3 多喷头新机了解多少、是否与 Snapmaker U1 类似，属发售前讨论（播放 733 / 赞 3）。",
        trans="Creality K3。大家对创想这台多喷头新机 K3 了解多少？和 Snapmaker U1 类似吗？",
        competitor="Snapmaker", p0=False),

    # ========== 2026-10-22 批次（6 条，已人工标注；同批剔 4 条：无关玩具/带货抽奖/纯玩法视频） ==========
    "https://www.youtube.com/watch?v=D0G7RmyBDlU": dict(
        sentiment="中性", topics=["kliTek"],
        dimensions=["日常使用体验 - 开箱装配"],
        problems=[],
        summary="海外 UP 主 K3 开箱直播，逐一展示整机、四组喷嘴组件与随箱配件，全程未给打印实测数据，属首发期的开箱记录。",
        trans="创想三维 K3 开箱直播。K3 购买链接见简介，另有 Discord 与 Patreon 社群入口。",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=g1GjbogIv0o": dict(
        sentiment="中性", topics=["kliTek", "ecosystem"],
        dimensions=["电商渠道"],
        problems=[],
        summary="英国经销商 Smith3D 预告 K3 将于 2026 年 12 月到货，文案强调「四个喷嘴、四条耗材通道」，反映欧洲渠道铺货节奏晚于美国。",
        trans="创想三维 K3：四个喷嘴，一台机器｜2026 年 12 月登陆 Smith3D。四个喷嘴、四条独立耗材通道。",
        competitor="", p0=False),
    "https://www.bilibili.com/video/BV1Rpnz6pEPS": dict(
        sentiment="正面", topics=["kliTek", "multicolor", "nozzle"],
        dimensions=["硬件性能 - 多色系统", "日常使用体验 - 效率"],
        problems=[],
        summary="B 站 UP 主首发上手 K3，实测「5 秒换喷嘴」并演示多口径混打，认为创想的多头多色方案「终于是交作业了」，整体评价积极。",
        trans="",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=yK5fFPIJe6Q": dict(
        sentiment="中性", topics=["kliTek"],
        dimensions=["日常使用体验 - 开箱装配"],
        problems=[],
        summary="UP 主记录 K3 首次装机：从清空包装材料、拆固定件到通电初始化，属真实上手流程记录，未涉及性能评价。",
        trans="创想三维 K3 装机实录：开箱日第一件事就是把所有包装材料清走，我拿到的是 K3 套装版。",
        competitor="", p0=False),
    "https://www.reddit.com/r/3DPrintingDeal/comments/1x9znrb/ebay_72165_pre_salecreality_k3_ebay_59415/": dict(
        sentiment="中性", topics=["price", "competitor"],
        dimensions=["市场与定价", "竞品对比"],
        problems=[],
        summary="Reddit 促销版块列出 eBay 上 K3 预售价 721.65 美元，低于 849 美元官方 MSRP；同帖并列出 FlashForge Creator 5（594.15 美元）等同价位机型，反映首发期已出现渠道让价。",
        trans="eBay 预售 721.65 美元！创想 K3；eBay 594.15 美元 FlashForge Creator 5；721.65 美元 FlashForge Creator 5 Pro；191.25 美元翻新 ANYCUBIC Kobra X。",
        competitor="FlashForge Creator 5", p0=False),
    "https://www.bilibili.com/video/BV1snJo69Evp": dict(
        sentiment="负面", topics=["price", "competitor"],
        dimensions=["市场与定价", "竞品对比"],
        problems=["价格与首发信心"],
        summary="B 站 UP 主在「无机之谈」中认为 K3 与 SPARKX i8 定价偏高，建议用户观望等待，反映国内首批用户对首发价的心理落差。",
        trans="",
        competitor="SPARKX i8", p0=False),
    # ========== 2026-10-23 批次（YouTube 打印实拍 / 创意改装） ==========
    "https://www.youtube.com/watch?v=qjkSG7iK5Xc": dict(
        sentiment="中性", topics=["kliTek"],
        dimensions=["日常使用体验 - 打印质量"],
        problems=[],
        summary="Lukis3D Studio 用搭载 KliTek 的 K3 打印鳄鱼模型 Macca，属常规打印实拍展示（播放 4105 / 点赞 33 / 评论 0），未展开性能评价。",
        trans="用全新的创想三维 K3 KliTek 打印鳄鱼 Macca。",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=XAmbmNY5NKc": dict(
        sentiment="中性", topics=["quality"],
        dimensions=["日常使用体验 - 打印质量"],
        problems=[],
        summary="JJ Shankles 用 K3 打印可热成形的万圣节南瓜糖果盒，并把已打印件二次加热重熔成形（播放 7.1 万 / 点赞 1559 / 评论 31），展示的是打印件的后处理可塑性而非整机评测。",
        trans="把 3D 打印件重新熔成南瓜 - 创想三维 K3。STL 链接见 MakerWorld 的热成形南瓜万圣节糖果盒模型。",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=wVmEPeE_b1s": dict(
        sentiment="中性", topics=["kliTek", "nozzle"],
        dimensions=["日常使用体验 - 打印质量"],
        problems=[],
        summary="频道 GT3D 发布拉伸骷髅解压玩具打印实拍，描述里带上 K3 卖点（高速打印、快速换喷嘴），属带官方口播的成品展示（播放 3.0 万 / 点赞 312 / 评论 0），无实测数据。",
        trans="3D 打印拉伸骷髅解压玩具。来看看全新的创想三维 K3：高速打印、快速换喷嘴，效果令人印象深刻。",
        competitor="", p0=False),
    # ========== 2026-10-29 批次（B站详测 + 海外视频观察） ==========
    "https://www.bilibili.com/video/BV1iex56iEe4": dict(
        sentiment="中性", topics=["kliTek", "multicolor", "nozzle"],
        dimensions=["硬件性能 - 多色系统", "硬件性能 - 机械结构"],
        problems=["只换打印头、不换整个工具头，喷嘴快换方案的长期可靠性待验证"],
        summary="B站 UP 主大鱼DIY 发布 K3 详细测评（播放 4276 / 弹幕 3 / 评论 55），开场即点明 K3 属换嘴方案——只更换打印头而非整个工具头，明确要扒这种方案的优势与缺陷；单色、多色、混色、多口径混打四类场景全程实拍，声明无美颜无滤镜。",
        trans="【详细测评】多喷嘴多色创想三维 K3 的真实水平到底如何！？多口径混打 + 混色打印实测。哈喽，我是大鱼，今天测评的 3D 打印机是创想三维的 K3。准确来说，这是一台换嘴 3D 打印机，因为它并不是更换整个工具头，而是只更换打印头。那么这种方案效果怎么样呢？有什么优势，又有什么缺陷，且随大鱼一起来好好扒一扒。单色打印、多色打印、混色打印、多口径打印都有测试，全程实拍，无美颜无滤镜。",
        competitor="", p0=False),
    "https://www.bilibili.com/video/BV13BnR6tEnN": dict(
        sentiment="中性", topics=["kliTek", "ecosystem"],
        dimensions=["生态与配套", "硬件性能 - 机械结构"],
        problems=[],
        summary="创想三维官方 B 站账号发布 K3 集中答疑（播放 892 / 评论 23），标题即「你想知道的都在这里」，属首发期官方口径汇总，可作后续核对的基准文本；评论量明显高于同期官方内容，反映首批用户疑问集中。",
        trans="关于创想三维 K3，你想知道的都在这里。",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=1TNYgLoMhBg": dict(
        sentiment="中性", topics=["multicolor", "kliTek"],
        dimensions=["硬件性能 - 多色系统"],
        problems=["四喷嘴对换色冲刷废料的实际降幅尚无第三方量化"],
        summary="土耳其频道 3D CART CURT 解读 K3 的产品思路（播放 1571 / 点赞 15 / 评论 2）：认为 Creality 这套名为 KliTek 的四喷嘴系统，核心目标就是削减换色过程中的冲刷（purge）浪费，属功能定位解读而非实测。",
        trans="创想三维 K3：用四个喷嘴对抗冲刷废料。Creality 的新 K3 通过名为 KliTek 的四喷嘴系统，试图减少换色过程中的冲刷浪费。",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=2XlI863wsIo": dict(
        sentiment="中性", topics=["multicolor"],
        dimensions=["硬件性能 - 多色系统", "日常使用体验 - 效率"],
        problems=[],
        summary="西班牙语频道 Zuluprints 发布 K3 多色介绍（播放 735 / 点赞 6 / 评论 2），落点是「不必在频繁换料上耗时间也能全彩打印」，与小语种市场对多色效率的关注一致，无实测数据。",
        trans="创想三维 K3：超快多色 3D 打印，废料更少。如果你能在不把时间浪费在不停换料的前提下全彩打印呢？全新的 Creality K3 带来了……",
        competitor="", p0=False),

    # ========== 2026-11-02 批次：豆包投喂（抖音 / 小红书 / X）+ Reddit 自动采集 ==========
    # 豆包只负责把登录墙平台的内容拿回来，情感/主题/维度/问题点全部在此逐条判定。
    "https://www.reddit.com/r/Creality/comments/1xjx9el/its_here_k3_is_in/": dict(
        sentiment="正面", topics=["kliTek", "multicolor"],
        dimensions=["日常使用体验 - 开箱装配"],
        problems=[],
        summary="Reddit r/Creality 用户晒开箱，称自己是「白鲸」抽奖的幸运中签者之一，盯了几周物流终于收到 K3，正在做对比测试，之后打算把 TMT 打印件捐给奥马哈的儿童医院。属首批到货的正面样本。",
        trans="它到了，K3 到手了。我是「白鲸」赠机活动的幸运中签者之一，盯了几周物流今天终于收到。正在做测试打印和其他机器对比，等我再熟悉一点，会打印 TMT 捐给奥马哈的儿童医院。感谢创想。",
        competitor="", p0=False),
    "https://www.reddit.com/r/CrealityCloud/comments/1xl7tsq/k3_redeemable_with_creality_cloud_points/": dict(
        sentiment="中性", topics=["ecosystem"],
        dimensions=["生态与配套"],
        problems=["能否用创想云积分兑换缺少官方说明"],
        summary="Reddit r/CrealityCloud 用户询问 K3 是否可以用创想云积分兑换，并想了解 K2 当初发售后隔了多久才上积分商城——手里攒了大量积分。属生态积分体系的规则咨询类反馈。",
        trans="K3 能用创想云积分兑换吗？有人知道 K2 从发售到上架创想云隔了多久吗？我手里攒了一大堆积分要用。",
        competitor="", p0=False),
    # ========== 2026-11-03 增量 ==========
    "https://www.youtube.com/watch?v=pmgb2Bc5DiE": dict(
        sentiment="中性", topics=["kliTek", "multicolor", "price"],
        dimensions=["硬件性能 - 多色系统", "市场与定价"],
        problems=["省废料幅度仍以官方口径为主，缺少独立的废料量化对比"],
        summary="YouTube 频道 Brandon Veza（4119 播放 / 67 赞）解读 K3 的四喷嘴换头：靠换头绕开冲刷环节省掉废料，并列出 10 月 31 日美国价 849 美元，向观众提问是否愿意为此换机。属卖点与价格结合的选购讨论，未给出自己的一手废料实测。",
        trans="创想新出的 K3 在四个喷嘴之间切换，从而跳过冲刷废料这一步。你会为这个功能换机吗？截至 2026 年 10 月 31 日的价格：K3 为 849 美元。",
        competitor="", p0=False),
    "https://www.reddit.com/r/Creality/comments/1xkm5pz/k3_redeemable_with_creality_cloud_points/": dict(
        sentiment="中性", topics=["ecosystem", "price"],
        dimensions=["生态与配套", "市场与定价"],
        problems=["K3 何时进入创想云积分兑换未公开"],
        summary="Reddit r/Creality 用户手里攒了大量创想云积分，询问 K3 能否用积分兑换，并想参照 K2 当年发售后多久才上架积分商城。属积分体系规则的咨询，反映首发期兑换路径未公开。",
        trans="K3 能用创想云积分兑换吗？有人记得 K2 发售后过了多久才上架创想云吗？我攒了一大堆积分想用掉。",
        competitor="", p0=False),
    # ========== 豆包投料（抖音 · 一手开箱 / 实测） ==========
    # ========== 2026-11-10（7 天窗口回捞，32 条候选里挑 2 条一手内容）==========
    # 口径：只收「真实到手 / 真实打印」的一手内容；媒体转述（Tom's Hardware 评测、
    # Formnext 阵容、美区开卖新闻）与玩梗帖（K3 Plus 许愿、Tom's 标题对比梗）不收。
    # B站两条（BV1SvWt6xEBi / BV1EtxZ68EwN）采集只拿到简介与器材表，无正文可判情感，
    # 按「拿不准宁可跳过」不入库。
    "https://www.reddit.com/r/crealityk3/comments/1xqiqtq/first_major_multi_color_print_on_my_creality_k3/": dict(
        sentiment="正面", topics=["multicolor", "kliTek"],
        dimensions=["硬件性能 - 多色系统", "日常使用体验 - 效率"],
        problems=["半尺寸多色件耗时 8 小时，换色节奏是主要耗时来源"],
        summary="r/crealityk3 到手用户的第一件大尺寸多色实测：以计划尺寸的一半打出一只鹦鹉，耗时 8 小时，用户强调「废料非常少」，成品仍需调参。这是 11-06 首批到货后第一件完整多色件的耗时与废料实证——相对 AMS 路线，KliTek 在废料上的优势得到一手复现，代价是换色带来的时间成本。",
        trans="我在 K3 上的第一件正式多色打印，是一只还在调整中的鹦鹉。还需要再调一些参数，但我想先拿 K3 做一次测试打印；这次是按计划尺寸的一半打的。花了 8 个小时，如你所见，废料非常少。",
        competitor="", p0=False),
    "https://www.reddit.com/r/CrealityCloud/comments/1xomch6/creality_k3_storage_box/": dict(
        sentiment="中性", topics=["ecosystem", "nozzle"],
        dimensions=["生态与配套 - 配件与耗材", "日常使用体验 - 收纳"],
        problems=["随机配件（多喷嘴/刷子/备用螺丝）无随箱收纳方案，需用户自行设计打印收纳盒"],
        summary="被选入 Creality Maker Program 的用户获赠 K3 后，发现随机配件（多个喷嘴、刷子、备用螺丝）没有随箱收纳方案，于是自建了一个免五金、可一次打印成型的收纳盒，专为 K3 的加长喷嘴留出槽位。属「配件多但不给收纳」的配套缺口样本，同时也是社区自补生态的正向信号。",
        trans="K3 收纳盒。思路是：我被选进 Creality Maker Program 的 Maker Elite，获赠了一台 K3；到手后发现随机配件没地方放——好几个喷嘴、刷子，还有备用螺丝都需要归置。既然没看到专为 K3 做的收纳盒，我就想不如自己做一个。设计上尽量好打、不需要额外五金，打完直接装配；尺寸足够放下 K3 用的加长喷嘴。",
        competitor="", p0=False),

    # ========== 2026-11-11 增量（YouTube / B站 一手到手 · 首打 / 开箱 / 展示） ==========
    # 口径：仅收真实到手、真实打印的一手视频；纯预热(countdown)、affiliate 带货、
    #   娱乐向(4 hobbies) 一律不收。以下均为 setup / first-print / unboxing / showcase，
    #   无上报问题 → 判中性、不编 problemPoints；summaryCn 据 titleCn + originalText 写。
    "https://www.youtube.com/watch?v=WnpHKp8Em78": dict(
        sentiment="中性", topics=["build"],
        dimensions=["日常使用体验 - 开箱装配"],
        problems=[],
        summary="YouTube 频道 Off The Build Plate 的 K3 装机连载第二期：机器正式装好、准备开打。继第一期拆箱看配件后，本期进入实际装配与上手，属首批海外用户的一手装机实录。",
        trans="Creality K3 装机与第一件打印！K3 已经正式装好、准备开打了。在看完第一期拆箱看配件之后，我们进入第二期：实际装配。",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=lkYYSR3mOQ4": dict(
        sentiment="中性", topics=["kliTek"],
        dimensions=["日常使用体验 - 开箱装配"],
        problems=[],
        summary="海外创作者 Hugo Lopes 3D 的 K3 第一印象视频，记录刚到手时的初步上手感受，未提及明显问题。",
        trans="Creality K3 第一印象。",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=I5MdYFs7OLc": dict(
        sentiment="中性", topics=["build"],
        dimensions=["日常使用体验 - 打印质量"],
        problems=[],
        summary="用户 BigFloridaCountry 的 K3 首件打印特写（benchy，11-06），展示第一批到手用户实际打出的模型，无问题反馈。",
        trans="Creality K3 第一件 3D 打印的特写镜头（benchy）。",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=_A4iyWRV_8I": dict(
        sentiment="中性", topics=["展示"],
        dimensions=["硬件性能"],
        problems=[],
        summary="用户 Gregory Mann 用 K3 打印了一盏灵感来自罂粟胶囊的台灯，1.4 万播放、446 赞，是首发期较高传播的纯作品展示型内容。",
        trans="一盏灵感来自罂粟胶囊的台灯，用 Creality K3 打印。",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=UnizS6UNhfo": dict(
        sentiment="中性", topics=["build"],
        dimensions=["日常使用体验 - 开箱装配"],
        problems=[],
        summary="用户 BigFloridaCountry 的 K3 多喷嘴 KliTek 3D 打印机开箱视频（11-06），记录拆箱与上手初体验。",
        trans="Creality K3 3D 打印机开箱，11-06-26。开箱这台 Creality K3 多喷嘴 KliTek 3D 打印机。",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=CsMiB-0s4RA": dict(
        sentiment="中性", topics=["build"],
        dimensions=["日常使用体验 - 开箱装配"],
        problems=[],
        summary="YouTube 频道 Off The Build Plate 的 K3 拆箱连载第一期：机器刚到，在开打前先看清盒子里都有什么配件。",
        trans="Creality K3：盒子里都有什么？K3 已经到了，在开打之前，我们先看看手里到底是些什么。这是本系列的第一期。",
        competitor="", p0=False),
    "https://www.bilibili.com/video/BV1BEWt6TE9o": dict(
        sentiment="中性", topics=["material", "build"],
        dimensions=["硬件性能 - 多色系统"],
        problems=[],
        summary="B站用户发布创想三维 K3 打印异料支撑的实测片段（455 播放 / 7 评论），演示多材料支撑的实际效果。",
        trans="创想三维 K3 打印异料支撑。",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=JoOpP7_O8u8": dict(
        sentiment="中性", topics=["build"],
        dimensions=["日常使用体验 - 开箱装配"],
        problems=[],
        summary="用户 3D and Tee Printing 的 K3 开箱直播录像，记录到手后的拆箱与上手过程。",
        trans="深夜打印：Creality K3 开箱（别让 Terri 在直播里伤到我）。",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=jUctrFKqjyk": dict(
        sentiment="中性", topics=["multicolor", "kliTek"],
        dimensions=["硬件性能 - 多色系统"],
        problems=[],
        summary="YouTube 频道 Off The Build Plate 的 K3 首发第一眼与开箱：四独立喷嘴、CMYK 物理混色、机器正式到货，记录首批到手用户的开箱与初印象。",
        trans="Creality K3 终于来了！第一眼与开箱。K3 已经在 Off The Build Plate 正式落地：四个独立喷嘴、CMYK 物理混色。",
        competitor="", p0=False),

    # ========== 2026-11-12 增量（3 条视频主体，全部无上报问题 → 动态档） ==========
    # 口径同 11-11：候选池已全是视频主体（标题+简介），Reddit 403/429 拿不到一手帖；
    # 补拉评论（_k3_yt_comments_probe.py，10 条）只有 2 条涉及议题且均为对评测方法的质疑，
    # 属媒体评价范畴、非到手体验，按「拿不准宁可跳过」不入库。
    # 余下 4 条 fresh 里 yOvPCQXr2fg 与页面已有 I5MdYFs7OLc 为同一作者同段 benchy 特写，跳重。
    "https://www.youtube.com/watch?v=WI8hVScsIx8": dict(
        sentiment="中性", topics=["multicolor", "kliTek"],
        dimensions=["硬件性能 - 多色系统"],
        problems=[],
        summary="捷克 3D Stisk 频道的 K3 与 Snapmaker U1 同价位横评（2940 播放 / 62 赞 / 9 评论）：两台价格相近的多色机放在同一批真实工况下对照检验。属第三方横评视频主体，本期无具体问题上报。",
        trans="Creality K3 对比 Snapmaker U1——哪台更好？Creality K3 与 Snapmaker U1！两台价格相近的 3D 打印机，我们在真实使用场景里认真检验过。",
        competitor="Snapmaker U1", p0=False),
    "https://www.youtube.com/watch?v=tD8LdmB0YpI": dict(
        sentiment="中性", topics=["multicolor"],
        dimensions=["硬件性能 - 多色系统"],
        problems=[],
        summary="频道 Off The Build Plate 的 K3 四色打印连载第三期（Shorts）：用三件作品检验四色能力并给出结果，属首发期系列化展示内容，无问题反馈。",
        trans="Creality K3：四种颜色、三件打印与最终结果！K3 正在检验它的四色打印能力，我们在收尾 K3 介绍连载的第三期。",
        competitor="", p0=False),
    "https://www.bilibili.com/video/BV1SvWt6xEBi": dict(
        sentiment="中性", topics=["multicolor"],
        dimensions=["硬件性能 - 多色系统"],
        problems=[],
        summary="B站 UP 主机甲中心的 K3 四喷嘴实测（1.2 万播放 / 58 评论 / 20 弹幕），主题是四喷嘴除四色打印外的其他用法；简介为拍摄器材清单，未含观点与问题，本期只计声量。",
        trans="不只是四色打印！四喷嘴还能玩出什么花样？创想三维 K3 实测。",
        competitor="", p0=False),

    # ========== 2026-11-17 新增（15 条：YouTube 13 + B站 2，多为开箱/展示/评测）==========
    # 口径：只有标题+简介、无明确缺陷反馈 → 动态档（只计声量，不进问题榜）；
    #       有明确测试结论/竞品对比/废料验证 → 有效档（中性 + topics）。
    "https://www.youtube.com/watch?v=V_Tr8ovSkPQ": dict(
        sentiment="中性", topics=[], dimensions=[], problems=[],
        summary="YouTube 频道 additiveworks 用 K3 打印彩色运动卡扣作品（播放 1.1 万 / 点赞 44），展示多色创意落地，简介无缺陷反馈，只计声量。",
        trans="探索新的配色：用我的运动卡扣作品玩转多彩创意。Creality K3 让 colorful 想法轻松变成实物。",
        competitor="", p0=False, kind="动态"),
    "https://www.bilibili.com/video/BV1i4sP6qEsy": dict(
        sentiment="中性", topics=["kliTek", "reliability"],
        dimensions=["硬件性能 - 换头可靠性"], problems=[],
        summary="B站南极熊3D打印网搬运 The Next Layer 的 K3 极限耐久测试（100 小时 / 1 万次换头 / 0 失败，播放 406 / 评论 10），核心结论是换头机构在长时高负载下零失败，属正面耐久性数据，无缺陷反馈。",
        trans="100 小时、1 万次换头、0 失败，创想三维 K3 的极限在哪？",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=oRRRzuNi8wQ": dict(
        sentiment="中性", topics=["unboxing", "comparison"],
        dimensions=["日常使用体验 - 开箱装配"], problems=[],
        summary="德语频道 3D Printiverse 的 K3 开箱（播放 1.1 万 / 点赞 221 / 评论 53），把新 K3 与 Snapmaker U1 放在一起对比（标题抛出了 U1 是否面临挑战），属高热度开箱对比，简介无明确缺陷。",
        trans="新 Creality K3 来了！Snapmaker U1 有麻烦了吗？和大家一起拆开全新的 Creality K3 看看。",
        competitor="Snapmaker U1", p0=False),
    "https://www.youtube.com/watch?v=ejsZb4rVCEE": dict(
        sentiment="中性", topics=["unboxing"],
        dimensions=["日常使用体验 - 开箱装配"], problems=[],
        summary="葡萄牙语频道 Hugo Lopes 3D 的 K3 从零开箱与装配（播放 1.5 万 / 点赞 415 / 评论 27），属高热度首发开箱内容，简介主要为 STLFLIX 课程推广，无缺陷反馈。",
        trans="全新 Creality K3 开箱与从零装配！",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=G1RZWmaTYR0": dict(
        sentiment="中性", topics=[], dimensions=[], problems=[],
        summary="YouTube 频道 SUVIDI 用 K3 多喷嘴多色打印制作打印平台清洁刷（播放 5.1 万 / 点赞 449），属高热度应用场景展示，简介无观点与问题，只计声量。",
        trans="3D 打印清洁刷：用 Creality K3 多喷嘴多色打印制作。",
        competitor="", p0=False, kind="动态"),
    "https://www.youtube.com/watch?v=DNCrrXdsT5M": dict(
        sentiment="中性", topics=[], dimensions=[], problems=[],
        summary="Creality 官方 YouTube 短片，展示用 K3 打印的打印平台清洁工具（播放 4.5 万 / 点赞 960），属厂商官方营销内容，按口径不计入用户声量。",
        trans="更干净的打印平台、更聪明的工作台：用 K3 打印，快速多色打印带来更多可能。",
        competitor="", p0=False, kind="动态"),
    "https://www.youtube.com/watch?v=iaEJA9nO0KE": dict(
        sentiment="中性", topics=["review"],
        dimensions=["硬件性能 - 多色系统"], problems=[],
        summary="法语频道 Isidon 的 K3 评测（播放 1.0 万 / 点赞 213 / 评论 71），标题称其为新挑战者，含购买预购链接；属高热度第三方评测，简介无明确缺陷反馈。",
        trans="一位新挑战者来了！Creality K3 评测。",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=ERnMajcC2x0": dict(
        sentiment="中性", topics=[], dimensions=[], problems=[],
        summary="YouTube 频道 Versatile 3D 短片，主题是 3D 打印机能省多少钱（播放 5988 / 点赞 151），带折扣联盟链接，属营销向展示，无缺陷反馈，只计声量。",
        trans="一台 3D 打印机能帮你省多少钱？用 Creality K3 打印。",
        competitor="", p0=False, kind="动态"),
    "https://www.youtube.com/watch?v=em-qXMuPW6Q": dict(
        sentiment="中性", topics=["nozzle", "waste"],
        dimensions=["硬件性能 - 换头可靠性"], problems=[],
        summary="法语频道 Atome3D.com 介绍 K3 四喷嘴 5 秒换头、每色独立喷嘴免冲刷废料的原理（播放 7039 / 点赞 108 / 评论 4），属产品机制讲解，无缺陷反馈。",
        trans="Creality K3：5 秒换喷嘴的 3D 打印机。四色各有独立喷嘴，减少冲刷废料。",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=QrieYjTFbLM": dict(
        sentiment="中性", topics=[], dimensions=[], problems=[],
        summary="捷克语频道 3D Stisk 短片，测试金色 Silk PLA 加 PETG 支撑在 K3 上的打印效果（播放 2573 / 点赞 26），简介仅 short，无观点，只计声量。",
        trans="金色 Silk PLA + PETG 支撑在 Creality K3 上打印效果如何？",
        competitor="", p0=False, kind="动态"),
    "https://www.youtube.com/watch?v=ll0ELtrUQ5U": dict(
        sentiment="中性", topics=["waste", "nozzle"],
        dimensions=["硬件性能 - 换头可靠性", "使用成本与兼容性 - 耗材"], problems=[],
        summary="葡萄牙语频道 Bancada 3D 验证 K3 四喷嘴是否真能减少废料（播放 1438 / 点赞 24），提到厂商宣称省 85% 耗材、约 5 秒换头，属带验证意图的评测，无明确缺陷结论。",
        trans="Creality K3：四个喷嘴能终结浪费吗？测试显示还剩多少。四喷嘴预装、约 5 秒切换，厂商称可省最多 85% 耗材。",
        competitor="", p0=False),
    "https://www.youtube.com/watch?v=2l9tkKsHcWc": dict(
        sentiment="中性", topics=["comparison"],
        dimensions=["日常使用体验 - 开箱装配"], problems=[],
        summary="越南语频道 Kỹ Sư Thái 3D 的 K3 与 Snapmaker U1 对比短片（播放 547 / 点赞 2），简介为空、无明确观点，只计声量。",
        trans="Creality K3 和 Snapmaker U1 有什么不同？",
        competitor="Snapmaker U1", p0=False, kind="动态"),
    "https://www.youtube.com/watch?v=GQnhHtCPojg": dict(
        sentiment="中性", topics=[], dimensions=[], problems=[],
        summary="YouTube 频道 BigFloridaCountry 用 K3 打印蒸汽船 Benchy 模型（播放 1390 / 点赞 8），属个人作品展示，无观点与问题，只计声量。",
        trans="Steamship Benchy：用 Creality K3 打印。",
        competitor="", p0=False, kind="动态"),
    "https://www.youtube.com/watch?v=2oF_g7DAgyc": dict(
        sentiment="中性", topics=["waste", "kliTek"],
        dimensions=["硬件性能 - 换头可靠性"], problems=[],
        summary="YouTube 频道 THE PRINT MASTER 短片，质疑 K3 四喷嘴 5 秒换头是否真能省 85% 废料（播放 1161 / 点赞 11），引用厂商宣称与已发布测试，属验证向内容，无明确缺陷结论。",
        trans="4 个喷嘴、5 秒换头：Creality K3 真的少浪费 85% 吗？厂商说法与已发布测试。",
        competitor="", p0=False),
    "https://www.bilibili.com/video/BV1tfWB6SE7u": dict(
        sentiment="中性", topics=[], dimensions=[], problems=[],
        summary="B站 UP 铜牌杰瑞的 K3 评测与 KliTek 拆解（播放 4254 / 评论 25），核心判断是混合喷嘴要选对场景、小模型用大喷嘴打支撑不一定划算；该条已在 11-16 批次入库，此标注用于幂等跳过。",
        trans="创想三维 K3 评测 + KliTek 拆解：混合喷嘴打印要找到适合的场景。",
        competitor="", p0=False, kind="动态"),
    # ========== 2026-11-18 新增（YouTube 评论区，评论级 sourceLink 带 &lc=）==========
    # 当日候选池只有 11 个视频主体，均无用户观点；用 _k3_yt_comments_probe.py 补拉
    # 11 个候选视频的评论（69 条窗口内），挑 4 条有明确判断的入页。
    "https://www.youtube.com/watch?v=ejsZb4rVCEE&lc=UgwxaGH6lFMC-eg7_XF4AaABAg": dict(
        sentiment="中性", topics=["price", "ecosystem"],
        dimensions=["市场与定价", "竞品对比"],
        problems=["若定价落在 R$8000 区间，3 年 Creality 老用户也会改选 Snapmaker U1"],
        summary="巴西用户的定价判断：K3 若落在 R$8000 区间，即便自己是用了三年、体验良好的 Creality 老用户也会改选 Snapmaker U1——属价格锚点上的竞品置换风险，不是对机器本身的否定。",
        trans="如果 K3 落在 8000 雷亚尔这个区间，我会选 Snapmaker U1。而且我已经有一台 Creality 打印机用了三年，一直很好用！",
        competitor="Snapmaker U1", p0=False),
    "https://www.youtube.com/watch?v=ejsZb4rVCEE&lc=Ugz7lfKE-4Vb3yHy9iR4AaABAg": dict(
        sentiment="负面", topics=["ecosystem"],
        dimensions=["硬件性能 - 机械结构"],
        problems=["外观与固定式屏幕被指照搬 Snapmaker，屏幕不可调角度影响观看"],
        summary="开箱视频下的用户指 K3 连固定式屏幕都在照搬 Snapmaker，并点出屏幕不能调角度、观看不便——把同质化设计与一个具体的人机交互缺陷绑在一起，属结构层面的负面判断。",
        trans="连屏幕都照搬了 Snapmaker，固定式的、不能调角度来获得更好的观看视角。",
        competitor="Snapmaker", p0=False),
    "https://www.youtube.com/watch?v=oRRRzuNi8wQ&lc=UgxOMjBf_pUSmAzyy7B4AaABAg": dict(
        sentiment="负面", topics=["swaptek", "multicolor"],
        dimensions=["硬件性能 - 多色系统"],
        problems=["4 个喷头做彩色打印被指逻辑不通，头数堆叠不等于彩色体验更好"],
        summary="德语区用户在 K3 与 U1 对比视频下质疑产品逻辑：如果想打彩色，4 个喷头本身说不通，因为这正是这台机器的定位——属对多喷头路线必要性的根本性质疑，不是使用问题。",
        trans="如果是要打彩色，4 个打印头怎么看都说不通，而这台机器大概就是为彩色准备的。",
        competitor="Snapmaker U1", p0=False),
    "https://www.youtube.com/watch?v=3bVeeQUT-QY&lc=UgyUsF9hFV_f2e9aZRp4AaABAg": dict(
        sentiment="中性", topics=["multicolor"],
        dimensions=["硬件性能 - 多色系统"],
        problems=["i8 默认冲刷量偏高，未把 flush volume 下调到 0.15 会放大废料，横评废料数据失真"],
        summary="观众从评测方法切入：i8 不该产生那么多冲刷废料，怀疑测试没把 flush volume 调到官方建议的 0.15，因此横评里的废料对比被放大——属对实测口径的技术性纠偏，与 K3 换头零废料的定位互为参照。",
        trans="i8 不该有那么多冲刷废料。我猜是你没把冲刷量调低，Creality 建议降到 0.15。",
        competitor="SparkX i8", p0=False),
}


# ---------------------------------------------------------------- 注入引擎
def js_str(s):
    """把 Python 字符串渲染成合法的 JS 双引号字面量。"""
    return json.dumps(s, ensure_ascii=False)


def js_arr(arr):
    return "[" + ",".join(js_str(x) for x in (arr or [])) + "]"


def classify_entry(ann, cand=None):
    """判定一条已标注候选属于「有效」还是「动态」（不计声量）。

    A2 批次（2026-11-11）：统一 09:00 主链与 10:00 拆链的入页判据。
    判据与 B 批次人工回收的 9 条完全吻合——「问题点 / 情感 / P0」三者全无，
    说明这条只有标题+简介、没有用户观点，不该按 reviewGrade:有效 直入有效口径。

      有观点 = problemPoints 非空 / 情感非中性 / isP0
      三者全无 → 动态（entryKind:动态 + countInVolume:false）

    标注表可用 kind="有效" | "动态" 显式覆盖，供日后特例使用。
    只作用于新增注入，历史页面数据不动。
    """
    override = ann.get("kind")
    if override in ("有效", "动态"):
        return override
    has_view = (
        bool(ann.get("problems"))
        or (ann.get("sentiment") or "中性") != "中性"
        or bool(ann.get("p0"))
    )
    return "有效" if has_view else "动态"


def build_item(c, ann, run_date, seq):
    """由候选元数据(c) + 人工标注(ann) 拼出一条与页面同构的 item。"""
    platform = c.get("platform", "")
    content_kind = "图文" if platform == "Reddit" else (c.get("contentKind") or "视频")
    dynamic = (classify_entry(ann, c) == "动态")
    return {
        "id": "K3-%s-%03d" % (run_date.replace("-", ""), seq),
        "date": run_date,
        "publishedAt": c.get("publishedAt", ""),
        "channel": c.get("channel", "海外"),
        "sourceType": c.get("sourceType") or "用户",
        "contentKind": content_kind,
        "platform": platform,
        "site": c.get("site", platform),
        "collectMethod": c.get("collectMethod") or "auto",
        "sourceLink": c.get("sourceLink", ""),
        "country": c.get("country", ""),
        "language": c.get("language", ""),
        "sentiment": "中性" if dynamic else ann.get("sentiment", "中性"),
        # 动态条目不带语义标签：问题点 Top / 信源结构是全量口径面板，会被污染
        "topics": [] if dynamic else ann.get("topics", []),
        "dimensions": [] if dynamic else ann.get("dimensions", []),
        "problemPoints": [] if dynamic else ann.get("problems", []),
        "originalText": c.get("originalText", ""),
        "translation": ann.get("trans", ""),
        "summaryCn": ann.get("summary", ""),
        "competitorMentioned": ann.get("competitor", ""),
        "heat": c.get("heat", ""),
        "isP0": False if dynamic else bool(ann.get("p0", False)),
        "uid": c.get("uid", ""),
        # 与 B 批次一致：reviewGrade 仍「有效」，靠 countInVolume:false 由 isPromoScope() 排除
        "reviewGrade": "有效",
        **({"countInVolume": False, "entryKind": "动态"} if dynamic else {}),
    }


def item_to_js(it):
    parts = [
        "id:" + js_str(it["id"]),
        "date:" + js_str(it["date"]),
        "publishedAt:" + js_str(it["publishedAt"]),
        "channel:" + js_str(it["channel"]),
        "sourceType:" + js_str(it["sourceType"]),
        "contentKind:" + js_str(it["contentKind"]),
        "platform:" + js_str(it["platform"]),
        "site:" + js_str(it["site"]),
        "collectMethod:" + js_str(it["collectMethod"]),
        "sourceLink:" + js_str(it["sourceLink"]),
        "country:" + js_str(it["country"]),
        "language:" + js_str(it["language"]),
        "sentiment:" + js_str(it["sentiment"]),
        "topics:" + js_arr(it["topics"]),
        "dimensions:" + js_arr(it["dimensions"]),
        "problemPoints:" + js_arr(it["problemPoints"]),
        "originalText:" + js_str(it["originalText"]),
        "translation:" + js_str(it["translation"]),
        "summaryCn:" + js_str(it["summaryCn"]),
        "competitorMentioned:" + js_str(it["competitorMentioned"]),
        "heat:" + js_str(it["heat"]),
        "isP0:" + ("true" if it["isP0"] else "false"),
        "uid:" + js_str(it["uid"]),
        "reviewGrade:" + js_str(it["reviewGrade"]),
    ]
    if it.get("entryKind"):
        parts.append("countInVolume:" + ("false" if it.get("countInVolume") is False else "true"))
        parts.append("entryKind:" + js_str(it["entryKind"]))
    return "{" + ",".join(parts) + "}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真正写入 HTML；缺省为预检")
    ap.add_argument("--date", default=DATE, help="入库日期 YYYY-MM-DD（默认今天）")
    args = ap.parse_args()
    run_date = args.date

    kinds = {"有效": 0, "动态": 0}
    for a in LABELS.values():
        kinds[classify_entry(a)] += 1
    print("[CLASSIFY] 标注表 %d 条：有效 %d / 动态 %d（问题点/情感/P0 任一有值即有效；kind 可覆盖）"
          % (len(LABELS), kinds["有效"], kinds["动态"]))
    tag = run_date.replace("-", "")
    cand_path = os.path.join(HERE, "_k3_candidates_%s.json" % tag)
    if not os.path.exists(cand_path):
        print("[ERR] 找不到候选池: %s" % cand_path)
        sys.exit(2)

    cands = json.load(open(cand_path, encoding="utf-8"))
    pool = cands.get("items", [])

    html = open(HTML, encoding="utf-8").read()
    existing_links = set(re.findall(r'sourceLink:"(.*?)"', html))

    # P4 闸门：标注表里不得有 ASCII 双引号（会导致 JS 字面量断裂）
    bad = [k for k, v in LABELS.items() if '"' in (v.get("summary", "") + v.get("trans", "") + v.get("competitor", ""))]
    if bad:
        print("[ERR] 以下 LABELS 含 ASCII 双引号，先修 P4 闸门: %s" % bad[:5])
        sys.exit(3)

    to_inject = []
    seq = 1
    for c in pool:
        link = c.get("sourceLink", "")
        if link not in LABELS:
            continue          # 未标注 → 不猜、不自动补
        if link in existing_links:
            continue          # 已存在 → 幂等跳过
        to_inject.append(build_item(c, LABELS[link], run_date, seq))
        seq += 1

    if not to_inject:
        print("[PRECHECK] 无可注入条目（已标注候选均已在页面中）。")
        sys.exit(0)

    print("[PRECHECK] 将注入 %d 条:" % len(to_inject))
    for it in to_inject:
        tag = "动态/不计声量" if it.get("entryKind") == "动态" else "有效"
        print("   %s  [%s]  %s" % (it["id"], tag, it["sourceLink"]))

    if not args.apply:
        sys.exit(0)

    # 注入：在 items: [ 之后整块插入新条目
    marker = "items: ["
    idx = html.find(marker)
    if idx < 0:
        print("[ERR] 找不到 items: [ 锚点")
        sys.exit(4)
    nl = html.find("\n", idx)
    block = ",\n".join("    " + item_to_js(it) for it in to_inject)
    new_html = html[:nl + 1] + block + ",\n" + html[nl + 1:]
    # 更新 updated 字段为本次入库日
    new_html = re.sub(r'updated:\s*"[^"]*"', 'updated: "%s"' % run_date, new_html, count=1)
    open(HTML, "w", encoding="utf-8").write(new_html)
    print("[APPLIED] 已注入 %d 条，updated=%s。" % (len(to_inject), run_date))


if __name__ == "__main__":
    main()