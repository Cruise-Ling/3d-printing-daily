"""
从全部简报 HTML 中提取资讯数据，生成 search_index.js
纯正则实现，无需 bs4 依赖
用法: python build_search_index.py
"""
import re
import json
from pathlib import Path

WORKSPACE = Path(r"C:\Users\123004\WorkBuddy\automation-claw-20260423184755")

ZONE_MAP = {
    "general-zone":   ("泛行业资讯",       "#1a73e8"),
    "specific-zone":   ("细分领域动态",     "#e65100"),
    "consumer-zone":   ("消费级赛道",       "#2e7d32"),
    "niche-zone":      ("细分市场 Niche",   "#bf360c"),
    "scenario-zone":   ("场景×3D打印",      "#00695c"),
    "global-zone":     ("海外资讯",         "#7b1fa2"),
    "feedback-zone":   ("用户口碑",         "#00838f"),
}

BRIEFING_RE = re.compile(r"briefing_(\d{8})(?:_v\d+)?\.html$")
SKIP_FILES = {"briefing_20260510_bak.html", "briefing_20260511_bak.html",
              "briefing_20260506.html", "briefing_20260506_v2.html",
              "briefing_20260512_new.html", "briefing_20260506_v3.html"}

def get_zone_cls(class_str):
    for z in ZONE_MAP:
        if z in class_str:
            return z
    return None

def is_item_class(class_str):
    """
    判断 class_str 是否表示"资讯条目"div，而非其子元素。
    真正的 item div: class="item" 或 class="item zone" 或 class="zone item"
    子 div: class="item-head", class="item-title", class="item-summary", class="item-source"
    """
    parts = class_str.split()
    return 'item' in parts and 'item-' not in class_str

def clean_title(raw):
    t = re.sub(r'<[^>]+>', '', raw)
    t = re.sub(r'[\U00010000-\U0010FFFF\xa0]+', '', t)  # 去掉 emoji + NBSP
    t = re.sub(r'✅\s*A\s*级\s*', '', t)
    t = re.sub(r'^\d+ +\s*', '', t)  # 去掉 "1. " "1 " 等数字+空格前缀，保留 "2026年" 类
    t = re.sub(r'^[一二三四五六七八九十]+[、.]\s*', '', t)  # 中文序号
    t = re.sub(r'\s*[\|｜]\s*.*', '', t)  # 去掉 | 后缀
    return t.strip()

def find_matching_close(text, start):
    """从 start 位置开始，找对应的 </div> 闭合位置"""
    depth = 0
    pos = start
    while pos < len(text):
        nxt = text.find('<div', pos)
        clo = text.find('</div>', pos)
        if clo == -1:
            return -1
        if nxt != -1 and nxt < clo:
            depth += 1
            pos = nxt + 5
        else:
            depth -= 1
            if depth == 0:
                return clo + 6
            pos = clo + 6
    return -1

def extract_from_html(text, date_str):
    """
    扫描所有 <div>，根据 class 精确判断类型：
    - 真正的 item div: class="item" 或 class="item zone" 等（不含 item- 前缀）
    - zone div: class="X-zone" 不含 item
    - 子 div: class="item-head/item-title" 等含 item-，跳过
    """
    items = []

    # 预先找所有 zone div 位置，供"往前找最近 zone"使用
    zone_positions = []
    for zm in re.finditer(r'<div\s+class="([^"]+)"[^>]*>', text):
        cls = zm.group(1)
        zc = get_zone_cls(cls)
        if zc:
            zone_positions.append((zm.start(), zc))

    def find_enclosing_zone(item_pos):
        """找 item_pos 之前最近的 zone div"""
        for zp_start, zc in reversed(zone_positions):
            if zp_start < item_pos:
                return zc
        return None

    # 扫描所有 div
    for m in re.finditer(r'<div\s+class="([^"]+)"[^>]*>', text):
        cls = m.group(1)
        zone_cls = get_zone_cls(cls)
        is_item = is_item_class(cls)

        if not is_item:
            continue

        # 确定 zone
        if zone_cls:
            zone = zone_cls  # 旧格式：item div 上直接有 zone class
        else:
            # 新格式：item div，需要往前找最近的 zone
            zone = find_enclosing_zone(m.start())
            if not zone:
                continue

        # 提取 item 内容块
        close_pos = find_matching_close(text, m.end())
        if close_pos == -1:
            continue
        block = text[m.start():close_pos]

        # 提链接和标题
        link_m = re.search(r'<a\s+href="([^"]+)"[^>]*>(.*?)</a>', block, re.DOTALL)
        if link_m:
            href = link_m.group(1)
            title = clean_title(link_m.group(2))
        else:
            href = ""
            title_m = re.search(r'class="item-title"[^>]*>(.*?)</div>', block, re.DOTALL)
            title = clean_title(title_m.group(1)) if title_m else ""

        if title:
            section_name, section_color = ZONE_MAP[zone]
            items.append({
                "zone": zone,
                "sectionName": section_name,
                "sectionColor": section_color,
                "title": title,
                "href": href,
                "date": date_str
            })

    return items

