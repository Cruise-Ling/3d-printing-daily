# -*- coding: utf-8 -*-
import json, datetime

DATA_DATE = "2026-08-10"
TODAY = "2026-08-11"

# ---- 5 条数据（来自 batch KB-EN-20260811，publishedAt 均为 2026-08-10）----
items = [
    {
        "seq": 1, "emoji": "🔴", "sentiment": "非常负面",
        "brand": "Snapmaker", "model": "U1", "platform": "Reddit",
        "publishedAt": "2026-08-10",
        "sourceLink": "https://www.reddit.com/r/snapmaker/comments/1vjs7kl/warning_snapmaker_u1_will_ruin_all_your_prints/",
        "title": "WARNING: Snapmaker U1 will ruin all your prints that need tree supports by snapping them after tool change",
        "tags": ["换刀后树支撑断裂", "官方拒认缺陷", "拒绝退货"],
        "detail": "Snapmaker U1 每次换刀后树状支撑必断裂，用户怒斥为垃圾；更糟的是官方拒绝承认缺陷、拒绝按质保退货，售后态度引发社区强烈不满。",
    },
    {
        "seq": 2, "emoji": "🟡", "sentiment": "负面",
        "brand": "QIDI", "model": "Q2", "platform": "Reddit",
        "publishedAt": "2026-08-10",
        "sourceLink": "https://www.reddit.com/r/QidiTech3D/comments/1vk4uls/hell_yeah/",
        "title": "Hell yeah",
        "tags": ["死亡料块", "陶瓷热端QC缺陷", "高温耗材失败"],
        "detail": "QIDI Q2 用 PA612 发生死亡料块，社区直指陶瓷热端/喷嘴在 280°C 以上质量控制失效，代工缺乏品控，高温耗材打印风险高。",
    },
    {
        "seq": 3, "emoji": "🟡", "sentiment": "负面",
        "brand": "ELEGOO", "model": "Centauri Carbon 2", "platform": "Reddit",
        "publishedAt": "2026-08-10",
        "sourceLink": "https://www.reddit.com/r/ElegooCentauriCarbon/comments/1vk2l8s/cc2_doesnt_detect_when_it_cuts_filament_error/",
        "title": "Cc2 doesn’t detect when it Cuts filament error code 1231",
        "tags": ["切丝传感器失效", "报错1231", "更换两次仍复现"],
        "detail": "Centauri Carbon 2 切丝传感器更换两次仍 90% 检测不到切丝，报错 1231，实际已切却误判未切，自动换料可靠性存疑。",
    },
    {
        "seq": 4, "emoji": "🟡", "sentiment": "负面",
        "brand": "Prusa", "model": "Core One", "platform": "Reddit",
        "publishedAt": "2026-08-10",
        "sourceLink": "https://www.reddit.com/r/prusa3d/comments/1vjs17e/core_one_layer_shifting/",
        "title": "Core one layer shifting",
        "tags": ["层移", "皮带调校无效", "龙门方正无效"],
        "detail": "Prusa Core One 套件（约1年）出现小幅层移，调整皮带张力、龙门方正、换料、陀螺填充、不穿越轮廓均无效，根因未明。",
    },
    {
        "seq": 5, "emoji": "🟡", "sentiment": "负面",
        "brand": "Anycubic", "model": "Kobra 2 Max", "platform": "Reddit",
        "publishedAt": "2026-08-10",
        "sourceLink": "https://www.reddit.com/r/anycubic/comments/1vjptl1/anycubic_kobra_2_max_suddenly_started_losing/",
        "title": "Anycubic Kobra 2 Max suddenly started losing position and now Auto Leveling is going crazy — looking for ideas",
        "tags": ["突然丢位", "自动调平横向刮床", "疑似主板/固件故障"],
        "detail": "Anycubic Kobra 2 Max 打印中途突然丢位、自动调平横向刮伤 PEI 床，排查排除皮带滑轮，疑主板/固件/步进电机，固件3.1.5。",
    },
]

# ---- Step 2: 150字今日总结（写死，严格<=150）----
summary = ("今日采集5条海外用户点评，覆盖5大品牌。情感：非常负面1条、负面4条，无中性与正面。"
           "热点集中在 Snapmaker U1 换刀后树支撑断裂且官方拒退货、QIDI Q2 陶瓷热端致死亡料块、"
           "ELEGOO CC2 切丝传感器误报1231，品控与售后隐忧突出。")

# ---- 组装 5 条详情 lark_md ----
blocks = []
for it in items:
    lines = []
    lines.append(f"**（{it['seq']}）{it['emoji']}{it['sentiment']} · {it['platform']} · {it['brand']} {it['model']}**")
    lines.append(f"📰 [{it['title']}]({it['sourceLink']}) · {it['publishedAt']}")
    lines.append("「" + "」「".join(it['tags']) + "」")
    lines.append(it['detail'])
    blocks.append("\n".join(lines))

detail_md = "\n\n".join(blocks)

# ---- 组装整体 lark_md（速览 + 详情）----
overview = f"**📋 今日点评速览**\n\n{summary}"
elements_md = overview + "\n\n" + detail_md

card = {
    "msg_type": "interactive",
    "card": {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"💬 3D打印用户点评 · {DATA_DATE}"},
            "template": "turquoise",
        },
        "elements": [
            {"tag": "div", "text": {"tag": "lark_md", "content": elements_md}},
            {"tag": "hr"},
            {"tag": "note", "elements": [
                {"tag": "plain_text", "content": f"数据截至 {DATA_DATE} · 由 3D打印每日资讯 自动生成"}
            ]},
            {"tag": "action", "actions": [
                {"tag": "button", "text": {"tag": "plain_text", "content": "📖 查看完整点评"},
                 "type": "primary", "url": "https://cruise-ling.github.io/3d-printing-daily/user-complaints.html"},
                {"tag": "button", "text": {"tag": "plain_text", "content": "🏠 返回首页"},
                 "url": "https://cruise-ling.github.io/3d-printing-daily/"}
            ]},
        ],
    },
}

out = r"C:\Users\123004\WorkBuddy\automation-claw-20260423184755\feishu_user_review_card.json"
with open(out, "w", encoding="utf-8") as f:
    json.dump(card, f, ensure_ascii=False, indent=2)

# ---- 校验字数 ----
print("summary chars:", len(summary))
assert len(summary) <= 150, "summary too long"
for it in items:
    print(f"detail #{it['seq']} chars:", len(it['detail']))
    assert len(it['detail']) <= 100, f"detail {it['seq']} too long"
print("card written OK")

# ---- 更新标题缓存 ----
cache_path = r"C:\Users\123004\WorkBuddy\automation-claw-20260423184755\feishu_review_title_cache.json"
try:
    cache = json.load(open(cache_path, encoding="utf-8"))
except Exception:
    cache = {}
for it in items:
    cache[it["sourceLink"]] = {"title": it["title"], "fetched_at": TODAY}
json.dump(cache, open(cache_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("cache updated, total:", len(cache))
