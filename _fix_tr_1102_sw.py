# -*- coding: utf-8 -*-
"""补译 2026-11-02 批次 sw 缺译的 46 条（Reddit 新帖 + YouTube 教程），合并进 _col_tr_sw.json"""
import io
import json

TR = "_col_tr_sw.json"
NEW = {
 "rd_1xlizmb": ("Bambu 专用 PLA/PETG 支撑料表现异常？",
  "用 Bambu H2C + AMS 2 Pro / AMS HT，一直拿 PETG 当 PLA 的支撑接触面，效果不错；最近换了 Bambu 官方的 PLA/PETG 专用支撑料，行为变了，想确认是否正常。用的是 Bambu Studio，耗材类型都识别对了、走默认配置，打印件有相对较小的支撑接触面。"),
 "yt_WXcZj3xdLMY": ("打印中途暂停以嵌入物件",
  "在模型封闭之前的层加一个暂停：Bambu Studio 里选中该层、添加暂停，然后重新切片即可。"),
 "rd_1xli4it": ("支撑和擦料塔要不要也丢进废料罐？",
  "我把打印废料丢在这个水壶里，用来直观展示浪费量。问支撑和擦料塔（prime tower）是否也该一起算进去。"),
 "rd_1xlhug7": ("Ender 3 V3 SE 换料后首层附着变差",
  "之前用 eSUN PLA 一切正常，换成 Creality Ender PLA 后持续出现热床附着与打印质量问题。主要发生在首层，料丝粘不住平台；有时开头正常，打着打着就崩。"),
 "rd_1xlht4a": ("打印质量突然崩了（自查：模型被转了 1 度）",
  "更新：找到原因了。这盘同时打了多个件，这个件在切片里其实没真正贴住平台——回去打开自动支撑，它在这半个件下面自动补了一层支撑。应该是模型在 CAD 里被转了 1 度甚至更小，肉眼没看出来。"),
 "rd_1xlh0ma": ("怎么把 MRI 数据打成 3D 模型？",
  "看到有人用 MRI 打印自己的大脑，想给女儿一个惊喜。问三件事：耗材选什么颜色和类型（PETG 行不行）；要不要专用软件，还是直接丢进 Bambu Studio；做过的人有什么后悔没早知道的经验。"),
 "rd_1xlgzxa": ("自己写了个网页，一屏看所有打印机",
  "受不了开多个 Bambu Studio 窗口盯打印，别人的方案也不合用，就自己做了 Bambu Multicast：一个 DIY 网站，把所有打印机和当前状态流到同一页。整站约 7 个文件（服务端+客户端），不改代码、只改一个配置文件就能跑起来。"),
 "rd_1xlgoy9": ("K1C 首层异常，求判断",
  "Creality K1C 打 PLA+，首层 60 mm/s、其余层 200 mm/s，用 Creality Print 切片。不知道这是什么现象、怎么产生、怎么修。"),
 "rd_1xlfpay": ("桥接填充能延伸进内部填充吗？",
  "PrusaSlicer 里有没有办法把桥接填充延伸进内部填充？有个悬空内唇边，桥接填充看起来只在边缘挂着一丝，若能把两层填充合并成一次走线会结实得多。"),
 "rd_1xlfcj5": ("预览里料丝又粗又乱是正常的吗？",
  "支撑设置里明明选了树形支撑，预览里却不是树形。机器昨天刚到手，还不太懂，想确认这是正常现象还是哪里设置错了。"),
 "rd_1xlf2o3": ("为什么切片会把模型自带的支撑删掉？",
  "模型本身内建了支撑结构，切片后整块支撑被削掉，于是软件又提示需要生成支撑。想知道为什么会这样、怎么修。"),
 "rd_1xlet2k": ("这个件需要支撑吗？（Creality 5 Pro）",
  "新手，用 Creality 5 Pro。问了 Grok 和 ChatGPT，ChatGPT 说不用支撑、Grok 说必须要，拿不准，来问问真人设定的 Cura 参数该怎么选。"),
 "rd_1xlce6f": ("0.8 喷嘴装上后手机端不能直接打印",
  "装了 0.8 喷嘴，A2L 手机端打印直接报「喷嘴不兼容」，只能回到电脑上用 0.8 配置切片再发。希望出门在外也能直接用手机打。"),
 "rd_1xlcccp": ("怎么给模型加一个平板底面？",
  "模型没有平面可以贴平台，试过挤出底面但效果不好。想找方法或工具给模型补一块平面／方块，让它能立在热床上。"),
 "rd_1xlc4k5": ("ASA 悬垂位置糊成一团",
  "用 ASA 打 AMS 2 的干燥箱，流量与流量动态都校准过，风扇、喷嘴温度也调过、速度也降过，不打悬垂时很好。一打悬垂喷嘴就刮进件里糊掉。机器是 Bambu X2D，才用 3 天，PLA 打得很完美。"),
 "rd_1xlc22s": ("ASA 悬垂位置糊成一团（重复帖）",
  "同上一条：ASA 打干燥箱，悬垂处喷嘴刮料糊面，PLA 正常。疑为同帖重复抓取。"),
 "rd_1xlbpvu": ("层偏移 + 支撑被撞倒（Ender 3 V2 Neo）",
  "热床只有磁吸没有夹具，怀疑喷嘴时不时刮到件。想问加装压片固定平台能不能解决这个问题。"),
 "rd_1xlazdq": ("光固化小件取不下来（Saturn 4）",
  "用了一周的 Elegoo Saturn 4，小件从平台取下很困难，以前用 Saturn 2 反而好取。主要是 10mm 比例的 Warmaster 微缩模型，1–2 厘米高、带小底座，用 Anycubic 水洗树脂 2.0，底层曝光时间已试过多种。"),
 "rd_1xla3e3": ("悬垂层一团糟（H2S + PLA）",
  "用 H2S 打 PLA，悬垂和支撑位置总是一片糊。温度降到 200°C、开大风扇都试过，改善有限，附了照片与参数，求指点。"),
 "rd_1xla0wq": ("报错「请拔出料架上的外置耗材」",
  "第一次打印，P2S Combo（带 AMS）。之前用外置料架上的 PLA 打成功过；这次换 PETG 打 SolidWorks 建的模型，改好耗材类型后启动，就弹出这个提示，硬拽也拽不出来。"),
 "rd_1xl9kh5": ("A1 背部料管固定问题",
  "把 AMS 装在 A1 上方后，背部料管老是被拉扯。问需不需要加支撑件、怎么改，以及料管多久该换一次。"),
 "rd_1xl8qia": ("打印件上出现随机「划痕」是什么原因？",
  "打 Nerf 发射器（P2S，哑光 PETG，用 Bambu 默认哑光 PETG 配置，件竖直摆放）。这一件除表面多处随机划痕外整体正常，想知道成因。"),
 "rd_1xl80bi": ("新 P1S 擦料塔拉丝，是操作问题吗？",
  "打了几个多色件，擦料塔（priming tower）几乎每次都有拉丝，A1 上从来没这样过。"),
 "yt_vRFeLYGARBI": ("Bambu Studio 耗材映射教程（AMS 与切片）",
  "讲解如何把耗材映射到 Bambu Lab AMS 的正确槽位。"),
 "yt_FED-4B4u-m4": ("只在需要的地方加填充",
  "用修改器（modifier）只在模型局部调整填充：添加修改器、调整大小与位置覆盖目标区域，再单独提高该区域的填充密度。"),
 "yt_op2wkJgLf1c": ("新手必知的 10 个 Bambu Studio 设置",
  "逐个讲解 10 个关键设置，用于提升打印质量。"),
 "yt_ZeQOEBalSp8": ("Bambu Studio 零基础完整课程（第 1 讲）",
  "葡萄牙语课程，面向完全新手，从零讲 Bambu Studio 的基础操作。"),
 "yt_yngYjdDrS1g": ("SolidCraft 入门：第一个模型导进 Bambu Studio",
  "面向没用过 CAD 的人：从建立第一个简单模型，到导入 Bambu Studio 打印。"),
 "yt_Ea8Svz4sZLE": ("给模型加多色 SVG 徽标（最简单做法）",
  "演示把多色 SVG 徽标贴到 3D 模型上的简便流程，单色模型也适用。"),
 "yt_ylZcerlHPwA": ("用 Bambu Studio 处理负形模具",
  "演示如何用 Bambu Studio 处理负形件（Bath & Body Works 模具）。"),
 "yt_RXU8L9MmMsg": ("只给部分层加一圈额外墙",
  "用「交替额外墙」（Alternate Extra Wall）实现隔层加墙，而不必每一层都加。"),
 "yt__SGxHrDnbCw": ("修掉麻点、接缝与疙瘩：5 个真正有效的切片设置",
  "发打之前先检查这 5 项切片设置，专门针对表面麻点（zits）、接缝和疙瘩。"),
 "58793133e1d23843": ("SPARKX i7 从 Creality Print 发打印，G-code 上传到 1% 就中断",
  "机器是 SPARKX i7 Combo + CFS Lite。Creality Print 里切片成功、G-code 预览正常、颜色都对，点「发送到打印机」后开始上传到云端，但几乎立刻停住不走。"),
 "yt_5DaR3LUafDA": ("我为什么用不了 Prusa Core One",
  "测了一周 Prusa Core One，发现 PrusaSlicer 有个相当严重的问题，下期视频详细讲。"),
 "yt_ywKEeb0P6PQ": ("在 Bambu Studio 里让文字贴合曲面（5 分钟）",
  "德语教程：演示如何把 3D 打印文字贴合到模型曲面上。"),
 "yt_CHbVJz3LYrY": ("OrcaSlicer 2.5.0 预览：Orca Cloud 插件体系",
  "介绍 OrcaSlicer 2.5.0 新增的插件系统：在线订阅、本地激活，用来扩展切片工作流。"),
 "yt_PmyHPoxR9Go": ("2026 年五款最佳切片软件横评",
  "对比 OrcaSlicer、Bambu Studio、Cura、PrusaSlicer 等五款主流免费切片器，回答到底该用哪个。"),
 "8e577db63448efcb": ("求助：设计一枚可定制的邮轮纪念币",
  "新手，想设计一枚约 3 英寸的圆形邮轮纪念币（中间镂空一只鸭子），打印一批，下次上船时藏在船里各处。"),
 "yt_aOuHG9pzQMo": ("哪款切片软件最好？四款常用横评（捷克语）",
  "对比四款最常用的切片软件，给出适用场景判断。"),
 "yt_pDzjZKY18Zc": ("一周技巧：一个开关修掉糊成一团的文字",
  "演示用单个切片开关解决打印文字糊连的问题。"),
 "yt_LCaV2F80D7g": ("OrcaSlicer 2.4.2：Z 轴抗锯齿让曲面更顺",
  "官方说明 Z Anti-Aliasing（ZAA）的作用与开启方式。"),
 "yt_pVmK2Kqq-3Q": ("这 5 个切片设置彻底改变了我的打印",
  "作者认为大多数切片参数没想象中重要，真正起作用的只有这几个，基于大规模机队打印量的经验。"),
 "yt_AZNaGiMkKns": ("新手切片指南（OrcaSlicer）",
  "从配置 OrcaSlicer 到切片并发送打印的完整入门流程。"),
 "yt_TmRqaYLNtlY": ("OrcaSlicer 2.4.0：相对桥接角度",
  "官方说明相对桥接角度（Relative Bridge Angle）的作用，可更精细地控制桥接方向。"),
 "yt_42q267yj4aU": ("OrcaSlicer 2.4.0：桥接线宽独立设置",
  "官方说明专用桥接线宽（Dedicated Bridge Line Width），让桥接更实、接触更好。"),
 "yt_NTGoRc-sOMs": ("用 scarf 接缝设置隐藏打印接缝",
  "用 scarf joint 相关设置把打印接缝藏到看不见的位置。"),
}


def main():
    tr = json.load(io.open(TR, encoding="utf-8"))
    before = len(tr)
    add = 0
    for uid, (t, b) in NEW.items():
        if uid in tr:
            continue
        tr[uid] = {"t": t, "b": b}
        add += 1
    io.open(TR, "w", encoding="utf-8").write(json.dumps(tr, ensure_ascii=False, indent=1))
    print("[tr] %d → %d（新增 %d）" % (before, len(tr), add))
    left = [k for k in NEW if k not in tr]
    if left:
        print("[tr] 异常未写入:", left[:5])


if __name__ == "__main__":
    main()