def extract_items_from_file(filepath):
    date_match = BRIEFING_RE.match(filepath.name)
    if not date_match:
        return []
    date_str = date_match.group(1)

    try:
        text = filepath.read_text(encoding="utf-8")
    except Exception as e:
        print(f"  [WARN] {filepath.name} 读取失败: {e}")
        return []

    extracted = extract_from_html(text, date_str)
    status = "✓" if extracted else "○"
    print(f"  [{status}] {filepath.name}: {len(extracted)} 条")
    return extracted

def get_date(f):
    m = BRIEFING_RE.match(f.name)
    return m.group(1) if m else "00000000"

def build_index():
    files = [f for f in WORKSPACE.glob("briefing_*.html") if f.name not in SKIP_FILES]
    files.sort(key=get_date, reverse=True)

    all_items = []
    for f in files:
        items = extract_items_from_file(f)
        all_items.extend(items)
    return all_items

def generate_search_index_js(items):
    seen = set()
    unique = []
    for it in items:
        key = it["href"] or (it["date"] + it["title"])
        if key not in seen:
            seen.add(key)
            unique.append(it)
    unique.sort(key=lambda x: x["date"], reverse=True)

    data = {
        "version": "1.0",
        "updated": "2026-05-20",
        "totalItems": len(unique),
        "items": unique
    }

    js = [
        "/* search_index.js - 3D打印每日资讯搜索索引 */",
        "/* 由 build_search_index.py 自动生成 */",
        "",
        "var SEARCH_INDEX = " + json.dumps(data, ensure_ascii=False, indent=2) + ";",
        "",
        "/* === 搜索函数 === */",
        "function getDisplayDate(dateStr) {",
        "  const m = dateStr.match(/^(\\d{4})(\\d{2})(\\d{2})$/);",
        "  if (!m) return dateStr;",
        "  return `${parseInt(m[2])}月${parseInt(m[3])}日`;",
        "}",
        "",
        "function searchNews(query, maxResults) {",
        "  if (!query || query.trim().length < 2) return [];",
        "  const q = query.trim().toLowerCase();",
        "  const results = [];",
        "  for (const item of SEARCH_INDEX.items) {",
        "    if (item.title.toLowerCase().includes(q) ||",
        "        item.sectionName.toLowerCase().includes(q)) {",
        "      results.push(item);",
        "      if (maxResults && results.length >= maxResults) break;",
        "    }",
        "  }",
        "  return results;",
        "}",
        "",
        "/* 高亮函数（供简报页面调用 ?h=关键词） */",
        "function highlightSearch(term) {",
        "  if (!term || !term.trim()) return;",
        "  const q = term.trim().toLowerCase();",
        "  const els = document.querySelectorAll('.item');",
        "  let found = false;",
        "  els.forEach(el => {",
        "    const linkEl = el.querySelector('.item-title a');",
        "    if (!linkEl) return;",
        "    const text = linkEl.textContent || '';",
        "    if (text.toLowerCase().includes(q)) {",
        "      el.classList.add('search-highlight');",
        "      if (!found) {",
        "        el.scrollIntoView({ behavior: 'smooth', block: 'center' });",
        "        found = true;",
        "      }",
        "    }",
        "  });",
        "}",
    ]
    return "\n".join(js)

if __name__ == "__main__":
    print("正在扫描简报文件...")
    items = build_index()
    print(f"\n共提取 {len(items)} 条资讯（去重前）")

    js_content = generate_search_index_js(items)
    out_path = WORKSPACE / "search_index.js"
    out_path.write_text(js_content, encoding="utf-8")
    print(f"已写入: {out_path}")
    print(f"文件大小: {out_path.stat().st_size:,} bytes")
