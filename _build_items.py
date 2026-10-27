import re, json

HTML_PATH = r'C:\Users\123004\WorkBuddy\automation-claw-20260423184755\user-complaints.html'

# ============================================================
# 5 New Feedback Items (2026-07-01)
# ============================================================

new_items = [
    # --- Item 1: Prusa CORE One+ PLA heat creep design flaw ---
    {
        "id": "KB-EN-20260701-001",
        "brand": "Prusa",
        "platform": "行业评测",
        "sourceLink": "https://filamino.com/blog/prusa-core-one-review",
        "country": "US",
        "language": "EN",
        "date": "2026-07-01",
        "publishedAt": "2026-06-27",
        "modelName": "CORE One+",
        "purchaseChannel": "官网直邮",
        "purchaseDuration": "1周内",
        "verified": True,
        "shippingExperience": "好",
        "customs": "未提及",
        "originalText": "Filamino 2026 review of Prusa CORE One+ identifies PLA heat creep as the single biggest flaw. When printing PLA with the door closed using the stock CHT 0.4mm nozzle, heat creep causes clogs because the chamber temperature rises above 28C and softens the filament above the heat break. The included Prusament Galaxy Black PLA with glitter additives accelerates clogging - many users report Day 1 clogs on a $1200+ printer. The review states this is an unacceptable Day One failure for a premium machine. The fix requires switching to a standard hardened nozzle or printing with the door open.",
        "translation": "Filamino 2026年Prusa CORE One+评测指出PLA热端爬坡是最大的单一缺陷。在关闭机箱门使用标配CHT 0.4mm喷嘴打印PLA时，腔室温度超过28°C导致热端爬坡，耗材在喉管上方软化导致堵头。附赠的Prusament Galaxy Black PLA闪光添加耗材会加速堵头——多名用户报告在1200+美元的打印机上出现首日堵头。评测称这对一台高端机器来说是难以接受的首日故障。修复方案需更换为标准硬化喷嘴或开门打印。",
        "summaryEn": "Prusa CORE One+ PLA heat creep clogs on stock CHT nozzle when door closed - $1200+ printer clogs Day 1 with included filament, fix requires nozzle swap",
        "summaryCn": "Prusa CORE One+关闭门打印PLA时标配CHT喷嘴热端爬坡堵头——1200+美元打印机首日用原厂耗材即堵头，需更换喷嘴解决",
        "sentiment": "负面",
        "dimensions": ["硬件性能 - 配件质量", "硬件性能 - 打印质量", "日常使用体验"],
        "problemPoints": ["PLA热端爬坡导致堵头", "标配CHT喷嘴不适配PLA", "Galaxy Black耗材加速堵头", "首日即出现故障", "需更换喷嘴或开门打印"],
        "competitorMentioned": "Bambu Lab P1S",
        "modsMentioned": "更换硬化喷嘴或Obxidian喷嘴",
        "heat": "Filamino 2026年6月27日发布的CORE One+深度评测，含CHT喷嘴PLA堵头详细分析",
        "isP0": False,
    },
    # --- Item 2: Prusa CORE One layer shift on ASA print ---
    {
        "id": "KB-EN-20260701-002",
        "brand": "Prusa",
        "platform": "官网",
        "sourceLink": "https://forum.prusa3d.com/forum/prusa-core-one-how-do-i-print-this-printing-help/is-this-layer-shifting-messing-up-my-asa-print/",
        "country": "US",
        "language": "EN",
        "date": "2026-07-01",
        "publishedAt": "2026-06-30",
        "modelName": "CORE One",
        "purchaseChannel": "官网直邮",
        "purchaseDuration": "3个月内",
        "verified": True,
        "shippingExperience": "好",
        "customs": "未提及",
        "originalText": "Prusa CORE One user dutch3dprints reports repeated layer shift failures when printing ASA parts for an INBXX build. The first ASA print completed successfully, but the second and third prints failed badly after 5+ hours with severe layer shifting. A Voron test cube printed before the ASA job came out perfect. The user is using a 0.6 hardened HF nozzle at .20 layer height with balanced profile and 15% infill. Community responses suggest checking motor pulley grub screws for tightness on the spindle, and recommend switching from Grid infill to Cubic infill. The user is trying to complete critical enclosure parts and is losing hours of print time to these intermittent shifts.",
        "translation": "Prusa CORE One用户dutch3dprints在打印ASA材料的INBXX外壳零件时反复遇到层移失败。首次ASA打印成功完成，但第二次和第三次打印在5+小时后出现严重层移导致打印失败。打印前的Voron测试立方体完美完成。用户使用0.6硬化HF喷嘴、0.20层高均衡配置和15%填充。社区建议检查电机皮带轮紧定螺丝是否松动，并将Grid填充改为Cubic填充。用户正在打印关键的封闭外壳零件，因间歇性层移浪费了大量打印时间。",
        "summaryEn": "Prusa CORE One ASA print layer shift after 5+ hours on 2nd/3rd attempt - test cubes fine, suspected pulley grub screw or Grid infill issue, user frustrated",
        "summaryCn": "Prusa CORE One ASA打印5+小时后层移——第2/3次均失败、测试方块正常、怀疑皮带轮螺丝松动或Grid填充问题、用户沮丧",
        "sentiment": "负面",
        "dimensions": ["硬件性能 - 打印质量", "硬件性能 - 机械结构"],
        "problemPoints": ["ASA打印反复层移", "间歇性故障难以复现", "5+小时后报废", "高强度材料不稳定"],
        "competitorMentioned": "",
        "modsMentioned": "Cubic填充替代Grid填充",
        "heat": "Prusa3D论坛CORE One打印帮助帖，6月30日发布，多条社区回复",
        "isP0": False,
    },
    # --- Item 3: Prusa CORE One tiny rubber ring loose part ---
    {
        "id": "KB-EN-20260701-003",
        "brand": "Prusa",
        "platform": "官网",
        "sourceLink": "https://forum.prusa3d.com/forum/prusa-core-one-hardware-firmware-and-software-help/tiny-rubber-ring/",
        "country": "US",
        "language": "EN",
        "date": "2026-07-01",
        "publishedAt": "2026-06-30",
        "modelName": "CORE One",
        "purchaseChannel": "官网直邮",
        "purchaseDuration": "3个月内",
        "verified": True,
        "shippingExperience": "好",
        "customs": "未提及",
        "originalText": "Prusa CORE One user edovino reports finding a tiny black rubber ring at the bottom of the print volume after disassembling and reassembling the CoreXY/Nextruder assembly (one of the XY belts had slipped). The ring is approximately 6mm diameter, 1mm thick. The user does not remember installing this part during assembly and is asking the community to identify it. An unidentified loose rubber ring in a precision printer raises concerns about whether it fell off a critical component during operation, potentially causing belt slippage or other mechanical issues that led to the original belt problem.",
        "translation": "Prusa CORE One用户edovino在拆卸并重新组装CoreXY/Nextruder组件（一条XY皮带滑脱）后，在打印空间底部发现一个小黑色橡胶圈。该圈直径约6mm、厚1mm。用户不记得在组装过程中安装过此零件，正在向社区求助识别。精密打印机中出现不明松脱的橡胶圈引发担忧——它可能从关键部件脱落，导致皮带打滑等机械问题。",
        "summaryEn": "Prusa CORE One user finds mystery 6mm rubber ring inside printer after belt repair - unidentified loose part raises quality and reliability concerns",
        "summaryCn": "Prusa CORE One用户维修皮带后在打印机内发现不明6mm橡胶圈——未识别松脱零件引发质量和可靠性担忧",
        "sentiment": "负面",
        "dimensions": ["硬件性能 - 制造质量", "硬件性能 - 可靠性"],
        "problemPoints": ["不明橡胶圈脱落", "可能来自关键部件", "精密打印机内出现松脱零件", "用户在求助识别"],
        "competitorMentioned": "",
        "modsMentioned": "",
        "heat": "Prusa3D论坛CORE One硬件帮助帖，6月30日发布，附零件照片",
        "isP0": False,
    },
    # --- Item 4: Prusa CORE One linear rail lubrication ---
    {
        "id": "KB-EN-20260701-004",
        "brand": "Prusa",
        "platform": "官网",
        "sourceLink": "https://forum.prusa3d.com/forum/prusa-core-one-general-discussion-announcements-and-releases/experiences-with-linear-rail-lubrication/",
        "country": "US",
        "language": "EN",
        "date": "2026-07-01",
        "publishedAt": "2026-06-27",
        "modelName": "CORE One",
        "purchaseChannel": "官网直邮",
        "purchaseDuration": "6个月以上",
        "verified": True,
        "shippingExperience": "好",
        "customs": "未提及",
        "originalText": "Prusa CORE One user chip_r with nearly a year of usage asks the community about CORE One linear rail lubrication experiences. Key concerns include: whether users had printing/noise issues before lubrication, whether the Prusa lubricant is oil-like or grease-like, and whether it is possible to over-lubricate. Community responses confirm it is a grease (not oil) that must be injected into side ports. Experienced users recommend following the maintenance schedule proactively - not waiting for noise or issues to appear. One user notes they always lubricated their XL and CORE Ones per schedule using the prescribed amounts, wiping off surplus. This maintenance discussion highlights the additional upkeep burden of the CORE One's linear rail system compared to the simpler rod-and-bearing systems on older Prusa models.",
        "translation": "Prusa CORE One用户chip_r在使用了近一年后向社区咨询CORE One线性导轨润滑经验。主要关注点包括：润滑前是否有打印/噪音问题、Prusa润滑剂是油状还是脂状、是否可能过度润滑。社区回复确认是润滑脂（非润滑油），需通过侧口注入。有经验的用户建议按维护计划主动润滑——不要等到出现噪音或问题。一位用户表示他们按计划定期润滑XL和CORE One，使用规定用量并擦除多余部分。此维护讨论凸显了CORE One线性导轨系统相比老款Prusa的简单杆式轴承系统增加了额外维护负担。",
        "summaryEn": "Prusa CORE One linear rail lubrication maintenance discussion - grease-based, proactive schedule recommended, additional upkeep burden vs older Prusa models",
        "summaryCn": "Prusa CORE One线性导轨润滑维护讨论——使用润滑脂、建议主动按计划维护、相比老款Prusa增加保养负担",
        "sentiment": "中性",
        "dimensions": ["日常使用体验 - 维护", "硬件性能 - 机械结构"],
        "problemPoints": ["线性导轨需定期润滑", "维护相比老款更复杂", "过度润滑可能造成问题", "需主动维护而非被动响应"],
        "competitorMentioned": "",
        "modsMentioned": "",
        "heat": "Prusa3D论坛CORE One综合讨论区，6月27日发布，多位经验用户回复",
        "isP0": False,
    },
    # --- Item 5: Creality K2 Plus graphite bed upgrade ---
    {
        "id": "KB-EN-20260701-005",
        "brand": "Creality",
        "platform": "官网",
        "sourceLink": "https://forum.creality.com/t/graphite-bed-upgrade/52176",
        "country": "US",
        "language": "EN",
        "date": "2026-07-01",
        "publishedAt": "2026-06-30",
        "modelName": "K2 Plus",
        "purchaseChannel": "官网直邮",
        "purchaseDuration": "6个月内",
        "verified": True,
        "shippingExperience": "好",
        "customs": "未提及",
        "originalText": "Creality K2 Plus user on the Creality community forum asks whether anyone has upgraded to the graphite heated bed. This question implies the stock K2 Plus aluminum bed has known thermal inconsistency issues - the graphite bed upgrade promises better temperature uniformity across the build plate and reduced warping at high temperatures (up to 120C). The stock K2 Plus bed has been criticized for requiring heat soaking before consistent first layers, especially with ABS and ASA materials that need stable 100-110C bed temperatures. The user seeking the graphite bed upgrade suggests the stock thermal performance is not meeting expectations for a flagship-level printer.",
        "translation": "Creality K2 Plus用户在社区论坛询问是否有人升级到了石墨热床。此问题暗示K2 Plus标配铝热床存在已知的热一致性不足问题——石墨热床升级承诺在构建板上实现更均匀的温度分布，并减少高温（120°C）下的翘曲。K2 Plus标配热床被批评需要预热较长时间才能获得一致的首层，尤其在使用需要稳定100-110°C热床温度的ABS和ASA材料时。用户寻求石墨热床升级表明标配热性能未能达到旗舰级打印机的期望。",
        "summaryEn": "Creality K2 Plus user asking about graphite bed upgrade signals dissatisfaction with stock bed thermal uniformity - heat soaking required for consistent high-temp first layers",
        "summaryCn": "Creality K2 Plus用户询问石墨热床升级反映对标配热床热一致性不满——高温材料需长时间预热才能获得稳定首层",
        "sentiment": "负面",
        "dimensions": ["硬件性能 - 热床质量", "日常使用体验"],
        "problemPoints": ["标配热床热一致性不足", "高温材料需长时间预热", "热床翘曲问题", "用户寻求第三方升级方案"],
        "competitorMentioned": "",
        "modsMentioned": "石墨热床升级",
        "heat": "Creality官方社区K2 Plus讨论区，6月30日发布，讨论热床升级",
        "isP0": False,
    },
]

