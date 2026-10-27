# -*- coding: utf-8 -*-
import json, io

DATA_DATE = "2026-08-09"

# ---- 今日总结 (严格 150 字) ----
summary = ("今日采集5条海外点评，覆盖Anycubic、ELEGOO、Snapmaker、Prusa、Creality五品牌。情感：非常负面2条、负面3条。热点为自动调平不准（3条）、第一层附着力差（2条）及线缆硬件缺陷；Kobra X新机Z归位压床报错10120、U1工具头4线缆缺陷致MCU失联，凸显品控隐患。")

print("SUMMARY_LEN=", len(summary))

# ---- 5 条详情 ----
items = [
    {
        "emoji": "🔴", "sentiment": "非常负面", "platform": "Reddit",
        "brand": "Anycubic", "model": "Kobra X", "published": "2026-08-09",
        "title": "New Kobra X keeps pressing the nozzle into the bed during Z homing — Error 10120. Help - r/anycubic",
        "url": "https://www.reddit.com/r/anycubic/comments/1vj422r/new_kobra_x_keeps_pressing_the_nozzle_into_the/",
        "tags": ["自动调平不准", "Z轴问题", "新机故障"],
        "detail": "全新Kobra X初始校准Z归位时喷嘴持续压入热床并发出巨大研磨声，报错10120，只能强制关机，疑似新机故障。",
    },
    {
        "emoji": "🟡", "sentiment": "负面", "platform": "Reddit",
        "brand": "ELEGOO", "model": "Neptune 4 Pro", "published": "2026-08-08",
        "title": "ASA ISSUE - r/ElegooNeptune4",
        "url": "https://www.reddit.com/r/ElegooNeptune4/comments/1vhonwg/asa_issue/",
        "tags": ["第一层附着力差", "打印质量差", "耗材兼容性"],
        "detail": "Neptune 4 Pro打印官方ASA到25%-50%模型总从平台脱落，封闭外壳/30mm/s/流量94%/关风扇/调平/raft/brim全试无效。",
    },
    {
        "emoji": "🔴", "sentiment": "非常负面", "platform": "Reddit",
        "brand": "Snapmaker", "model": "U1", "published": "2026-08-09",
        "title": "day 2… MCU error - r/snapmaker",
        "url": "https://www.reddit.com/r/snapmaker/comments/1vitp92/day_2_mcu_error/",
        "tags": ["MCU通信错误", "线缆质量缺陷", "固件启动失败"],
        "detail": "U1新机第2天打印中工具头4失电，互换线缆后错误跟随线缆转移证实线缆缺陷，排查后Klipper启动失败死机，已开售后工单。",
    },
    {
        "emoji": "🟡", "sentiment": "负面", "platform": "Reddit",
        "brand": "Prusa", "model": "Mini", "published": "2026-08-09",
        "title": "Issues with first layer - Prusa mini, version 6.0.0+14794, 2.3.5 - r/prusa3d",
        "url": "https://www.reddit.com/r/prusa3d/comments/1vixqxd/issues_with_first_layer_prusa_mini_version/",
        "tags": ["自动调平不准", "第一层附着力差"],
        "detail": "Prusa Mini首层校准测试完美但实际打印左侧明显过近刮床，各级别各方向床面水平校正均无效，固件6.0.0+14794。",
    },
    {
        "emoji": "🟡", "sentiment": "负面", "platform": "Reddit",
        "brand": "Creality", "model": "Sparkx i7", "published": "2026-08-09",
        "title": "Sparkx i7 calibrating off plate - r/Creality",
        "url": "https://www.reddit.com/r/Creality/comments/1vj7o4t/sparkx_i7_calibrating_off_plate/",
        "tags": ["自动调平不准", "床位移", "校准失败"],
        "detail": "Sparkx i7打印床无故前移2-3英寸，校准时空转报错；全归零对齐正常，恢复出厂设置仍复现，故障前打印完全正常。",
    },
]

blocks = []
for i, it in enumerate(items, 1):
    print(f"DETAIL_{i}_LEN=", len(it["detail"]))
    tag_line = "「" + "」「".join(it["tags"]) + "」"
    block = (
        f"**（{i}）{it['emoji']}{it['sentiment']} · {it['platform']} · {it['brand']} {it['model']}**\n"
        f"📰 [{it['title']}]({it['url']}) · {it['published']}\n"
        f"{tag_line}\n"
        f"{it['detail']}"
    )
    blocks.append(block)

detail_md = "\n\n".join(blocks)

card = {
    "msg_type": "interactive",
    "card": {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"💬 3D打印用户点评 · {DATA_DATE}"},
            "template": "turquoise",
        },
        "elements": [
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"**📋 今日点评速览**\n\n{summary}"},
            },
            {"tag": "hr"},
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": detail_md},
            },
            {"tag": "hr"},
            {
                "tag": "note",
                "elements": [
                    {"tag": "plain_text", "content": f"数据截至 {DATA_DATE} · 由 3D打印每日资讯 自动生成"}
                ],
            },
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "📖 查看完整点评"},
                        "type": "primary",
                        "url": "https://cruise-ling.github.io/3d-printing-daily/user-complaints.html",
                    },
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "🏠 返回首页"},
                        "url": "https://cruise-ling.github.io/3d-printing-daily/",
                    },
                ],
            },
        ],
    },
}

with io.open(r"C:\Users\123004\WorkBuddy\automation-claw-20260423184755\feishu_user_review_card.json", "w", encoding="utf-8") as f:
    json.dump(card, f, ensure_ascii=False, indent=2)

print("WRITTEN_OK")