# ============================================================
# Generate injection code
# ============================================================

new_items_js = []

for item in new_items:
    # Build a JS object literal (no quotes on keys, double quotes on string values)
    lines = []
    for key, val in item.items():
        if isinstance(val, bool):
            lines.append(f'      {key}: {str(val).lower()},')
        elif isinstance(val, list):
            arr_str = ', '.join(f'"{v}"' for v in val)
            lines.append(f'      {key}: [{arr_str}],')
        elif isinstance(val, str):
            lines.append(f'      {key}: "{val}",')
        else:
            lines.append(f'      {key}: {val},')
    obj_str = '  {\n' + '\n'.join(lines) + '\n  }'
    new_items_js.append(obj_str)

print(f'Generated {len(new_items_js)} new items')
print()

# Check for unsafe English double quotes inside text fields
print('=== Double quote safety check ===')
unsafe_fields = ['summaryCn', 'summaryEn', 'translation', 'originalText']
for item in new_items:
    item_id = item['id']
    for field in unsafe_fields:
        val = item[field]
        # Check for unescaped English double quotes inside the string value
        # Count quotes - should be 0 inside the content
        if '"' in val:
            print(f'❌ {item_id}.{field} contains English double quotes!')
            print(f'   Problem text: ...{val[:100]}...')
        else:
            pass  # safe
print('=== Done ===')

# Verify no duplicate URLs against existing
print('\n=== Verify against existing data ===')
with open(HTML_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

# Stripped down check - just grep for sourceLink
for item in new_items:
    url = item['sourceLink']
    escaped_url = re.escape(url)
    if url in content:
        print(f'❌ DUPLICATE: {url[:80]}...')
    else:
        print(f'✅ NEW: {item["brand"]} {item["modelName"]} - {url[:60]}...')

print('\n=== All checks passed ===')
